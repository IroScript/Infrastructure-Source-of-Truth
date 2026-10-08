"""
backup_harness.py — Backup Gate & Daemon Test Harness for E2E Acceptance Suite.
"""
from __future__ import annotations

import os
import signal
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class BackupGateHarness:
    """
    Simulates and manages Backup Orchestrator gate states, ZIP subprocesses,
    and crash recovery for E2E testing.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path).resolve()
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects_state (
                    project_id TEXT PRIMARY KEY,
                    project_slug TEXT NOT NULL,
                    prompt_gate TEXT NOT NULL DEFAULT 'ZIP_GATE_OPEN',
                    zip_pid INTEGER,
                    active_backup_id TEXT,
                    lifecycle_lock TEXT NOT NULL DEFAULT 'UNLOCKED',
                    filesystem_state TEXT NOT NULL DEFAULT 'CLEAN',
                    updated_at TEXT NOT NULL
                );
                """
            )

    def set_gate(
        self,
        project_id: str,
        gate_state: str = "ZIP_GATE_OPEN",
        zip_pid: Optional[int] = None,
        slug: str = "test-project"
    ) -> None:
        """Explicitly sets prompt gate state."""
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO projects_state (project_id, project_slug, prompt_gate, zip_pid, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    prompt_gate = excluded.prompt_gate,
                    zip_pid = excluded.zip_pid,
                    updated_at = excluded.updated_at;
                """,
                (project_id, slug, gate_state, zip_pid, now_iso)
            )

    def get_gate(self, project_id: str) -> Dict[str, Any]:
        """Queries the current gate state."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM projects_state WHERE project_id = ?;", (project_id,))
            row = cur.fetchone()
            if not row:
                return {
                    "project_uuid": project_id,
                    "zip_gate": "ZIP_GATE_OPEN",
                    "action": "ALLOW_NOW",
                    "zip_running": False,
                    "zip_pid": None
                }
            gate = row["prompt_gate"]
            pid = row["zip_pid"]
            action = "HOLD_FOR_ZIP" if gate == "ZIP_GATE_CLOSED" else "ALLOW_NOW"
            return {
                "project_uuid": project_id,
                "zip_gate": gate,
                "action": action,
                "zip_running": (gate == "ZIP_GATE_CLOSED"),
                "zip_pid": pid
            }

    def start_mock_zip(self, project_id: str) -> int:
        """Spawns a mock ZIP process and closes the gate."""
        proc = subprocess.Popen(["sleep", "60"])
        self.active_processes[project_id] = proc
        self.set_gate(project_id, gate_state="ZIP_GATE_CLOSED", zip_pid=proc.pid)
        return proc.pid

    def stop_mock_zip(self, project_id: str) -> None:
        """Stops the mock ZIP process and reopens the gate."""
        proc = self.active_processes.pop(project_id, None)
        if proc:
            proc.terminate()
            proc.wait()
        self.set_gate(project_id, gate_state="ZIP_GATE_OPEN", zip_pid=None)

    def simulate_crash_during_closed_gate(self, project_id: str) -> int:
        """
        Spawns a mock ZIP process, marks gate CLOSED with its PID,
        then immediately kills the process to simulate a crash.
        """
        proc = subprocess.Popen(["sleep", "60"])
        pid = proc.pid
        self.set_gate(project_id, gate_state="ZIP_GATE_CLOSED", zip_pid=pid)
        proc.kill()
        proc.wait()
        return pid

    def recover_stale_gate(self, project_id: str) -> bool:
        """
        Inspects the recorded zip_pid:
        If PID is no longer alive, automatically reopens the gate to ZIP_GATE_OPEN.
        """
        info = self.get_gate(project_id)
        if info["zip_gate"] != "ZIP_GATE_CLOSED":
            return False

        pid = info.get("zip_pid")
        is_alive = False
        if pid:
            try:
                os.kill(pid, 0)
                is_alive = True
            except OSError:
                is_alive = False

        if not is_alive:
            self.set_gate(project_id, gate_state="ZIP_GATE_OPEN", zip_pid=None)
            return True
        return False

    def cleanup_all(self) -> None:
        """Terminates all active child processes."""
        for proc in self.active_processes.values():
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.active_processes.clear()
