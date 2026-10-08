"""Project Directory Zipper & Integrity Verifier with Symlink Preservation (Sections 44, 47)."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple


@dataclass
class ZipResult:
    status: str  # "LOCAL_VERIFIED", "MUTATION_DETECTED", "VERIFICATION_FAILED"
    archive_path: Optional[Path]
    size: int = 0
    sha256: str = ""
    md5: str = ""
    mutation_seen: bool = False
    error: str = ""


class ProjectZipper:
    """Creates complete zip archive of a live project root and verifies local integrity."""

    def __init__(self, staging_dir: Path):
        self.staging_dir = Path(staging_dir).resolve()
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def create_project_zip(
        self,
        project_root: Path,
        archive_name: str,
        zip_start_generation: int,
        check_mutation_callback: Optional[Callable[[], bool]] = None,
        get_current_generation_callback: Optional[Callable[[], int]] = None,
    ) -> ZipResult:
        """
        Creates a zip archive of the project root:
        - Includes hidden files, .git, logs, source, etc.
        - Preserves symlinks as symlinks without reading external targets.
        - Monitors for mutations during archive creation.
        - Verifies CRC32 and computes SHA256 & MD5.
        """
        project_root = Path(project_root).resolve()
        final_zip_path = self.staging_dir / archive_name
        partial_zip_path = self.staging_dir / f"{archive_name}.partial"

        if partial_zip_path.exists():
            partial_zip_path.unlink()
        if final_zip_path.exists():
            final_zip_path.unlink()

        mutation_seen_during_zip = False

        try:
            with zipfile.ZipFile(
                partial_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
            ) as zf:
                for root, dirs, files in os.walk(project_root, topdown=True, followlinks=False):
                    # Check mutation during walk
                    if check_mutation_callback and check_mutation_callback():
                        mutation_seen_during_zip = True
                        break

                    rel_dir = os.path.relpath(root, project_root)
                    if rel_dir != ".":
                        # Record directory entries
                        dir_zinfo = zipfile.ZipInfo(f"{rel_dir}/")
                        dir_zinfo.create_system = 3  # UNIX
                        dir_zinfo.external_attr = (stat.S_IFDIR | 0o755) << 16
                        zf.writestr(dir_zinfo, b"")

                    for f in files:
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, project_root)

                        # Check mutation periodically
                        if check_mutation_callback and check_mutation_callback():
                            mutation_seen_during_zip = True
                            break

                        if os.path.islink(full_path):
                            # Store symlink without dereferencing or reading target bytes
                            link_target = os.readlink(full_path)
                            zinfo = zipfile.ZipInfo(rel_path)
                            zinfo.create_system = 3  # UNIX
                            zinfo.external_attr = (stat.S_IFLNK | 0o777) << 16
                            zf.writestr(zinfo, link_target.encode("utf-8"))
                        else:
                            try:
                                zf.write(full_path, arcname=rel_path)
                            except FileNotFoundError:
                                # File deleted during walk -> mutation
                                mutation_seen_during_zip = True
                                break

                    if mutation_seen_during_zip:
                        break

            # Check mutation callback after walk concludes
            if check_mutation_callback and check_mutation_callback():
                mutation_seen_during_zip = True

            # Compare final filesystem generation with captured generation
            if get_current_generation_callback:
                current_gen = get_current_generation_callback()
                if current_gen != zip_start_generation:
                    mutation_seen_during_zip = True

            if mutation_seen_during_zip:
                if partial_zip_path.exists():
                    partial_zip_path.unlink()
                return ZipResult(
                    status="MUTATION_DETECTED",
                    archive_path=None,
                    mutation_seen=True,
                    error="Filesystem mutation observed during zip archive creation",
                )

            # Atomic rename from .partial to final
            partial_zip_path.rename(final_zip_path)

            # Local verification: testzip()
            with zipfile.ZipFile(final_zip_path, "r") as test_zf:
                bad_file = test_zf.testzip()
                if bad_file:
                    final_zip_path.unlink(missing_ok=True)
                    return ZipResult(
                        status="VERIFICATION_FAILED",
                        archive_path=None,
                        error=f"Corrupted file inside archive: {bad_file}",
                    )

            # Calculate SHA256 and MD5
            sha256_hash = hashlib.sha256()
            md5_hash = hashlib.md5()
            total_size = 0
            with open(final_zip_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    sha256_hash.update(chunk)
                    md5_hash.update(chunk)
                    total_size += len(chunk)

            return ZipResult(
                status="LOCAL_VERIFIED",
                archive_path=final_zip_path,
                size=total_size,
                sha256=sha256_hash.hexdigest(),
                md5=md5_hash.hexdigest(),
                mutation_seen=False,
            )

        except Exception as exc:
            if partial_zip_path.exists():
                partial_zip_path.unlink()
            if final_zip_path.exists():
                final_zip_path.unlink()
            return ZipResult(
                status="VERIFICATION_FAILED",
                archive_path=None,
                error=str(exc),
            )
