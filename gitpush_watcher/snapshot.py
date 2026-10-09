import fnmatch
import hashlib
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class SnapshotManager:
    """Manages consistent Git staging without interrupting concurrent writers (RULE 5)."""

    @staticmethod
    def get_file_fingerprint(path: Path) -> Tuple[int, int, str]:
        """Returns (mtime_ns, size_bytes, sha256_hash) for a physical file."""
        st = path.stat()
        # Compute sha256 content hash (read up to 10MB to detect content modifications even if size matches)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
                if h.digest_size > 10 * 1024 * 1024:
                    break
        return st.st_mtime_ns, st.st_size, h.hexdigest()

    @classmethod
    def capture_working_fingerprints(cls, repo_path: Path, ignored_subpaths: List[str] | None = None) -> Dict[str, Tuple[int, int, str]]:
        """Captures fingerprint state of modified/trackable files before/after staging (sub-second fast path)."""
        repo = Path(repo_path).resolve()
        fingerprints: Dict[str, Tuple[int, int, str]] = {}
        ignored = set(ignored_subpaths or [])

        # Sub-second fast path via git status --porcelain
        try:
            proc = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if len(line) < 4:
                        continue
                    path_part = line[3:].strip()
                    if " -> " in path_part:
                        path_part = path_part.split(" -> ")[1].strip()
                    fpath = repo / path_part
                    try:
                        rel = str(fpath.relative_to(repo))
                        if any(
                            fnmatch.fnmatch(rel, ign)
                            or fnmatch.fnmatch(fpath.name, ign)
                            or fnmatch.fnmatch(f"*/{fpath.name}", ign)
                            or any(fnmatch.fnmatch(part, ign) for part in fpath.parts)
                            or rel == ign
                            or rel.startswith(ign.rstrip("*"))
                            for ign in ignored
                        ):
                            continue
                        if fpath.is_file() and not fpath.is_symlink():
                            fingerprints[rel] = cls.get_file_fingerprint(fpath)
                    except (OSError, ValueError):
                        continue
                return fingerprints
        except Exception:
            pass

        # Fallback directory walk
        for root, dirs, files in os.walk(repo):
            dirs[:] = [d for d in dirs if d not in (
                ".git", ".project-locks", ".pytest_cache", "__pycache__",
                "node_modules", "wa_auth", "wa_auth_snapshots", "wa_auth_senderkeys_backup",
                ".cache", ".venv", "venv", ".nvm", "All_Backup", "target", "build", "dist",
                ".gradle", ".dart_tool", "out", "Pods"
            ) and not d.endswith("_backup") and not d.startswith(".")]

            for fname in files:
                fpath = Path(root) / fname
                try:
                    rel = str(fpath.relative_to(repo))
                    if any(
                        fnmatch.fnmatch(rel, ign)
                        or fnmatch.fnmatch(fname, ign)
                        or fnmatch.fnmatch(f"*/{fname}", ign)
                        or any(fnmatch.fnmatch(part, ign) for part in fpath.parts)
                        or rel == ign
                        or rel.startswith(ign.rstrip("*"))
                        for ign in ignored
                    ):
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
            text=True,
            timeout=30
        )
        if proc.returncode != 0:
            return False, f"Staging failed: {proc.stderr.strip()}"
        return True, "STAGED"

    @classmethod
    def verify_consistency(cls, repo_path: Path, pre_fingerprints: Dict[str, Tuple[int, int, str]], ignored_subpaths: List[str] | None = None) -> Tuple[bool, str]:
        """Verifies that no file was added, removed, or mutated during the staging interval (FIX 5)."""
        repo = Path(repo_path).resolve()
        # Recapture full working-tree state post-staging
        post_fingerprints = cls.capture_working_fingerprints(repo, ignored_subpaths)

        pre_paths = set(pre_fingerprints.keys())
        post_paths = set(post_fingerprints.keys())

        # 1. Detect newly created files during staging
        added_paths = post_paths - pre_paths
        if added_paths:
            return False, f"Files created during staging interval: {list(added_paths)[:5]}"

        # 2. Detect files removed during staging
        deleted_paths = pre_paths - post_paths
        if deleted_paths:
            return False, f"Files removed during staging interval: {list(deleted_paths)[:5]}"

        # 3. Detect mutated files (mtime, size, or content hash mismatch)
        for rel_path in pre_paths:
            pre_mtime, pre_size, pre_hash = pre_fingerprints[rel_path]
            post_mtime, post_size, post_hash = post_fingerprints[rel_path]
            if pre_size != post_size or pre_hash != post_hash:
                return False, f"File {rel_path} content mutated during staging (writer active)"

        return True, "CONSISTENT"

    @classmethod
    def discard_staged_snapshot(cls, repo_path: Path) -> None:
        """Discards staged changes in index ONLY. NEVER touches working tree files (RULE 5)."""
        head_check = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            timeout=10
        )
        if head_check.returncode == 0:
            subprocess.run(["git", "-C", str(repo_path), "restore", "--staged", "."], capture_output=True, timeout=20)
        else:
            subprocess.run(["git", "-C", str(repo_path), "rm", "--cached", "-f", "-r", "."], capture_output=True, timeout=20)

    @classmethod
    def has_staged_changes(cls, repo_path: Path) -> bool:
        """Returns True if there are any staged changes in git index."""
        proc = subprocess.run(
            ["git", "-C", str(repo_path), "diff", "--cached", "--quiet"],
            capture_output=True,
            timeout=15
        )
        return proc.returncode == 1

