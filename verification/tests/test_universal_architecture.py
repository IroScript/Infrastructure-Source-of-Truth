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


if __name__ == "__main__":
    unittest.main()
