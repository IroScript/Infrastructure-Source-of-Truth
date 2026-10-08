"""Backup Subsystem (Backup Orchestrator) for SOT Baseline.
Implements non-Git runtime decision backup orchestrator with:
- 30-minute quiet interval (monotonic time)
- Atomic prompt gate & dispatch boundary
- Captured generation data correctness
- Durable SQLite WAL state store ($STATE_ROOT/backup_orchestrator/backup_state.sqlite)
- Inotify recursive event tracking with mutation invalidation during ZIP
- Google Drive rclone hash & client-id verification
- Verified GOOD retention transactions (10 newest retained, 11th pruned)
- Crash recovery & non-blocking upload retries
"""
from __future__ import annotations

__version__ = "1.0.0"
