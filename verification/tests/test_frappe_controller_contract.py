"""
Tests for Frappe Native Controller Contract Enforcement (Blocker-07).
Verifies that custom app DocType controllers are verified for runtime importability,
and that broken dependencies fail the native contract with CONTROLLER_IMPORT_ERROR.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from project_profiles.frappe.profile import FrappeProjectProfile


def test_frappe_controller_positive_contract(tmp_path: Path):
    """
    Positive test: Valid DocType controller and hooks must pass the contract.
    """
    bench_root = tmp_path / "frappe-bench"
    apps_dir = bench_root / "apps"
    apps_dir.mkdir(parents=True)

    # Core apps
    (apps_dir / "frappe").mkdir()
    (apps_dir / "erpnext").mkdir()

    # Custom app
    c_app = apps_dir / "my_custom_app"
    pkg_dir = c_app / "my_custom_app"
    dt_dir = pkg_dir / "doctype" / "sample_doc"
    dt_dir.mkdir(parents=True)

    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "hooks.py").write_text('app_name = "my_custom_app"\n', encoding="utf-8")
    (dt_dir / "__init__.py").write_text("", encoding="utf-8")
    (dt_dir / "sample_doc.json").write_text(json.dumps({"name": "Sample Doc", "doctype": "DocType"}), encoding="utf-8")
    (dt_dir / "sample_doc.py").write_text(
        "class SampleDoc:\n    def get_title(self):\n        return 'Sample'\n",
        encoding="utf-8",
    )

    sot_root = Path(__file__).resolve().parents[2]
    profile = FrappeProjectProfile(sot_root)
    res = profile.verify_native_test_contract(bench_root)

    assert res.status == "PASS"
    assert len(res.errors) == 0
    assert res.details.get("my_custom_app.doctype.sample_doc.sample_doc_imported") is True


def test_frappe_controller_import_failure_negative(tmp_path: Path):
    """
    Negative test: A DocType controller with a non-existent import dependency
    must be caught and fail verification with CONTROLLER_IMPORT_ERROR.
    """
    bench_root = tmp_path / "frappe-bench"
    apps_dir = bench_root / "apps"
    apps_dir.mkdir(parents=True)

    # Core apps
    (apps_dir / "frappe").mkdir()
    (apps_dir / "erpnext").mkdir()

    # Custom app with broken dependency in controller
    c_app = apps_dir / "broken_custom_app"
    pkg_dir = c_app / "broken_custom_app"
    dt_dir = pkg_dir / "doctype" / "broken_doc"
    dt_dir.mkdir(parents=True)

    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "hooks.py").write_text('app_name = "broken_custom_app"\n', encoding="utf-8")
    (dt_dir / "__init__.py").write_text("", encoding="utf-8")
    (dt_dir / "broken_doc.json").write_text(json.dumps({"name": "Broken Doc", "doctype": "DocType"}), encoding="utf-8")
    (dt_dir / "broken_doc.py").write_text(
        "import definitely_nonexistent_controller_dependency_427\n\nclass BrokenDoc:\n    pass\n",
        encoding="utf-8",
    )

    sot_root = Path(__file__).resolve().parents[2]
    profile = FrappeProjectProfile(sot_root)
    res = profile.verify_native_test_contract(bench_root)

    assert res.status == "FAIL"
    assert any("CONTROLLER_IMPORT_ERROR" in err for err in res.errors)
    assert any("definitely_nonexistent_controller_dependency_427" in err for err in res.errors)
