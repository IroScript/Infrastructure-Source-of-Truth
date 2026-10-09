"""
Tests for empirical project recovery and negative verification (Blocker-05).
Validates that project recovery never produces fake/stub successes.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
import pytest

from bootstrap.project_recovery import ProjectRecoveryOrchestrator


def test_recovery_nonexistent_remote_negative(tmp_path: Path):
    """
    Empirical negative test:
    Attempt recovery of a project with a nonexistent remote URL.
    Must return PROJECT_RESTORE_INCOMPLETE and must not claim PROJECT_RESTORED.
    """
    sot_root = tmp_path / "sot"
    projects_dir = sot_root / "projects"
    projects_dir.mkdir(parents=True)

    fake_registry = {
        "version": "2.0.0",
        "projects": [
            {
                "project_id": "fake_nonexistent_project",
                "display_name": "Fake Nonexistent Project",
                "canonical_path": "/home/azureuser/IroScript_Projects/FakeNonexistent",
                "project_type": "application",
                "git": {
                    "enabled": True,
                    "remote": "https://github.com/nonexistent-org-404/nonexistent-repo-does-not-exist-999.git",
                    "branch": "main",
                },
            }
        ],
    }
    (projects_dir / "PROJECT_REGISTRY.json").write_text(json.dumps(fake_registry), encoding="utf-8")

    projects_root = tmp_path / "projects_root"
    projects_root.mkdir(parents=True)

    orchestrator = ProjectRecoveryOrchestrator(sot_root)
    report = orchestrator.recover_all(projects_root)

    assert report["status"] == "PROJECT_RESTORE_INCOMPLETE"
    assert report.get("failed_stage") == "PROJECT_RESTORE_BLOCKED"
    assert "PROJECT_RESTORED" not in report.get("stages", [])
    assert "fake_nonexistent_project" not in report.get("restored_projects", [])
    assert len(report.get("errors", [])) > 0
    assert report["errors"][0]["project_id"] == "fake_nonexistent_project"


def test_recovery_frappe_missing_apps_negative(tmp_path: Path):
    """
    Empirical negative test for Frappe compound recovery:
    Missing required apps without valid remotes or sources must fail
    with PROJECT_RESTORE_INCOMPLETE and never write fake/mock stubs.
    """
    sot_root = tmp_path / "sot"
    frappe_dir = sot_root / "project_profiles" / "frappe"
    frappe_dir.mkdir(parents=True)

    manifest = {
        "manifest_version": "1.0.0",
        "project_id": "frappe_test",
        "installed_apps": ["frappe", "erpnext", "alco_ecommerce"],
        "repositories": [
            {
                "name": "frappe",
                "url": "https://github.com/nonexistent-org-404/frappe-fake-404.git",
            },
            {
                "name": "erpnext",
                "url": "https://github.com/nonexistent-org-404/erpnext-fake-404.git",
            },
            {
                "name": "alco_ecommerce",
                "url": "https://github.com/nonexistent-org-404/alco-fake-404.git",
            },
        ],
    }
    (frappe_dir / "recovery_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    orchestrator = ProjectRecoveryOrchestrator(sot_root)
    target_bench_dir = tmp_path / "target_bench"

    res = orchestrator.recover_frappe_bench(
        target_bench_dir,
        home=tmp_path / "home",
        projects_root=tmp_path / "projects",
    )

    assert res["status"] == "PROJECT_RESTORE_INCOMPLETE"
    assert "missing_components" in res
    assert len(res["missing_components"]) > 0

    # Ensure no fake stub files were written
    frappe_init = target_bench_dir / "frappe-bench" / "apps" / "frappe" / "frappe" / "__init__.py"
    assert not frappe_init.exists()
