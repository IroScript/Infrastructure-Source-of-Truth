"""Deployment profile & runtime configuration for Backup Orchestrator."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BackupOrchestratorConfig:
    sot_root: Path
    home: Path
    projects_root: Path
    state_root: Path
    backup_state_dir: Path
    staging_dir: Path
    db_path: Path
    quiet_interval_seconds: float = 1800.0  # 30 minutes monotonic
    rclone_remote: str = "gdrive:Backups/Projects"
    retention_count: int = 10
    timezone_name: str = "Asia/Dhaka"

    @classmethod
    def resolve(
        cls,
        sot_root: Optional[Path] = None,
        home: Optional[Path] = None,
        projects_root: Optional[Path] = None,
        state_root: Optional[Path] = None,
        staging_dir: Optional[Path] = None,
        quiet_interval_seconds: Optional[float] = None,
    ) -> BackupOrchestratorConfig:
        s_root = Path(sot_root or Path(__file__).resolve().parent.parent).resolve()
        h_dir = Path(home or os.environ.get("HOME", "/home/azureuser")).resolve()
        p_dir = Path(
            projects_root
            or os.environ.get("PROJECTS_ROOT")
            or (h_dir / "IroScript_Projects")
        ).resolve()
        st_dir = Path(
            state_root
            or os.environ.get("STATE_ROOT")
            or (h_dir / ".agents")
        ).resolve()
        b_state = st_dir / "backup_orchestrator"
        stg_dir = Path(
            staging_dir
            or os.environ.get("BACKUP_STAGING_ROOT")
            or (b_state / "staging")
        ).resolve()

        q_interval = (
            float(quiet_interval_seconds)
            if quiet_interval_seconds is not None
            else float(os.environ.get("BACKUP_QUIET_INTERVAL_SECONDS", 1800.0))
        )

        return cls(
            sot_root=s_root,
            home=h_dir,
            projects_root=p_dir,
            state_root=st_dir,
            backup_state_dir=b_state,
            staging_dir=stg_dir,
            db_path=b_state / "backup_state.sqlite",
            quiet_interval_seconds=q_interval,
            rclone_remote=os.environ.get("BACKUP_RCLONE_REMOTE", "gdrive:Backups/Projects"),
            retention_count=int(os.environ.get("BACKUP_RETENTION_COUNT", 10)),
            timezone_name="Asia/Dhaka",
        )

    def load_registered_projects(self) -> List[Dict[str, Any]]:
        """Loads projects from projects/PROJECT_REGISTRY.json with dynamic root expansion."""
        reg_file = self.sot_root / "projects" / "PROJECT_REGISTRY.json"
        if not reg_file.is_file():
            return []
        try:
            data = json.loads(reg_file.read_text(encoding="utf-8"))
            projects = []
            for p in data.get("projects", []):
                p_copy = dict(p)
                raw_path = p_copy.get("canonical_path", "")
                expanded = raw_path.replace("${HOME}", str(self.home)).replace(
                    "${PROJECTS_ROOT}", str(self.projects_root)
                )
                p_copy["resolved_canonical_path"] = expanded
                projects.append(p_copy)
            return projects
        except Exception:
            return []
