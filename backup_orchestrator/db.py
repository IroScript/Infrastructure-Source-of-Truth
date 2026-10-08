"""Durable SQLite Transactional Store & Migration Engine for Backup Orchestrator (Section 37)."""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


CURRENT_SCHEMA_VERSION = 1

SCHEMA_MIGRATIONS = [
    # Version 1 Initial Schema
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS projects_state (
        project_id TEXT PRIMARY KEY,
        project_slug TEXT NOT NULL,
        canonical_path TEXT NOT NULL,
        dirty_generation INTEGER NOT NULL DEFAULT 0,
        last_good_generation INTEGER NOT NULL DEFAULT 0,
        prompt_gate TEXT NOT NULL DEFAULT 'OPEN', -- 'OPEN' or 'CLOSED'
        lifecycle_lock TEXT NOT NULL DEFAULT 'UNLOCKED', -- 'UNLOCKED' or 'LOCKED'
        active_backup_id TEXT,
        last_activity_mono REAL NOT NULL DEFAULT 0.0,
        filesystem_state TEXT NOT NULL DEFAULT 'CLEAN', -- 'CLEAN', 'DIRTY', 'UNKNOWN_DIRTY'
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS held_prompt_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        message_id TEXT NOT NULL UNIQUE,
        routing_target TEXT NOT NULL,
        payload TEXT NOT NULL,
        sequence_num INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'HELD', -- 'HELD', 'DISPATCHING', 'DELIVERED', 'ACKNOWLEDGED'
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects_state(project_id)
    );

    CREATE TABLE IF NOT EXISTS backup_runs (
        backup_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        project_slug TEXT NOT NULL,
        captured_generation INTEGER NOT NULL,
        zip_path TEXT NOT NULL,
        zip_size INTEGER DEFAULT 0,
        zip_sha256 TEXT DEFAULT '',
        zip_md5 TEXT DEFAULT '',
        status TEXT NOT NULL, -- 'CAPTURING', 'LOCAL_VERIFIED', 'UPLOADING', 'GOOD', 'FAILED', 'MUTATION_INVALIDATED'
        mutation_seen INTEGER NOT NULL DEFAULT 0,
        error_message TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        finished_at TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS verified_backups (
        backup_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        project_slug TEXT NOT NULL,
        captured_generation INTEGER NOT NULL,
        remote_path TEXT NOT NULL,
        remote_object_id TEXT DEFAULT '',
        size INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        md5 TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'GOOD', -- 'GOOD', 'PRUNED'
        retention_state TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'PRUNED', 'RETENTION_PENDING'
        created_at TEXT NOT NULL,
        verified_at TEXT NOT NULL,
        deleted_at TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS watcher_health (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        component TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL,
        last_heartbeat REAL NOT NULL,
        details TEXT NOT NULL DEFAULT '{}'
    );

    CREATE INDEX IF NOT EXISTS idx_held_queue_proj_seq ON held_prompt_queue(project_id, sequence_num);
    CREATE INDEX IF NOT EXISTS idx_verified_backups_proj_date ON verified_backups(project_id, verified_at);
    CREATE INDEX IF NOT EXISTS idx_backup_runs_proj_gen ON backup_runs(project_id, captured_generation);
    """
]


class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=15.0,
            isolation_level=None,  # Autocommit mode by default; manual transactions with BEGIN
        )
        conn.row_factory = sqlite3.Row
        # Durable transactional PRAGMA settings appropriate for crash recovery
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=15000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        conn = self.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.cursor()
            yield cur
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """Executes deterministic schema migrations up to CURRENT_SCHEMA_VERSION."""
        conn = self.get_connection()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);"
            )
            cur = conn.cursor()
            cur.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1;")
            row = cur.fetchone()
            current_ver = row[0] if row else 0

            for ver_idx in range(current_ver, CURRENT_SCHEMA_VERSION):
                sql = SCHEMA_MIGRATIONS[ver_idx]
                conn.executescript(sql)
                now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                    (ver_idx + 1, now_str),
                )
        finally:
            conn.close()

    def export_encrypted_backup(self, dst_encrypted_file: Path, key: Optional[str] = None) -> Path:
        """Creates a crash-consistent VACUUM INTO copy of state DB and encrypts it with AES-256-CBC."""
        from storage.backup_data import encrypt_file
        dst_encrypted_file = Path(dst_encrypted_file).resolve()
        dst_encrypted_file.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="sot-db-vacuum-") as tmpdir:
            temp_db = Path(tmpdir) / "snapshot.sqlite"
            conn = self.get_connection()
            try:
                # VACUUM INTO produces an atomic, consistent, defragmented backup
                conn.execute(f"VACUUM INTO '{str(temp_db)}';")
            finally:
                conn.close()

            encrypt_file(temp_db, dst_encrypted_file, key=key)

        return dst_encrypted_file

    def import_encrypted_backup(self, src_encrypted_file: Path, key: Optional[str] = None) -> None:
        """Decrypts and restores the state DB from an encrypted backup."""
        from storage.backup_data import decrypt_file
        src_encrypted_file = Path(src_encrypted_file).resolve()
        if not src_encrypted_file.is_file():
            raise FileNotFoundError(f"Encrypted state file does not exist: {src_encrypted_file}")

        with tempfile.TemporaryDirectory(prefix="sot-db-restore-") as tmpdir:
            temp_db = Path(tmpdir) / "restored.sqlite"
            decrypt_file(src_encrypted_file, temp_db, key=key)

            # Verify sqlite integrity before overwriting
            with sqlite3.connect(f"file:{str(temp_db)}?mode=ro", uri=True) as chk:
                integrity = chk.execute("PRAGMA integrity_check;").fetchone()[0]
                if integrity != "ok":
                    raise ValueError(f"Restored DB failed integrity check: {integrity}")

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            # Replace database atomically
            shutil.copy2(str(temp_db), str(self.db_path))
