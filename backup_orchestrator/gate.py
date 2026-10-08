"""Atomic Prompt Gate & Dispatch Boundary Coordinator (Sections 38, 46)."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from .db import Database


def is_pid_alive(pid: Optional[int]) -> bool:
    """Checks whether a given process ID is actively running on the host system."""
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


@dataclass
class DispatchDecision:
    status: str  # "DISPATCHING" or "HELD"
    message_id: str
    sequence_num: int
    gate_state: str
    project_id: str


class PromptGateCoordinator:
    """
    Coordinates atomic transactions between the WhatsApp/bridge dispatcher and
    the backup orchestrator gate boundary.
    """

    _project_locks: Dict[str, threading.RLock] = {}
    _global_meta_lock = threading.Lock()

    def __init__(self, db: Database):
        self.db = db
        self._dispatch_handlers: Dict[str, Callable[[Dict[str, Any]], bool]] = {}
        self._default_dispatch_handler: Optional[Callable[[Dict[str, Any]], bool]] = None
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensures zip_pid column exists in projects_state and backup_runs."""
        try:
            with self.db.transaction() as cur:
                cur.execute("ALTER TABLE projects_state ADD COLUMN zip_pid INTEGER DEFAULT NULL;")
        except Exception:
            pass
        try:
            with self.db.transaction() as cur:
                cur.execute("ALTER TABLE backup_runs ADD COLUMN zip_pid INTEGER DEFAULT NULL;")
        except Exception:
            pass

    def set_default_dispatch_handler(self, handler: Callable[[Dict[str, Any]], bool]) -> None:
        self._default_dispatch_handler = handler

    def register_dispatch_handler(self, project_id: str, handler: Callable[[Dict[str, Any]], bool]) -> None:
        self._dispatch_handlers[project_id] = handler

    def _get_project_lock(self, project_id: str) -> threading.RLock:
        with self._global_meta_lock:
            if project_id not in self._project_locks:
                self._project_locks[project_id] = threading.RLock()
            return self._project_locks[project_id]

    def register_or_update_project(
        self,
        project_id: str,
        project_slug: str,
        canonical_path: str,
        initial_generation: int = 0,
    ) -> None:
        """Ensures project record exists in projects_state table."""
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO projects_state (
                    project_id, project_slug, canonical_path, dirty_generation,
                    last_good_generation, prompt_gate, lifecycle_lock, updated_at
                ) VALUES (?, ?, ?, ?, 0, 'OPEN', 'UNLOCKED', ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    project_slug=excluded.project_slug,
                    canonical_path=excluded.canonical_path,
                    updated_at=excluded.updated_at;
                """,
                (project_id, project_slug, canonical_path, initial_generation, now_str),
            )

    def dispatch_or_hold_message(
        self,
        project_id: str,
        message_id: str,
        routing_target: str,
        payload: str,
    ) -> DispatchDecision:
        """
        Atomic dispatch boundary for incoming prompts.
        BEGIN transaction / project coordination lock:
        read PROMPT_GATE and existing HELD count
        if OPEN and HELD count == 0: atomically persist message as DISPATCHING, return DISPATCHING
        if CLOSED or HELD count > 0: atomically persist as HELD, return HELD
        COMMIT
        """
        proj_lock = self._get_project_lock(project_id)
        with proj_lock:
            with self.db.transaction() as cur:
                # Ensure project record exists in projects_state to satisfy FOREIGN KEY constraint
                cur.execute(
                    "SELECT prompt_gate, zip_pid FROM projects_state WHERE project_id = ?;",
                    (project_id,),
                )
                row = cur.fetchone()
                now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                if not row:
                    cur.execute(
                        """
                        INSERT INTO projects_state (
                            project_id, project_slug, canonical_path, dirty_generation,
                            last_good_generation, prompt_gate, zip_pid, lifecycle_lock, updated_at
                        ) VALUES (?, ?, ?, 0, 0, 'OPEN', NULL, 'UNLOCKED', ?);
                        """,
                        (project_id, project_id, routing_target or project_id, now_str),
                    )
                    gate_state = "OPEN"
                else:
                    gate_raw = (row["prompt_gate"] or "").upper()
                    zip_pid = row["zip_pid"] if "zip_pid" in row.keys() else None
                    if gate_raw in ("CLOSED", "ZIP_GATE_CLOSED"):
                        if is_pid_alive(zip_pid):
                            gate_state = "CLOSED"
                        else:
                            # Autonomous crash recovery: dead ZIP PID recovers gate immediately
                            cur.execute(
                                """
                                UPDATE projects_state
                                SET prompt_gate = 'OPEN',
                                    lifecycle_lock = 'UNLOCKED',
                                    zip_pid = NULL,
                                    active_backup_id = NULL,
                                    updated_at = ?
                                WHERE project_id = ?;
                                """,
                                (now_str, project_id),
                            )
                            gate_state = "OPEN"
                    else:
                        gate_state = "OPEN"

                # Check if message_id was already received (idempotency check)
                cur.execute(
                    "SELECT status, sequence_num FROM held_prompt_queue WHERE message_id = ?;",
                    (message_id,),
                )
                existing = cur.fetchone()
                if existing:
                    status_to_return = "DUPLICATE_REJECTED" if existing["status"] == "DELIVERED" else existing["status"]
                    return DispatchDecision(
                        status=status_to_return,
                        message_id=message_id,
                        sequence_num=existing["sequence_num"],
                        gate_state=gate_state,
                        project_id=project_id,
                    )

                # Check if there are already held prompts for this project
                cur.execute(
                    "SELECT COUNT(*) FROM held_prompt_queue WHERE project_id = ? AND status = 'HELD';",
                    (project_id,),
                )
                held_count = cur.fetchone()[0]

                # Get next monotonic sequence number for project
                cur.execute(
                    "SELECT COALESCE(MAX(sequence_num), 0) + 1 FROM held_prompt_queue WHERE project_id = ?;",
                    (project_id,),
                )
                seq_num = cur.fetchone()[0]

                # If gate is CLOSED OR there are earlier held prompts, status must be HELD to preserve FIFO sequence
                status = "DISPATCHING" if (gate_state == "OPEN" and held_count == 0) else "HELD"

                cur.execute(
                    """
                    INSERT INTO held_prompt_queue (
                        project_id, message_id, routing_target, payload, sequence_num, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (project_id, message_id, routing_target, payload, seq_num, status, now_str, now_str),
                )

                decision = DispatchDecision(
                    status=status,
                    message_id=message_id,
                    sequence_num=seq_num,
                    gate_state=gate_state,
                    project_id=project_id,
                )

            return decision

    def mark_message_delivered(self, message_id: str) -> None:
        """Marks a DISPATCHING message as DELIVERED upon broker/receiver confirmation."""
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE held_prompt_queue SET status = 'DELIVERED', updated_at = ? WHERE message_id = ?;",
                (now_str, message_id),
            )

    def close_gate(
        self,
        project_id: str,
        zip_pid: Optional[int] = None,
        recheck_agent_callback: Optional[Callable[[], bool]] = None,
        recheck_generation_callback: Optional[Callable[[], int]] = None,
        expected_generation: Optional[int] = None,
    ) -> bool:
        """
        Closes prompt gate atomically.
        1. Acquire project gate lock.
        2. Verify no dispatch transition is in-flight (status='DISPATCHING').
        3. Persist PROMPT_GATE = 'CLOSED' with recorded zip_pid.
        4. Recheck active agent state + filesystem generation.
        5. If agent became BUSY or generation changed, rollback gate to OPEN and return False.
        """
        actual_pid = zip_pid if zip_pid is not None else os.getpid()
        proj_lock = self._get_project_lock(project_id)
        with proj_lock:
            with self.db.transaction() as cur:
                # Check for in-flight dispatching messages
                cur.execute(
                    "SELECT COUNT(*) FROM held_prompt_queue WHERE project_id = ? AND status = 'DISPATCHING';",
                    (project_id,),
                )
                in_flight = cur.fetchone()[0]
                if in_flight > 0:
                    return False  # Message currently crossing boundary

                now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                cur.execute(
                    """
                    INSERT INTO projects_state (
                        project_id, project_slug, canonical_path, dirty_generation,
                        last_good_generation, prompt_gate, zip_pid, lifecycle_lock, updated_at
                    ) VALUES (?, ?, ?, 0, 0, 'CLOSED', ?, 'UNLOCKED', ?)
                    ON CONFLICT(project_id) DO UPDATE SET
                        prompt_gate = 'CLOSED',
                        zip_pid = excluded.zip_pid,
                        updated_at = excluded.updated_at;
                    """,
                    (project_id, project_id, project_id, actual_pid, now_str),
                )

            # Recheck active-agent + filesystem-generation
            if recheck_agent_callback and not recheck_agent_callback():
                self.open_gate(project_id)
                return False

            if recheck_generation_callback and expected_generation is not None:
                current_gen = recheck_generation_callback()
                if current_gen != expected_generation:
                    self.open_gate(project_id)
                    return False

            return True

    def open_gate(self, project_id: str, dispatch_func: Optional[Callable[[Dict[str, Any]], bool]] = None) -> int:
        """Opens prompt gate immediately, clears zip_pid, and drains held prompts in strict FIFO order."""
        proj_lock = self._get_project_lock(project_id)
        with proj_lock:
            now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with self.db.transaction() as cur:
                cur.execute(
                    """
                    INSERT INTO projects_state (
                        project_id, project_slug, canonical_path, dirty_generation,
                        last_good_generation, prompt_gate, zip_pid, lifecycle_lock, updated_at
                    ) VALUES (?, ?, ?, 0, 0, 'OPEN', NULL, 'UNLOCKED', ?)
                    ON CONFLICT(project_id) DO UPDATE SET
                        prompt_gate = 'OPEN',
                        zip_pid = NULL,
                        updated_at = excluded.updated_at;
                    """,
                    (project_id, project_id, project_id, now_str),
                )
            fn = dispatch_func or self._dispatch_handlers.get(project_id) or self._default_dispatch_handler
            if fn:
                return self.release_held_prompts(project_id, fn)
            return 0

    def recover_stale_gate(self, project_id: str, reason: str = "") -> None:
        """
        Autonomous crash recovery for stale closed gate (Sections 12, 24).
        Reopens gate to OPEN, clears zip_pid, unlocks lifecycle_lock,
        and marks any active CAPTURING backup run as FAILED.
        """
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        proj_lock = self._get_project_lock(project_id)
        with proj_lock:
            with self.db.transaction() as cur:
                cur.execute(
                    "SELECT active_backup_id FROM projects_state WHERE project_id = ?;",
                    (project_id,),
                )
                row = cur.fetchone()
                active_b_id = row["active_backup_id"] if row else None
                if active_b_id:
                    cur.execute(
                        """
                        UPDATE backup_runs
                        SET status = 'FAILED', error_message = ?, finished_at = ?
                        WHERE backup_id = ? AND status IN ('CAPTURING', 'LOCKED');
                        """,
                        (f"Interrupted: {reason}", now_str, active_b_id),
                    )
                cur.execute(
                    """
                    UPDATE projects_state
                    SET prompt_gate = 'OPEN',
                        lifecycle_lock = 'UNLOCKED',
                        zip_pid = NULL,
                        active_backup_id = NULL,
                        updated_at = ?
                    WHERE project_id = ?;
                    """,
                    (now_str, project_id),
                )

    def check_gate(self, project_id: str) -> Dict[str, Any]:
        """
        Fast, lightweight gate inspection API (PROJECT.md § Interface Contracts).
        Returns:
            {
                "project_uuid": project_id,
                "zip_gate": "ZIP_GATE_OPEN" | "ZIP_GATE_CLOSED",
                "action": "ALLOW_NOW" | "HOLD_FOR_ZIP",
                "zip_running": bool,
                "zip_pid": int | None,
            }
        Autonomous recovery: If prompt_gate is CLOSED but recorded zip_pid is no longer alive,
        automatically reopens gate, marks interrupted backup FAILED, and returns ALLOW_NOW.
        """
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT prompt_gate, zip_pid FROM projects_state WHERE project_id = ?;",
                (project_id,),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return {
                "project_uuid": project_id,
                "zip_gate": "ZIP_GATE_OPEN",
                "action": "ALLOW_NOW",
                "zip_running": False,
                "zip_pid": None,
            }

        gate_val = (row["prompt_gate"] or "").upper()
        zip_pid = row["zip_pid"] if "zip_pid" in row.keys() else None

        if gate_val in ("CLOSED", "ZIP_GATE_CLOSED"):
            if is_pid_alive(zip_pid):
                return {
                    "project_uuid": project_id,
                    "zip_gate": "ZIP_GATE_CLOSED",
                    "action": "HOLD_FOR_ZIP",
                    "zip_running": True,
                    "zip_pid": zip_pid,
                }
            else:
                self.recover_stale_gate(
                    project_id=project_id,
                    reason=f"Recorded zip_pid {zip_pid} is no longer alive",
                )
                return {
                    "project_uuid": project_id,
                    "zip_gate": "ZIP_GATE_OPEN",
                    "action": "ALLOW_NOW",
                    "zip_running": False,
                    "zip_pid": None,
                }
        return {
            "project_uuid": project_id,
            "zip_gate": "ZIP_GATE_OPEN",
            "action": "ALLOW_NOW",
            "zip_running": False,
            "zip_pid": None,
        }

    def release_held_prompts(
        self,
        project_id: str,
        dispatch_func: Callable[[Dict[str, Any]], bool],
    ) -> int:
        """
        Releases held prompts in strict FIFO order on gate reopen.
        Dispatches one by one, waiting for receiver readiness/acknowledgement.
        """
        proj_lock = self._get_project_lock(project_id)
        released_count = 0
        with proj_lock:
            conn = self.db.get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT id, project_id, message_id, routing_target, payload, sequence_num
                    FROM held_prompt_queue
                    WHERE project_id = ? AND status = 'HELD'
                    ORDER BY sequence_num ASC;
                    """,
                    (project_id,),
                )
                rows = cur.fetchall()
            finally:
                conn.close()

            for row in rows:
                item = {
                    "id": row["id"],
                    "project_id": row["project_id"],
                    "message_id": row["message_id"],
                    "routing_target": row["routing_target"],
                    "payload": row["payload"],
                    "sequence_num": row["sequence_num"],
                }
                # Transition status to DISPATCHING
                now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                with self.db.transaction() as cur:
                    cur.execute(
                        "UPDATE held_prompt_queue SET status = 'DISPATCHING', updated_at = ? WHERE id = ?;",
                        (now_str, item["id"]),
                    )

                # Dispatch through normal receiver mechanism
                try:
                    success = dispatch_func(item)
                except Exception:
                    success = False

                if success:
                    with self.db.transaction() as cur:
                        cur.execute(
                            "UPDATE held_prompt_queue SET status = 'DELIVERED', updated_at = ? WHERE id = ?;",
                            (now_str, item["id"]),
                        )
                    released_count += 1
                else:
                    # Broker/receiver failed: roll back status to HELD so message is retried and does not permanently block close_gate
                    with self.db.transaction() as cur:
                        cur.execute(
                            "UPDATE held_prompt_queue SET status = 'HELD', updated_at = ? WHERE id = ?;",
                            (now_str, item["id"]),
                        )
                    break

        return released_count

    def rollback_to_held(self, message_id: str) -> None:
        """Rolls back a DISPATCHING message to HELD upon broker/receiver delivery failure."""
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE held_prompt_queue SET status = 'HELD', updated_at = ? WHERE message_id = ?;",
                (now_str, message_id),
            )

    def has_in_flight_messages(self, project_id: str) -> bool:
        """Checks if any messages are currently DISPATCHING for the project."""
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM held_prompt_queue WHERE project_id = ? AND status = 'DISPATCHING';",
                (project_id,),
            )
            return cur.fetchone()[0] > 0
        finally:
            conn.close()

    def register_delivery_owner(self, owner_instance_id: str, daemon_pid: int) -> None:
        """
        Deprecated registration stub. SOT is ZIP gate owner only;
        WhatsApp Bridge is the sole delivery owner of terminal transport.
        """
        pass

    def heartbeat_delivery_owner(self, owner_instance_id: str) -> None:
        """Updates daemon heartbeat in delivery_owner_state."""
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            with self.db.transaction() as cur:
                cur.execute(
                    "UPDATE delivery_owner_state SET heartbeat_at = ? WHERE owner_instance_id = ?;",
                    (now_str, owner_instance_id),
                )
        except Exception:
            pass

    def unregister_delivery_owner(self, owner_instance_id: str) -> None:
        """Gracefully unregisters delivery owner on shutdown."""
        try:
            with self.db.transaction() as cur:
                cur.execute(
                    "UPDATE delivery_owner_state SET status = 'SHUTDOWN' WHERE owner_instance_id = ?;",
                    (owner_instance_id,),
                )
        except Exception:
            pass

    def claim_next_held_prompt(
        self, project_id: str, owner_instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Process-safe transactional queue claim (BEGIN IMMEDIATE).
        Strict Head-of-Line FIFO: oldest non-final message blocks subsequent messages.
        """
        proj_lock = self._get_project_lock(project_id)
        with proj_lock:
            with self.db.transaction() as cur:
                # 1. Gate must be OPEN
                cur.execute(
                    "SELECT prompt_gate FROM projects_state WHERE project_id = ?;",
                    (project_id,),
                )
                row_g = cur.fetchone()
                if row_g and row_g["prompt_gate"] != "OPEN":
                    return None

                # 2. Strict head-of-line: if any message for this target is actively in-flight with an owner,
                # no new message may be claimed
                cur.execute(
                    "SELECT COUNT(*) FROM held_prompt_queue WHERE project_id = ? AND status = 'DISPATCHING' AND delivery_owner_instance_id IS NOT NULL AND delivery_owner_instance_id != '';",
                    (project_id,),
                )
                if cur.fetchone()[0] > 0:
                    return None

                # 3. Select oldest eligible message (HELD or unowned DISPATCHING)
                cur.execute(
                    """
                    SELECT id, project_id, message_id, routing_target, payload, sequence_num
                    FROM held_prompt_queue
                    WHERE project_id = ? AND (status = 'HELD' OR (status = 'DISPATCHING' AND (delivery_owner_instance_id IS NULL OR delivery_owner_instance_id = '')))
                    ORDER BY sequence_num ASC
                    LIMIT 1;
                    """,
                    (project_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                # 4. Atomically transition HELD -> DISPATCHING bound to delivery owner
                now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                attempt_id = secrets.token_hex(4)
                cur.execute(
                    """
                    UPDATE held_prompt_queue
                    SET status = 'DISPATCHING',
                        delivery_owner_instance_id = ?,
                        claim_timestamp = ?,
                        attempt_id = ?,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (owner_instance_id, now_str, attempt_id, now_str, row["id"]),
                )
                return {
                    "id": row["id"],
                    "project_id": row["project_id"],
                    "message_id": row["message_id"],
                    "routing_target": row["routing_target"],
                    "payload": row["payload"],
                    "sequence_num": row["sequence_num"],
                    "attempt_id": attempt_id,
                }

    def complete_delivery(self, message_id: str, owner_instance_id: str) -> None:
        """Transitions claimed DISPATCHING prompt to DELIVERED."""
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE held_prompt_queue
                SET status = 'DELIVERED', updated_at = ?
                WHERE message_id = ? AND status = 'DISPATCHING';
                """,
                (now_str, message_id),
            )

    def fail_delivery(
        self, message_id: str, owner_instance_id: str, retryable: bool = True
    ) -> None:
        """
        Transitions DISPATCHING prompt back to HELD (retryable) or FAILED.
        Enforces head-of-line: remaining HELD prompts will wait until this item succeeds.
        """
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        new_status = "HELD" if retryable else "FAILED"
        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE held_prompt_queue
                SET status = ?, retry_count = retry_count + 1, updated_at = ?
                WHERE message_id = ? AND status = 'DISPATCHING';
                """,
                (new_status, now_str, message_id),
            )

    def get_gate_state(self, project_id: str) -> Dict[str, Any]:
        """Returns the current prompt gate state for a project with autonomous recovery."""
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT project_id, prompt_gate, zip_pid, lifecycle_lock, active_backup_id FROM projects_state WHERE project_id = ?;",
                (project_id,),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if row:
            gate_val = (row["prompt_gate"] or "").upper()
            zip_pid = row["zip_pid"] if "zip_pid" in row.keys() else None
            if gate_val in ("CLOSED", "ZIP_GATE_CLOSED") and not is_pid_alive(zip_pid):
                self.recover_stale_gate(project_id, reason=f"Recorded zip_pid {zip_pid} is dead")
                return {
                    "project_id": row["project_id"],
                    "prompt_gate": "OPEN",
                    "lifecycle_lock": "UNLOCKED",
                    "active_backup_id": None,
                    "zip_pid": None,
                }
            return {
                "project_id": row["project_id"],
                "prompt_gate": row["prompt_gate"],
                "lifecycle_lock": row["lifecycle_lock"],
                "active_backup_id": row["active_backup_id"],
                "zip_pid": zip_pid,
            }
        return {
            "project_id": project_id,
            "prompt_gate": "OPEN",
            "lifecycle_lock": "UNLOCKED",
            "active_backup_id": None,
            "zip_pid": None,
        }

