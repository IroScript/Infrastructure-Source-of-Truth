"""
Tests for alternate root portability and blank VM simulation (Blocker-06).
Verifies that no /home/azureuser dependencies are leaked or required.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from backup_orchestrator.config import BackupOrchestratorConfig
from bootstrap.project_recovery import ProjectRecoveryOrchestrator


def test_backup_orchestrator_alternate_root(tmp_path: Path):
    """
    Simulates a blank VM environment under an alternate root.
    Verifies that BackupOrchestratorConfig.load_registered_projects()
    dynamically replaces all /home/azureuser paths with the alternate roots.
    """
    alt_home = tmp_path / "alt_home"
    alt_projects = tmp_path / "alt_projects"
    alt_state = tmp_path / "alt_state"
    alt_backups = tmp_path / "alt_backups"

    alt_home.mkdir(parents=True)
    alt_projects.mkdir(parents=True)
    alt_state.mkdir(parents=True)
    alt_backups.mkdir(parents=True)

    sot_root = Path(__file__).resolve().parents[2]

    config = BackupOrchestratorConfig.resolve(
        sot_root=sot_root,
        home=alt_home,
        projects_root=alt_projects,
        state_root=alt_state,
        backup_root=alt_backups,
    )

    assert str(config.home) == str(alt_home)
    assert str(config.projects_root) == str(alt_projects)
    assert str(config.state_root) == str(alt_state)
    assert str(config.backup_root) == str(alt_backups)

    projects = config.load_registered_projects()
    assert len(projects) > 0

    for p in projects:
        resolved_path = p.get("resolved_canonical_path", "")
        assert "/home/azureuser" not in resolved_path, (
            f"Project {p.get('project_id')} leaked /home/azureuser in path: {resolved_path}"
        )
        assert str(alt_projects) in resolved_path or str(alt_home) in resolved_path, (
            f"Project {p.get('project_id')} path {resolved_path} does not point to alternate root"
        )
        for alias in p.get("resolved_aliases", []):
            assert "/home/azureuser" not in alias, (
                f"Project {p.get('project_id')} leaked /home/azureuser in alias: {alias}"
            )


def test_project_recovery_relative_path_portability():
    """
    Verifies that ProjectRecoveryOrchestrator correctly derives relative paths
    from various canonical prefixes without requiring /home/azureuser.
    """
    sot_root = Path(__file__).resolve().parents[2]
    orchestrator = ProjectRecoveryOrchestrator(sot_root)

    test_cases = [
        ("${PROJECTS_ROOT}/MyProject", "MyProject"),
        ("${HOME}/IroScript_Projects/MySub/Project", "MySub/Project"),
        ("/home/azureuser/IroScript_Projects/Deep/Nested/Project", "Deep/Nested/Project"),
        ("/home/azureuser/Frappe-erp-Alco", "Frappe-erp-Alco"),
        ("${HOME}/Frappe-erp-Alco", "Frappe-erp-Alco"),
    ]

    for input_path, expected_rel in test_cases:
        rel = orchestrator.resolve_relative_path(input_path)
        assert rel == expected_rel, f"Failed for {input_path}: expected {expected_rel}, got {rel}"
