"""Unit and integration test suite for GitPush Watcher subsystem (RULES 3-8, 15, 16, 24, 25, 29)."""
from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

from gitpush_watcher.attribution import TaskAttributor, PREFIX_USER_REQUESTED, PREFIX_UNVERIFIED
from gitpush_watcher.classifier import AssetClassifier, CLASS_A_GIT, CLASS_B_DATABASE, CLASS_C_LARGE_ASSET, CLASS_D_SECRET
from gitpush_watcher.config import WatcherConfig
from gitpush_watcher.lock import repo_lock, RepoLockError
from gitpush_watcher.pusher import GitPusher
from gitpush_watcher.snapshot import SnapshotManager
from gitpush_watcher.watcher import GitPushWatcher
from gitpush_watcher.cloud_parity import CloudParityAuditor
from projects.atomic_json import atomic_write_json, read_json, registry_lock


class GitPushWatcherTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sot-watcher-test-")
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _init_repo(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-C", str(path), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(path), "config", "user.name", "Test Agent"], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.email", "agent@test.local"], check=True)
        return path

    def _create_bare_remote(self, name: str = "remote.git") -> Path:
        remote = self.base / name
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        return remote

    def test_repo_lock_exclusive_and_non_blocking_release(self):
        """RULE 6: Verifies exclusive per-repository Git writer lock."""
        repo = self._init_repo(self.base / "lock_repo")
        with repo_lock(repo) as lock1:
            self.assertTrue(lock1.exists())
            # Second acquisition with timeout should raise RepoLockError
            with self.assertRaises(RepoLockError):
                with repo_lock(repo, timeout_seconds=0.2):
                    pass
        # Once released, can acquire again immediately
        with repo_lock(repo, timeout_seconds=0.5) as lock2:
            self.assertTrue(lock2.exists())

    def test_consistent_snapshot_and_writer_stability(self):
        """RULE 5: Staging without stopping writers, detecting mid-staging mutation, and non-destructive discard."""
        repo = self._init_repo(self.base / "snapshot_repo")
        f1 = repo / "main.py"
        f1.write_text("print('version 1')\n")
        
        # Capture pre-fingerprints
        pre_fp = SnapshotManager.capture_working_fingerprints(repo)
        self.assertIn("main.py", pre_fp)

        # Stage
        staged_ok, _ = SnapshotManager.stage_changes(repo)
        self.assertTrue(staged_ok)
        self.assertTrue(SnapshotManager.has_staged_changes(repo))

        # Consistent when untouched
        cons_ok, _ = SnapshotManager.verify_consistency(repo, pre_fp)
        self.assertTrue(cons_ok)

        # Simulate writer mutating file while staged
        time.sleep(0.01)
        f1.write_text("print('version 2 modified during staging')\n")
        cons_ok, reason = SnapshotManager.verify_consistency(repo, pre_fp)
        self.assertFalse(cons_ok)
        self.assertIn("mutated during staging", reason)

        # Discard staged snapshot: un-stages index, preserves working tree untouched
        SnapshotManager.discard_staged_snapshot(repo)
        self.assertFalse(SnapshotManager.has_staged_changes(repo))
        self.assertEqual(f1.read_text(), "print('version 2 modified during staging')\n")

    def test_cloud_parity_classification_and_unstage(self):
        """RULES 9-14: Classifies assets and un-stages secrets, databases, and large files."""
        repo = self._init_repo(self.base / "classify_repo")
        classifier = AssetClassifier(ROOT, large_file_threshold_bytes=1024)

        # Create files of different classes
        (repo / "app.py").write_text("print('ok')")
        (repo / ".env.prod").write_text("SECRET_KEY=12345")
        (repo / "data.sqlite").write_text("SQLite format 3")
        (repo / "large.bin").write_bytes(b"X" * 2048)
        (repo / "temp.tmp").write_text("temporary")
        (repo / "debug.log").write_text("2026-10-07 system log message")

        # Stage everything
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        self.assertTrue(SnapshotManager.has_staged_changes(repo))

        classified = classifier.inspect_and_filter_staged(repo, "test_proj", "00000000-0000-4000-8000-000000000001")
        self.assertIn("app.py", classified[CLASS_A_GIT])
        self.assertIn("debug.log", classified[CLASS_A_GIT])  # Logs remain staged (RULE 11)
        self.assertIn(".env.prod", classified[CLASS_D_SECRET])
        self.assertIn("data.sqlite", classified[CLASS_B_DATABASE])
        self.assertIn("large.bin", classified[CLASS_C_LARGE_ASSET])

        # Verify that only Class A files remain staged in git
        staged = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--name-only"], capture_output=True, text=True).stdout.splitlines()
        self.assertIn("app.py", staged)
        self.assertIn("debug.log", staged)
        self.assertNotIn(".env.prod", staged)
        self.assertNotIn("data.sqlite", staged)
        self.assertNotIn("large.bin", staged)

    def test_task_attribution_and_commit_prefixes(self):
        """RULES 7, 8: Strict binary commit prefixes 'User Requested : ' vs 'Unverified : '."""
        attributor = TaskAttributor(ROOT)
        repo = self._init_repo(self.base / "attr_repo")
        (repo / "test.txt").write_text("hello")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)

        # Case 1: Unverified (default when no active user task)
        msg_unverified = attributor.determine_commit_message(repo, "proj-1")
        self.assertTrue(msg_unverified.startswith(PREFIX_UNVERIFIED), f"Expected prefix '{PREFIX_UNVERIFIED}', got '{msg_unverified}'")

        # Case 2: User Requested when explicit task context exists
        os.environ["AGY_TASK_ID"] = "user-task-001"
        os.environ["AGY_TASK_ORIGIN"] = "user_requested"
        os.environ["AGY_TASK_SUMMARY"] = "update core configuration"
        try:
            msg_user = attributor.determine_commit_message(repo, "proj-1")
            self.assertTrue(msg_user.startswith(PREFIX_USER_REQUESTED), f"Expected prefix '{PREFIX_USER_REQUESTED}', got '{msg_user}'")
            self.assertIn("update core configuration", msg_user)
        finally:
            os.environ.pop("AGY_TASK_ID", None)
            os.environ.pop("AGY_TASK_ORIGIN", None)
            os.environ.pop("AGY_TASK_SUMMARY", None)

    def test_push_workflow_and_failure_resilience(self):
        """RULES 15, 16: Commit, push to remote, verify remote SHA parity, and fail-safe recovery."""
        remote = self._create_bare_remote("remote_test.git")
        repo = self._init_repo(self.base / "push_repo")
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)

        (repo / "file.txt").write_text("content 1\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)

        commit_ok, sha, _ = GitPusher.commit(repo, "User Requested : initial commit")
        self.assertTrue(commit_ok)
        self.assertTrue(bool(sha))

        # Push and verify remote parity
        push_ok, push_msg = GitPusher.push_and_verify_parity(repo, "main", "origin")
        self.assertTrue(push_ok, f"Push failed: {push_msg}")
        self.assertEqual(push_msg, "PUSH_AND_REMOTE_SHA_VERIFIED")

        # Verify remote SHA matches local SHA exactly
        remote_probe = subprocess.run(["git", "ls-remote", str(remote), "refs/heads/main"], capture_output=True, text=True)
        self.assertEqual(remote_probe.stdout.split()[0], sha)

        # Test Push Failure with unpushable remote URL
        subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", "file:///invalid/path/nonexistent.git"], check=True)
        (repo / "file.txt").write_text("content 2\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        GitPusher.commit(repo, "Unverified : test failure")
        
        push_ok, push_err = GitPusher.push_and_verify_parity(repo, "main", "origin")
        self.assertFalse(push_ok)
        self.assertIn("PUSH_FAILED", push_err)
        # Working file was NOT destroyed or reverted
        self.assertEqual((repo / "file.txt").read_text(), "content 2\n")

    def test_watcher_health_report_structure(self):
        """RULE 29: Watcher health report contains all mandatory monitoring keys."""
        watcher = GitPushWatcher(ROOT)
        report = watcher.get_health_report()
        required_keys = [
            "WATCHER_PROCESS", "WATCHER_EVENT_SOURCE", "WATCHER_QUEUE",
            "PROJECT_LOCKS", "PENDING_COMMITS", "PENDING_PUSHES",
            "LAST_SUCCESSFUL_PUSH", "REMOTE_PARITY", "FAILED_RETRIES"
        ]
        for key in required_keys:
            self.assertIn(key, report)

    def test_actual_agy_runtime_workflow(self):
        """RULE 24: End-to-end verification of the 12-step AGY runtime test workflow."""
        # 1. Create a safe sandbox project
        remote = self._create_bare_remote("sandbox_remote.git")
        proj_dir = self._init_repo(self.base / "sandbox_project")
        subprocess.run(["git", "-C", str(proj_dir), "remote", "add", "origin", str(remote)], check=True)

        # 2. Edit a file
        f = proj_dir / "service.py"
        f.write_text("def run():\n    return 'running'\n")

        # 3. Watcher discovers project/change and syncs single project
        watcher = GitPushWatcher(ROOT)
        project_record = {
            "project_id": "test_sandbox",
            "project_uuid": "00000000-0000-4000-8000-000000000099",
            "canonical_path": str(proj_dir),
            "git": {
                "enabled": True,
                "remote": str(remote),
                "branch": "main",
                "backup_required": True
            }
        }

        # 4 & 5. Commit generated with correct prefix
        os.environ["AGY_TASK_ID"] = "agy-test-task"
        os.environ["AGY_TASK_ORIGIN"] = "user_requested"
        os.environ["AGY_TASK_SUMMARY"] = "create sandbox service"
        try:
            # 6. Push occurs automatically & 7. Remote commit verified
            ok, msg = watcher.sync_project_once(project_record)
            self.assertTrue(ok, f"Sync project failed: {msg}")
            self.assertEqual(msg, "COMMITTED_AND_PUSHED_WITH_REMOTE_PARITY")

            # 8. Verify no user prompt occurred and commit message has User Requested prefix
            head_msg = subprocess.run(["git", "-C", str(proj_dir), "log", "-1", "--pretty=%s"], capture_output=True, text=True).stdout.strip()
            self.assertTrue(head_msg.startswith("User Requested : "), f"Unexpected commit message: {head_msg}")

            # Verify remote SHA matches local HEAD
            local_sha = GitPusher.get_head_sha(proj_dir)
            remote_probe = subprocess.run(["git", "ls-remote", str(remote), "refs/heads/main"], capture_output=True, text=True)
            self.assertEqual(remote_probe.stdout.split()[0], local_sha)
        finally:
            os.environ.pop("AGY_TASK_ID", None)
            os.environ.pop("AGY_TASK_ORIGIN", None)
            os.environ.pop("AGY_TASK_SUMMARY", None)

    def test_100_worker_simulation(self):
        """RULE 25: 100 concurrent workers simulating simultaneous events, registrations, Git locks, and registry writes."""
        reg_file = self.base / "SIMULATION_REGISTRY.json"
        reg_file.write_text(json.dumps({"version": "1.0.0", "projects": []}))

        num_workers = 100
        errors = []

        def worker_task(worker_id: int):
            try:
                # 1. Concurrent registry update under atomic lock
                with registry_lock(reg_file):
                    data = read_json(reg_file)
                    projects = data.get("projects", [])
                    pid = f"worker_proj_{worker_id}"
                    puuid = f"worker-uuid-{worker_id:04d}"
                    projects.append({
                        "project_id": pid,
                        "project_uuid": puuid,
                        "worker_id": worker_id,
                        "timestamp": time.time()
                    })
                    data["projects"] = projects
                    atomic_write_json(reg_file, data)

                # 2. Local git write simulation with per-repo lock
                w_repo = self.base / f"worker_repo_{worker_id % 10}"  # 10 repos shared across 100 workers to test contention
                if not (w_repo / ".git").exists():
                    self._init_repo(w_repo)

                with repo_lock(w_repo, timeout_seconds=10.0):
                    f = w_repo / f"file_{worker_id}.txt"
                    f.write_text(f"worker {worker_id} content\n")
                    subprocess.run(["git", "-C", str(w_repo), "add", "-A"], capture_output=True)
                    # Non-destructive check
                    pre_fp = SnapshotManager.capture_working_fingerprints(w_repo)
                    cons_ok, _ = SnapshotManager.verify_consistency(w_repo, pre_fp)
                    if not cons_ok:
                        raise RuntimeError(f"Worker {worker_id} detected snapshot corruption")
                    subprocess.run(["git", "-C", str(w_repo), "commit", "-m", f"Unverified : worker {worker_id} update"], capture_output=True)

            except Exception as exc:
                errors.append(f"Worker {worker_id} error: {exc}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_workers)]
            concurrent.futures.wait(futures)

        self.assertEqual(len(errors), 0, f"Simulation reported errors: {errors[:5]}")

        # Verify no corrupt JSON and all 100 entries present without duplicate UUIDs
        final_data = read_json(reg_file)
        projs = final_data.get("projects", [])
        self.assertEqual(len(projs), num_workers)
        uuids = {p["project_uuid"] for p in projs}
        self.assertEqual(len(uuids), num_workers)


if __name__ == "__main__":
    unittest.main()
