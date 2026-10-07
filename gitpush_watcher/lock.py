"""Exclusive short-lived per-repository lock to prevent Git metadata race conditions (RULE 6)."""
from __future__ import annotations

import contextlib
import fcntl
import os
import time
from pathlib import Path
from typing import Generator


class RepoLockError(Exception):
    """Raised when repository lock cannot be acquired."""


@contextlib.contextmanager
def repo_lock(repo_path: Path | str, timeout_seconds: float = 15.0) -> Generator[Path, None, None]:
    """Acquires an exclusive short lock for Git write operations on the repository.
    Never blocks or halts coding agents, only coordinates between Git writers.
    """
    repo = Path(repo_path).resolve()
    git_dir = repo / ".git"
    
    if git_dir.is_dir():
        lock_file = git_dir / "sot_gitpush.lock"
    else:
        # For non-git or bare/alternate repos
        lock_dir = repo.parent / ".project-locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_file = lock_dir / f"{repo.name}.git.lock"

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.time() + timeout_seconds
    acquired = False

    try:
        while time.time() < deadline:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (BlockingIOError, OSError):
                time.sleep(0.05)
        
        if not acquired:
            raise RepoLockError(f"Timed out after {timeout_seconds}s waiting for Git lock on {repo}")
        
        yield lock_file
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            os.close(fd)
        except OSError:
            pass
