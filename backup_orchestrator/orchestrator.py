"""Core Backup Orchestrator Engine (Sections 36, 40, 41, 52, 53, 58)."""
from __future__ import annotations

import os
import secrets
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from .agent_model import AgentState, AgentStateEvaluator
from .config import BackupOrchestratorConfig
from .db import Database
from .gate import PromptGateCoordinator
from .retention import RetentionManager
from .timekeeping import Clock, RealClock, generate_backup_filename
from .uploader import BackupUploader
from .watcher import ProjectFsWatcher
from .zipper import ProjectZipper


@dataclass
class BackupCycleResult:
    project_id: str
    action_taken: str  # "BACKUP_COMPLETED", "SKIPPED_NOT_QUIET", "SKIPPED_BUSY", "MUTATION_ABORTED", "UPLOAD_FAILED"
    backup_id: Optional[str] = None
    captured_generation: int = 0
    dirty_generation: int = 0
    last_good_generation: int = 0
    error: str = ""


class BackupOrchestrator:
    """
    Core orchestrator coordinating:
    - Filesystem watchers & monotonic quiet interval evaluation
    - Prompt gate opening/closing boundaries
    - Immutable ZIP snapshot generation with symlink preservation
    - Independent remote upload & hash verification
    - Captured generation tracking (last_good_generation = captured_generation)
    - Verified GOOD retention transactions
    - Crash recovery & non-blocking upload retries
    """

    def __init__(
        self,
        config: BackupOrchestratorConfig,
        clock: Optional[Clock] = None,
        agent_evaluator: Optional[AgentStateEvaluator] = None,
        uploader: Optional[BackupUploader] = None,
        terminal_receiver: Optional[Any] = None,
    ):
        self.config = config
        self.clock = clock or RealClock(config.timezone_name)
        self.db = Database(self.config.db_path)
        self.gate_coordinator = PromptGateCoordinator(self.db)
        self.agent_evaluator = agent_evaluator or AgentStateEvaluator()
        self.zipper = ProjectZipper(self.config.staging_dir)
        self.uploader = uploader or BackupUploader()
        self.retention_manager = RetentionManager(
            self.db, max_good_retention=self.config.retention_count
        )
        self.watchers: Dict[str, ProjectFsWatcher] = {}
        self.project_metadata: Dict[str, Dict[str, Any]] = {}
        # Zero terminal delivery ownership in BackupOrchestrator (Section 1).
        # WhatsApp Bridge is the sole terminal delivery owner.
        self.delivery_owner_instance_id = f"daemon-{os.getpid()}-{secrets.token_hex(4)}"
        self._init_projects_and_crash_recovery()

    def _init_projects_and_crash_recovery(self) -> None:
        """
        Loads registered projects, registers them in state DB, and executes
        Crash Recovery Gate Rule (Section 53):
        - If PROMPT_GATE=CLOSED and no active local backup in progress:
          recovers queue, marks interrupted run FAILED, opens gate, and resumes FIFO delivery.
        - If an immutable LOCAL_VERIFIED ZIP exists and crash occurred during upload:
          gate remains OPEN, retries upload.
        """
        registered = self.config.load_registered_projects()
        for p in registered:
            p_id = p.get("project_id", "")
            p_slug = p.get("project_id", "").replace(" ", "_").lower()
            c_path = p.get("resolved_canonical_path") or p.get("canonical_path", "")
            if not p_id or not c_path:
                continue

            self.project_metadata[p_id] = p
            self.gate_coordinator.register_or_update_project(
                project_id=p_id,
                project_slug=p_slug,
                canonical_path=c_path,
            )
            # Create watcher
            p_dir = Path(c_path)
            if p_dir.is_dir():
                watcher = ProjectFsWatcher(p_id, p_dir, self.db, clock=self.clock)
                watcher.start_watches()
                self.watchers[p_id] = watcher

        # Perform crash recovery audit across projects
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT project_id, prompt_gate, zip_pid, lifecycle_lock, active_backup_id
                FROM projects_state
                WHERE prompt_gate = 'CLOSED' OR lifecycle_lock = 'LOCKED';
                """
            )
            stranded_projects = cur.fetchall()
        finally:
            conn.close()

        for sp in stranded_projects:
            p_id = sp["project_id"]
            active_b_id = sp["active_backup_id"]
            zip_pid = sp["zip_pid"] if "zip_pid" in sp.keys() else None

            # Check if active backup run exists and its status
            run_status = None
            zip_path = None
            if active_b_id:
                conn = self.db.get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT status, zip_path FROM backup_runs WHERE backup_id = ?;",
                        (active_b_id,),
                    )
                    r = cur.fetchone()
                    if r:
                        run_status = r["status"]
                        zip_path = r["zip_path"]
                finally:
                    conn.close()

            now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            if run_status == "LOCAL_VERIFIED" and zip_path and Path(zip_path).is_file():
                # Crash occurred during upload: gate should be OPEN, retry upload later
                with self.db.transaction() as cur:
                    cur.execute(
                        """
                        UPDATE projects_state
                        SET prompt_gate = 'OPEN', zip_pid = NULL, lifecycle_lock = 'UNLOCKED', updated_at = ?
                        WHERE project_id = ?;
                        """,
                        (now_str, p_id),
                    )
            else:
                # If zip_pid is still genuinely alive, do not interrupt active run
                from .gate import is_pid_alive
                if is_pid_alive(zip_pid):
                    continue

                # Interrupted during local capture: mark FAILED, clean partial, OPEN gate
                if active_b_id:
                    with self.db.transaction() as cur:
                        cur.execute(
                            """
                            UPDATE backup_runs
                            SET status = 'FAILED', error_message = 'Interrupted by service restart or dead ZIP process', finished_at = ?
                            WHERE backup_id = ?;
                            """,
                            (now_str, active_b_id),
                        )
                # Reconcile filesystem if watcher exists
                if p_id in self.watchers:
                    self.watchers[p_id].reconcile_filesystem()

                # Clean any partial zips for this project in staging
                for pz in self.config.staging_dir.glob(f"{p_id}*.partial*"):
                    try:
                        pz.unlink()
                    except OSError:
                        pass

                # Unlock lifecycle and OPEN gate
                with self.db.transaction() as cur:
                    cur.execute(
                        """
                        UPDATE projects_state
                        SET prompt_gate = 'OPEN', zip_pid = NULL, lifecycle_lock = 'UNLOCKED', active_backup_id = NULL, updated_at = ?
                        WHERE project_id = ?;
                        """,
                        (now_str, p_id),
                    )

    def run_cycle_for_project(
        self,
        project_id: str,
        force: bool = False,
        agent_state_override: Optional[AgentState] = None,
        strict_download_verify: bool = False,
    ) -> BackupCycleResult:
        """
        Executes one atomic backup orchestration cycle for a project:
        1. Checks eligibility: dirty > last_good, quiet >= 30m, agent IDLE, lifecycle UNLOCKED.
        2. Acquires project lifecycle lock & closes prompt gate atomically.
        3. Records captured_generation = current dirty_generation.
        4. Creates local ZIP archive while tracking mutation.
        5. Verifies local ZIP (testzip, sha256, md5).
        6. Immediately OPENS prompt gate (coding resumes!).
        7. Uploads archive to remote storage independently.
        8. Verifies remote object (size, MD5, strict SHA256).
        9. On GOOD: sets last_good_generation = captured_generation (NEVER current generation!).
        10. Executes retention transaction (prunes oldest if count > 10).
        11. Releases project lifecycle lock.
        """
        # Invariant: Drain inotify events FIRST so recent writes are never skipped
        watcher = self.watchers.get(project_id)
        if watcher:
            watcher.process_events()

        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT project_id, project_slug, canonical_path, dirty_generation,
                       last_good_generation, prompt_gate, lifecycle_lock, filesystem_state
                FROM projects_state
                WHERE project_id = ?;
                """,
                (project_id,),
            )
            p_row = cur.fetchone()
        finally:
            conn.close()

        if not p_row:
            return BackupCycleResult(project_id=project_id, action_taken="PROJECT_NOT_FOUND")

        project_slug = p_row["project_slug"]
        project_root = Path(p_row["canonical_path"])
        dirty_gen = p_row["dirty_generation"]
        last_good = p_row["last_good_generation"]
        lifecycle_lock = p_row["lifecycle_lock"]
        fs_state = p_row["filesystem_state"]

        # Invariant: Lifecycle lock must be UNLOCKED
        if lifecycle_lock == "LOCKED":
            return BackupCycleResult(
                project_id=project_id,
                action_taken="SKIPPED_LIFECYCLE_LOCKED",
                dirty_generation=dirty_gen,
                last_good_generation=last_good,
            )

        # Invariant: Project must have unbacked changes
        if not force and dirty_gen <= last_good:
            return BackupCycleResult(
                project_id=project_id,
                action_taken="SKIPPED_CLEAN",
                dirty_generation=dirty_gen,
                last_good_generation=last_good,
            )

        # Invariant: Quiet interval >= 30 minutes
        if not force and watcher and not watcher.is_quiet_interval_satisfied(self.config.quiet_interval_seconds):
            return BackupCycleResult(
                project_id=project_id,
                action_taken="SKIPPED_NOT_QUIET",
                dirty_generation=dirty_gen,
                last_good_generation=last_good,
            )

        # Invariant: Agent state must be IDLE (or safe OFFLINE)
        has_in_flight = self.gate_coordinator.has_in_flight_messages(project_id)
        p_meta = self.project_metadata.get(project_id, {})
        runtime_info = p_meta.get("runtime", {})
        tmux_win = runtime_info.get("tmux_window") or p_meta.get("tmux", "")
        windows = [w.strip() for w in tmux_win.split(",") if w.strip()] if isinstance(tmux_win, str) else []
        session = "agy"
        if windows and ":" in windows[0]:
            session = windows[0].split(":")[0]
        project_connections = {
            "tmux": {
                "session": session,
                "windows": windows,
            }
        }
        agent_st = self.agent_evaluator.evaluate_project_agents(
            project_connections=project_connections,
            has_in_flight_messages=has_in_flight,
            mock_override=agent_state_override,
        )
        if not force and not self.agent_evaluator.is_backup_eligible(agent_st, has_in_flight):
            return BackupCycleResult(
                project_id=project_id,
                action_taken="SKIPPED_BUSY",
                dirty_generation=dirty_gen,
                last_good_generation=last_good,
            )

        # Generate unique backup_id
        backup_id = f"b-{project_slug}-{int(self.clock.monotonic())}-{secrets.token_hex(4)}"

        # 1. Acquire project lifecycle lock and close prompt gate atomically
        captured_gen = dirty_gen
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE projects_state
                SET lifecycle_lock = 'LOCKED', active_backup_id = ?, updated_at = ?
                WHERE project_id = ?;
                """,
                (backup_id, now_str, project_id),
            )

        # Re-check callbacks for atomic gate closure
        current_pid = os.getpid()
        gate_closed = self.gate_coordinator.close_gate(
            project_id=project_id,
            zip_pid=current_pid,
            recheck_agent_callback=lambda: self.agent_evaluator.is_backup_eligible(
                self.agent_evaluator.evaluate_project_agents(project_connections, False, mock_override=agent_state_override),
                self.gate_coordinator.has_in_flight_messages(project_id),
            ),
            recheck_generation_callback=lambda: (
                self.db.get_connection().execute(
                    "SELECT dirty_generation FROM projects_state WHERE project_id = ?;", (project_id,)
                ).fetchone()[0]
            ),
            expected_generation=captured_gen,
        )

        if not gate_closed:
            # Rollback lifecycle lock
            with self.db.transaction() as cur:
                cur.execute(
                    """
                    UPDATE projects_state
                    SET lifecycle_lock = 'UNLOCKED', active_backup_id = NULL, updated_at = ?
                    WHERE project_id = ?;
                    """,
                    (now_str, project_id),
                )
            return BackupCycleResult(
                project_id=project_id,
                action_taken="GATE_CLOSURE_REJECTED",
                dirty_generation=dirty_gen,
                last_good_generation=last_good,
            )

        # Resolve project UUID
        project_uuid = self.project_metadata.get(project_id, {}).get("project_uuid")
        if not project_uuid:
            registered = self.config.load_registered_projects()
            for p in registered:
                if p.get("project_id") == project_id:
                    project_uuid = p.get("project_uuid")
                    break
        project_uuid = project_uuid or project_id

        # Dedicated local backup root layout: $BACKUP_ROOT/<ProjectSlug__UUID>/
        if getattr(self.config, "backup_root", None):
            proj_backup_dir = self.config.get_project_backup_dir(project_slug, project_id, project_uuid)
        else:
            proj_backup_dir = self.config.staging_dir

        archive_name = generate_backup_filename(project_slug, self.clock, unique_suffix=backup_id)
        expected_zip_path = proj_backup_dir / archive_name
        with self.db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO backup_runs (
                    backup_id, project_id, project_slug, captured_generation, zip_path, status, zip_pid, created_at
                ) VALUES (?, ?, ?, ?, ?, 'CAPTURING', ?, ?);
                """,
                (backup_id, project_id, project_slug, captured_gen, str(expected_zip_path), current_pid, now_str),
            )

        # 2. Create local ZIP archive while tracking mutations
        mutation_flag = False

        def check_mutation() -> bool:
            nonlocal mutation_flag
            if watcher:
                if watcher.process_events() > 0:
                    mutation_flag = True
            return mutation_flag

        def get_current_gen() -> int:
            conn = self.db.get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT dirty_generation FROM projects_state WHERE project_id = ?;", (project_id,))
                return cur.fetchone()[0]
            finally:
                conn.close()

        def on_capture_complete() -> None:
            # Exact ZIP gate boundary: Gate reopens IMMEDIATELY when source walk/write finishes!
            self.gate_coordinator.open_gate(project_id)

        try:
            zip_res = self.zipper.create_project_zip(
                project_root=project_root,
                archive_name=archive_name,
                zip_start_generation=captured_gen,
                check_mutation_callback=check_mutation,
                get_current_generation_callback=get_current_gen,
                on_capture_complete_callback=on_capture_complete,
                destination_dir=proj_backup_dir,
            )

            # Ensure gate is open if not already opened by callback
            self.gate_coordinator.open_gate(project_id)

            if zip_res.status != "LOCAL_VERIFIED":
                # Mutation or verification failed
                status_val = "INVALIDATED" if zip_res.mutation_seen else "FAILED"
                with self.db.transaction() as cur:
                    cur.execute(
                        """
                        UPDATE backup_runs
                        SET status = ?,
                            mutation_seen = ?,
                            error_message = ?,
                            finished_at = ?
                        WHERE backup_id = ?;
                        """,
                        (status_val, int(zip_res.mutation_seen), zip_res.error, now_str, backup_id),
                    )
                    cur.execute(
                        """
                        UPDATE projects_state
                        SET lifecycle_lock = 'UNLOCKED', active_backup_id = NULL, updated_at = ?
                        WHERE project_id = ?;
                        """,
                        (now_str, project_id),
                    )
                return BackupCycleResult(
                    project_id=project_id,
                    action_taken="MUTATION_ABORTED" if zip_res.mutation_seen else "ZIP_FAILED",
                    backup_id=backup_id,
                    captured_generation=captured_gen,
                    dirty_generation=get_current_gen(),
                    last_good_generation=last_good,
                    error=zip_res.error,
                )
        except Exception as exc:
            self.gate_coordinator.open_gate(project_id)
            with self.db.transaction() as cur:
                cur.execute(
                    """
                    UPDATE backup_runs
                    SET status = 'FAILED', error_message = ?, finished_at = ?
                    WHERE backup_id = ?;
                    """,
                    (str(exc), now_str, backup_id),
                )
                cur.execute(
                    """
                    UPDATE projects_state
                    SET lifecycle_lock = 'UNLOCKED', active_backup_id = NULL, updated_at = ?
                    WHERE project_id = ?;
                    """,
                    (now_str, project_id),
                )
            raise

        # Local ZIP verified! Update backup run state
        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE backup_runs
                SET status = 'LOCAL_VERIFIED',
                    zip_size = ?,
                    zip_sha256 = ?,
                    zip_md5 = ?
                WHERE backup_id = ?;
                """,
                (zip_res.size, zip_res.sha256, zip_res.md5, backup_id),
            )

        # 4. Upload to remote storage independently: <rclone-remote>:IroScript_Project_Backups/<ProjectSlug__UUID>/
        remote_base = self.config.rclone_remote.rstrip("/")
        if not remote_base.startswith("/") and not remote_base.endswith("IroScript_Project_Backups") and "IroScript_Project_Backups" not in remote_base:
            remote_dest_root = f"{remote_base}:IroScript_Project_Backups" if ":" not in remote_base else f"{remote_base}/IroScript_Project_Backups"
        else:
            remote_dest_root = remote_base

        folder_slug_uuid = f"{project_slug}__{project_uuid}" if f"__{project_uuid}" not in project_slug else project_slug
        remote_dest_dir = f"{remote_dest_root}/{folder_slug_uuid}"

        upload_res = self.uploader.upload_and_verify(
            local_archive=zip_res.archive_path,
            remote_dest_dir=remote_dest_dir,
            expected_sha256=zip_res.sha256,
            expected_md5=zip_res.md5,
            strict_download_verify=strict_download_verify,
        )

        fin_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if upload_res.status != "GOOD":
            # Upload failed: gate remains OPEN, retry later from existing ZIP without rebuilding
            with self.db.transaction() as cur:
                cur.execute(
                    """
                    UPDATE backup_runs
                    SET status = 'UPLOAD_PENDING', error_message = ?, finished_at = ?
                    WHERE backup_id = ?;
                    """,
                    (upload_res.error, fin_time, backup_id),
                )
                cur.execute(
                    """
                    UPDATE projects_state
                    SET lifecycle_lock = 'UNLOCKED', active_backup_id = NULL, updated_at = ?
                    WHERE project_id = ?;
                    """,
                    (fin_time, project_id),
                )
            return BackupCycleResult(
                project_id=project_id,
                action_taken="UPLOAD_FAILED",
                backup_id=backup_id,
                captured_generation=captured_gen,
                dirty_generation=get_current_gen(),
                last_good_generation=last_good,
                error=upload_res.error,
            )

        # 5. Remote upload verified GOOD!
        # Critical Section 40 Rule: last_good_generation = captured_generation (NEVER current dirty_gen!)
        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE backup_runs
                SET status = 'GOOD', finished_at = ?
                WHERE backup_id = ?;
                """,
                (fin_time, backup_id),
            )
            cur.execute(
                """
                INSERT INTO verified_backups (
                    backup_id, project_id, project_slug, captured_generation, remote_path,
                    remote_object_id, size, sha256, md5, status, retention_state, created_at, verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'GOOD', 'ACTIVE', ?, ?);
                """,
                (
                    backup_id,
                    project_id,
                    project_slug,
                    captured_gen,
                    upload_res.remote_path,
                    upload_res.remote_object_id,
                    upload_res.remote_size,
                    zip_res.sha256,
                    zip_res.md5,
                    now_str,
                    fin_time,
                ),
            )
            cur.execute(
                """
                UPDATE projects_state
                SET last_good_generation = ?,
                    lifecycle_lock = 'UNLOCKED',
                    active_backup_id = NULL,
                    updated_at = ?
                WHERE project_id = ?;
                """,
                (captured_gen, fin_time, project_id),
            )

        # 6. Retention transaction
        self.retention_manager.process_retention(project_id, self.config.staging_dir)

        current_dirty = get_current_gen()
        return BackupCycleResult(
            project_id=project_id,
            action_taken="BACKUP_COMPLETED",
            backup_id=backup_id,
            captured_generation=captured_gen,
            dirty_generation=current_dirty,
            last_good_generation=captured_gen,
        )

    def retry_pending_uploads(self, strict_download_verify: bool = False) -> List[Dict[str, Any]]:
        """
        Retries failed uploads from existing LOCAL_VERIFIED archives without rebuilding (Section 52).
        Gate remains OPEN during upload retry.
        """
        if os.environ.get("TASK_MODE") == "READ_ONLY":
            raise PermissionError("POLICY_VIOLATION_READ_ONLY: mutating operations forbidden in READ_ONLY mode")
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT backup_id, project_id, project_slug, captured_generation, zip_path, zip_size, zip_sha256, zip_md5
                FROM backup_runs
                WHERE status IN ('LOCAL_VERIFIED', 'FAILED', 'UPLOAD_PENDING') AND zip_size > 0
                ORDER BY created_at ASC;
                """
            )
            candidate_runs = cur.fetchall()
        finally:
            conn.close()

        results = []
        for run in candidate_runs:
            b_id = run["backup_id"]
            p_id = run["project_id"]
            p_slug = run["project_slug"]
            cap_gen = run["captured_generation"]
            z_path = Path(run["zip_path"])

            if not z_path.is_file():
                continue

            # Check if this backup is already recorded as GOOD
            conn = self.db.get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM verified_backups WHERE backup_id = ?;", (b_id,))
                if cur.fetchone()[0] > 0:
                    continue
            finally:
                conn.close()

            # Upload existing immutable zip
            upload_res = self.uploader.upload_and_verify(
                local_archive=z_path,
                remote_dest_dir=f"{self.config.rclone_remote.rstrip('/')}/{p_slug}",
                expected_sha256=run["zip_sha256"],
                expected_md5=run["zip_md5"],
                strict_download_verify=strict_download_verify,
            )

            now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if upload_res.status == "GOOD":
                with self.db.transaction() as cur:
                    cur.execute(
                        "UPDATE backup_runs SET status = 'GOOD', finished_at = ? WHERE backup_id = ?;",
                        (now_str, b_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO verified_backups (
                            backup_id, project_id, project_slug, captured_generation, remote_path,
                            remote_object_id, size, sha256, md5, status, retention_state, created_at, verified_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'GOOD', 'ACTIVE', ?, ?);
                        """,
                        (
                            b_id,
                            p_id,
                            p_slug,
                            cap_gen,
                            upload_res.remote_path,
                            upload_res.remote_object_id,
                            upload_res.remote_size,
                            run["zip_sha256"],
                            run["zip_md5"],
                            now_str,
                            now_str,
                        ),
                    )
                    cur.execute(
                        """
                        UPDATE projects_state
                        SET last_good_generation = MAX(last_good_generation, ?), updated_at = ?
                        WHERE project_id = ?;
                        """,
                        (cap_gen, now_str, p_id),
                    )
                self.retention_manager.process_retention(p_id, self.config.staging_dir)
                results.append({"backup_id": b_id, "status": "GOOD"})
            else:
                results.append({"backup_id": b_id, "status": "RETRY_FAILED", "error": upload_res.error})

        return results

    def get_health_report(self, target_project_id: Optional[str] = None) -> Dict[str, Any]:
        """Provides overall health and status report across all projects with full observability."""
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT project_id, project_slug, canonical_path, dirty_generation,
                       last_good_generation, prompt_gate, zip_pid, lifecycle_lock, filesystem_state, updated_at
                FROM projects_state;
                """
            )
            raw_projects = [dict(r) for r in cur.fetchall()]

            enriched_projects = []
            for p in raw_projects:
                p_id = p["project_id"]
                gate_raw = (p.get("prompt_gate") or "OPEN").upper()
                zip_pid = p.get("zip_pid")
                from .gate import is_pid_alive
                zip_running = is_pid_alive(zip_pid) if zip_pid else False
                zip_gate = "ZIP_GATE_CLOSED" if gate_raw in ("CLOSED", "ZIP_GATE_CLOSED") and zip_running else "ZIP_GATE_OPEN"

                cur.execute(
                    """
                    SELECT status, error_message, created_at, finished_at
                    FROM backup_runs
                    WHERE project_id = ?
                    ORDER BY created_at DESC LIMIT 1;
                    """,
                    (p_id,),
                )
                run_row = cur.fetchone()
                backup_state = run_row["status"] if run_row else "IDLE"
                last_error = run_row["error_message"] if run_row else None

                cur.execute(
                    """
                    SELECT verified_at FROM verified_backups
                    WHERE project_id = ? AND status = 'GOOD' AND retention_state = 'ACTIVE'
                    ORDER BY verified_at DESC LIMIT 1;
                    """,
                    (p_id,),
                )
                vg_row = cur.fetchone()
                last_good = vg_row["verified_at"] if vg_row else None

                cur.execute(
                    """
                    SELECT COUNT(*) FROM verified_backups
                    WHERE project_id = ? AND status = 'GOOD' AND retention_state = 'ACTIVE';
                    """,
                    (p_id,),
                )
                remote_good_count = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT zip_path FROM backup_runs
                    WHERE project_id = ? AND (status IN ('GOOD', 'LOCAL_VERIFIED')) AND zip_path IS NOT NULL;
                    """,
                    (p_id,),
                )
                local_good_count = sum(1 for r in cur.fetchall() if r["zip_path"] and Path(r["zip_path"]).is_file())

                cur.execute(
                    """
                    SELECT COUNT(*) FROM held_prompt_queue
                    WHERE project_id = ? AND status = 'HELD';
                    """,
                    (p_id,),
                )
                held_count = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*) FROM held_prompt_queue
                    WHERE project_id = ? AND status IN ('RETRYING', 'DISPATCHING');
                    """,
                    (p_id,),
                )
                retry_count = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT updated_at FROM held_prompt_queue
                    WHERE project_id = ? AND status = 'DELIVERED'
                    ORDER BY updated_at DESC LIMIT 1;
                    """,
                    (p_id,),
                )
                del_row = cur.fetchone()
                last_delivery = del_row["updated_at"] if del_row else None

                meta = self.project_metadata.get(p_id, {})
                target_terminal = meta.get("runtime", {}).get("tmux_window") or meta.get("connections", {}).get("whatsapp", {}).get("agent_route") or "agy:0"

                wa_auth_dir = Path(os.environ.get("HOME") or "/root") / ".webterminal" / "wa_auth"
                wa_conn = "CONNECTED" if wa_auth_dir.is_dir() else "UNKNOWN"

                proj_record = {
                    **p,
                    "PROJECT": p_id,
                    "ZIP_GATE": zip_gate,
                    "ZIP_RUNNING": zip_running,
                    "ZIP_PID": zip_pid,
                    "BACKUP_STATE": backup_state,
                    "LAST_GOOD": last_good,
                    "LOCAL_GOOD_COUNT": local_good_count,
                    "REMOTE_GOOD_COUNT": remote_good_count,
                    "HELD_FOR_ZIP_MESSAGES": held_count,
                    "DELIVERY_RETRY_MESSAGES": retry_count,
                    "WHATSAPP_CONNECTION": wa_conn,
                    "TARGET_TERMINAL": target_terminal,
                    "LAST_DELIVERY": last_delivery,
                    "LAST_ERROR": last_error,
                }
                enriched_projects.append(proj_record)

            cur.execute("SELECT COUNT(*) FROM held_prompt_queue WHERE status = 'HELD';")
            total_held = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM verified_backups WHERE status = 'GOOD' AND retention_state = 'ACTIVE';")
            total_good = cur.fetchone()[0]
        finally:
            conn.close()

        primary = None
        if target_project_id:
            for ep in enriched_projects:
                if ep["PROJECT"] == target_project_id or ep.get("project_slug") == target_project_id:
                    primary = ep
                    break
        if not primary and enriched_projects:
            primary = enriched_projects[0]
        if not primary:
            primary = {
                "PROJECT": "none",
                "ZIP_GATE": "ZIP_GATE_OPEN",
                "ZIP_RUNNING": False,
                "ZIP_PID": None,
                "BACKUP_STATE": "IDLE",
                "LAST_GOOD": None,
                "LOCAL_GOOD_COUNT": 0,
                "REMOTE_GOOD_COUNT": 0,
                "HELD_FOR_ZIP_MESSAGES": 0,
                "DELIVERY_RETRY_MESSAGES": 0,
                "WHATSAPP_CONNECTION": "UNKNOWN",
                "TARGET_TERMINAL": "agy:0",
                "LAST_DELIVERY": None,
                "LAST_ERROR": None,
            }

        rclone_audit = self.uploader.audit_rclone_client_id(self.config.rclone_remote)

        return {
            "status": "HEALTHY",
            "db_path": str(self.config.db_path),
            "projects_count": len(enriched_projects),
            "PROJECT": primary.get("PROJECT"),
            "ZIP_GATE": primary.get("ZIP_GATE"),
            "ZIP_RUNNING": primary.get("ZIP_RUNNING"),
            "ZIP_PID": primary.get("ZIP_PID"),
            "BACKUP_STATE": primary.get("BACKUP_STATE"),
            "LAST_GOOD": primary.get("LAST_GOOD"),
            "LOCAL_GOOD_COUNT": primary.get("LOCAL_GOOD_COUNT"),
            "REMOTE_GOOD_COUNT": primary.get("REMOTE_GOOD_COUNT"),
            "HELD_FOR_ZIP_MESSAGES": primary.get("HELD_FOR_ZIP_MESSAGES"),
            "DELIVERY_RETRY_MESSAGES": primary.get("DELIVERY_RETRY_MESSAGES"),
            "WHATSAPP_CONNECTION": primary.get("WHATSAPP_CONNECTION"),
            "TARGET_TERMINAL": primary.get("TARGET_TERMINAL"),
            "LAST_DELIVERY": primary.get("LAST_DELIVERY"),
            "LAST_ERROR": primary.get("LAST_ERROR"),
            "projects": enriched_projects,
            "held_prompts_count": total_held,
            "verified_goods_count": total_good,
            "rclone_client_id_audit": rclone_audit,
            "staging_dir": str(self.config.staging_dir),
        }

    def drain_pending_prompts(self) -> int:
        """
        Deprecated. SOT is ZIP gate owner only; terminal transport delivery belongs
        exclusively to WhatsApp Bridge.
        If an in-memory dispatch handler is explicitly registered (e.g. in test suites),
        drains held prompts to that handler; otherwise zero terminal injection is performed.
        """
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT project_id FROM held_prompt_queue
                WHERE status = 'HELD' OR (status = 'DISPATCHING' AND (delivery_owner_instance_id IS NULL OR delivery_owner_instance_id = ''));
                """
            )
            held_projects = [r["project_id"] for r in cur.fetchall()]
        finally:
            conn.close()

        delivered_total = 0
        for project_id in held_projects:
            gate_state = self.gate_coordinator.get_gate_state(project_id)
            if gate_state.get("prompt_gate") != "OPEN":
                continue

            handler = self.gate_coordinator._dispatch_handlers.get(project_id)
            if not handler:
                continue

            while True:
                item = self.gate_coordinator.claim_next_held_prompt(
                    project_id, self.delivery_owner_instance_id
                )
                if not item:
                    break

                try:
                    delivered = handler(item)
                    if delivered:
                        self.gate_coordinator.complete_delivery(
                            item["message_id"], self.delivery_owner_instance_id
                        )
                        delivered_total += 1
                    else:
                        self.gate_coordinator.fail_delivery(
                            item["message_id"], self.delivery_owner_instance_id, retryable=True
                        )
                        break
                except Exception:
                    self.gate_coordinator.fail_delivery(
                        item["message_id"], self.delivery_owner_instance_id, retryable=True
                    )
                    break

        return delivered_total

    def run_daemon(self, interval_seconds: int = 30, stop_event: Optional[Any] = None) -> None:
        """
        Continuous unattended daemon execution loop (Section 58):
        - Evaluates all registered projects periodically
        - Runs backup cycles for eligible projects
        - Retries failed uploads
        - Handles termination signals gracefully
        """
        # If in-memory dispatch handlers were registered (e.g. in test fixtures), drain them
        self.drain_pending_prompts()

        last_cycle_time = 0.0
        try:
            while not (stop_event and stop_event.is_set()):
                now = time.monotonic()
                if now - last_cycle_time >= interval_seconds:
                    for project_id in list(self.watchers.keys()):
                        try:
                            self.run_cycle_for_project(project_id)
                        except Exception:
                            pass
                    try:
                        self.retry_pending_uploads()
                    except Exception:
                        pass
                    last_cycle_time = now

                sleep_chunk = min(0.2, interval_seconds)
                if stop_event:
                    if stop_event.wait(timeout=sleep_chunk):
                        break
                else:
                    time.sleep(sleep_chunk)
        finally:
            pass
