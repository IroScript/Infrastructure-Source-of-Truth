"""GitPush Watcher Core Daemon and Reconciliation Engine (RULES 3, 4, 5, 6, 11, 28, 29).
Monitors all registered projects, debounces active writers, and syncs Git checkpoints unattended.
"""
from __future__ import annotations
import ctypes
import json
import os
import select
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from .attribution import TaskAttributor
from .classifier import AssetClassifier
from .config import WatcherConfig
from .lock import repo_lock, RepoLockError
from .pusher import GitPusher
from .snapshot import SnapshotManager

class GitPushWatcher:
    """Continuous unattended Git synchronization engine."""

    def __init__(self, root: Path, config: Optional[WatcherConfig]=None):
        self.root = Path(root).resolve()
        self.config = config or WatcherConfig.load(self.root)
        self.classifier = AssetClassifier(self.root, self.config.large_file_threshold_bytes)
        self.attributor = TaskAttributor(self.root)
        self.pusher = GitPusher(self.root)
        self.state_file = self.config.state_file
        self.running = False
        self.event_source = 'polling'
        self.project_queues: Dict[str, float] = {}
        self.pending_pushes: Dict[str, Dict[str, Any]] = {}
        self.last_successful_pushes: Dict[str, Dict[str, Any]] = {}
        self.failed_retries = 0
        self._lock = threading.Lock()

    def load_registered_projects(self) -> List[Dict[str, Any]]:
        """Loads projects from projects/PROJECT_REGISTRY.json."""
        reg_file = self.root / 'projects' / 'PROJECT_REGISTRY.json'
        if not reg_file.is_file():
            return []
        try:
            data = json.loads(reg_file.read_text(encoding='utf-8'))
            return data.get('projects', [])
        except Exception:
            return []

    def load_state(self) -> Dict[str, Any]:
        """Loads persistent watcher state."""
        if not self.state_file.is_file():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def save_state(self) -> None:
        """Saves persistent watcher state atomically (self-suppressed by ignored patterns)."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        report = self.get_health_report()
        tmp = self.state_file.with_suffix('.tmp')
        try:
            tmp.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            tmp.replace(self.state_file)
        except Exception:
            pass

    def get_health_report(self) -> Dict[str, Any]:
        """Generates machine-readable health metrics conforming to RULE 29."""
        pid = os.getpid() if self.running else None
        is_alive = False
        if pid:
            try:
                os.kill(pid, 0)
                is_alive = True
            except OSError:
                pass
        remote_parity = {}
        projects = self.load_registered_projects()
        for p in projects:
            pid_name = p.get('project_id', '')
            remote = p.get('git', {}).get('remote', '')
            if remote and p.get('git', {}).get('backup_required', True):
                last = self.last_successful_pushes.get(pid_name, {})
                remote_parity[pid_name] = 'VERIFIED' if last else 'UNKNOWN'
            else:
                remote_parity[pid_name] = 'LOCAL_ONLY'
        return {'schema_version': '1.0.0', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'WATCHER_PROCESS': {'running': self.running, 'pid': pid, 'alive': is_alive}, 'WATCHER_EVENT_SOURCE': self.event_source, 'WATCHER_QUEUE': {'active_queues': len(self.project_queues), 'queued_projects': list(self.project_queues.keys())}, 'PROJECT_LOCKS': {'active_locks': []}, 'PENDING_COMMITS': [], 'PENDING_PUSHES': list(self.pending_pushes.values()), 'LAST_SUCCESSFUL_PUSH': self.last_successful_pushes, 'REMOTE_PARITY': remote_parity, 'FAILED_RETRIES': self.failed_retries}

    def sync_project_once(self, project: Dict[str, Any], explicit_message: str='') -> Tuple[bool, str]:
        """Synchronizes a single project through the full zero-interaction GitPush pipeline."""
        pid = project.get('project_id', '')
        puuid = project.get('project_uuid', '')
        repo_path = Path(project.get('canonical_path', '')).resolve()
        if not repo_path.is_dir() or not (repo_path / '.git').exists():
            return (False, 'NOT_A_GIT_REPOSITORY')
        git_conf = project.get('git', {})
        backup_required = git_conf.get('backup_required', True)
        remote = git_conf.get('remote', '')
        branch = git_conf.get('branch', '') or GitPusher.get_current_branch(repo_path)
        try:
            with repo_lock(repo_path, timeout_seconds=5.0):
                st = subprocess.run(['git', '-C', str(repo_path), 'status', '--porcelain'], capture_output=True, text=True, timeout=15)
                if not st.stdout.strip():
                    return (True, 'CLEAN_NO_CHANGES')
                pre_fp = SnapshotManager.capture_working_fingerprints(repo_path, self.config.ignored_patterns)
                staged_ok, stage_msg = SnapshotManager.stage_changes(repo_path)
                if not staged_ok:
                    return (False, stage_msg)
                cons_ok, cons_msg = SnapshotManager.verify_consistency(repo_path, pre_fp, self.config.ignored_patterns)
                if not cons_ok:
                    SnapshotManager.discard_staged_snapshot(repo_path)
                    return (False, f'SNAPSHOT_MUTATED_RETRY: {cons_msg}')
                classified = self.classifier.inspect_and_filter_staged(repo_path, pid, puuid)
                if not SnapshotManager.has_staged_changes(repo_path):
                    return (True, 'NO_GIT_CHANGES_AFTER_CLASSIFICATION')
                msg = explicit_message or self.attributor.determine_commit_message(repo_path, puuid)
                commit_ok, commit_sha, commit_err = GitPusher.commit(repo_path, msg)
                if not commit_ok:
                    return (False, commit_err)
                if backup_required and remote:
                    push_ok, push_msg = GitPusher.push_and_verify_parity(repo_path, branch, 'origin', canonical_remote_url=remote)
                    if push_ok:
                        with self._lock:
                            self.last_successful_pushes[pid] = {'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'commit_sha': commit_sha, 'branch': branch, 'remote': remote}
                            self.pending_pushes.pop(pid, None)
                        return (True, 'COMMITTED_AND_PUSHED_WITH_REMOTE_PARITY')
                    else:
                        with self._lock:
                            self.pending_pushes[pid] = {'project_id': pid, 'commit_sha': commit_sha, 'error': push_msg, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'retry_count': self.pending_pushes.get(pid, {}).get('retry_count', 0) + 1}
                            self.failed_retries += 1
                        return (False, push_msg)
                else:
                    return (True, 'COMMITTED_LOCAL_ONLY')
        except RepoLockError as exc:
            return (False, f'LOCK_CONTENTION: {exc}')

    def sync_all_once(self, explicit_message: str='') -> Dict[str, Tuple[bool, str]]:
        """Performs a single complete synchronization pass across all registered projects."""
        results: Dict[str, Tuple[bool, str]] = {}
        projects = self.load_registered_projects()
        for p in projects:
            pid = p.get('project_id', '')
            results[pid] = self.sync_project_once(p, explicit_message)
        self.save_state()
        return results

    def run_reconciliation_cycle(self) -> None:
        """Executes debounced queues and periodic scans."""
        now = time.time()
        ready_projects = []
        with self._lock:
            for pid, last_time in list(self.project_queues.items()):
                if now - last_time >= self.config.debounce_seconds:
                    ready_projects.append(pid)
                    self.project_queues.pop(pid, None)
        projects = {p.get('project_id'): p for p in self.load_registered_projects()}
        for pid in ready_projects:
            proj = projects.get(pid)
            if proj:
                self.sync_project_once(proj)
        with self._lock:
            pending = list(self.pending_pushes.values())
        for item in pending:
            pid = item.get('project_id', '')
            proj = projects.get(pid)
            if proj:
                self.sync_project_once(proj)
        self.save_state()

    def run_daemon(self, stop_event: Optional[threading.Event]=None) -> None:
        """Main daemon loop supporting real libc inotify watches and periodic reconciliation fallback (FIX 2)."""
        self.running = True
        self.save_state()
        inotify_fd = -1
        inotify_add_watch = None
        wd_to_project: Dict[int, str] = {}
        watched_paths: Set[str] = set()
        try:
            libc = ctypes.CDLL(None)
            inotify_init1 = libc.inotify_init1
            inotify_init1.restype = ctypes.c_int
            inotify_init1.argtypes = [ctypes.c_int]
            inotify_add_watch = libc.inotify_add_watch
            inotify_add_watch.restype = ctypes.c_int
            inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
            inotify_fd = inotify_init1(2048)
        except Exception:
            inotify_fd = -1

        def _update_watches():
            nonlocal inotify_fd, inotify_add_watch
            if inotify_fd < 0 or not inotify_add_watch:
                return
            mask = 2 | 8 | 256 | 512 | 128
            for p in self.load_registered_projects():
                cpath = str(Path(p.get('canonical_path', '')).resolve())
                if cpath and cpath not in watched_paths and os.path.isdir(cpath):
                    wd = inotify_add_watch(inotify_fd, cpath.encode('utf-8'), mask)
                    if wd >= 0:
                        wd_to_project[wd] = p.get('project_id', '')
                        watched_paths.add(cpath)
        _update_watches()
        self.event_source = 'inotify' if wd_to_project else 'polling'
        last_reconcile = time.time()
        try:
            while self.running and (not stop_event or not stop_event.is_set()):
                now = time.time()
                if inotify_fd >= 0 and self.event_source == 'inotify':
                    r, _, _ = select.select([inotify_fd], [], [], 0.5)
                    if r:
                        try:
                            event_data = os.read(inotify_fd, 4096)
                            offset = 0
                            while offset + 16 <= len(event_data):
                                wd, mask, cookie, length = struct.unpack_from('iIII', event_data, offset)
                                offset += 16 + length
                                pid = wd_to_project.get(wd)
                                if pid:
                                    with self._lock:
                                        self.project_queues[pid] = now
                        except OSError:
                            pass
                if now - last_reconcile >= self.config.reconciliation_interval_seconds:
                    _update_watches()
                    for p in self.load_registered_projects():
                        cpath = Path(p.get('canonical_path', ''))
                        if cpath.is_dir() and (cpath / '.git').exists():
                            st = subprocess.run(['git', '-C', str(cpath), 'status', '--porcelain'], capture_output=True, text=True, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}, timeout=15)
                            if st.stdout.strip():
                                with self._lock:
                                    self.project_queues[p.get('project_id')] = now
                    last_reconcile = now
                self.run_reconciliation_cycle()
                time.sleep(0.5)
        finally:
            if inotify_fd >= 0:
                try:
                    os.close(inotify_fd)
                except OSError:
                    pass
            self.running = False
            self.save_state()