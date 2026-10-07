import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from sotlib.rules import (RuleError, discover_packages, install_package, load_profile,
                          rollback_package, validate_package, verify_package)
from sotlib import artifacts


class UniversalArchitectureTests(unittest.TestCase):
    def test_future_rule_auto_discovery_full_proof_and_rollback(self):
        with tempfile.TemporaryDirectory(prefix="sot-future-rule-") as td:
            sandbox = Path(td)
            repo = sandbox / "repo"
            shutil.copytree(ROOT / "governance/rules", repo / "governance/rules")
            shutil.copytree(ROOT / "trust/verification/rules", repo / "trust/verification/rules")
            package_root = repo / "governance/rules/RULE-FUTURE-SANDBOX-EXAMPLE/1.0.0"
            package_root.mkdir(parents=True, exist_ok=True)
            manifest = json.loads((ROOT / "verification/tests/fixtures/future-rule/rule.json").read_text())
            for artifact in manifest["artifacts"]:
                source = ROOT / artifact["source"]
                dest = repo / artifact["source"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            manifest_path = package_root / "rule.json"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            discovered = discover_packages(repo)
            self.assertIn("RULE-FUTURE-SANDBOX-EXAMPLE", [p["rule_id"] for _, p in discovered])
            profile_path = ROOT / "deployment/profiles/portable-linux.json"
            home = sandbox / "unrelated-user-home"
            profile = load_profile(profile_path, {**os.environ, "HOME": str(home)})
            roots = profile["resolved_roots"]
            roots["RUNTIME_ROOT"] = str(sandbox / "alternate-runtime-root")
            state = sandbox / "state"
            pkg = next(p for _, p in discovered if p["rule_id"] == "RULE-FUTURE-SANDBOX-EXAMPLE")
            (Path(roots["RUNTIME_ROOT"]) / "future-rule").mkdir(parents=True)
            old = Path(roots["RUNTIME_ROOT"]) / "future-rule/config.json"
            old.write_text('{"previous":true}\n')
            before = hashlib.sha256(old.read_bytes()).hexdigest()
            install_package(repo, pkg, roots, state)
            result = verify_package(repo, pkg, roots, state, sandbox / "evidence")
            self.assertEqual(result["verdict"], "VERIFIED", result)
            self.assertEqual(result["achieved_level"], 7)
            restored = rollback_package(pkg, state)
            self.assertEqual(len(restored), 2)
            self.assertEqual(before, hashlib.sha256(old.read_bytes()).hexdigest())
            self.assertFalse((Path(roots["RUNTIME_ROOT"]) / "future-rule/hook.py").exists())

    def test_tampered_or_missing_rule_artifacts_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="sot-tampered-rule-") as td:
            repo = Path(td)
            package_dir = repo / "governance/rules/RULE-BAD/1.0.0"
            package_dir.mkdir(parents=True)
            source = repo / "artifact.py"
            source.write_text("print('ok')\n")
            manifest = {
                "manifest_version":"1.0.0", "schema_version":"1.0.0", "rule_id":"RULE-BAD", "version":"1.0.0",
                "name":"Bad", "scope":"test", "severity":"low", "enabled":True,
                "supported_agent_classes":["generic_cli"],
                "artifacts":[{"artifact_id":"hook","source":"artifact.py","destination_template":"${RUNTIME_ROOT}/bad.py","mode":"0644","sha256":"0"*64,"kind":"python","permissions":[]}],
                "load_order":1,"precedence":[],"activation":{"method":"probe","argv":["python3","-c","pass"],"expected_exit_code":0},
                "reload_requirement":"none","required_proof_level":3,"expected_effect":"hash validation",
                "positive_probe":{"argv":["python3","-c","pass"],"expected_exit_code":0},
                "negative_probe":{"argv":["python3","-c","raise SystemExit(1)"],"expected_exit_code":1,"expected_effect":"nonzero"},
                "supersedes":[],"rollback":{"strategy":"restore_previous_or_remove_new"}}
            path = package_dir / "rule.json"
            path.write_text(json.dumps(manifest))
            with self.assertRaises(RuleError):
                validate_package(repo, path)
            source.unlink()
            with self.assertRaises(RuleError):
                validate_package(repo, path)

    def test_portable_profile_uses_provided_home_and_alternate_root(self):
        with tempfile.TemporaryDirectory(prefix="different-user-") as td:
            home = Path(td) / "home" / "nobody-like"
            profile = load_profile(ROOT / "deployment/profiles/portable-linux.json", {**os.environ, "HOME": str(home)})
            self.assertEqual(profile["resolved_roots"]["HOME"], str(home))
            self.assertEqual(profile["resolved_roots"]["PROJECTS_ROOT"], str(home / "projects"))
            self.assertNotIn("azureuser", json.dumps(profile["resolved_roots"]))

    def test_blank_home_bootstrap_binds_alternate_projects_root(self):
        with tempfile.TemporaryDirectory(prefix="sot-alt-profile-") as td:
            base=Path(td); home=base/"different-user"; profile_path=base/"profile.json"
            profile={"profile_id":"test-portable","version":"1.0.0","platform":"linux",
                     "roots":{"HOME":"${HOME}","PROJECTS_ROOT":str(base/"workspace-root"),
                              "STATE_ROOT":"${HOME}/state","RUNTIME_ROOT":"${HOME}/runtime","BACKUP_ROOT":"${HOME}/backup"},
                     "agent_classes":["generic_cli"]}
            profile_path.write_text(json.dumps(profile))
            result=subprocess.run([str(ROOT/"sot"),"bootstrap","--profile",str(profile_path),"--home",str(home),"--agent-class","generic_cli"],
                                  cwd=ROOT,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual((home/".agents/projects_root").read_text().strip(),str(base/"workspace-root"))
            self.assertEqual((home/".agents/sot_root").read_text().strip(),str(ROOT))

    def test_external_artifact_install_preserves_and_rolls_back_prior_files(self):
        with tempfile.TemporaryDirectory(prefix="sot-artifact-rollback-") as td:
            base=Path(td);home=base/"home";profile=load_profile(ROOT/"deployment/profiles/portable-linux.json",{**os.environ,"HOME":str(home)})
            existing=home/"AGENTS.md";existing.parent.mkdir(parents=True);existing.write_text("preexisting operator content\n")
            state=base/"state"
            artifacts.install(ROOT,profile,state)
            self.assertIn("AGY Workspace Governance",existing.read_text())
            self.assertTrue((home/".agents/projects_root").is_file())
            restored=artifacts.rollback(state)
            self.assertGreater(len(restored),1)
            self.assertEqual(existing.read_text(),"preexisting operator content\n")
            self.assertFalse((home/".codex/rules/sot-governance.rules").exists())

    def test_evidence_validator_rejects_missing_and_forged_artifacts(self):
        from verification.validate_verifier_result import validate
        base = {"task_id":"task", "verifier_id":"agent-x", "verifier_type":"generic_cli",
                "timestamp":"2026-10-07T00:00:00Z", "claim":"checked", "evidence":[],
                "deterministic_result":{"verdict":"pass"}, "independent_verdict":"approved",
                "unresolved_items":[], "confidence_category":"high"}
        self.assertFalse(validate(base)[0])


    def test_rule_sync_and_install_merges_multiple_package_configs(self):
        with tempfile.TemporaryDirectory(prefix="sot-multi-rule-") as td:
            base = Path(td)
            repo = base / "repo"
            shutil.copytree(ROOT / "governance/rules", repo / "governance/rules")
            shutil.copytree(ROOT / "trust/verification/rules", repo / "trust/verification/rules")
            shutil.copytree(ROOT / "external", repo / "external")
            shutil.copytree(ROOT / "configuration", repo / "configuration")
            shutil.copytree(ROOT / "deployment", repo / "deployment")
            shutil.copytree(ROOT / "trust", repo / "trust", dirs_exist_ok=True)
            
            # Setup Rule 1
            q1 = repo / "governance/rules/RULE-TEST-MERGE-1/1.0.0"
            q1.mkdir(parents=True)
            (q1 / "hook.py").write_text("import sys\nprint('loaded');sys.exit(0)\n")
            cfg1 = {"rule1_entry": {"enabled": True}}
            (q1 / "agent-setting.json").write_text(json.dumps(cfg1, indent=2))
            m1 = {
                "manifest_version": "1.0.0", "schema_version": "1.0.0", "rule_id": "RULE-TEST-MERGE-1", "version": "1.0.0",
                "name": "Merge 1", "scope": "test", "severity": "low", "enabled": True, "supported_agent_classes": ["generic_cli"],
                "artifacts": [
                    {"artifact_id": "hook", "source": str((q1 / "hook.py").relative_to(repo)), "destination_template": "${HOME}/.agents/hooks/m1.py", "mode": "0755", "sha256": hashlib.sha256((q1 / "hook.py").read_bytes()).hexdigest(), "kind": "python", "permissions": ["read", "execute"]},
                    {"artifact_id": "agent-config", "source": str((q1 / "agent-setting.json").relative_to(repo)), "destination_template": "${HOME}/.gemini/config/hooks.json", "mode": "0644", "sha256": hashlib.sha256((q1 / "agent-setting.json").read_bytes()).hexdigest(), "kind": "agent_config", "permissions": ["read"]}
                ],
                "load_order": 1, "precedence": [], "activation": {"method": "probe", "argv": ["python3", "{artifact:hook}", "load"], "expected_exit_code": 0, "expected_stdout_contains": "loaded"},
                "reload_requirement": "none", "required_proof_level": 4, "expected_effect": "merge 1",
                "positive_probe": {"argv": ["python3", "{artifact:hook}", "load"], "expected_exit_code": 0},
                "negative_probe": {"argv": ["python3", "{artifact:hook}", "load"], "expected_exit_code": 0, "expected_effect": "ok"},
                "supersedes": [], "rollback": {"strategy": "restore_previous_or_remove_new"}
            }
            (q1 / "rule.json").write_text(json.dumps(m1, indent=2))

            # Setup Rule 2
            q2 = repo / "governance/rules/RULE-TEST-MERGE-2/1.0.0"
            q2.mkdir(parents=True)
            (q2 / "hook.py").write_text("import sys\nprint('loaded');sys.exit(0)\n")
            cfg2 = {"rule2_entry": {"enabled": True}}
            (q2 / "agent-setting.json").write_text(json.dumps(cfg2, indent=2))
            m2 = {
                "manifest_version": "1.0.0", "schema_version": "1.0.0", "rule_id": "RULE-TEST-MERGE-2", "version": "1.0.0",
                "name": "Merge 2", "scope": "test", "severity": "low", "enabled": True, "supported_agent_classes": ["generic_cli"],
                "artifacts": [
                    {"artifact_id": "hook", "source": str((q2 / "hook.py").relative_to(repo)), "destination_template": "${HOME}/.agents/hooks/m2.py", "mode": "0755", "sha256": hashlib.sha256((q2 / "hook.py").read_bytes()).hexdigest(), "kind": "python", "permissions": ["read", "execute"]},
                    {"artifact_id": "agent-config", "source": str((q2 / "agent-setting.json").relative_to(repo)), "destination_template": "${HOME}/.gemini/config/hooks.json", "mode": "0644", "sha256": hashlib.sha256((q2 / "agent-setting.json").read_bytes()).hexdigest(), "kind": "agent_config", "permissions": ["read"]}
                ],
                "load_order": 2, "precedence": [], "activation": {"method": "probe", "argv": ["python3", "{artifact:hook}", "load"], "expected_exit_code": 0, "expected_stdout_contains": "loaded"},
                "reload_requirement": "none", "required_proof_level": 4, "expected_effect": "merge 2",
                "positive_probe": {"argv": ["python3", "{artifact:hook}", "load"], "expected_exit_code": 0},
                "negative_probe": {"argv": ["python3", "{artifact:hook}", "load"], "expected_exit_code": 0, "expected_effect": "ok"},
                "supersedes": [], "rollback": {"strategy": "restore_previous_or_remove_new"}
            }
            (q2 / "rule.json").write_text(json.dumps(m2, indent=2))

            home = base / "home"
            profile = {
                "profile_id": "test-merge", "version": "1.0.0", "platform": "linux",
                "roots": {"HOME": str(home), "PROJECTS_ROOT": str(base / "projects"), "STATE_ROOT": str(base / "state"),
                          "RUNTIME_ROOT": str(base / "runtime"), "BACKUP_ROOT": str(base / "backups")},
                "agent_classes": ["generic_cli"]
            }
            pp = base / "profile.json"
            pp.write_text(json.dumps(profile))
            roots = profile["roots"]
            state = Path(roots["STATE_ROOT"])
            for v in roots.values(): Path(v).mkdir(parents=True, exist_ok=True)

            install_package(repo, m1, roots, state)
            install_package(repo, m2, roots, state)

            target = home / ".gemini/config/hooks.json"
            self.assertTrue(target.is_file())
            content = json.loads(target.read_text())
            self.assertIn("rule1_entry", content)
            self.assertIn("rule2_entry", content)

            v1 = verify_package(repo, m1, roots, state, base / "evidence")
            self.assertEqual(v1["verdict"], "VERIFIED", v1)
            v2 = verify_package(repo, m2, roots, state, base / "evidence")
            self.assertEqual(v2["verdict"], "VERIFIED", v2)

    def test_secret_backup_mandatory_encryption_and_decrypted_restore(self):
        import unittest.mock
        import storage.backup_data as backup_data
        from storage.backup_data import backup_asset, restore_asset
        with tempfile.TemporaryDirectory(prefix="sot-enc-backup-") as td:
            base = Path(td)
            secret = base / ".env.prod"
            secret.write_text("API_SECRET_KEY=super-confidential-secret-999\n")
            cloud = base / "cloud"
            cloud.mkdir()
            target_remote = cloud / "env.enc"
            cat_file = base / "cat.json"
            cat_file.write_text(json.dumps({"backups": []}))
            reg_file = base / "reg.json"
            reg_file.write_text(json.dumps({"assets": []}))
            asset = {
                "asset_id": "test-synthetic-secret",
                "project_id": "test-proj",
                "source_path": str(secret),
                "primary_backup_target": str(cloud),
                "remote_path": str(target_remote),
                "classification": "secret",
                "encryption": "required"
            }
            with unittest.mock.patch.object(backup_data, "CATALOG_FILE", str(cat_file)), \
                 unittest.mock.patch.object(backup_data, "REGISTRY_FILE", str(reg_file)):
                res = backup_asset(asset, verify_remote=False)
                self.assertEqual(res.get("status"), "REMOTE_UPLOAD_COMPLETE")
                self.assertTrue(target_remote.is_file())
                # Must be ciphertext, never unencrypted plaintext
                self.assertNotEqual(target_remote.read_bytes(), secret.read_bytes())

                restored = base / "restored.env"
                restore_asset(asset, str(restored))
                self.assertTrue(restored.is_file())
                self.assertEqual(restored.read_text(), secret.read_text())


    def test_git_push_normalize_url_case_preservation_and_remote_drift(self):
        from gitpush_watcher.pusher import normalize_git_url, GitPusher
        # Filesystem URLs strictly preserve case
        self.assertEqual(normalize_git_url("/tmp/MixedCase_Path/Repo.git"), "/tmp/MixedCase_Path/Repo")
        self.assertEqual(normalize_git_url("file:///Tmp/Case_Repo.GIT/"), "/Tmp/Case_Repo")
        self.assertEqual(normalize_git_url("../Relative_Path/Repo.git"), "../Relative_Path/Repo")
        self.assertEqual(normalize_git_url("./My_Relative/Repo.git"), "./My_Relative/Repo")
        # Network URLs normalize scheme and netloc to lowercase
        self.assertEqual(normalize_git_url("https://github.com/Org/Repo.git"), "https://github.com/org/repo")

        # Test remote drift rejection
        with tempfile.TemporaryDirectory(prefix="sot-drift-") as td:
            repo = Path(td) / "local_repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test.local"], check=True)
            (repo / "f.txt").write_text("content\n")
            subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "Unverified : init"], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "file:///tmp/Configured_Path.git"], check=True)

            ok, reason = GitPusher.push_and_verify_parity(repo, "main", "origin", canonical_remote_url="file:///tmp/Canonical_Different.git")
            self.assertFalse(ok)
            self.assertIn("REMOTE_DRIFT", reason)

    def test_precommit_safety_classifier_literals_and_adversarial_bypass_prevention(self):
        from projects.precommit_safety import unsafe_paths, _has_secret_pattern
        # Exact classifier literals do not flag as secrets
        self.assertFalse(_has_secret_pattern(b"CLASS_D_SECRET = 'CLASS_D_SECRET'"))
        self.assertFalse(_has_secret_pattern(b'CLASS_D_SECRET = "CLASS_D_SECRET"'))
        self.assertFalse(_has_secret_pattern(b'classified = {"secret": "CLASS_D_SECRET"}'))

        # Negative Adversarial test: embedded secret with classifier prefix MUST FAIL CLOSED
        self.assertTrue(_has_secret_pattern(b'api_key = "CLASS_D_SECRET_adversarial_token_1234567890"'))
        self.assertTrue(_has_secret_pattern(b'secret = "CLASS_D_SECRET_leak_real_credential_98765"'))

        with tempfile.TemporaryDirectory(prefix="sot-precommit-") as td:
            p = Path(td)
            # Safe file with classifier literal
            safe_file = p / "classifier.py"
            safe_file.write_text("CLASS_D_SECRET = 'CLASS_D_SECRET'\n")
            self.assertEqual(unsafe_paths(p), [])

            # Adversarial secret file
            bad_file = p / "compromised.py"
            bad_file.write_text("api_key = 'CLASS_D_SECRET_adversarial_token_1234567890'\n")
            self.assertIn(str(bad_file.relative_to(p)), unsafe_paths(p))

    def test_delete_guard_alternate_home_and_profile_resolution(self):
        from trust.verification.delete_guard import resolve_roots_and_incident_paths, log_incident
        with tempfile.TemporaryDirectory(prefix="sot-del-guard-") as td:
            alt_home = Path(td) / "alternate_home"
            alt_home.mkdir()
            prof_file = Path(td) / "profile.json"
            prof_file.write_text(json.dumps({
                "profile_id": "portable-test",
                "roots": {
                    "HOME": "${HOME}",
                    "PROJECTS_ROOT": "${HOME}/projects",
                    "STATE_ROOT": "${HOME}/.state"
                }
            }))
            old_env = dict(os.environ)
            try:
                os.environ["HOME"] = str(alt_home)
                os.environ["AGY_DEPLOYMENT_PROFILE"] = str(prof_file)
                os.environ.pop("PROJECTS_ROOT", None)
                os.environ.pop("STATE_ROOT", None)

                home_res, proj_res, inc_dir_res, inc_log_res, _, _ = resolve_roots_and_incident_paths()
                self.assertEqual(home_res, str(alt_home))
                self.assertEqual(proj_res, str(alt_home / "projects"))
                self.assertNotIn("azureuser", proj_res)
                self.assertNotIn("${HOME}", proj_res)

                # Test log_incident returns enforcement decision even if disk write fails
                with unittest.mock.patch("os.makedirs", side_effect=PermissionError("read-only filesystem")):
                    inc = log_incident("run_command", {"CommandLine": "rm -rf /"}, "Catastrophic root deletion", "RULE_37")
                    self.assertEqual(inc["decision"], "DENIED")
                    self.assertEqual(inc["rule_id"], "RULE_37")
            finally:
                os.environ.clear()
                os.environ.update(old_env)

    def test_config_tamper_detection_and_restoration(self):
        with tempfile.TemporaryDirectory(prefix="sot-tamper-") as td:
            base = Path(td)
            home = base / "home"
            home.mkdir()
            state = base / "state"
            state.mkdir()
            profile = load_profile(ROOT / "deployment/profiles/portable-linux.json", {**os.environ, "HOME": str(home)})

            # Install canonical external artifacts
            artifacts.install(ROOT, profile, state)

            target = home / ".gemini/config/hooks.json"
            self.assertTrue(target.is_file())

            # Tamper with installed config
            tampered = json.loads(target.read_text())
            tampered["boundary-guard"]["enabled"] = False
            target.write_text(json.dumps(tampered, indent=2))

            # Verify detects tamper
            verify_res = artifacts.verify(ROOT, profile)
            self.assertFalse(verify_res["ok"])
            self.assertTrue(any("hash mismatch" in err for err in verify_res["errors"]))

            # Re-install restores canonical rule
            artifacts.install(ROOT, profile, state)
            restored = json.loads(target.read_text())
            self.assertTrue(restored["boundary-guard"]["enabled"])

    def test_backup_mandatory_encryption_fails_closed_without_key(self):
        import unittest.mock
        import storage.backup_data as backup_data
        from storage.backup_data import backup_asset

        with tempfile.TemporaryDirectory(prefix="sot-fail-enc-") as td:
            base = Path(td)
            secret = base / ".env.secret"
            secret.write_text("SUPER_SECRET_KEY=1234567890123456\n")
            cloud = base / "remote_cloud"
            cloud.mkdir()
            cat_file = base / "cat.json"
            cat_file.write_text(json.dumps({"backups": []}))
            reg_file = base / "reg.json"
            reg_file.write_text(json.dumps({"assets": []}))
            asset = {
                "asset_id": "test-no-key-asset",
                "project_id": "test-proj",
                "source_path": str(secret),
                "primary_backup_target": str(cloud),
                "remote_path": str(cloud / "secret.enc"),
                "classification": "secret",
                "encryption": "required"
            }

            # Negative test: resolve_encryption_key returns "" -> MUST FAIL CLOSED before upload
            with unittest.mock.patch.object(backup_data, "CATALOG_FILE", str(cat_file)), \
                 unittest.mock.patch.object(backup_data, "REGISTRY_FILE", str(reg_file)), \
                 unittest.mock.patch("storage.backup_data.resolve_encryption_key", return_value=""):
                res = backup_asset(asset, verify_remote=False)
                self.assertEqual(res.get("status"), "FAILED")
                self.assertIn("ENCRYPTION_KEY_MISSING", res.get("reason", ""))
                # Remote file MUST NOT be created
                self.assertFalse((cloud / "secret.enc").exists())


if __name__ == "__main__":
    unittest.main()
