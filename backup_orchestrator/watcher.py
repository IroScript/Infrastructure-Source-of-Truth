"""Recursive Filesystem Watcher & Quiet Interval Manager (Sections 42, 47)."""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import select
import struct
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from .db import Database
from .timekeeping import Clock, RealClock


# Inotify constants
IN_CLOSE_WRITE = 0x00000008
IN_MODIFY = 0x00000002
IN_ATTRIB = 0x00000004
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_Q_OVERFLOW = 0x00004000
IN_IGNORED = 0x00008000
IN_NONBLOCK = 0o0004000
IN_CLOEXEC = 0o2000000

WATCH_MASK = (
    IN_CLOSE_WRITE
    | IN_MODIFY
    | IN_ATTRIB
    | IN_MOVED_FROM
    | IN_MOVED_TO
    | IN_CREATE
    | IN_DELETE
    | IN_DELETE_SELF
    | IN_MOVE_SELF
    | IN_Q_OVERFLOW
)


class ProjectFsWatcher:
    """
    Monitors a project's filesystem recursively:
    - Tracks dirty_generation and monotonic last_activity_mono.
    - Handles inotify queue overflow by marking state UNKNOWN_DIRTY.
    - Supports full deterministic reconciliation.
    """

    def __init__(self, project_id: str, project_root: Path, db: Database, clock: Optional[Clock] = None):
        self.project_id = project_id
        self.project_root = Path(project_root).resolve()
        self.db = db
        self.clock = clock or RealClock()
        self.wd_to_path: Dict[int, str] = {}
        self.path_to_wd: Dict[str, int] = {}
        self.inotify_fd = -1
        self.libc: Optional[ctypes.CDLL] = None
        self._init_libc()

    def _init_libc(self) -> None:
        try:
            libname = ctypes.util.find_library("c") or "libc.so.6"
            self.libc = ctypes.CDLL(libname, use_errno=True)
            self.libc.inotify_init1.argtypes = [ctypes.c_int]
            self.libc.inotify_init1.restype = ctypes.c_int
            self.libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
            self.libc.inotify_add_watch.restype = ctypes.c_int
            self.libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
            self.libc.inotify_rm_watch.restype = ctypes.c_int
        except Exception:
            self.libc = None

    def start_watches(self) -> bool:
        """Installs recursive watches across all directories in project_root."""
        if not self.libc or not self.project_root.is_dir():
            return False

        if self.inotify_fd >= 0:
            self.stop_watches()

        self.inotify_fd = self.libc.inotify_init1(IN_NONBLOCK | IN_CLOEXEC)
        if self.inotify_fd < 0:
            return False

        self._add_watches_recursive(self.project_root)
        return True

    def _add_watches_recursive(self, root_dir: Path) -> None:
        if not self.libc or self.inotify_fd < 0:
            return

        for dirpath, dirnames, _ in os.walk(str(root_dir), followlinks=False):
            # Avoid watching external mounts or symlinked dirs
            p_bytes = dirpath.encode("utf-8")
            wd = self.libc.inotify_add_watch(self.inotify_fd, p_bytes, WATCH_MASK)
            if wd >= 0:
                self.wd_to_path[wd] = dirpath
                self.path_to_wd[dirpath] = wd

    def stop_watches(self) -> None:
        if self.inotify_fd >= 0:
            try:
                os.close(self.inotify_fd)
            except OSError:
                pass
            self.inotify_fd = -1
        self.wd_to_path.clear()
        self.path_to_wd.clear()

    def process_events(self) -> int:
        """
        Reads pending inotify events and updates dirty_generation & quiet timer.
        Returns count of relevant mutations detected.
        """
        if self.inotify_fd < 0:
            return 0

        mutations = 0
        now_mono = self.clock.monotonic()

        while True:
            r, _, _ = select.select([self.inotify_fd], [], [], 0.0)
            if not r:
                break

            try:
                data = os.read(self.inotify_fd, 8192)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                # Descriptor failure
                self._mark_unknown_dirty("INOTIFY_READ_ERROR")
                return mutations

            if not data:
                break

            idx = 0
            while idx + 16 <= len(data):
                wd, mask, cookie, length = struct.unpack_from("iIII", data, idx)
                name = ""
                if length > 0:
                    raw_name = data[idx + 16 : idx + 16 + length]
                    name = raw_name.split(b"\x00", 1)[0].decode("utf-8", "replace")
                idx += 16 + length

                if mask & IN_Q_OVERFLOW:
                    # Inotify queue overflowed (Section 42)
                    self._mark_unknown_dirty("IN_Q_OVERFLOW")
                    return mutations + 1

                # If new directory created or moved in, add watch recursively
                if (mask & (IN_CREATE | IN_MOVED_TO)) and wd in self.wd_to_path and name:
                    full_p = os.path.join(self.wd_to_path[wd], name)
                    if os.path.isdir(full_p) and not os.path.islink(full_p):
                        self._add_watches_recursive(Path(full_p))

                # Relevant mutation events
                if mask & (IN_CLOSE_WRITE | IN_MODIFY | IN_ATTRIB | IN_MOVED_FROM | IN_MOVED_TO | IN_CREATE | IN_DELETE):
                    mutations += 1

        if mutations > 0:
            self.increment_generation(now_mono)

        return mutations

    def increment_generation(self, now_mono: Optional[float] = None) -> int:
        """Increments dirty generation and resets quiet timer."""
        mono_val = now_mono if now_mono is not None else self.clock.monotonic()
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE projects_state
                SET dirty_generation = dirty_generation + 1,
                    last_activity_mono = ?,
                    filesystem_state = CASE WHEN filesystem_state = 'UNKNOWN_DIRTY' THEN 'UNKNOWN_DIRTY' ELSE 'DIRTY' END,
                    updated_at = ?
                WHERE project_id = ?;
                """,
                (mono_val, now_str, self.project_id),
            )
            cur.execute(
                "SELECT dirty_generation FROM projects_state WHERE project_id = ?;",
                (self.project_id,),
            )
            return cur.fetchone()[0]

    def _mark_unknown_dirty(self, reason: str) -> None:
        """Sets filesystem state to UNKNOWN_DIRTY on overflow or watch loss."""
        now_mono = self.clock.monotonic()
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE projects_state
                SET dirty_generation = dirty_generation + 1,
                    last_activity_mono = ?,
                    filesystem_state = 'UNKNOWN_DIRTY',
                    updated_at = ?
                WHERE project_id = ?;
                """,
                (now_mono, now_str, self.project_id),
            )

    def reconcile_filesystem(self) -> None:
        """
        Runs deterministic full reconciliation:
        Re-scans project directory, reinstalls watches, and clears UNKNOWN_DIRTY state.
        """
        self.start_watches()
        now_mono = self.clock.monotonic()
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE projects_state
                SET filesystem_state = 'DIRTY',
                    last_activity_mono = ?,
                    updated_at = ?
                WHERE project_id = ?;
                """,
                (now_mono, now_str, self.project_id),
            )

    def is_quiet_interval_satisfied(self, quiet_interval_seconds: float) -> bool:
        """
        Returns True if monotonic quiet interval >= quiet_interval_seconds AND
        filesystem_state != 'UNKNOWN_DIRTY'.
        """
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT last_activity_mono, filesystem_state, dirty_generation, last_good_generation
                FROM projects_state
                WHERE project_id = ?;
                """,
                (self.project_id,),
            )
            row = cur.fetchone()
            if not row:
                return False

            if row["filesystem_state"] == "UNKNOWN_DIRTY":
                return False  # Overflow or event gap prevents quiet status

            if row["dirty_generation"] <= row["last_good_generation"]:
                return False  # Already backed up

            last_act = row["last_activity_mono"]
            current_mono = self.clock.monotonic()
            elapsed = current_mono - last_act
            return elapsed >= quiet_interval_seconds
        finally:
            conn.close()
