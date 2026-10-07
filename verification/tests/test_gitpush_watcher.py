"""Unit and integration test suite for GitPush Watcher subsystem (RULES 3-8, 15, 16, 24, 25, 29)."""
from __future__ import annotations
import json
import multiprocessing
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
from gitpush_watcher.pusher import GitPusher, normalize_git_url
from gitpush_watcher.snapshot import SnapshotManager
from gitpush_watcher.watcher import GitPushWatcher
from gitpush_watcher.cloud_parity import CloudParityAuditor
from projects.atomic_json import atomic_write_json, read_json, registry_lock

def _process_worker_task(args):
    """Standalone worker for multiprocessing simulation (FIX 6)."""
    worker_id, reg_file_str, repo_path_str = args
    reg_file = Path(reg_file_str)
    w_repo = Path(repo_path_str)
    try:
        with registry_lock(reg_file):
            data = read_json(reg_file)
            projects = data.get('projects', [])
            pid = f'worker_proj_{worker_id}'
            puuid = f'worker-uuid-{worker_id:04d}'
            projects.append({'project_id': pid, 'project_uuid': puuid, 'worker_id': worker_id, 'timestamp': time.time()})
            data['projects'] = projects
            atomic_write_json(reg_file, data)
        with repo_lock(w_repo, timeout_seconds=15.0):
            f = w_repo / f'file_{worker_id}.txt'
            f.write_text(f'worker {worker_id} content\n')
            subprocess.run(['git', '-C', str(w_repo), 'add', '-A'], capture_output=True, timeout=15)
            pre_fp = SnapshotManager.capture_working_fingerprints(w_repo)
            cons_ok, cons_err = SnapshotManager.verify_consistency(w_repo, pre_fp)
            if not cons_ok:
                return f'Worker {worker_id} snapshot inconsistency: {cons_err}'
            subprocess.run(['git', '-C', str(w_repo), 'commit', '-m', f'Unverified : worker {worker_id} update'], capture_output=True, timeout=15, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
        return None
    except Exception as exc:
        return f'Worker {worker_id} exception: {exc}'

class GitPushWatcherTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='sot-watcher-test-')
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _init_repo(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', '-C', str(path), 'init'], check=True, capture_output=True, timeout=15)
        subprocess.run(['git', '-C', str(path), 'config', 'user.name', 'Test Agent'], check=True, timeout=15)
        subprocess.run(['git', '-C', str(path), 'config', 'user.email', 'agent@test.local'], check=True, timeout=15)
        return path

    def _create_bare_remote(self, name: str='remote.git') -> Path:
        remote = self.base / name
        subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True, timeout=15)
        return remote

    def test_repo_lock_exclusive_and_non_blocking_release(self):
        """RULE 6: Verifies exclusive per-repository Git writer lock."""
        repo = self._init_repo(self.base / 'lock_repo')
        with repo_lock(repo) as lock1:
            self.assertTrue(lock1.exists())
            with self.assertRaises(RepoLockError):
                with repo_lock(repo, timeout_seconds=0.2):
                    pass
        with repo_lock(repo, timeout_seconds=0.5) as lock2:
            self.assertTrue(lock2.exists())

    def test_consistent_snapshot_and_writer_stability(self):
        """RULE 5: Non-destructive staging discard on consistent snapshot."""
        repo = self._init_repo(self.base / 'snapshot_repo')
        f1 = repo / 'stable.txt'
        f1.write_text('initial content\n')
        SnapshotManager.stage_changes(repo)
        GitPusher.commit(repo, 'Unverified : initial')
        f2 = repo / 'new_work.txt'
        f2.write_text('in-progress changes\n')
        pre_fp = SnapshotManager.capture_working_fingerprints(repo)
        staged_ok, _ = SnapshotManager.stage_changes(repo)
        self.assertTrue(staged_ok)
        self.assertTrue(SnapshotManager.has_staged_changes(repo))
        SnapshotManager.discard_staged_snapshot(repo)
        self.assertFalse(SnapshotManager.has_staged_changes(repo))
        self.assertTrue(f2.exists())
        self.assertEqual(f2.read_text(), 'in-progress changes\n')

    def test_consistent_snapshot_detects_mutation_during_staging(self):
        """FIX 5: Verifies that snapshot detects file creation, deletion, and content mutation during staging."""
        repo = self._init_repo(self.base / 'race_repo')
        f1 = repo / 'file1.txt'
        f1.write_text('base content\n')
        pre_fp = SnapshotManager.capture_working_fingerprints(repo)
        SnapshotManager.stage_changes(repo)
        f_late = repo / 'file_late.txt'
        f_late.write_text('late arriving content\n')
        cons_ok, cons_msg = SnapshotManager.verify_consistency(repo, pre_fp)
        self.assertFalse(cons_ok)
        self.assertIn('Files created during staging interval', cons_msg)
        f_late.unlink()
        f1.write_text('diff content\n')
        cons_ok, cons_msg = SnapshotManager.verify_consistency(repo, pre_fp)
        self.assertFalse(cons_ok)
        self.assertIn('content mutated', cons_msg)

    def test_fail_closed_asset_classification(self):
        """FIX 9: Verifies fail-closed classification for plain .env, 10KB mp4, and suspicious binaries."""
        classifier = AssetClassifier(ROOT)
        env_file = self.base / '.env'
        env_file.write_text('API_KEY=12345\n')
        self.assertEqual(classifier.classify_file(env_file), CLASS_D_SECRET)
        env_local = self.base / '.env.local'
        env_local.write_text('SECRET=xyz\n')
        self.assertEqual(classifier.classify_file(env_local), CLASS_D_SECRET)
        mp4_file = self.base / 'sample.mp4'
        mp4_file.write_bytes(b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 10240)
        self.assertEqual(classifier.classify_file(mp4_file), CLASS_C_LARGE_ASSET)
        db_file = self.base / 'app.db'
        db_file.write_text('fake db\n')
        self.assertEqual(classifier.classify_file(db_file), CLASS_B_DATABASE)
        bin_file = self.base / 'unknown.bin'
        bin_file.write_bytes(b'\x7fELF' + b'\x00' * 50)
        self.assertEqual(classifier.classify_file(bin_file), CLASS_C_LARGE_ASSET)

    def test_commit_prefix_boundary_enforcement(self):
        """FIX 4: Enforces that GitPusher.commit always sanitizes and prefixes commit messages."""
        repo = self._init_repo(self.base / 'prefix_repo')
        f = repo / 'file.txt'
        f.write_text('hello\n')
        SnapshotManager.stage_changes(repo)
        GitPusher.commit(repo, 'raw unverified message')
        msg = subprocess.run(['git', '-C', str(repo), 'log', '-1', '--pretty=%s'], capture_output=True, text=True, timeout=15).stdout.strip()
        self.assertTrue(msg.startswith(PREFIX_UNVERIFIED))
        self.assertIn('raw unverified message', msg)
        f.write_text('hello 2\n')
        SnapshotManager.stage_changes(repo)
        GitPusher.commit(repo, '')
        msg2 = subprocess.run(['git', '-C', str(repo), 'log', '-1', '--pretty=%s'], capture_output=True, text=True, timeout=15).stdout.strip()
        self.assertTrue(msg2.startswith(PREFIX_UNVERIFIED))
        f.write_text('hello 3\n')
        SnapshotManager.stage_changes(repo)
        GitPusher.commit(repo, 'User Requested : update documentation')
        msg3 = subprocess.run(['git', '-C', str(repo), 'log', '-1', '--pretty=%s'], capture_output=True, text=True, timeout=15).stdout.strip()
        self.assertEqual(msg3, 'User Requested : update documentation')

    def test_remote_drift_detected_and_rejected(self):
        """FIX 3: Verifies that if git origin != canonical registry remote, push fails with REMOTE_DRIFT."""
        remote_a = self._create_bare_remote('remote_a.git')
        remote_b = self._create_bare_remote('remote_b.git')
        repo = self._init_repo(self.base / 'drift_repo')
        subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', str(remote_b)], check=True, timeout=15)
        (repo / 'file.txt').write_text('content\n')
        SnapshotManager.stage_changes(repo)
        GitPusher.commit(repo, 'Unverified : test')
        push_ok, push_msg = GitPusher.push_and_verify_parity(repo, 'main', 'origin', canonical_remote_url=str(remote_a))
        self.assertFalse(push_ok)
        self.assertIn('REMOTE_DRIFT', push_msg)

    def test_task_attribution_and_commit_prefixes(self):
        """RULES 7, 8: TaskAttributor produces strictly binary commit prefixes."""
        repo = self._init_repo(self.base / 'attrib_repo')
        attributor = TaskAttributor(ROOT)
        msg = attributor.determine_commit_message(repo, 'proj-1')
        self.assertTrue(msg.startswith(PREFIX_UNVERIFIED), f"Expected prefix '{PREFIX_UNVERIFIED}', got '{msg}'")
        os.environ['AGY_TASK_ID'] = 'task-test-user-123'
        os.environ['AGY_TASK_ORIGIN'] = 'user_requested'
        os.environ['AGY_TASK_SUMMARY'] = 'update core configuration'
        try:
            msg_user = attributor.determine_commit_message(repo, 'proj-1')
            self.assertTrue(msg_user.startswith(PREFIX_USER_REQUESTED), f"Expected prefix '{PREFIX_USER_REQUESTED}', got '{msg_user}'")
            self.assertIn('update core configuration', msg_user)
        finally:
            os.environ.pop('AGY_TASK_ID', None)
            os.environ.pop('AGY_TASK_ORIGIN', None)
            os.environ.pop('AGY_TASK_SUMMARY', None)

    def test_push_workflow_and_failure_resilience(self):
        """RULES 15, 16: Commit, push to remote, verify remote SHA parity, and fail-safe recovery."""
        remote = self._create_bare_remote('remote_test.git')
        repo = self._init_repo(self.base / 'push_repo')
        subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', str(remote)], check=True, timeout=15)
        (repo / 'file.txt').write_text('content 1\n')
        subprocess.run(['git', '-C', str(repo), 'add', '-A'], check=True, timeout=15)
        commit_ok, sha, _ = GitPusher.commit(repo, 'User Requested : initial commit')
        self.assertTrue(commit_ok)
        self.assertTrue(bool(sha))
        push_ok, push_msg = GitPusher.push_and_verify_parity(repo, 'main', 'origin', canonical_remote_url=str(remote))
        self.assertTrue(push_ok, f'Push failed: {push_msg}')
        self.assertEqual(push_msg, 'PUSH_AND_REMOTE_SHA_VERIFIED')
        remote_probe = subprocess.run(['git', 'ls-remote', str(remote), 'refs/heads/main'], capture_output=True, text=True, timeout=15)
        self.assertEqual(remote_probe.stdout.split()[0], sha)

    def test_watcher_health_report_structure(self):
        """RULE 29: Watcher health report contains all mandatory monitoring keys."""
        watcher = GitPushWatcher(ROOT)
        report = watcher.get_health_report()
        required_keys = ['WATCHER_PROCESS', 'WATCHER_EVENT_SOURCE', 'WATCHER_QUEUE', 'PROJECT_LOCKS', 'PENDING_COMMITS', 'PENDING_PUSHES', 'LAST_SUCCESSFUL_PUSH', 'REMOTE_PARITY', 'FAILED_RETRIES']
        for key in required_keys:
            self.assertIn(key, report)

    def test_actual_agy_runtime_workflow(self):
        """FIX 13 & RULE 24: Daemon-driven end-to-end test without harness calling sync manually."""
        remote = self._create_bare_remote('sandbox_remote.git')
        proj_dir = self._init_repo(self.base / 'sandbox_project')
        subprocess.run(['git', '-C', str(proj_dir), 'remote', 'add', 'origin', str(remote)], check=True, timeout=15)
        conf = WatcherConfig.load(ROOT)
        conf.reconciliation_interval_seconds = 0.5
        conf.debounce_seconds = 0.2
        watcher = GitPushWatcher(ROOT, conf)
        orig_load = watcher.load_registered_projects
        sandbox_project = {'project_id': 'test_daemon_sandbox', 'project_uuid': '00000000-0000-4000-8000-000000000099', 'canonical_path': str(proj_dir), 'git': {'enabled': True, 'remote': str(remote), 'branch': 'main', 'backup_required': True}}
        watcher.load_registered_projects = lambda: [sandbox_project]
        stop_event = threading.Event()
        daemon_thread = threading.Thread(target=watcher.run_daemon, args=(stop_event,), daemon=True)
        os.environ['AGY_TASK_ID'] = 'agy-test-task'
        os.environ['AGY_TASK_ORIGIN'] = 'user_requested'
        os.environ['AGY_TASK_SUMMARY'] = 'create sandbox daemon service'
        try:
            daemon_thread.start()
            time.sleep(0.5)
            f = proj_dir / 'service.py'
            f.write_text("def run():\n    return 'running'\n")
            start_time = time.time()
            synced = False
            while time.time() - start_time < 10.0:
                remote_probe = subprocess.run(['git', 'ls-remote', str(remote), 'refs/heads/main'], capture_output=True, text=True, timeout=15)
                lines = remote_probe.stdout.strip().split()
                if lines:
                    synced = True
                    break
                time.sleep(0.3)
            self.assertTrue(synced, 'Watcher daemon did not automatically detect and push changes within timeout')
            head_msg = subprocess.run(['git', '-C', str(proj_dir), 'log', '-1', '--pretty=%s'], capture_output=True, text=True, timeout=15).stdout.strip()
            self.assertTrue(head_msg.startswith('User Requested : '), f'Unexpected commit message: {head_msg}')
            local_sha = GitPusher.get_head_sha(proj_dir)
            remote_probe = subprocess.run(['git', 'ls-remote', str(remote), 'refs/heads/main'], capture_output=True, text=True, timeout=15)
            self.assertEqual(remote_probe.stdout.split()[0], local_sha)
        finally:
            stop_event.set()
            daemon_thread.join(timeout=3.0)
            os.environ.pop('AGY_TASK_ID', None)
            os.environ.pop('AGY_TASK_ORIGIN', None)
            os.environ.pop('AGY_TASK_SUMMARY', None)

    def test_100_worker_simulation(self):
        """FIX 6 & RULE 25: Real process-level multiprocessing simulation across 100 concurrent workers."""
        reg_file = self.base / 'SIMULATION_REGISTRY.json'
        reg_file.write_text(json.dumps({'version': '1.0.0', 'projects': []}))
        shared_repos = []
        for i in range(10):
            r = self._init_repo(self.base / f'worker_repo_{i}')
            shared_repos.append(str(r))
        num_workers = 100
        tasks = []
        for i in range(num_workers):
            target_repo = shared_repos[i % len(shared_repos)]
            tasks.append((i, str(reg_file), target_repo))
        ctx = multiprocessing.get_context('fork')
        with ctx.Pool(processes=8) as pool:
            results = pool.map(_process_worker_task, tasks)
        errors = [r for r in results if r is not None]
        self.assertEqual(len(errors), 0, f'Process simulation reported errors: {errors[:5]}')
        final_data = read_json(reg_file)
        projs = final_data.get('projects', [])
        self.assertEqual(len(projs), num_workers)
        uuids = {p['project_uuid'] for p in projs}
        self.assertEqual(len(uuids), num_workers)
if __name__ == '__main__':
    unittest.main()
    def test_adversarial_stdin_dev_null_termination(self, temp_home):
        """FIX 1: Prove deterministic termination with stdin=/dev/null."""
        import subprocess
        root = Path("/home/azureuser/IroScript_Projects/Infrastructure-Source-of-Truth")
        sot_exec = root / "sot"
        
        with open(os.devnull, 'r') as devnull:
            try:
                # Add some test flag if available, or just run version/help
                result = subprocess.run(
                    [sys.executable, str(sot_exec)],
                    stdin=devnull,
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                assert result.returncode in (0, 1, 2)
            except subprocess.TimeoutExpired:
                pytest.fail("Process did not terminate when stdin=/dev/null (hanging on prompt?)")