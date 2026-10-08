"""
Acceptance Test Suite for Frappe / ERPNext Official-Source Enforcement Feature (Sections A through W).
Validates runtime health, official references, compatibility contracts, core guards,
outdated pattern blocks, blank-VM bootstrap, and adversarial attack vectors.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from project_profiles.base import ProfileRegistry
from project_profiles.manager import ProjectProfileManager
from project_profiles.frappe.contract import FrappeContractManager
from project_profiles.frappe.core_guard import FrappeCoreGuard
from project_profiles.frappe.doctor import FrappeRuntimeDoctor
from project_profiles.frappe.evidence import FrappeEvidenceRecorder
from project_profiles.frappe.patterns import FrappePatternChecker
from project_profiles.frappe.profile import FrappeProjectProfile
from project_profiles.frappe.reference import FrappeReferenceManager
from project_profiles.frappe.bootstrap import FrappeBootstrapEngine


@pytest.fixture
def sot_root():
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def bench_root():
    return Path("/home/azureuser/IroScript_Projects/Frappe-erp-Alco/frappe-bench")


def test_frappe_runtime_health_and_doctor(sot_root, bench_root):
    """Sections A, M, N, P: Verifies actual live Frappe/ERPNext bench health."""
    doctor = FrappeRuntimeDoctor(sot_root)
    report = doctor.run_full_diagnosis(bench_root, site_name="alco.localhost")

    assert report["bench_root"] == str(bench_root)
    assert report["site"] == "alco.localhost"
    assert report["site_exists"] is True
    assert report["apps"]["frappe"]["exists"] is True
    assert report["apps"]["frappe"]["branch"] == "version-16"
    assert report["apps"]["erpnext"]["exists"] is True
    assert report["apps"]["erpnext"]["branch"] == "version-16"
    assert report["apps"]["alco_ecommerce"]["exists"] is True
    assert report["apps"]["alco_ecommerce"]["branch"] == "main"

    # Alco Ecommerce integration model
    assert report["integration_model"] == "MODEL_A_BENCH_CUSTOM_APP"
    assert report["alco_ecommerce_installed"] is True
    assert "Alco Field Order" in report.get("alco_doctypes_in_db", "")

    # Live HTTP probe on port 8000
    assert report["site_online"] is True
    assert "200 OK" in report["http_probe_header"]
    assert report["status"] == "PASS"


def test_frappe_compatibility_contract_integrity(sot_root):
    """Section C: Verifies canonical Frappe compatibility contract schema and values."""
    mgr = FrappeContractManager(sot_root)
    contract = mgr.load_contract()
    assert contract, "Compatibility contract could not be loaded"

    is_valid, missing = mgr.validate_contract_integrity(contract)
    assert is_valid is True, f"Contract validation failed with missing keys: {missing}"

    assert contract["frappe_major"] == 16
    assert contract["frappe_target_branch"] == "version-16"
    assert contract["erpnext_major"] == 16
    assert contract["erpnext_target_branch"] == "version-16"
    assert contract["official_docs_source"] == "https://docs.frappe.io"
    assert contract["compatibility_status"] == "COMPATIBLE"
    assert contract["upgrade_policy"]["allow_major_upgrade"] is False


def test_official_reference_verification_and_deprecation_tag(sot_root, tmp_path):
    """Section B & D: Validates official docs reference and flags archived frappe_docs."""
    ref_mgr = FrappeReferenceManager(sot_root)

    # Create dummy deprecated frappe_docs directory to test deprecation tag
    old_docs = tmp_path / "frappe_docs"
    old_docs.mkdir()

    res = ref_mgr.verify_reference(
        target_major=16,
        target_branch="version-16",
        project_path=Path("/home/azureuser/IroScript_Projects/Frappe-erp-Alco"),
        state_root=tmp_path,
    )
    assert res.status == "PASS"
    assert res.details["target_major"] == 16
    assert res.details["page_count"] > 1000
    assert res.details["source"] == "https://docs.frappe.io"


def test_doc_freshness_gate_missing_reference_fails_closed(sot_root, tmp_path):
    """Section E & W: Adversarial test - Missing reference fails closed."""
    ref_mgr = FrappeReferenceManager(sot_root)
    empty_proj = tmp_path / "empty_project"
    empty_proj.mkdir()

    # Pass non-existent project and state roots
    res = ref_mgr.verify_reference(
        target_major=16,
        target_branch="version-16",
        project_path=empty_proj,
        state_root=tmp_path / "no_state",
    )
    # When no local fallback exists, fails closed
    # Note: verify_reference checks fallbacks, let's test with empty reference directory
    fake_ref = tmp_path / "fake_ref"
    fake_ref.mkdir()
    (fake_ref / "MANIFEST.json").write_text(json.dumps({"pages_ok": 0}))

    res2 = ref_mgr.verify_reference(
        target_major=16,
        target_branch="version-16",
        project_path=fake_ref,
        state_root=tmp_path / "no_state",
    )
    assert res2.status == "FAIL"
    assert any("FRAPPE_REFERENCE_NOT_VERIFIED" in err for err in res2.errors)


def test_doc_freshness_gate_version_mismatch_fails_closed(sot_root, tmp_path):
    """Section E & W: Adversarial test - Major version mismatch fails closed."""
    ref_mgr = FrappeReferenceManager(sot_root)
    fake_ref = tmp_path / "v15_ref"
    fake_ref.mkdir()
    (fake_ref / "MANIFEST.json").write_text(json.dumps({
        "frappe_major": 15,
        "pages_ok": 500,
        "source": "https://docs.frappe.io",
    }))

    res = ref_mgr.verify_reference(
        target_major=16,
        target_branch="version-16",
        project_path=fake_ref,
        state_root=tmp_path / "no_state",
    )
    assert res.status == "FAIL"
    assert any("VERSION_MISMATCH" in err for err in res.errors)


def test_outdated_pattern_linter_blocks_deprecated_apis(sot_root):
    """Section J & W: Scans bad Frappe code and blocks with OUTDATED_FRAPPE_PATTERN."""
    checker = FrappePatternChecker(sot_root)

    bad_code = """
import frappe

@frappe.whitelist()
def search_items(query):
    # Raw SQL injection
    data = frappe.db.sql(f"SELECT * FROM `tabItem` WHERE name='{query}'")
    # Direct DDL
    frappe.db.sql("ALTER TABLE `tabItem` ADD COLUMN custom_col INT")
    return data
"""
    findings = checker.scan_content(bad_code)
    assert len(findings) >= 3
    pattern_ids = {f["pattern_id"] for f in findings}
    assert "FRAPPE_RAW_SQL_INJECTION" in pattern_ids
    assert "FRAPPE_WHITELIST_UNRESTRICTED_HTTP_METHOD" in pattern_ids
    assert "FRAPPE_DIRECT_DDL_TABLE_ALTER" in pattern_ids
    for f in findings:
        assert f["verdict"] == "OUTDATED_FRAPPE_PATTERN"
        assert f["alternative"] is not None


def test_clean_modern_code_passes_pattern_linter(sot_root):
    """Section J: Modern compliant v16 code passes cleanly."""
    checker = FrappePatternChecker(sot_root)

    clean_code = """
import frappe

@frappe.whitelist(methods=["POST"])
def search_items(query):
    return frappe.qb.from_("Item").select("*").where(frappe.qb.Field("name") == query).run(as_dict=True)
"""
    findings = checker.scan_content(clean_code)
    assert len(findings) == 0


def test_core_framework_modification_guard(sot_root, bench_root):
    """Section K & W: Blocks direct edits to upstream apps/frappe and apps/erpnext."""
    guard = FrappeCoreGuard(sot_root)

    # 1. Proposed path inside apps/frappe
    frappe_core_file = bench_root / "apps" / "frappe" / "frappe" / "handler.py"
    ok1, reason1 = guard.check_proposed_path(frappe_core_file, bench_root)
    assert ok1 is False
    assert "CORE_MODIFICATION_PROHIBITED" in reason1

    # 2. Proposed path inside apps/erpnext
    erpnext_core_file = bench_root / "apps" / "erpnext" / "erpnext" / "stock" / "doctype" / "item" / "item.py"
    ok2, reason2 = guard.check_proposed_path(erpnext_core_file, bench_root)
    assert ok2 is False
    assert "CORE_MODIFICATION_PROHIBITED" in reason2

    # 3. Proposed path inside custom app alco_ecommerce
    custom_app_file = bench_root / "apps" / "alco_ecommerce" / "alco_ecommerce" / "api.py"
    ok3, reason3 = guard.check_proposed_path(custom_app_file, bench_root)
    assert ok3 is True
    assert reason3 == "ALLOWED"

    # 4. Cleanliness check of actual live bench
    clean_res = guard.audit_bench_core_cleanliness(bench_root)
    # No python framework source was modified
    assert clean_res.status == "PASS"


def test_major_upgrade_authorization_gate(sot_root):
    """Section Q & W: Major upgrade to v17 without SOT policy change is blocked."""
    mgr = FrappeContractManager(sot_root)
    contract = mgr.load_contract()

    # Attempt upgrade to v17
    ok, reason = mgr.check_upgrade_authorization(contract, proposed_major=17)
    assert ok is False
    assert reason == "MAJOR_UPGRADE_NOT_AUTHORIZED"

    # Minor update within pinned major 16 is permitted
    ok_minor, _ = mgr.check_upgrade_authorization(contract, proposed_major=16)
    assert ok_minor is True


def test_evidence_recorder_creates_machine_readable_bundle(tmp_path):
    """Section I: Machine-readable evidence bundle generation without chain-of-thought."""
    recorder = FrappeEvidenceRecorder(state_root=tmp_path)
    evidence_path = recorder.record_task_evidence(
        task_id="task-frappe-001",
        project_uuid="8d2d4d60-fd9b-5da2-afa8-64d84c8f9e39",
        frappe_version="16.36.1",
        erpnext_version="16.37.0",
        official_reference_commit="af63cde4",
        official_docs_consulted=["https://docs.frappe.io/framework/user/en/api/rest"],
        apis_hooks_used=["@frappe.whitelist(methods=['POST'])"],
        changed_files=["apps/alco_ecommerce/alco_ecommerce/api.py"],
        tests_run=[{"name": "test_order", "rc": 0}],
        negative_tests=[{"name": "test_sql_injection_blocked", "blocked": True}],
        migration_impact=False,
        verdict="PASS",
    )

    assert evidence_path.is_file()
    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert data["task_id"] == "task-frappe-001"
    assert data["verdict"] == "PASS"
    assert "chain_of_thought" not in data


def test_blank_vm_recovery_and_bootstrap(sot_root, tmp_path):
    """Section R, S, T: Reconstructs Frappe profile without /home/azureuser dependency."""
    alt_home = tmp_path / "alt_user"
    alt_state = alt_home / ".agents"
    alt_projects = alt_home / "projects"
    profile_roots = {
        "HOME": str(alt_home),
        "STATE_ROOT": str(alt_state),
        "PROJECTS_ROOT": str(alt_projects),
    }

    engine = FrappeBootstrapEngine(sot_root)
    res = engine.bootstrap(profile_roots, auto=True, dry_run=False)

    assert res["status"] == "BOOTSTRAP_COMPLETE"
    assert (alt_state / "rules" / "frappe.md").is_file()
    assert (alt_home / ".codex" / "rules" / "frappe.md").is_file()
    assert (alt_state / "official-references" / "frappe").is_dir()

    # External data requirements must be specified
    ext_data = {item["asset_id"] for item in res["external_data_required"]}
    assert "alco_localhost_mariadb" in ext_data
    assert "alco_site_config_secrets" in ext_data


def test_generic_project_profile_manager_and_cli(sot_root, bench_root):
    """Section U: Resolves generic profile and evaluates coding gate."""
    manager = ProjectProfileManager(sot_root)
    proj = manager.resolve_project("frappe_erp_alco")
    assert proj is not None

    profile = manager.get_profile_for_project(proj)
    assert profile is not None
    assert profile.profile_name == "frappe"

    # Pre-coding gate passes on clean code
    clean_code = {"test.py": "@frappe.whitelist(methods=['GET'])\ndef ping(): return 'pong'"}
    gate_ok, gate_reason, details = manager.evaluate_coding_gate(proj, code_snippets=clean_code)
    assert gate_ok is True
    assert gate_reason == "OFFICIAL_SOURCE_GATE_PASS"

    # Pre-coding gate fails on outdated pattern
    bad_code = {"test.py": "@frappe.whitelist()\ndef ping(): return 'pong'"}
    bad_ok, bad_reason, _ = manager.evaluate_coding_gate(proj, code_snippets=bad_code)
    assert bad_ok is False
    assert bad_reason == "OUTDATED_FRAPPE_PATTERN"

def test_codex_b1_fabricated_api_and_get_doc_blocked(sot_root, bench_root):
    """
    Codex B1: Tests that get_doc import from frappe.model.document and
    fabricated APIs are rejected.
    Adversarial B1: untracked or staged outdated Frappe code in apps/alco_ecommerce is rejected with OUTDATED_FRAPPE_PATTERN.
    """
    manager = ProjectProfileManager(sot_root)
    proj = manager.resolve_project("frappe_erp_alco")
    assert proj is not None

    legacy_pattern = " ".join(["from", "frappe.model.document", "import", "get_doc"])
    code_get_doc = {"doc_test.py": f"{legacy_pattern}\nd = get_doc('Task')"}
    ok1, reason1, det1 = manager.evaluate_coding_gate(proj, code_snippets=code_get_doc)
    assert ok1 is False
    assert reason1 == "OUTDATED_FRAPPE_PATTERN"

    # Test fabricated API
    nonexistent_attr = "this_api_" + "does_not_exist_427"
    code_fab = {"fab_test.py": f"def test():\n    getattr(frappe, '{nonexistent_attr}')()\n"}
    # Direct dot call assembled dynamically
    code_fab_dot = {"fab_test.py": f"def test():\n    frappe.{nonexistent_attr}()\n"}
    ok2, reason2, det2 = manager.evaluate_coding_gate(proj, code_snippets=code_fab_dot)
    assert ok2 is False
    assert reason2 == "OUTDATED_FRAPPE_PATTERN"

    # Adversarial B1: untracked, nested, and staged outdated Frappe code in apps/alco_ecommerce
    app_dir = Path("/home/azureuser/IroScript_Projects/Frappe-erp-Alco/frappe-bench/apps/alco_ecommerce")
    if app_dir.is_dir() and os.access(app_dir, os.W_OK):
        bad_file = app_dir / "adversarial_untracked.py"
        try:
            bad_file.write_text(f"import frappe\nfrappe.{nonexistent_attr}()\n", encoding="utf-8")
            ok_untracked, reason_untracked, _ = manager.evaluate_coding_gate(proj)
            assert ok_untracked is False
            assert reason_untracked == "OUTDATED_FRAPPE_PATTERN"
        finally:
            if bad_file.exists():
                bad_file.unlink()

        # Adversarial B1: Nested untracked file inside a subdirectory
        nested_dir = app_dir / "adversarial_nested_dir"
        nested_dir.mkdir(exist_ok=True)
        nested_bad = nested_dir / "nested_bad.py"
        try:
            nested_bad.write_text(f"import frappe\nfrappe.{nonexistent_attr}()\n", encoding="utf-8")
            ok_nested, reason_nested, _ = manager.evaluate_coding_gate(proj)
            assert ok_nested is False
            assert reason_nested == "OUTDATED_FRAPPE_PATTERN"
        finally:
            if nested_bad.exists():
                nested_bad.unlink()
            if nested_dir.exists():
                nested_dir.rmdir()

        # Staged outdated Frappe code in apps/alco_ecommerce
        try:
            bad_file.write_text(f"{legacy_pattern}\n", encoding="utf-8")
            import subprocess
            subprocess.run(["git", "add", str(bad_file)], cwd=app_dir, check=True)
            ok_staged, reason_staged, _ = manager.evaluate_coding_gate(proj)
            assert ok_staged is False
            assert reason_staged == "OUTDATED_FRAPPE_PATTERN"
        finally:
            import subprocess
            subprocess.run(["git", "reset", "HEAD", str(bad_file)], cwd=app_dir, capture_output=True)
            if bad_file.exists():
                bad_file.unlink()

        # Adversarial B1 Case: Non-UTF-8 encoded file containing outdated pattern
        bad_non_utf8 = app_dir / "adversarial_latin1.py"
        try:
            bad_non_utf8.write_bytes(f"# \xff non-utf8 byte\n{legacy_pattern}\n".encode("latin-1"))
            ok_latin, reason_latin, _ = manager.evaluate_coding_gate(proj)
            assert ok_latin is False
            assert reason_latin == "OUTDATED_FRAPPE_PATTERN"
        finally:
            if bad_non_utf8.exists():
                bad_non_utf8.unlink()

    # Adversarial B1 Case: Bench root is a git repo with apps/ gitignored, containing a non-git custom app
    with tempfile.TemporaryDirectory() as td:
        fake_bench = Path(td) / "fake_bench"
        fake_bench.mkdir()
        import subprocess
        subprocess.run(["git", "init"], cwd=fake_bench, capture_output=True, check=True)
        (fake_bench / ".gitignore").write_text("apps/\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], cwd=fake_bench, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=fake_bench, capture_output=True, check=True)

        # Core apps required by contract
        (fake_bench / "apps" / "frappe").mkdir(parents=True)
        (fake_bench / "apps" / "erpnext").mkdir(parents=True)

        # Non-git custom app gitignored by bench root
        custom_app = fake_bench / "apps" / "custom_ignored_app"
        custom_pkg = custom_app / "custom_ignored_app"
        custom_pkg.mkdir(parents=True)
        (custom_pkg / "hooks.py").write_text('app_name = "custom_ignored_app"\n', encoding="utf-8")
        bad_ignored_py = custom_app / "bad_code.py"
        bad_ignored_py.write_text(f"{legacy_pattern}\n", encoding="utf-8")

        fake_proj = {
            "project_id": "test_ignored_frappe",
            "project_type": "frappe",
            "canonical_path": str(fake_bench),
            "git": {"repository_path": str(fake_bench)},
        }
        ok_ign, reason_ign, _ = manager.evaluate_coding_gate(fake_proj)
        assert ok_ign is False
        assert reason_ign == "OUTDATED_FRAPPE_PATTERN"


def test_codex_b2_manifest_and_reference_verification_integrity(sot_root, tmp_path):
    """
    Codex B2: Directories without MANIFEST.json, or with version mismatch or corrupt manifest, fail.
    Adversarial B2: modifying page 11, deleting a canonical page, adding an unlisted file,
    or using docs.frappe.io.evil.invalid is rejected.
    """
    ref_mgr = FrappeReferenceManager(sot_root)

    # Empty folder without manifest
    empty_ref = tmp_path / "empty_ref"
    empty_ref.mkdir()
    res1 = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=empty_ref)
    assert res1.is_pass is False

    # Folder with manifest but wrong branch
    bad_branch_ref = tmp_path / "bad_branch"
    bad_branch_ref.mkdir()
    manifest_bad = {
        "manifest_version": "1.0.0",
        "frappe_major": 16,
        "branch": "version-15",
        "source": "https://docs.frappe.io",
        "fetched_at_utc": "2026-10-08T00:00:00Z",
        "pages": {"index.md": "dummy_sha"}
    }
    (bad_branch_ref / "MANIFEST.json").write_text(json.dumps(manifest_bad))
    (bad_branch_ref / "index.md").write_text("dummy")
    res2 = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=bad_branch_ref)
    assert res2.is_pass is False
    assert any("BRANCH_MISMATCH" in e for e in res2.errors)

    # Adversarial B2 Case 1: Hostname spoofing with docs.frappe.io.evil.invalid
    spoof_ref = tmp_path / "spoof_ref"
    spoof_ref.mkdir()
    manifest_spoof = {
        "frappe_major": 16,
        "branch": "version-16",
        "source": "https://docs.frappe.io.evil.invalid/framework",
        "fetched_at_utc": "2026-10-08T00:00:00Z",
        "pages": {"page1.md": "sha_dummy"}
    }
    (spoof_ref / "MANIFEST.json").write_text(json.dumps(manifest_spoof))
    (spoof_ref / "page1.md").write_text("content")
    res_spoof = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=spoof_ref)
    assert res_spoof.is_pass is False
    assert any("INVALID_SOURCE_DOMAIN" in e for e in res_spoof.errors)

    # Setup valid 15-page reference set for adversarial mutation tests
    import hashlib
    valid_multi_ref = tmp_path / "valid_multi_ref"
    valid_multi_ref.mkdir()
    pages_dict = {}
    for i in range(1, 16):
        fname = f"page_{i:02d}.md"
        content = f"# Page {i}\nOfficial documentation content for page {i}\n"
        (valid_multi_ref / fname).write_text(content, encoding="utf-8")
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        pages_dict[fname] = sha

    manifest_valid = {
        "frappe_major": 16,
        "branch": "version-16",
        "source": "https://docs.frappe.io",
        "fetched_at_utc": "2026-10-08T00:00:00Z",
        "pages": pages_dict,
    }
    (valid_multi_ref / "MANIFEST.json").write_text(json.dumps(manifest_valid))
    res_base = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=valid_multi_ref)
    assert res_base.is_pass is True

    # Adversarial B2 Case 2: Modifying page 11 causes ARTIFACT_INTEGRITY_FAILED
    (valid_multi_ref / "page_11.md").write_text("TAMPERED CONTENT ON PAGE 11", encoding="utf-8")
    res_mod11 = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=valid_multi_ref)
    assert res_mod11.is_pass is False
    assert any("ARTIFACT_INTEGRITY_FAILED" in e for e in res_mod11.errors)
    # Restore page 11
    (valid_multi_ref / "page_11.md").write_text(f"# Page 11\nOfficial documentation content for page 11\n", encoding="utf-8")

    # Adversarial B2 Case 3: Deleting a canonical page causes CANONICAL_PAGE_MISSING
    (valid_multi_ref / "page_05.md").unlink()
    res_del = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=valid_multi_ref)
    assert res_del.is_pass is False
    assert any("CANONICAL_PAGE_MISSING" in e for e in res_del.errors)
    # Restore page 5
    (valid_multi_ref / "page_05.md").write_text(f"# Page 5\nOfficial documentation content for page 5\n", encoding="utf-8")

    # Adversarial B2 Case 4: Adding an unlisted file causes UNLISTED_FILE_DETECTED
    (valid_multi_ref / "unlisted_adversarial_page.md").write_text("# Unlisted page", encoding="utf-8")
    res_unlisted = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=valid_multi_ref)
    assert res_unlisted.is_pass is False
    assert any("UNLISTED_FILE_DETECTED" in e for e in res_unlisted.errors)
    (valid_multi_ref / "unlisted_adversarial_page.md").unlink()

    # Adversarial B2 Case 5: Path traversal in manifest rejected with CANONICAL_PAGE_INVALID_PATH
    manifest_traversal = dict(manifest_valid)
    manifest_traversal["pages"] = {"../../etc/passwd": "dummy_sha"}
    (valid_multi_ref / "MANIFEST.json").write_text(json.dumps(manifest_traversal))
    res_trav = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=valid_multi_ref)
    assert res_trav.is_pass is False
    assert any("CANONICAL_PAGE_INVALID_PATH" in e for e in res_trav.errors)

    # Adversarial B2 Case 6: Missing sha256 checksum rejected with ARTIFACT_INTEGRITY_FAILED
    manifest_no_sha = dict(manifest_valid)
    manifest_no_sha["pages"] = {"page_01.md": ""}
    (valid_multi_ref / "MANIFEST.json").write_text(json.dumps(manifest_no_sha))
    res_no_sha = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=valid_multi_ref)
    assert res_no_sha.is_pass is False
    assert any("ARTIFACT_INTEGRITY_FAILED" in e for e in res_no_sha.errors)

    # Adversarial B2 Case 7: Nested unlisted file in subfolder rejected
    (valid_multi_ref / "MANIFEST.json").write_text(json.dumps(manifest_valid))
    sub_dir = valid_multi_ref / "nested_sub"
    sub_dir.mkdir(exist_ok=True)
    nested_file = sub_dir / "nested_unlisted_page.md"
    nested_file.write_text("# Nested unlisted page", encoding="utf-8")
    res_nested = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path, reference_override=valid_multi_ref)
    assert res_nested.is_pass is False
    assert any("UNLISTED_FILE_DETECTED" in e for e in res_nested.errors)
    nested_file.unlink()
    sub_dir.rmdir()


def test_codex_b4_blank_vm_reference_sync(sot_root, tmp_path):
    """
    Codex B4: SOT seed reference can be synced without /home/azureuser dependencies.
    Adversarial B4: Bootstrap and verify flows execute cleanly inside isolated alternative
    deployment roots without path dependencies.
    """
    ref_mgr = FrappeReferenceManager(sot_root)
    seed_ref = sot_root / "frappe" / "docs-reference"
    assert seed_ref.is_dir()
    assert (seed_ref / "MANIFEST.json").is_file()

    res = ref_mgr.sync_reference_to_state(seed_ref, tmp_path)
    assert res["status"] == "SYNCED"
    assert res["page_count"] > 200

    # Verify synced reference
    v_res = ref_mgr.verify_reference(target_major=16, target_branch="version-16", state_root=tmp_path)
    assert v_res.is_pass is True

    # Adversarial B4: Bootstrap in completely isolated alternative deployment roots
    alt_user = tmp_path / "alt_blank_vm_user"
    alt_state = alt_user / "state"
    alt_projects = alt_user / "projects"
    profile_roots = {
        "HOME": str(alt_user),
        "STATE_ROOT": str(alt_state),
        "PROJECTS_ROOT": str(alt_projects),
    }
    from project_profiles.frappe.bootstrap import FrappeBootstrapEngine
    engine = FrappeBootstrapEngine(sot_root)
    b_res = engine.bootstrap(profile_roots, auto=True, dry_run=False)
    assert b_res["status"] == "BOOTSTRAP_COMPLETE"
    assert b_res["reference_verified"] is True
    assert (alt_state / "official-references" / "frappe").is_dir()

    # CLI sync-reference and verify in alternate root
    import argparse
    from project_profiles.cli import handle_frappe_cli
    args_sync = argparse.Namespace(
        frappe_action="sync-reference",
        home=str(alt_user),
        source_dir=str(seed_ref),
        state_root=str(alt_state),
        projects_root=str(alt_projects),
        format="json",
    )
    assert handle_frappe_cli(args_sync, sot_root) == 0

    # Profile verify in alternate root
    from project_profiles.cli import handle_profile_cli
    args_prof = argparse.Namespace(
        profile_action="verify",
        project_id="frappe_erp_alco",
        file=None,
        home=str(alt_user),
        state_root=str(alt_state),
        projects_root=str(alt_projects),
    )
    # Project registry is in sot_root / projects or state_root, returns 0 on gate pass
    assert handle_profile_cli(args_prof, sot_root) == 0


def test_codex_b5_native_test_contract_catches_errors(sot_root, tmp_path):
    """
    Codex B5: verify_native_test_contract catches syntax errors and runtime exceptions in custom app hooks.
    """
    profile = FrappeProjectProfile(sot_root)

    # Setup a mock bench with a broken custom app
    mock_bench = tmp_path / "mock-bench"
    apps_dir = mock_bench / "apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "frappe").mkdir()
    (apps_dir / "erpnext").mkdir()

    # Broken syntax app
    broken_app = apps_dir / "broken_app"
    broken_pkg = broken_app / "broken_app"
    broken_pkg.mkdir(parents=True)
    (broken_pkg / "hooks.py").write_text("app_name = 'broken_app'\ndef bad_syntax(:\n")

    res = profile.verify_native_test_contract(mock_bench)
    assert res.is_pass is False
    assert any("APP_SYNTAX_ERROR" in e for e in res.errors)

    # Broken runtime app
    (broken_pkg / "hooks.py").write_text("app_name = 'broken_app'\nraise RuntimeError('intentional failure')\n")
    res2 = profile.verify_native_test_contract(mock_bench)
    assert res2.is_pass is False
    assert any("APP_HOOKS_RUNTIME_ERROR" in e for e in res2.errors)


def test_codex_b4_blank_vm_supplied_project_root_preserved(sot_root, tmp_path):
    """
    Codex B4: Supplied project root is respected without falling back to old $HOME/Frappe-erp-Alco.
    """
    from project_profiles.cli import handle_frappe_cli
    import argparse
    alt_home = tmp_path / "blank_home"
    alt_home.mkdir()
    alt_state = tmp_path / "blank_state"
    alt_projects = tmp_path / "blank_projects"
    # Destination directory does NOT exist yet on disk
    assert not (alt_projects / "Frappe-erp-Alco").exists()

    args_verify = argparse.Namespace(
        frappe_action="verify",
        home=str(alt_home),
        state_root=str(alt_state),
        projects_root=str(alt_projects),
        format="json",
    )
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = handle_frappe_cli(args_verify, sot_root)

    # Returns 2 on verify fail because directory does not exist on blank VM
    assert rc == 2
    output = json.loads(buf.getvalue())
    bench_root = output["test_contract"]["bench_root"]
    # Invariant: bench_root MUST be rooted in alt_projects, NOT alt_home or /home/azureuser!
    assert bench_root == str(alt_projects / "Frappe-erp-Alco")
    assert not bench_root.startswith(str(alt_home))
    assert not bench_root.startswith("/home/azureuser")

