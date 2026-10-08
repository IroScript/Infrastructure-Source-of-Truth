"""Rclone Google Drive Uploader & Hash Verifier with Client-ID Audit (Sections 48, 49, 50)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class UploadVerificationResult:
    status: str  # "GOOD", "REMOTE_VERIFY_FAILED", "RCLONE_CLIENT_ID_MIGRATION_REQUIRED", "UPLOAD_FAILED"
    remote_path: str
    remote_object_id: str = ""
    remote_size: int = 0
    remote_md5: str = ""
    local_sha256: str = ""
    error: str = ""


class BackupUploader:
    """Manages uploads to Google Drive/object storage via rclone and verifies remote integrity."""

    def __init__(self, rclone_bin: str = "rclone"):
        self.rclone_bin = rclone_bin

    def audit_rclone_client_id(self, remote_name: str) -> Dict[str, Any]:
        """
        Inspects rclone configuration for the remote (Section 49).
        Google Drive shared default client ID is retired in 2026.
        If own client_id or service_account_file is configured -> PASS.
        Otherwise -> RCLONE_CLIENT_ID_MIGRATION_REQUIRED.
        """
        clean_remote = remote_name.split(":")[0].strip()
        try:
            res = subprocess.run(
                [self.rclone_bin, "config", "show", clean_remote],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                return {
                    "status": "FAIL",
                    "code": "REMOTE_NOT_CONFIGURED",
                    "remote": clean_remote,
                    "error": res.stderr.strip(),
                }

            lines = res.stdout.splitlines()
            cfg: Dict[str, str] = {}
            for line in lines:
                if "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip().lower()] = v.strip()

            remote_type = cfg.get("type", "")
            if remote_type != "drive":
                # Non-drive backend (e.g. s3, local, etc.)
                return {"status": "PASS", "remote": clean_remote, "type": remote_type}

            has_own_client = bool(cfg.get("client_id")) or bool(cfg.get("service_account_file"))
            if has_own_client:
                return {"status": "PASS", "remote": clean_remote, "type": "drive", "client_configured": True}
            else:
                return {
                    "status": "RCLONE_CLIENT_ID_MIGRATION_REQUIRED",
                    "remote": clean_remote,
                    "type": "drive",
                    "reason": "Google Drive remote uses retired default shared client ID without own client_id or service-account",
                }
        except Exception as exc:
            return {"status": "FAIL", "remote": clean_remote, "error": str(exc)}

    def upload_and_verify(
        self,
        local_archive: Path,
        remote_dest_dir: str,
        expected_sha256: str,
        expected_md5: str,
        strict_download_verify: bool = False,
    ) -> UploadVerificationResult:
        """
        Uploads archive to remote destination and performs cryptographic verification:
        1. Uploads via rclone copyto
        2. Queries remote metadata via lsjson --hash
        3. Confirms exact filename and uniqueness (detects duplicates)
        4. Validates size and MD5 hash
        5. In strict mode: streams/downloads object to compute and confirm SHA256
        """
        local_archive = Path(local_archive).resolve()
        if not local_archive.is_file():
            return UploadVerificationResult(
                status="UPLOAD_FAILED",
                remote_path="",
                error=f"Local archive does not exist: {local_archive}",
            )

        filename = local_archive.name
        remote_full_path = f"{remote_dest_dir.rstrip('/')}/{filename}"

        # Perform upload
        try:
            up_res = subprocess.run(
                [self.rclone_bin, "copyto", str(local_archive), remote_full_path],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if up_res.returncode != 0:
                return UploadVerificationResult(
                    status="UPLOAD_FAILED",
                    remote_path=remote_full_path,
                    error=f"rclone copyto failed: {up_res.stderr.strip()}",
                )
        except Exception as exc:
            return UploadVerificationResult(
                status="UPLOAD_FAILED",
                remote_path=remote_full_path,
                error=str(exc),
            )

        # Query remote object metadata
        try:
            ls_res = subprocess.run(
                [self.rclone_bin, "lsjson", "--hash", remote_full_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if ls_res.returncode != 0:
                return UploadVerificationResult(
                    status="REMOTE_VERIFY_FAILED",
                    remote_path=remote_full_path,
                    error=f"rclone lsjson failed: {ls_res.stderr.strip()}",
                )

            items = json.loads(ls_res.stdout)
            # Filter non-directory items matching exact filename
            matching = [x for x in items if not x.get("IsDir") and (x.get("Name") == filename or x.get("Path") == filename)]

            if not matching:
                return UploadVerificationResult(
                    status="REMOTE_VERIFY_FAILED",
                    remote_path=remote_full_path,
                    error="Remote object not found after upload",
                )

            if len(matching) > 1:
                # Ambiguous duplicate remote objects (Section 50)
                return UploadVerificationResult(
                    status="REMOTE_VERIFY_FAILED",
                    remote_path=remote_full_path,
                    error="Ambiguous duplicate remote objects detected with identical filename",
                )

            remote_meta = matching[0]
            remote_size = remote_meta.get("Size", -1)
            remote_id = remote_meta.get("ID", "")
            remote_hashes = remote_meta.get("Hashes", {})
            remote_md5 = remote_hashes.get("md5", "")

            local_size = local_archive.stat().st_size
            if remote_size != local_size:
                return UploadVerificationResult(
                    status="REMOTE_VERIFY_FAILED",
                    remote_path=remote_full_path,
                    remote_object_id=remote_id,
                    remote_size=remote_size,
                    error=f"Size mismatch: local={local_size}, remote={remote_size}",
                )

            if remote_md5 and expected_md5 and remote_md5.lower() != expected_md5.lower():
                return UploadVerificationResult(
                    status="REMOTE_VERIFY_FAILED",
                    remote_path=remote_full_path,
                    remote_object_id=remote_id,
                    remote_size=remote_size,
                    remote_md5=remote_md5,
                    error=f"MD5 hash mismatch: local={expected_md5}, remote={remote_md5}",
                )

            # Strict download verification if requested or if backend exposed no remote hash
            if strict_download_verify or not remote_md5:
                with tempfile.TemporaryDirectory(prefix="sot-verify-dl-") as tmpdir:
                    dl_file = Path(tmpdir) / filename
                    dl_res = subprocess.run(
                        [self.rclone_bin, "copyto", remote_full_path, str(dl_file)],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if dl_res.returncode != 0:
                        return UploadVerificationResult(
                            status="REMOTE_VERIFY_FAILED",
                            remote_path=remote_full_path,
                            remote_object_id=remote_id,
                            error=f"Strict verification download failed: {dl_res.stderr.strip()}",
                        )

                    h = hashlib.sha256()
                    with open(dl_file, "rb") as f:
                        while chunk := f.read(1024 * 1024):
                            h.update(chunk)
                    dl_sha = h.hexdigest()

                    if dl_sha != expected_sha256:
                        return UploadVerificationResult(
                            status="REMOTE_VERIFY_FAILED",
                            remote_path=remote_full_path,
                            remote_object_id=remote_id,
                            error=f"Strict SHA256 mismatch: local={expected_sha256}, downloaded={dl_sha}",
                        )

            return UploadVerificationResult(
                status="GOOD",
                remote_path=remote_full_path,
                remote_object_id=remote_id,
                remote_size=remote_size,
                remote_md5=remote_md5,
                local_sha256=expected_sha256,
            )

        except Exception as exc:
            return UploadVerificationResult(
                status="REMOTE_VERIFY_FAILED",
                remote_path=remote_full_path,
                error=str(exc),
            )
