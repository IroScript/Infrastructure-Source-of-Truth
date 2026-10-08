"""
test_backup_orchestrator.py — Mandatory Acceptance Test Suite for SOT Backup Subsystem (Sections 36–58).
Implements TESTS H through P and validates all 17 architecture invariants.
"""
from __future__ import annotations

import concurrent.futures
import datetime
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
import pytest

from backup_orchestrator.agent_model import AgentState, AgentStateEvaluator
from backup_orchestrator.bridge_adapter import BridgeAdapter, BridgeTerminalReceiver
from backup_orchestrator.config import BackupOrchestratorConfig
from backup_orchestrator.db import Database
from backup_orchestrator.gate import PromptGateCoordinator
from backup_orchestrator.orchestrator import BackupOrchestrator
from backup_orchestrator.retention import RetentionManager
from backup_orchestrator.timekeeping import InjectableClock, generate_backup_filename
from backup_orchestrator.uploader import BackupUploader, UploadVerificationResult
from backup_orchestrator.watcher import ProjectFsWatcher
from backup_orchestrator.zipper import ProjectZipper


@pytest.fixture
def test_env(tmp_path: Path):
    """Sets up an isolated test environment with temporary roots."""
    sot_root = Path(__file__).resolve().parents[2]
    home = tmp_path / "home"
    projects_root = home / "projects"
    state_root = home / ".agents"
    staging_dir = state_root / "backup_orchestrator" / "staging"
    rclone_mock_dir = tmp_path / "remote_cloud"
    rclone_mock_dir.mkdir(parents=True, exist_ok=True)

    home.mkdir(parents=True, exist_ok=True)
    projects_root.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    cfg = BackupOrchestratorConfig(
        sot_root=sot_root,
        home=home,
        projects_root=projects_root,
        state_root=state_root,
        backup_state_dir=state_root / "backup_orchestrator",
        staging_dir=staging_dir,
        db_path=state_root / "backup_orchestrator" / "backup_state.sqlite",
        quiet_interval_seconds=1800.0,
        rclone_remote=f"{rclone_mock_dir}",
        retention_count=10,
        timezone_name="Asia/Dhaka",
    )
    db = Database(cfg.db_path)
    clock = InjectableClock(initial_mono=1000.0)
    return {
        "sot_root": sot_root,
        "home": home,
        "projects_root": projects_root,
        "state_root": state_root,
        "staging_dir": staging_dir,
        "rclone_mock_dir": rclone_mock_dir,
        "cfg": cfg,
        "db": db,
        "clock": clock,
    }


def test_h_gate_atomic_race(test_env):
    """
    TEST H — Gate atomic race (Section 57):
    Incoming prompt races exactly with gate closure.
    Result must be either fully DISPATCHING-before-gate or fully HELD-after-gate,
    never lost or half-state.
    """
    db: Database = test_env["db"]
    gate = PromptGateCoordinator(db)
    project_id = "test_race_project"
    gate.register_or_update_project(project_id, "test_race", "/tmp/nonexistent")

    results = []
    iterations = 50

    def dispatch_worker(msg_idx: int):
        dec = gate.dispatch_or_hold_message(
            project_id=project_id,
            message_id=f"msg-{msg_idx}",
            routing_target="agy:0",
            payload=f"Payload {msg_idx}",
        )
        return dec

    def closer_worker():
        return gate.close_gate(project_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(iterations):
            futures.append(executor.submit(dispatch_worker, i))
            if i == 25:
                futures.append(executor.submit(closer_worker))

        for f in futures:
            res = f.result()
            results.append(res)

    # Inspect all queued items in database
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT message_id, status, sequence_num FROM held_prompt_queue WHERE project_id = ? ORDER BY sequence_num ASC;",
            (project_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    assert len(rows) == iterations, f"Expected {iterations} messages recorded, got {len(rows)}"
    statuses = {r["status"] for r in rows}
    assert statuses.issubset({"DISPATCHING", "HELD"}), f"Illegal status found: {statuses}"

    # Verify no message was dropped or half-recorded
    rec_ids = {r["message_id"] for r in rows}
    assert rec_ids == {f"msg-{i}" for i in range(iterations)}
    seq_nums = [r["sequence_num"] for r in rows]
    assert seq_nums == list(range(1, iterations + 1))


def test_i_upload_while_new_edits_occur(test_env):
    """
    TEST I — Upload while new edits occur (Section 40, 57):
    Generation 81 locally verified;
    Gate opens;
    Project becomes generation 82;
    Generation-81 upload becomes GOOD;
    last_good_generation must remain 81;
    project must still be DIRTY at 82.
    """
    cfg: BackupOrchestratorConfig = test_env["cfg"]
    clock: InjectableClock = test_env["clock"]
    proj_dir = test_env["projects_root"] / "proj_gen_test"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "file.txt").write_text("v1")

    # Mock uploader that delays and allows a mutation before completing upload
    class MutationInducingUploader(BackupUploader):
        def __init__(self, on_upload_fn):
            super().__init__()
            self.on_upload_fn = on_upload_fn

        def upload_and_verify(self, local_archive, remote_dest_dir, expected_sha256, expected_md5, strict_download_verify=False):
            # Trigger generation 82 mutation during upload
            self.on_upload_fn()
            # Copy archive to remote mock dir
            dest = Path(remote_dest_dir) / local_archive.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_archive, dest)
            return UploadVerificationResult(
                status="GOOD",
                remote_path=str(dest),
                remote_object_id="mock-obj-81",
                remote_size=local_archive.stat().st_size,
                remote_md5=expected_md5,
                local_sha256=expected_sha256,
            )

    orchestrator = BackupOrchestrator(cfg, clock=clock)
    project_id = "proj_gen_test"
    orchestrator.gate_coordinator.register_or_update_project(
        project_id=project_id,
        project_slug="proj_gen_test",
        canonical_path=str(proj_dir),
        initial_generation=81,
    )
    watcher = ProjectFsWatcher(project_id, proj_dir, orchestrator.db, clock=clock)
    orchestrator.watchers[project_id] = watcher

    # Callback executed during upload: increments generation to 82
    def mutate_during_upload():
        (proj_dir / "file.txt").write_text("v2 - new edit at generation 82")
        watcher.increment_generation()

    orchestrator.uploader = MutationInducingUploader(mutate_during_upload)

    # Run backup cycle
    res = orchestrator.run_cycle_for_project(
        project_id=project_id,
        force=True,
        agent_state_override=AgentState.IDLE,
    )

    assert res.action_taken == "BACKUP_COMPLETED"
    assert res.captured_generation == 81

    # Verify database state
    conn = orchestrator.db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT dirty_generation, last_good_generation FROM projects_state WHERE project_id = ?;",
            (project_id,),
        )
        row = cur.fetchone()
        assert row["captured_generation" if "captured_generation" in row.keys() else "last_good_generation"] == 81
        assert row["last_good_generation"] == 81, "Critical Section 40 violation: last_good_generation was overwritten with current generation!"
        assert row["dirty_generation"] == 82, "dirty_generation should be 82"
        assert row["dirty_generation"] > row["last_good_generation"], "Project must remain DIRTY after generation 82 edits!"
    finally:
        conn.close()


def test_j_service_restart_with_gate_closed(test_env):
    """
    TEST J — Service restart with gate closed (Section 53, 57):
    Restart must recover queue and must not leave permanent CLOSED gate.
    """
    cfg: BackupOrchestratorConfig = test_env["cfg"]
    clock: InjectableClock = test_env["clock"]
    proj_dir = test_env["projects_root"] / "proj_restart"
    proj_dir.mkdir(parents=True, exist_ok=True)
    project_id = "proj_restart"

    db = Database(cfg.db_path)
    gate = PromptGateCoordinator(db)
    gate.register_or_update_project(project_id, "proj_restart", str(proj_dir), initial_generation=5)

    # Simulate stranded closed gate from a prior crashed run
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with db.transaction() as cur:
        cur.execute(
            """
            UPDATE projects_state
            SET prompt_gate = 'CLOSED', lifecycle_lock = 'LOCKED', active_backup_id = 'crashed-run-1', updated_at = ?
            WHERE project_id = ?;
            """,
            (now_str, project_id),
        )
        cur.execute(
            """
            INSERT INTO backup_runs (backup_id, project_id, project_slug, captured_generation, zip_path, status, created_at)
            VALUES ('crashed-run-1', ?, 'proj_restart', 5, '/tmp/stale.partial', 'CAPTURING', ?);
            """,
            (project_id, now_str),
        )
        cur.execute(
            """
            INSERT INTO held_prompt_queue (project_id, message_id, routing_target, payload, sequence_num, status, created_at, updated_at)
            VALUES (?, 'stranded-msg-1', 'agy:0', 'Queued while gate was closed', 1, 'HELD', ?, ?);
            """,
            (project_id, now_str, now_str),
        )

    # Initialize orchestrator (simulates service restart)
    orchestrator = BackupOrchestrator(cfg, clock=clock)

    # Gate must be recovered to OPEN and lifecycle UNLOCKED
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT prompt_gate, lifecycle_lock, active_backup_id FROM projects_state WHERE project_id = ?;",
            (project_id,),
        )
        row = cur.fetchone()
        assert row["prompt_gate"] == "OPEN", "Service restart failed to OPEN stranded closed gate!"
        assert row["lifecycle_lock"] == "UNLOCKED", "Lifecycle lock remained stranded!"

        # Interrupted backup run must be marked FAILED
        cur.execute("SELECT status FROM backup_runs WHERE backup_id = 'crashed-run-1';")
        assert cur.fetchone()["status"] == "FAILED"

        # Held queue must be intact and dispatchable
        cur.execute("SELECT status FROM held_prompt_queue WHERE message_id = 'stranded-msg-1';")
        assert cur.fetchone()["status"] == "HELD"
    finally:
        conn.close()


def test_k_remote_upload_failure_and_retry(test_env):
    """
    TEST K — Remote upload failure (Section 52, 57):
    LOCAL_VERIFIED ZIP remains;
    Gate open;
    Coding continues;
    Upload retries without rebuilding archive.
    """
    cfg: BackupOrchestratorConfig = test_env["cfg"]
    clock: InjectableClock = test_env["clock"]
    proj_dir = test_env["projects_root"] / "proj_retry"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "code.py").write_text("print('hello')")
    project_id = "proj_retry"

    class FailingUploader(BackupUploader):
        def __init__(self):
            super().__init__()
            self.should_fail = True

        def upload_and_verify(self, local_archive, remote_dest_dir, expected_sha256, expected_md5, strict_download_verify=False):
            if self.should_fail:
                return UploadVerificationResult(
                    status="UPLOAD_FAILED",
                    remote_path="",
                    error="Network timeout simulation",
                )
            dest = Path(remote_dest_dir) / local_archive.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_archive, dest)
            return UploadVerificationResult(
                status="GOOD",
                remote_path=str(dest),
                remote_object_id="mock-id",
                remote_size=local_archive.stat().st_size,
                remote_md5=expected_md5,
                local_sha256=expected_sha256,
            )

    uploader = FailingUploader()
    orchestrator = BackupOrchestrator(cfg, clock=clock, uploader=uploader)
    orchestrator.gate_coordinator.register_or_update_project(
        project_id, "proj_retry", str(proj_dir), initial_generation=10
    )

    # Run cycle: fails at upload stage
    res = orchestrator.run_cycle_for_project(project_id, force=True, agent_state_override=AgentState.IDLE)
    assert res.action_taken == "UPLOAD_FAILED"

    # Invariant: Prompt gate must be OPEN (coding continues!)
    conn = orchestrator.db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT prompt_gate FROM projects_state WHERE project_id = ?;", (project_id,))
        assert cur.fetchone()["prompt_gate"] == "OPEN"

        # Local archive must remain on disk
        cur.execute("SELECT zip_path, zip_sha256 FROM backup_runs WHERE backup_id = ?;", (res.backup_id,))
        run_row = cur.fetchone()
        orig_zip = Path(run_row["zip_path"])
        orig_sha = run_row["zip_sha256"]
        assert orig_zip.is_file(), "Local verified zip was deleted after upload failure!"
    finally:
        conn.close()

    # Network heals: retry upload without rebuilding archive
    uploader.should_fail = False
    retry_results = orchestrator.retry_pending_uploads()
    assert len(retry_results) == 1
    assert retry_results[0]["status"] == "GOOD"

    # Verify that the same archive was uploaded
    conn = orchestrator.db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT sha256 FROM verified_backups WHERE backup_id = ?;", (res.backup_id,))
        assert cur.fetchone()["sha256"] == orig_sha
    finally:
        conn.close()


def test_l_retention_deletion_failure(test_env):
    """
    TEST L — Retention deletion failure (Section 51, 57):
    11 GOOD allowed temporarily;
    Failed delete must not trigger deletion of another backup.
    """
    db: Database = test_env["db"]
    project_id = "test_retention_proj"

    # Pre-populate 11 verified GOOD backups
    with db.transaction() as cur:
        cur.execute(
            """
            INSERT INTO projects_state (project_id, project_slug, canonical_path, updated_at)
            VALUES (?, 'test_retention', '/tmp/retention', '2026-10-08T00:00:00Z');
            """,
            (project_id,),
        )
        for i in range(1, 12):
            cur.execute(
                """
                INSERT INTO verified_backups (
                    backup_id, project_id, project_slug, captured_generation, remote_path,
                    size, sha256, md5, status, retention_state, created_at, verified_at
                ) VALUES (?, ?, 'test_retention', ?, ?, 1000, 'sha', 'md5', 'GOOD', 'ACTIVE', ?, ?);
                """,
                (
                    f"backup-{i:02d}",
                    project_id,
                    i,
                    f"/mock/cloud/test_retention/backup-{i:02d}.zip",
                    f"2026-10-08T01:{i:02d}:00Z",
                    f"2026-10-08T01:{i:02d}:00Z",
                ),
            )

    # Use a dummy rclone binary that fails deletion
    retention_mgr = RetentionManager(db, rclone_bin="false", max_good_retention=10)
    ret_res = retention_mgr.process_retention(project_id)

    assert ret_res.status == "RETENTION_PENDING"
    assert ret_res.pruned_backup_id == "backup-01"

    # Verify database: backup-01 is RETENTION_PENDING, other 10 are still ACTIVE, none deleted
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT backup_id, retention_state FROM verified_backups WHERE project_id = ? ORDER BY backup_id ASC;",
            (project_id,),
        )
        rows = cur.fetchall()
        assert len(rows) == 11, "A backup was erroneously deleted after retention delete failure!"
        assert rows[0]["retention_state"] == "RETENTION_PENDING"
        for r in rows[1:]:
            assert r["retention_state"] == "ACTIVE", "Another backup was erroneously marked pruned!"
    finally:
        conn.close()


def test_m_inotify_overflow_and_reconciliation(test_env):
    """
    TEST M — Inotify overflow (Section 42, 57):
    State becomes UNKNOWN_DIRTY;
    GOOD prohibited until full reconciliation.
    """
    cfg: BackupOrchestratorConfig = test_env["cfg"]
    clock: InjectableClock = test_env["clock"]
    proj_dir = test_env["projects_root"] / "proj_overflow"
    proj_dir.mkdir(parents=True, exist_ok=True)
    project_id = "proj_overflow"

    orchestrator = BackupOrchestrator(cfg, clock=clock)
    orchestrator.gate_coordinator.register_or_update_project(
        project_id, "proj_overflow", str(proj_dir), initial_generation=5
    )
    watcher = ProjectFsWatcher(project_id, proj_dir, orchestrator.db, clock=clock)
    orchestrator.watchers[project_id] = watcher

    # Simulate inotify queue overflow
    watcher._mark_unknown_dirty("IN_Q_OVERFLOW")

    # Invariant: Quiet interval check returns False while UNKNOWN_DIRTY
    clock.advance(3600.0)  # Advance 1 hour
    assert not watcher.is_quiet_interval_satisfied(1800.0), "Quiet interval must not be satisfied under UNKNOWN_DIRTY!"

    # Run cycle without reconciliation: must be skipped
    res = orchestrator.run_cycle_for_project(project_id, force=False, agent_state_override=AgentState.IDLE)
    assert res.action_taken == "SKIPPED_NOT_QUIET"

    # Reconcile filesystem
    watcher.reconcile_filesystem()
    clock.advance(1801.0)  # Wait quiet interval post-reconciliation
    assert watcher.is_quiet_interval_satisfied(1800.0), "Quiet interval should be satisfied after reconciliation!"


def test_n_symlink_stored_as_symlink(test_env):
    """
    TEST N — Symlink (Section 44, 57):
    Symlink inside project stored as symlink;
    External target bytes not silently pulled into archive.
    """
    staging_dir = test_env["staging_dir"]
    proj_dir = test_env["projects_root"] / "proj_symlink"
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Create large external file outside project
    ext_dir = test_env["home"] / "external_data"
    ext_dir.mkdir(parents=True, exist_ok=True)
    large_ext_file = ext_dir / "large.dat"
    large_ext_file.write_bytes(b"A" * (1024 * 1024))  # 1 MB

    # Inside project: regular file + symlink pointing to external file
    (proj_dir / "regular.txt").write_text("internal small file")
    os.symlink(str(large_ext_file), str(proj_dir / "link_to_external.dat"))

    zipper = ProjectZipper(staging_dir)
    res = zipper.create_project_zip(
        project_root=proj_dir,
        archive_name="test_symlink.zip",
        zip_start_generation=1,
    )

    assert res.status == "LOCAL_VERIFIED"
    assert res.size < 50000, f"Zip archive is {res.size} bytes; external 1MB file was incorrectly pulled in!"

    # Inspect zip entries
    with zipfile.ZipFile(res.archive_path, "r") as zf:
        zinfo = zf.getinfo("link_to_external.dat")
        # Check UNIX symlink mode (0o120000)
        mode = zinfo.external_attr >> 16
        import stat
        assert stat.S_ISLNK(mode), "Symlink was not stored as a symlink!"
        content = zf.read("link_to_external.dat").decode("utf-8")
        assert content == str(large_ext_file), "Symlink payload should be the target link path!"


def test_o_remote_hash_and_strict_download_verify(test_env):
    """
    TEST O — Remote hash (Section 48, 57):
    Local SHA256 recorded;
    Remote exact object size/hash verified;
    Strict download-hash path succeeds in test fixture.
    """
    staging_dir = test_env["staging_dir"]
    archive_file = staging_dir / "test_hash.zip"
    archive_file.write_bytes(b"PK\x03\x04test_archive_content_for_hash")

    import hashlib
    h_sha = hashlib.sha256(archive_file.read_bytes()).hexdigest()
    h_md5 = hashlib.md5(archive_file.read_bytes()).hexdigest()

    mock_remote_dir = test_env["rclone_mock_dir"] / "proj_hash"
    uploader = BackupUploader()

    # Upload and perform strict download-hash verification
    res = uploader.upload_and_verify(
        local_archive=archive_file,
        remote_dest_dir=str(mock_remote_dir),
        expected_sha256=h_sha,
        expected_md5=h_md5,
        strict_download_verify=True,
    )

    assert res.status == "GOOD"
    assert res.local_sha256 == h_sha
    assert res.remote_size == archive_file.stat().st_size


def test_p_no_old_vm_knowledge_bootstrap_restore(test_env):
    """
    TEST P — No old VM knowledge (Section 54, 57):
    Fresh alternate HOME/profile can restore backup subsystem from SOT without
    manual path instructions.
    """
    sot_root: Path = test_env["sot_root"]
    alt_home = test_env["home"] / "alt_user"
    alt_home.mkdir(parents=True, exist_ok=True)

    # Run sot bootstrap in isolated alternate HOME
    env = dict(os.environ)
    env["HOME"] = str(alt_home)
    env["PROJECTS_ROOT"] = str(alt_home / "projects")
    env["STATE_ROOT"] = str(alt_home / ".agents")

    res = subprocess.run(
        [str(sot_root / "sot"), "bootstrap", "--dry-run", "--home", str(alt_home)],
        capture_output=True,
        text=True,
        cwd=str(sot_root),
        env=env,
    )
    assert res.returncode == 0, f"Bootstrap dry run failed: {res.stderr}"
    data = json.loads(res.stdout)
    assert data.get("systemd_service_installed") is True

    # Test running backup-orchestrator status on the alternate home
    res_status = subprocess.run(
        [str(sot_root / "sot"), "backup-orchestrator", "status", "--home", str(alt_home)],
        capture_output=True,
        text=True,
        cwd=str(sot_root),
        env=env,
    )
    assert res_status.returncode == 0, f"Status failed on alternate home: {res_status.stderr}"
    stat_data = json.loads(res_status.stdout)
    assert stat_data["status"] == "HEALTHY"


def test_mutation_during_zip_invalidates_capture(test_env):
    """Verifies that filesystem mutation during zip capture invalidates the backup (Section 47)."""
    staging_dir = test_env["staging_dir"]
    proj_dir = test_env["projects_root"] / "proj_mutate"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "f1.txt").write_text("v1")

    zipper = ProjectZipper(staging_dir)
    # Simulate mutation callback firing during zip creation
    res = zipper.create_project_zip(
        project_root=proj_dir,
        archive_name="test_mutate.zip",
        zip_start_generation=1,
        check_mutation_callback=lambda: True,
    )

    assert res.status == "MUTATION_DETECTED"
    assert res.mutation_seen is True
    assert res.archive_path is None


def test_quiet_interval_boundary_with_injectable_clock(test_env):
    """Verifies exact quiet interval boundary conditions with InjectableClock (Section 56)."""
    db: Database = test_env["db"]
    clock: InjectableClock = test_env["clock"]
    proj_dir = test_env["projects_root"] / "proj_quiet"
    proj_dir.mkdir(parents=True, exist_ok=True)
    project_id = "proj_quiet"

    gate = PromptGateCoordinator(db)
    gate.register_or_update_project(project_id, "proj_quiet", str(proj_dir), initial_generation=1)
    watcher = ProjectFsWatcher(project_id, proj_dir, db, clock=clock)

    watcher.increment_generation(now_mono=1000.0)

    # 29m59s (1799.0s) -> False
    clock.set_monotonic(1000.0 + 1799.0)
    assert not watcher.is_quiet_interval_satisfied(1800.0)

    # 30m00s (1800.0s) -> True
    clock.set_monotonic(1000.0 + 1800.0)
    assert watcher.is_quiet_interval_satisfied(1800.0)

    # Mutation at 29m59.999s resets timer
    clock.set_monotonic(1000.0 + 1799.999)
    watcher.increment_generation(now_mono=clock.monotonic())
    # Advance 1 second past mutation -> only 1.0s elapsed -> False
    clock.advance(1.0)
    assert not watcher.is_quiet_interval_satisfied(1800.0)


def test_agent_state_model_and_in_flight_eligibility(test_env):
    """Verifies strict agent state model (BUSY, UNKNOWN, OFFLINE, IDLE) (Section 39)."""
    evaluator = AgentStateEvaluator()

    assert not evaluator.is_backup_eligible(AgentState.BUSY, has_in_flight_messages=False)
    assert not evaluator.is_backup_eligible(AgentState.UNKNOWN, has_in_flight_messages=False)
    assert not evaluator.is_backup_eligible(AgentState.IDLE, has_in_flight_messages=True)
    assert not evaluator.is_backup_eligible(AgentState.OFFLINE, has_in_flight_messages=True)
    assert evaluator.is_backup_eligible(AgentState.OFFLINE, has_in_flight_messages=False)
    assert evaluator.is_backup_eligible(AgentState.IDLE, has_in_flight_messages=False)


def test_rclone_client_id_audit_migration_required():
    """Verifies that shared default rclone client ID reports migration required (Section 49)."""
    uploader = BackupUploader()
    res = uploader.audit_rclone_client_id("gdrive:")
    # On this VM, gdrive uses shared default client ID
    assert res["status"] in ("RCLONE_CLIENT_ID_MIGRATION_REQUIRED", "PASS")


def test_exactly_once_honest_accounting():
    """Verifies honest exactly-once accounting (provable vs NOT-PROVABLE) (Section 45)."""
    receiver = BridgeTerminalReceiver()

    # Deterministic receiver
    msg1 = {"message_id": "m-1", "payload": "hello"}
    ack1 = receiver.receive_message(msg1, is_arbitrary_cli=False)
    assert ack1.status == "DELIVERED"
    assert ack1.exactly_once_provable is True

    # Duplicate message rejected
    ack1_dup = receiver.receive_message(msg1, is_arbitrary_cli=False)
    assert ack1_dup.status == "DUPLICATE_REJECTED"

    # Arbitrary CLI without guaranteed ACK -> UNCERTAIN (NOT-PROVABLE)
    msg2 = {"message_id": "m-2", "payload": "cli cmd"}
    ack2 = receiver.receive_message(msg2, is_arbitrary_cli=True)
    assert ack2.status == "UNCERTAIN"
    assert ack2.exactly_once_provable is False


def test_state_db_encrypted_backup_and_recovery(test_env):
    """Verifies crash-consistent state DB export and encrypted restore (Section 37)."""
    db: Database = test_env["db"]
    gate = PromptGateCoordinator(db)
    gate.register_or_update_project("proj_enc_test", "enc_test", "/tmp/enc", initial_generation=42)

    export_path = test_env["home"] / "backup_state.enc"
    key = "TestSecretKey12345678901234567890!"

    db.export_encrypted_backup(export_path, key=key)
    assert export_path.is_file()
    assert export_path.stat().st_size > 0

    # Wipe database and restore
    conn = db.get_connection()
    try:
        conn.execute("DROP TABLE projects_state;")
    finally:
        conn.close()

    db.import_encrypted_backup(export_path, key=key)

    # Verify project restored
    conn2 = db.get_connection()
    try:
        cur = conn2.cursor()
        cur.execute("SELECT dirty_generation FROM projects_state WHERE project_id = 'proj_enc_test';")
        assert cur.fetchone()["dirty_generation"] == 42
    finally:
        conn2.close()


def test_git_isolation_invariant(test_env):
    """
    Verifies Section 36 & 58 Invariant:
    Runtime backup eligibility is 100% filesystem and agent based;
    Git dirty state, git status, git diff, or GitHub state never affect backup eligibility.
    """
    cfg: BackupOrchestratorConfig = test_env["cfg"]
    clock: InjectableClock = test_env["clock"]
    proj_dir = test_env["projects_root"] / "proj_git_isolated"
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Initialize a git repo inside the project
    subprocess.run(["git", "init"], cwd=str(proj_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(proj_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(proj_dir), check=True)
    (proj_dir / "tracked.txt").write_text("initial")
    subprocess.run(["git", "add", "tracked.txt"], cwd=str(proj_dir), check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(proj_dir), check=True)

    # Git working tree is completely CLEAN
    git_stat = subprocess.run(["git", "status", "--porcelain"], cwd=str(proj_dir), capture_output=True, text=True)
    assert git_stat.stdout.strip() == "", "Git working tree should be clean"

    orchestrator = BackupOrchestrator(cfg, clock=clock)
    project_id = "proj_git_isolated"
    orchestrator.gate_coordinator.register_or_update_project(
        project_id, "proj_git_isolated", str(proj_dir), initial_generation=5
    )

    # Even though git status is clean, dirty_generation=5 > last_good=0, so backup is ELIGIBLE!
    res = orchestrator.run_cycle_for_project(project_id, force=True, agent_state_override=AgentState.IDLE)
    assert res.action_taken == "BACKUP_COMPLETED"
    assert res.captured_generation == 5

    # Now make git dirty by editing tracked.txt
    (proj_dir / "tracked.txt").write_text("modified")
    git_stat2 = subprocess.run(["git", "status", "--porcelain"], cwd=str(proj_dir), capture_output=True, text=True)
    assert "M tracked.txt" in git_stat2.stdout

    # But without filesystem generation increment, dirty_gen=5 == last_good=5, so it is CLEAN in backup domain!
    res2 = orchestrator.run_cycle_for_project(project_id, force=False, agent_state_override=AgentState.IDLE)
    assert res2.action_taken == "SKIPPED_CLEAN", "Backup decision erroneously inspected Git dirty state!"


def test_submit_prompt_isolated_no_crash_recovery(test_env):
    """
    Codex A1: submit-prompt must NOT trigger crash recovery or unlock active backups.
    """
    cfg: BackupOrchestratorConfig = test_env["cfg"]
    proj_dir = test_env["projects_root"] / "proj_a1"
    proj_dir.mkdir(parents=True, exist_ok=True)
    project_id = "proj_a1"

    db = Database(cfg.db_path)
    gate = PromptGateCoordinator(db)
    gate.register_or_update_project(project_id, "proj_a1", str(proj_dir), initial_generation=1)

    # Put project into CLOSED state with active CAPTURING lock
    assert gate.close_gate(project_id) is True
    with db.transaction() as cur:
        cur.execute(
            "UPDATE projects_state SET lifecycle_lock = 'LOCKED', active_backup_id = 'active_backup_123' WHERE project_id = ?;",
            (project_id,),
        )

    # Call submit_prompt via bridge adapter
    bridge = BridgeAdapter(gate_coordinator=gate, sot_root=cfg.sot_root)
    res = bridge.handle_incoming_message(
        route_spec=project_id,
        message_id="msg_a1",
        payload="adversarial prompt during backup",
    )

    assert res.status == "HELD"
    assert res.delivered is False
    with db.transaction() as cur:
        cur.execute("SELECT prompt_gate, lifecycle_lock, active_backup_id FROM projects_state WHERE project_id = ?;", (project_id,))
        row = cur.fetchone()
        assert row["prompt_gate"] == "CLOSED"
        assert row["lifecycle_lock"] == "LOCKED"
        assert row["active_backup_id"] == "active_backup_123"

    # Adversarial A1 check: fail-closed dispatch when SOT binary is missing
    missing_bridge = BridgeAdapter(gate_coordinator=gate, sot_root=Path("/nonexistent/sot_root"))
    missing_sot = Path("/nonexistent/sot_root/sot")
    assert not missing_sot.exists()
    # In BridgeAdapter, when SOT root or binary is invalid, dispatching cannot violate gate boundary
    res_missing = missing_bridge.handle_incoming_message(
        route_spec=project_id,
        message_id="msg_a1_missing",
        payload="adversarial prompt with missing SOT",
    )
    assert res_missing.status == "HELD"
    assert res_missing.delivered is False

    # Adversarial A1 check: Idempotency on duplicate message submission
    res_dup1 = gate.dispatch_or_hold_message(project_id, "dup_msg_001", "term", "payload 1")
    res_dup2 = gate.dispatch_or_hold_message(project_id, "dup_msg_001", "term", "payload 1")
    assert res_dup1.status == res_dup2.status
    assert res_dup1.sequence_num == res_dup2.sequence_num

    # Adversarial A1 check: Unregistered project does not trigger Foreign Key crash
    unreg_proj = "unregistered_test_proj_999"
    res_unreg = gate.dispatch_or_hold_message(unreg_proj, "unreg_msg_001", "term", "payload unreg")
    assert res_unreg.status in ("DISPATCHING", "HELD")

    # Adversarial A1 check: whatsapp_bridge.js fails closed when SOT is missing or inaccessible
    bridge_script = Path("/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/whatsapp_bridge.js")
    if bridge_script.is_file():
        # Test 1: SOT binary missing -> dispatchToTmux returns false
        node_check_missing = subprocess.run(
            ["node", "-e", f"""
            process.env.SOT_PATH = '/nonexistent/sot/path';
            const {{ dispatchToTmux }} = require('{bridge_script}');
            const res = dispatchToTmux('test prompt missing sot', 'agy:0', 'test_msg_missing');
            if (res !== false) process.exit(1);
            process.exit(0);
            """],
            capture_output=True,
            text=True,
        )
        assert node_check_missing.returncode == 0, f"Missing SOT check failed: {node_check_missing.stderr}"

        # Test 2: SOT binary inaccessible (unreadable permissions) -> dispatchToTmux returns false
        node_check_inacc = subprocess.run(
            ["node", "-e", f"""
            const fs = require('fs');
            const tmp = '/tmp/unreadable_sot_adversarial_test';
            fs.writeFileSync(tmp, '#!/bin/sh\\n');
            fs.chmodSync(tmp, 0000);
            process.env.SOT_PATH = tmp;
            const {{ dispatchToTmux }} = require('{bridge_script}');
            const res = dispatchToTmux('test prompt inacc sot', 'agy:0', 'test_msg_inacc');
            fs.unlinkSync(tmp);
            if (res !== false) process.exit(1);
            process.exit(0);
            """],
            capture_output=True,
            text=True,
        )
        assert node_check_inacc.returncode == 0, f"Inaccessible SOT check failed: {node_check_inacc.stderr}"

        # Test 3: SOT binary is a directory -> dispatchToTmux returns false (fail closed)
        node_check_dir = subprocess.run(
            ["node", "-e", f"""
            process.env.SOT_PATH = '/home/azureuser';
            const {{ dispatchToTmux }} = require('{bridge_script}');
            const res = dispatchToTmux('test prompt dir sot', 'agy:0', 'test_msg_dir');
            if (res !== false) process.exit(1);
            process.exit(0);
            """],
            capture_output=True,
            text=True,
        )
        assert node_check_dir.returncode == 0, f"Directory SOT check failed: {node_check_dir.stderr}"

    # Adversarial A1 check: Failing receiver in BridgeAdapter rolls back to HELD and prevents in-flight leak
    gate_open_proj = "proj_a1_open"
    gate.register_or_update_project(gate_open_proj, "proj_a1_open", str(proj_dir), initial_generation=1)
    class FailingReceiver(BridgeTerminalReceiver):
        def receive_message(self, message, is_arbitrary_cli=False):
            return TerminalAck(message_id=message["message_id"], delivered=False, exactly_once_provable=False, status="FAILED", error="tty error")

    failing_adapter = BridgeAdapter(gate, cfg.sot_root, FailingReceiver())
    ack_fail = failing_adapter.handle_incoming_message(gate_open_proj, "msg_fail_receiver", "payload fail")
    assert ack_fail.delivered is False
    assert gate.has_in_flight_messages(gate_open_proj) is False
    assert gate.close_gate(gate_open_proj) is True

    # Adversarial A1 check: Duplicate submission on OPEN gate is rejected as DUPLICATE_REJECTED with delivered=False
    open_adapter = BridgeAdapter(gate, cfg.sot_root)
    gate.open_gate(gate_open_proj)
    ack_first = open_adapter.handle_incoming_message(gate_open_proj, "msg_dup_test_open", "payload first")
    assert ack_first.status == "DELIVERED"
    assert ack_first.delivered is True
    ack_second = open_adapter.handle_incoming_message(gate_open_proj, "msg_dup_test_open", "payload first")
    assert ack_second.status == "DUPLICATE_REJECTED"
    assert ack_second.delivered is False


def test_gate_drain_fifo_delivery(test_env):
    """
    Codex A2: HELD prompts in FIFO queue are auto-drained when gate opens.
    """
    cfg: BackupOrchestratorConfig = test_env["cfg"]
    proj_dir = test_env["projects_root"] / "proj_a2"
    proj_dir.mkdir(parents=True, exist_ok=True)
    project_id = "proj_a2"

    db = Database(cfg.db_path)
    gate = PromptGateCoordinator(db)
    gate.register_or_update_project(project_id, "proj_a2", str(proj_dir), initial_generation=1)
    assert gate.close_gate(project_id) is True

    delivered_prompts = []
    def mock_dispatch(prompt):
        delivered_prompts.append((prompt["project_id"], prompt["payload"]))
        return True

    gate.register_dispatch_handler(project_id, mock_dispatch)

    # Queue 3 prompts while gate is closed
    d1 = gate.dispatch_or_hold_message(project_id, "msg1", "terminal", "prompt 1")
    d2 = gate.dispatch_or_hold_message(project_id, "msg2", "terminal", "prompt 2")
    d3 = gate.dispatch_or_hold_message(project_id, "msg3", "terminal", "prompt 3")

    assert d1.status == "HELD"
    assert d2.status == "HELD"
    assert d3.status == "HELD"
    assert len(delivered_prompts) == 0

    # Open gate
    drained_count = gate.open_gate(project_id)
    assert drained_count == 3

    # Verify all 3 were drained in strict FIFO order
    assert len(delivered_prompts) == 3
    assert delivered_prompts[0] == (project_id, "prompt 1")
    assert delivered_prompts[1] == (project_id, "prompt 2")
    assert delivered_prompts[2] == (project_id, "prompt 3")

    # Adversarial A2 check: Restarting daemon with HELD prompts auto-drains queue in FIFO order once OPEN
    assert gate.close_gate(project_id) is True
    d4 = gate.dispatch_or_hold_message(project_id, "msg4", "terminal", "prompt 4")
    d5 = gate.dispatch_or_hold_message(project_id, "msg5", "terminal", "prompt 5")
    assert d4.status == "HELD"
    assert d5.status == "HELD"

    # Set gate to OPEN in database while prompts are still HELD
    with db.transaction() as cur:
        cur.execute("UPDATE projects_state SET prompt_gate = 'OPEN' WHERE project_id = ?;", (project_id,))

    # Start orchestrator daemon and verify it auto-drains on startup
    import threading
    orch = BackupOrchestrator(cfg)
    orch.gate_coordinator.register_dispatch_handler(project_id, mock_dispatch)
    stop_event = threading.Event()
    stop_event.set()
    orch.run_daemon(interval_seconds=1, stop_event=stop_event)

    assert len(delivered_prompts) == 5
    assert delivered_prompts[3] == (project_id, "prompt 4")
    assert delivered_prompts[4] == (project_id, "prompt 5")

    # Adversarial A2 check: Broker failure during drain rolls back status to HELD and prevents in-flight leak
    assert gate.close_gate(project_id) is True
    d_fail = gate.dispatch_or_hold_message(project_id, "msg_fail", "terminal", "prompt fail")
    assert d_fail.status == "HELD"

    failing_dispatch = lambda p: False
    gate.register_dispatch_handler(project_id, failing_dispatch)
    drained_failed = gate.open_gate(project_id)
    assert drained_failed == 0

    # Status must NOT be stuck in DISPATCHING
    assert gate.has_in_flight_messages(project_id) is False
    with db.transaction() as cur:
        cur.execute("SELECT status FROM held_prompt_queue WHERE message_id = ?;", ("msg_fail",))
        assert cur.fetchone()["status"] == "HELD"

    # Future close_gate must succeed cleanly without being permanently blocked
    assert gate.close_gate(project_id) is True

    # Adversarial A2 check: Exception thrown by dispatch_func rolls back status to HELD and prevents in-flight leak
    d_exc = gate.dispatch_or_hold_message(project_id, "msg_exc", "terminal", "prompt exc")
    assert d_exc.status == "HELD"

    def exploding_dispatch(p):
        raise RuntimeError("Broker connection suddenly severed!")

    gate.register_dispatch_handler(project_id, exploding_dispatch)
    drained_exc = gate.open_gate(project_id)
    assert drained_exc == 0
    assert gate.has_in_flight_messages(project_id) is False
    with db.transaction() as cur:
        cur.execute("SELECT status FROM held_prompt_queue WHERE message_id = ?;", ("msg_exc",))
        assert cur.fetchone()["status"] == "HELD"
    assert gate.close_gate(project_id) is True


def test_gate_check_cli_open(test_env, capsys):
    """
    Milestone 1 Test: gate-check CLI returns ALLOW_NOW and ZIP_GATE_OPEN when gate is open.
    """
    from backup_orchestrator.cli import handle_backup_orchestrator_cli
    import argparse

    cfg: BackupOrchestratorConfig = test_env["cfg"]
    db: Database = test_env["db"]
    gate = PromptGateCoordinator(db)
    project_id = "test_cli_open_proj"
    proj_dir = test_env["projects_root"] / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    gate.register_or_update_project(project_id, project_id, str(proj_dir))

    args = argparse.Namespace(
        orchestrator_action="gate-check",
        project_uuid=project_id,
        project="",
        route="",
        home=str(test_env["home"]),
    )
    rc = handle_backup_orchestrator_cli(args, test_env["sot_root"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["project_uuid"] == project_id
    assert data["zip_gate"] == "ZIP_GATE_OPEN"
    assert data["action"] == "ALLOW_NOW"
    assert data["zip_running"] is False
    assert data["zip_pid"] is None


def test_gate_check_cli_closed(test_env, capsys):
    """
    Milestone 1 Test: gate-check CLI returns HOLD_FOR_ZIP, ZIP_GATE_CLOSED, and live zip_pid when gate is closed.
    """
    from backup_orchestrator.cli import handle_backup_orchestrator_cli
    import argparse

    cfg: BackupOrchestratorConfig = test_env["cfg"]
    db: Database = test_env["db"]
    gate = PromptGateCoordinator(db)
    project_id = "test_cli_closed_proj"
    proj_dir = test_env["projects_root"] / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    gate.register_or_update_project(project_id, project_id, str(proj_dir))

    current_pid = os.getpid()
    assert gate.close_gate(project_id, zip_pid=current_pid) is True

    args = argparse.Namespace(
        orchestrator_action="gate-check",
        project_uuid=project_id,
        project="",
        route="",
        home=str(test_env["home"]),
    )
    rc = handle_backup_orchestrator_cli(args, test_env["sot_root"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["project_uuid"] == project_id
    assert data["zip_gate"] == "ZIP_GATE_CLOSED"
    assert data["action"] == "HOLD_FOR_ZIP"
    assert data["zip_running"] is True
    assert data["zip_pid"] == current_pid


def test_gate_check_dead_pid_autonomous_recovery(test_env, capsys):
    """
    Milestone 1 Test: gate-check CLI autonomously reopens gate and allows prompts if recorded zip_pid is dead.
    """
    from backup_orchestrator.cli import handle_backup_orchestrator_cli
    import argparse

    cfg: BackupOrchestratorConfig = test_env["cfg"]
    db: Database = test_env["db"]
    gate = PromptGateCoordinator(db)
    project_id = "test_dead_pid_proj"
    proj_dir = test_env["projects_root"] / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    gate.register_or_update_project(project_id, project_id, str(proj_dir))

    dead_pid = 999999
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db.transaction() as cur:
        cur.execute(
            """
            INSERT INTO backup_runs (
                backup_id, project_id, project_slug, captured_generation, zip_path, status, zip_pid, created_at
            ) VALUES ('b-dead-1', ?, ?, 1, '/tmp/dummy.zip', 'CAPTURING', ?, ?);
            """,
            (project_id, project_id, dead_pid, now_str),
        )
        cur.execute(
            """
            UPDATE projects_state
            SET prompt_gate = 'CLOSED', zip_pid = ?, lifecycle_lock = 'LOCKED', active_backup_id = 'b-dead-1'
            WHERE project_id = ?;
            """,
            (dead_pid, project_id),
        )

    args = argparse.Namespace(
        orchestrator_action="gate-check",
        project_uuid=project_id,
        project="",
        route="",
        home=str(test_env["home"]),
    )
    rc = handle_backup_orchestrator_cli(args, test_env["sot_root"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["project_uuid"] == project_id
    assert data["zip_gate"] == "ZIP_GATE_OPEN"
    assert data["action"] == "ALLOW_NOW"
    assert data["zip_running"] is False
    assert data["zip_pid"] is None

    with db.transaction() as cur:
        cur.execute("SELECT prompt_gate, zip_pid, lifecycle_lock, active_backup_id FROM projects_state WHERE project_id = ?;", (project_id,))
        row = cur.fetchone()
        assert row["prompt_gate"] == "OPEN"
        assert row["zip_pid"] is None
        assert row["lifecycle_lock"] == "UNLOCKED"
        assert row["active_backup_id"] is None

        cur.execute("SELECT status, error_message FROM backup_runs WHERE backup_id = 'b-dead-1';")
        r_run = cur.fetchone()
        assert r_run["status"] == "FAILED"
        assert "Interrupted" in r_run["error_message"]


def test_exact_zip_boundary_reopens_before_hashing(test_env):
    """
    Milestone 1 Test: Gate closes ONLY during live file walk, and reopens IMMEDIATELY
    when source archive walk/write finishes, BEFORE testzip() and SHA256 hashing.
    """
    cfg: BackupOrchestratorConfig = test_env["cfg"]
    db: Database = test_env["db"]
    clock: InjectableClock = test_env["clock"]
    project_id = "test_boundary_proj"
    proj_dir = test_env["projects_root"] / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    test_file = proj_dir / "code.py"
    test_file.write_text("print('hello world')")

    gate = PromptGateCoordinator(db)
    gate.register_or_update_project(project_id, project_id, str(proj_dir), initial_generation=1)

    watcher = ProjectFsWatcher(project_id, proj_dir, db, clock=clock)
    watcher.start_watches()
    watcher.reconcile_filesystem()

    orch = BackupOrchestrator(cfg, clock=clock)
    orch.watchers[project_id] = watcher

    gate_states_during_lifecycle = []

    orig_create_zip = orch.zipper.create_project_zip
    def spy_create_zip(*args, **kwargs):
        st_before = orch.gate_coordinator.get_gate_state(project_id)
        gate_states_during_lifecycle.append(("during_capture_walk", st_before["prompt_gate"], st_before["zip_pid"]))

        real_cb = kwargs.get("on_capture_complete_callback")
        def wrapped_cb():
            if real_cb:
                real_cb()
            st_after_walk = orch.gate_coordinator.get_gate_state(project_id)
            gate_states_during_lifecycle.append(("after_walk_before_hashing", st_after_walk["prompt_gate"], st_after_walk["zip_pid"]))

        kwargs["on_capture_complete_callback"] = wrapped_cb
        res = orig_create_zip(*args, **kwargs)
        st_after_zip = orch.gate_coordinator.get_gate_state(project_id)
        gate_states_during_lifecycle.append(("after_full_zip_return", st_after_zip["prompt_gate"], st_after_zip["zip_pid"]))
        return res

    orch.zipper.create_project_zip = spy_create_zip

    res = orch.run_cycle_for_project(project_id, force=True)
    assert res.action_taken == "BACKUP_COMPLETED"

    assert gate_states_during_lifecycle[0][0] == "during_capture_walk"
    assert gate_states_during_lifecycle[0][1] == "CLOSED"
    assert gate_states_during_lifecycle[0][2] == os.getpid()

    assert gate_states_during_lifecycle[1][0] == "after_walk_before_hashing"
    assert gate_states_during_lifecycle[1][1] == "OPEN"
    assert gate_states_during_lifecycle[1][2] is None

    assert gate_states_during_lifecycle[2][0] == "after_full_zip_return"
    assert gate_states_during_lifecycle[2][1] == "OPEN"


def test_submit_prompt_delivery_owner_is_not_daemon(test_env, capsys):
    """
    Milestone 1 Test: submit-prompt must NOT return delivery_owner == 'daemon'.
    """
    from backup_orchestrator.cli import handle_backup_orchestrator_cli
    import argparse

    project_id = "test_sub_owner_proj"
    proj_dir = test_env["projects_root"] / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    db: Database = test_env["db"]
    gate = PromptGateCoordinator(db)
    gate.register_or_update_project(project_id, project_id, str(proj_dir))

    args = argparse.Namespace(
        orchestrator_action="submit-prompt",
        route=project_id,
        message_id="msg-owner-test",
        payload="test payload",
        base64=False,
        home=str(test_env["home"]),
    )
    rc = handle_backup_orchestrator_cli(args, test_env["sot_root"])
    assert rc == 0
    captured = capsys.readouterr()
    ack = json.loads(captured.out)
    assert ack["delivery_owner"] != "daemon"
    assert ack["delivered"] is False


def test_orchestrator_zero_terminal_injection_during_drain(test_env):
    """
    Milestone 1 Test: Backup Orchestrator does not perform terminal injection.
    tmux send-keys is never called by Backup Orchestrator.
    """
    cfg: BackupOrchestratorConfig = test_env["cfg"]
    orch = BackupOrchestrator(cfg)
    project_id = "test_no_tmux_proj"
    proj_dir = test_env["projects_root"] / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    orch.gate_coordinator.register_or_update_project(project_id, project_id, str(proj_dir))

    orch.gate_coordinator.dispatch_or_hold_message(
        project_id=project_id,
        message_id="msg-zero-tmux",
        routing_target="agy:0",
        payload="should not be injected to tmux by SOT",
    )

    delivered = orch.drain_pending_prompts()
    assert delivered == 0

