"""
Tests for Atomic Dispatch vs ZIP Generation Race Conditions (Blocker-03).
Verifies that no prompts can be dispatched into a terminal while .partial.zip
exists or the gate is closed, and that project-scoped claims do not block other projects.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from backup_orchestrator.db import Database
from backup_orchestrator.gate import PromptGateCoordinator


def test_dispatch_blocked_when_partial_zip_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Verifies that acquire_dispatch_claim rejects dispatch if a .partial.zip
    exists for the target project.
    """
    backup_root = tmp_path / "backups"
    backup_root.mkdir(parents=True)
    monkeypatch.setenv("BACKUP_ROOT", str(backup_root))

    db_path = tmp_path / "backup_state.sqlite"
    db = Database(db_path)
    coordinator = PromptGateCoordinator(db)

    project_id = "test_proj_alpha"

    # Create dummy .partial.zip for project_id
    proj_backup_dir = backup_root / f"{project_id}__uuid123"
    proj_backup_dir.mkdir(parents=True)
    partial_zip = proj_backup_dir / "backup_20261009_120000.partial.zip"
    partial_zip.write_bytes(b"PK\x03\x04dummy")

    claim = coordinator.acquire_dispatch_claim(project_id)
    assert claim["acquired"] is False
    assert claim["action"] == "HOLD_FOR_ZIP"
    assert "partial.zip" in claim["reason"]

    # Remove partial zip -> claim should now succeed
    partial_zip.unlink()
    claim_after = coordinator.acquire_dispatch_claim(project_id)
    assert claim_after["acquired"] is True
    assert claim_after["status"] == "CLAIM_ACQUIRED"
    coordinator.release_dispatch_claim(project_id)


def test_concurrent_claim_and_close_gate_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Verifies that close_gate fails if an in-flight dispatch claim is active,
    and conversely, dispatch claim fails if gate is already closed.
    """
    backup_root = tmp_path / "backups"
    backup_root.mkdir(parents=True)
    monkeypatch.setenv("BACKUP_ROOT", str(backup_root))
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True)
    monkeypatch.setenv("STATE_ROOT", str(state_root))

    db_path = tmp_path / "backup_state.sqlite"
    db = Database(db_path)
    coordinator = PromptGateCoordinator(db)

    project_a = "proj_a"
    project_b = "proj_b"

    # 1. Project A acquires dispatch claim
    claim_a = coordinator.acquire_dispatch_claim(project_a)
    assert claim_a["acquired"] is True

    # 2. Attempting to close gate on Project A while claim is active must fail
    closed = coordinator.close_gate(project_a, zip_pid=os.getpid())
    assert closed is False, "close_gate should fail while in-flight dispatch claim is held"

    # 3. Release claim on Project A -> close_gate should now succeed
    coordinator.release_dispatch_claim(project_a)
    closed_after = coordinator.close_gate(project_a, zip_pid=os.getpid())
    assert closed_after is True

    # 4. Now that gate is closed for Project A, acquiring dispatch claim on Project A must be rejected
    claim_a_blocked = coordinator.acquire_dispatch_claim(project_a)
    assert claim_a_blocked["acquired"] is False
    assert claim_a_blocked["action"] == "HOLD_FOR_ZIP"

    # 5. Project B must remain completely UNBLOCKED (non-blocking isolation)
    claim_b = coordinator.acquire_dispatch_claim(project_b)
    assert claim_b["acquired"] is True
    coordinator.release_dispatch_claim(project_b)
