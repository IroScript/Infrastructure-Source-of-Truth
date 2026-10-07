"""Task Attribution and Commit Message Generator (RULES 7, 8).
Enforces strict binary prefixes: 'User Requested : ' vs 'Unverified : '.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

PREFIX_USER_REQUESTED = "User Requested : "
PREFIX_UNVERIFIED = "Unverified : "


class TaskAttributor:
    """Attributes changes to active tasks and formats compliant commit messages."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def get_active_task_context(self, project_uuid: str = "") -> Optional[Dict[str, str]]:
        """Discovers active task context through provider-neutral registries or environment."""
        # 1. Environment variables
        env_task_id = os.environ.get("AGY_TASK_ID")
        env_origin = os.environ.get("AGY_TASK_ORIGIN")
        if env_task_id:
            return {
                "task_id": env_task_id,
                "project_uuid": os.environ.get("AGY_PROJECT_UUID", project_uuid),
                "origin": env_origin or "unverified",
                "request_summary": os.environ.get("AGY_TASK_SUMMARY", "automated task update")
            }

        # 2. Check SOT task evidence active marker
        active_file = self.root / "verification" / "TASK_EVIDENCE" / "active_task.json"
        if active_file.is_file():
            try:
                data = json.loads(active_file.read_text(encoding="utf-8"))
                if not project_uuid or data.get("project_uuid") == project_uuid or data.get("project_uuid") == "*":
                    return data
            except Exception:
                pass

        # 3. Check agent runtime active marker
        agent_active = Path.home() / ".agents" / "active_task.json"
        if agent_active.is_file():
            try:
                data = json.loads(agent_active.read_text(encoding="utf-8"))
                if not project_uuid or data.get("project_uuid") == project_uuid or data.get("project_uuid") == "*":
                    return data
            except Exception:
                pass

        return None

    def generate_change_summary(self, repo_path: Path) -> str:
        """Generates a concise factual summary of staged changes."""
        repo = Path(repo_path).resolve()
        res = subprocess.run(
            ["git", "-C", str(repo), "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True
        )
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if not lines:
            return "sync changes"

        if len(lines) == 1:
            parts = lines[0].split(None, 1)
            action = "update"
            if len(parts) >= 2:
                status, path = parts[0], parts[1]
                if status.startswith("A"):
                    action = "add"
                elif status.startswith("D"):
                    action = "remove"
                elif status.startswith("R"):
                    action = "rename"
                return f"{action} {path}"
            return f"update {lines[0]}"

        # Multiple files
        modified = [l.split()[-1] for l in lines[:3]]
        remaining = len(lines) - 3
        if remaining > 0:
            return f"update {', '.join(modified)} and {remaining} other files"
        return f"update {', '.join(modified)}"

    def determine_commit_message(self, repo_path: Path, project_uuid: str = "", explicit_summary: str = "") -> str:
        """Constructs an unalterable commit message with verified origin prefix."""
        context = self.get_active_task_context(project_uuid)
        summary = explicit_summary or (context.get("request_summary") if context else "")
        if not summary or summary.startswith("User Requested") or summary.startswith("Unverified"):
            summary = self.generate_change_summary(repo_path)

        # Ambiguity check: ONLY 'user_requested' maps to User Requested. Everything else is Unverified.
        if context and context.get("origin") == "user_requested":
            prefix = PREFIX_USER_REQUESTED
        else:
            prefix = PREFIX_UNVERIFIED

        return f"{prefix}{summary.strip()}"
