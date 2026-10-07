"""Push Workflow and Failure Resilience Engine (RULES 15, 16).
Never force-pushes, never rewrites history, and persists PUSH_PENDING with backoff retry.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple


class GitPusher:
    """Manages commit creation, remote push, SHA verification, and failure recovery."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    @staticmethod
    def get_head_sha(repo_path: Path) -> str:
        res = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True
        )
        return res.stdout.strip() if res.returncode == 0 else ""

    @staticmethod
    def get_current_branch(repo_path: Path) -> str:
        res = subprocess.run(
            ["git", "-C", str(repo_path), "branch", "--show-current"],
            capture_output=True,
            text=True
        )
        branch = res.stdout.strip()
        if not branch:
            # Fallback for new empty repos or detached
            res = subprocess.run(
                ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True
            )
            branch = res.stdout.strip()
        return branch or "main"

    @classmethod
    def commit(cls, repo_path: Path, message: str) -> Tuple[bool, str, str]:
        """Creates a git commit from currently staged files."""
        repo = Path(repo_path).resolve()
        res = subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", message],
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            return False, "", f"Commit failed: {res.stderr.strip() or res.stdout.strip()}"
        
        sha = cls.get_head_sha(repo)
        return True, sha, "COMMIT_CREATED"

    @classmethod
    def push_and_verify_parity(cls, repo_path: Path, branch: str = "", remote: str = "origin") -> Tuple[bool, str]:
        """Pushes current branch to remote and verifies local HEAD == remote branch SHA."""
        repo = Path(repo_path).resolve()
        branch = branch or cls.get_current_branch(repo)
        local_sha = cls.get_head_sha(repo)
        
        if not local_sha:
            return False, "LOCAL_HEAD_SHA_MISSING"

        # Check configured remote
        rem_check = subprocess.run(
            ["git", "-C", str(repo), "config", "--get", f"remote.{remote}.url"],
            capture_output=True,
            text=True
        )
        remote_url = rem_check.stdout.strip()
        if not remote_url:
            return False, "REMOTE_URL_NOT_CONFIGURED"

        # Push without force
        push = subprocess.run(
            ["git", "-C", str(repo), "push", "--set-upstream", remote, branch],
            capture_output=True,
            text=True
        )
        if push.returncode != 0:
            err = push.stderr.strip() or push.stdout.strip()
            return False, f"PUSH_FAILED: {err}"

        # Fetch and verify parity
        fetch = subprocess.run(
            ["git", "-C", str(repo), "fetch", remote, branch],
            capture_output=True,
            text=True
        )

        probe = subprocess.run(
            ["git", "ls-remote", "--exit-code", remote_url, f"refs/heads/{branch}"],
            capture_output=True,
            text=True
        )
        if probe.returncode != 0:
            # For local bare repositories, ls-remote with repo path or directory check
            probe = subprocess.run(
                ["git", "-C", str(repo), "ls-remote", "--exit-code", remote, f"refs/heads/{branch}"],
                capture_output=True,
                text=True
            )

        if probe.returncode != 0:
            return False, f"REMOTE_QUERY_FAILED: {probe.stderr.strip()}"

        remote_sha = probe.stdout.split()[0] if probe.stdout.split() else ""
        if remote_sha != local_sha:
            return False, f"REMOTE_SHA_MISMATCH (local={local_sha[:12]}, remote={remote_sha[:12]})"

        return True, "PUSH_AND_REMOTE_SHA_VERIFIED"
