"""Retention Policy Enforcement & Pruning Transactions (Section 51)."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from .db import Database


@dataclass
class RetentionResult:
    status: str  # "CLEAN", "PRUNED", "RETENTION_PENDING"
    pruned_backup_id: Optional[str] = None
    pruned_remote_path: Optional[str] = None
    pruned_local_path: Optional[str] = None
    error: str = ""


class RetentionManager:
    """Manages remote and local retention transactions strictly for VERIFIED GOOD backups."""

    def __init__(self, db: Database, rclone_bin: str = "rclone", max_good_retention: int = 10):
        self.db = db
        self.rclone_bin = rclone_bin
        self.max_good_retention = max_good_retention

    def process_retention(self, project_id: str, staging_dir: Optional[Path] = None) -> RetentionResult:
        """
        Applies retention policy after a new GOOD backup:
        1. Queries all active GOOD backups for the project ordered by verified_at ASC.
        2. If count <= max_good_retention (10), no pruning needed -> "CLEAN".
        3. If count > max_good_retention (11th GOOD):
           - Selects exactly the oldest active GOOD backup.
           - Attempts deletion of that exact remote object via rclone deletefile.
           - Verifies deletion.
           - If deletion succeeds: updates retention_state='PRUNED'.
           - If deletion fails: marks retention_state='RETENTION_PENDING', new backup remains GOOD,
             count temporarily remains 11, never deletes second-oldest.
        4. Local retention: retains newest 10 verified GOOD local archives.
        """
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT backup_id, remote_path, remote_object_id, size, sha256, verified_at
                FROM verified_backups
                WHERE project_id = ? AND status = 'GOOD' AND retention_state = 'ACTIVE'
                ORDER BY verified_at ASC, rowid ASC;
                """,
                (project_id,),
            )
            active_goods = cur.fetchall()
        finally:
            conn.close()

        if len(active_goods) <= self.max_good_retention:
            self._prune_local_staging(project_id, active_goods, staging_dir)
            return RetentionResult(status="CLEAN")

        # More than 10 active GOOD records: prune exactly the oldest
        oldest = active_goods[0]
        oldest_id = oldest["backup_id"]
        oldest_remote_path = oldest["remote_path"]

        # Attempt deletion of the exact remote object
        del_success = False
        err_msg = ""
        try:
            del_res = subprocess.run(
                [self.rclone_bin, "deletefile", oldest_remote_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if del_res.returncode == 0:
                # Verify it is gone via lsjson
                chk_res = subprocess.run(
                    [self.rclone_bin, "lsjson", oldest_remote_path],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if chk_res.returncode == 0 and chk_res.stdout.strip() in ("[]", ""):
                    del_success = True
                else:
                    err_msg = f"Remote object still reported present after deletefile: {chk_res.stdout.strip()}"
            else:
                err_msg = f"rclone deletefile failed (rc={del_res.returncode}): {del_res.stderr.strip()}"
        except Exception as exc:
            err_msg = str(exc)

        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if del_success:
            with self.db.transaction() as cur:
                cur.execute(
                    """
                    UPDATE verified_backups
                    SET retention_state = 'PRUNED', deleted_at = ?
                    WHERE backup_id = ?;
                    """,
                    (now_str, oldest_id),
                )
            self._prune_local_staging(project_id, active_goods[1:], staging_dir)
            return RetentionResult(
                status="PRUNED",
                pruned_backup_id=oldest_id,
                pruned_remote_path=oldest_remote_path,
            )
        else:
            # Deletion failed: keep count=11, mark RETENTION_PENDING, do NOT delete second oldest
            with self.db.transaction() as cur:
                cur.execute(
                    """
                    UPDATE verified_backups
                    SET retention_state = 'RETENTION_PENDING'
                    WHERE backup_id = ?;
                    """,
                    (oldest_id,),
                )
            return RetentionResult(
                status="RETENTION_PENDING",
                pruned_backup_id=oldest_id,
                pruned_remote_path=oldest_remote_path,
                error=err_msg,
            )

    def _prune_local_staging(
        self,
        project_id: str,
        retained_goods: List[Any],
        staging_dir: Optional[Path],
    ) -> None:
        """Prunes local staging archives that are not in the newest 10 verified goods."""
        if not staging_dir or not staging_dir.is_dir():
            return

        retained_backup_ids = {row["backup_id"] for row in retained_goods[-self.max_good_retention:]}

        # Query all backup runs for this project to map files
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT backup_id, zip_path FROM backup_runs WHERE project_id = ?;",
                (project_id,),
            )
            all_runs = cur.fetchall()
        finally:
            conn.close()

        for run in all_runs:
            b_id = run["backup_id"]
            z_path = Path(run["zip_path"])
            if b_id not in retained_backup_ids and z_path.is_file():
                try:
                    z_path.unlink()
                except OSError:
                    pass
