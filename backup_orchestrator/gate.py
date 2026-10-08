"""Atomic Prompt Gate & Dispatch Boundary Coordinator (Sections 38, 46)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from .db import Database


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

    _project_locks: Dict[str, threading.Lock] = {}
    _global_meta_lock = threading.Lock()

    def __init__(self, db: Database):
        self.db = db

    def _get_project_lock(self, project_id: str) -> threading.Lock:
        with self._global_meta_lock:
            if project_id not in self._project_locks:
                self._project_locks[project_id] = threading.Lock()
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
        read PROMPT_GATE
        if OPEN: atomically persist message as DISPATCHING, return DISPATCHING
        if CLOSED: atomically persist as HELD, return HELD
        COMMIT
        """
        proj_lock = self._get_project_lock(project_id)
        with proj_lock:
            with self.db.transaction() as cur:
                # Read current gate state
                cur.execute(
                    "SELECT prompt_gate FROM projects_state WHERE project_id = ?;",
                    (project_id,),
                )
                row = cur.fetchone()
                gate_state = row["prompt_gate"] if row else "OPEN"

                # Get next monotonic sequence number for project
                cur.execute(
                    "SELECT COALESCE(MAX(sequence_num), 0) + 1 FROM held_prompt_queue WHERE project_id = ?;",
                    (project_id,),
                )
                seq_num = cur.fetchone()[0]

                now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                status = "DISPATCHING" if gate_state == "OPEN" else "HELD"

                cur.execute(
                    """
                    INSERT INTO held_prompt_queue (
                        project_id, message_id, routing_target, payload, sequence_num, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (project_id, message_id, routing_target, payload, seq_num, status, now_str, now_str),
                )

                return DispatchDecision(
                    status=status,
                    message_id=message_id,
                    sequence_num=seq_num,
                    gate_state=gate_state,
                    project_id=project_id,
                )

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
        recheck_agent_callback: Optional[Callable[[], bool]] = None,
        recheck_generation_callback: Optional[Callable[[], int]] = None,
        expected_generation: Optional[int] = None,
    ) -> bool:
        """
        Closes prompt gate atomically.
        1. Acquire project gate lock.
        2. Verify no dispatch transition is in-flight (status='DISPATCHING').
        3. Persist PROMPT_GATE = 'CLOSED'.
        4. Recheck active agent state + filesystem generation.
        5. If agent became BUSY or generation changed, rollback gate to OPEN and return False.
        """
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
                    "UPDATE projects_state SET prompt_gate = 'CLOSED', updated_at = ? WHERE project_id = ?;",
                    (now_str, project_id),
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

    def open_gate(self, project_id: str) -> None:
        """Opens prompt gate immediately."""
        proj_lock = self._get_project_lock(project_id)
        with proj_lock:
            now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with self.db.transaction() as cur:
                cur.execute(
                    "UPDATE projects_state SET prompt_gate = 'OPEN', updated_at = ? WHERE project_id = ?;",
                    (now_str, project_id),
                )

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
                    SELECT id, message_id, routing_target, payload, sequence_num
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
                success = dispatch_func(item)
                if success:
                    with self.db.transaction() as cur:
                        cur.execute(
                            "UPDATE held_prompt_queue SET status = 'DELIVERED', updated_at = ? WHERE id = ?;",
                            (now_str, item["id"]),
                        )
                    released_count += 1
                else:
                    # Keep as DISPATCHING or return to HELD if broker failed
                    break

        return released_count

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
