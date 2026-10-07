"""Configuration loader and schema for GitPush Watcher."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0.0",
    "enabled": True,
    "debounce_seconds": 1.5,
    "max_checkpoint_seconds": 10.0,
    "reconciliation_interval_seconds": 10.0,
    "large_file_threshold_bytes": 52428800,  # 50 MB
    "max_push_retries": 5,
    "base_backoff_seconds": 2.0,
    "ignored_patterns": [
        ".git",
        ".git/*",
        ".git/**",
        "*.lock",
        "*.tmp",
        "__pycache__",
        "__pycache__/*",
        "*.pyc",
        ".pytest_cache",
        ".pytest_cache/*",
        ".project-locks",
        ".project-locks/*",
        "storage/GITPUSH_WATCHER_STATE.json",
        "storage/GITPUSH_WATCHER_STATE.json.lock",
        "storage/GITPUSH_WATCHER_STATE.json.tmp",
        "projects/CLOUD_PARITY_MATRIX.json",
        ".mapping-generator.lock"
    ],
    "ephemeral_patterns": [
        "*.swp",
        "*.swo",
        "*~",
        ".DS_Store"
    ],
    "secret_patterns": [
        ".env.prod",
        ".env.production",
        "id_rsa",
        "id_ecdsa",
        "id_ed25519",
        "*.pem",
        "*.key"
    ],
    "database_extensions": [
        ".db",
        ".sqlite",
        ".sqlite3",
        ".db-wal",
        ".db-shm"
    ]
}


class WatcherConfig:
    def __init__(self, data: Dict[str, Any], root: Path):
        self.root = root
        self.raw = dict(DEFAULT_CONFIG)
        self.raw.update(data)

    @classmethod
    def load(cls, root: Path, custom_path: Path | None = None) -> WatcherConfig:
        config_path = custom_path or (root / "configuration" / "gitpush_watcher.json")
        if config_path.is_file():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                return cls(data, root)
            except Exception:
                pass
        return cls(dict(DEFAULT_CONFIG), root)

    @property
    def debounce_seconds(self) -> float:
        return float(self.raw.get("debounce_seconds", 1.5))

    @debounce_seconds.setter
    def debounce_seconds(self, val: float) -> None:
        self.raw["debounce_seconds"] = float(val)

    @property
    def max_checkpoint_seconds(self) -> float:
        return float(self.raw.get("max_checkpoint_seconds", 10.0))

    @property
    def reconciliation_interval_seconds(self) -> float:
        return float(self.raw.get("reconciliation_interval_seconds", 10.0))

    @reconciliation_interval_seconds.setter
    def reconciliation_interval_seconds(self, val: float) -> None:
        self.raw["reconciliation_interval_seconds"] = float(val)


    @property
    def large_file_threshold_bytes(self) -> int:
        return int(self.raw.get("large_file_threshold_bytes", 52428800))

    @property
    def max_push_retries(self) -> int:
        return int(self.raw.get("max_push_retries", 5))

    @property
    def base_backoff_seconds(self) -> float:
        return float(self.raw.get("base_backoff_seconds", 2.0))

    @property
    def ignored_patterns(self) -> List[str]:
        return list(self.raw.get("ignored_patterns", []))

    @property
    def ephemeral_patterns(self) -> List[str]:
        return list(self.raw.get("ephemeral_patterns", []))

    @property
    def secret_patterns(self) -> List[str]:
        return list(self.raw.get("secret_patterns", []))

    @property
    def database_extensions(self) -> List[str]:
        return list(self.raw.get("database_extensions", []))

    @property
    def state_file(self) -> Path:
        return self.root / "storage" / "GITPUSH_WATCHER_STATE.json"
