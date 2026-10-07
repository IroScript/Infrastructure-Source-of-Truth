"""Consistent snapshot engine without stopping writers (RULE 5).
Safeguards working files by never destructively altering the working tree.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class SnapshotManager:
    """Manages consistent Git staging without interrupting concurrent writers."""

    @staticmethod
    def get_file_fingerprint(path: Path) -> Tuple[int, int]:
        """Returns (mtime_ns, size_bytes) for a physical file."""
        st = path.stat()
        return st.st_mtime_ns, st.st_size

    @classmethod
    def capture_working_fingerprints(cls, repo_path: Path, ignored_subpaths: List[str] | None = None) -> Dict[str, Tuple[int, int]]:
        """Captures fingerprints of all non-ignored files in repo before staging."""
        repo = Path(repo_path).resolve()
        fingerprints: Dict[str, Tuple[int, int]] = {}
        ignored = set(ignored_subpaths or [])

        for root, dirs, files in os.walk(repo):
            # Prune .git and lock directories
            if ".git" in dirs:
                dirs.remove(".git")
            if ".project-locks" in dirs:
                dirs.remove(".project-locks")
            if ".pytest_cache" in dirs:
                dirs.remove(".pytest_cache")
            if "__pycache__" in dirs:
                dirs.remove("__pycache__")

            for fname in files:
                fpath = Path(root) / fname
                try:
                    rel = str(fpath.relative_to(repo))
                    if any(rel == ign or rel.startswith(ign.rstrip("*")) for ign in ignored):
                        continue
                    if fpath.is_file() and not fpath.is_symlink():
                        fingerprints[rel] = cls.get_file_fingerprint(fpath)
                except (OSError, ValueError):
                    continue

        return fingerprints

    @classmethod
    def stage_changes(cls, repo_path: Path) -> Tuple[bool, str]:
        """Executes non-destructive staging (git add -A)."""
        proc = subprocess.run(
            ["git", "-C", str(repo_path), "add", "-A"],
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            return False, f"Staging failed: {proc.stderr.strip()}"
        return True, "STAGED"

    @classmethod
    def verify_consistency(cls, repo_path: Path, pre_fingerprints: Dict[str, Tuple[int, int]]) -> Tuple[bool, str]:
        """Verifies that no file was modified by an active writer during the staging interval."""
        repo = Path(repo_path).resolve()
        for rel_path, pre_fp in pre_fingerprints.items():
            full_path = repo / rel_path
            if not full_path.exists():
                return False, f"File {rel_path} was removed during staging interval"
            try:
                post_fp = cls.get_file_fingerprint(full_path)
                if post_fp != pre_fp:
                    return False, f"File {rel_path} mutated during staging interval (writer active)"
            except OSError as exc:
                return False, f"Could not inspect {rel_path}: {exc}"
        return True, "CONSISTENT"

    @classmethod
    def discard_staged_snapshot(cls, repo_path: Path) -> None:
        """Discards staged changes in index ONLY. NEVER touches working tree files (RULE 5)."""
        head_check = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--verify", "HEAD"],
            capture_output=True
        )
        if head_check.returncode == 0:
            subprocess.run(["git", "-C", str(repo_path), "restore", "--staged", "."], capture_output=True)
        else:
            subprocess.run(["git", "-C", str(repo_path), "rm", "--cached", "-f", "-r", "."], capture_output=True)

    @classmethod
    def has_staged_changes(cls, repo_path: Path) -> bool:
        """Returns True if there are any staged changes in git index."""
        proc = subprocess.run(
            ["git", "-C", str(repo_path), "diff", "--cached", "--quiet"],
            capture_output=True
        )
        return proc.returncode == 1
