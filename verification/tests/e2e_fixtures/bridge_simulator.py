"""
bridge_simulator.py — Opaque-Box WhatsApp Bridge Delivery Broker Simulator.

Implements the permanent ownership model:
- WhatsApp Bridge = SOLE TERMINAL DELIVERY OWNER.
- Backup Orchestrator = ZIP GATE OWNER ONLY.
- Truthful states: RECEIVED, HELD_FOR_ZIP, DELIVERING, DELIVERED, RETRYING, UNCERTAIN, DUPLICATE.
- Strict Head-of-Line FIFO ordering.
- Non-blocking ordinary delivery even when backup daemon is offline.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .tmux_harness import TmuxTestHarness


BANGLA_ZIP_HOLD_NOTICE = (
    "এই project-এর ZIP backup চলছে।\n"
    "আপনার prompt নিরাপদে queued আছে।\n"
    "ZIP capture শেষ হলেই স্বয়ংক্রিয়ভাবে পাঠানো হবে।"
)

BANGLA_ZIP_COMPLETE_NOTICE = "ZIP capture শেষ হয়েছে। অপেক্ষমান prompt পাঠানো হয়েছে।"

BANGLA_RECONNECT_TEMPLATE = "WhatsApp সংযোগ ফিরে এসেছে।\nঅপেক্ষমান {count}টি message আবার processing শুরু হয়েছে।"


class WhatsAppBridgeBroker:
    """
    Simulates the core WhatsApp Bridge delivery broker for opaque-box E2E testing.
    """

    def __init__(
        self,
        db_path: Path,
        tmux_harness: TmuxTestHarness,
        gate_checker: Optional[Callable[[str], Dict[str, Any]]] = None,
        sot_path: Optional[Path] = None,
    ):
        self.db_path = Path(db_path).resolve()
        self.tmux_harness = tmux_harness
        self.gate_checker = gate_checker
        self.sot_path = sot_path
        self.is_network_connected = True
        self.agent_busy_map: Dict[str, bool] = {}
        self.in_flight_locks: Dict[str, bool] = {}
        self.emitted_notifications: List[Dict[str, Any]] = []
        self._seq_counter = 0
        self._lock = threading.Lock()

        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_delivery_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_uuid TEXT NOT NULL,
                    message_id TEXT NOT NULL UNIQUE,
                    target_window TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    sequence_num INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    last_error TEXT DEFAULT ''
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proj_seq ON prompt_delivery_queue(project_uuid, sequence_num);"
            )

    def check_gate(self, project_uuid: str) -> Dict[str, Any]:
        """
        Inspects the ZIP gate for project_uuid.
        Follows the Interface Contract:
        If SOT CLI or daemon fails/is unavailable, default to ALLOW_NOW / ZIP_GATE_OPEN.
        """
        if self.gate_checker:
            try:
                return self.gate_checker(project_uuid)
            except Exception:
                return {"zip_gate": "ZIP_GATE_OPEN", "action": "ALLOW_NOW", "zip_running": False, "zip_pid": None}

        if self.sot_path and self.sot_path.exists():
            try:
                res = subprocess.run(
                    ["python3", str(self.sot_path), "backup-orchestrator", "gate-check", "--project-uuid", project_uuid, "--json"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if res.returncode == 0:
                    return json.loads(res.stdout.strip())
            except Exception:
                pass

        # Fallback contract: ALLOW_NOW
        return {"zip_gate": "ZIP_GATE_OPEN", "action": "ALLOW_NOW", "zip_running": False, "zip_pid": None}

    def receive_whatsapp_prompt(
        self,
        project_uuid: str,
        target_window: str,
        message_id: str,
        prompt_text: str
    ) -> Tuple[str, str]:
        """
        Processes an incoming WhatsApp prompt:
        Returns (action_taken, prompt_state).
        """
        with self._lock:
            self._seq_counter += 1
            seq = self._seq_counter
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            # 1. Deduplication check
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT status FROM prompt_delivery_queue WHERE message_id = ?;", (message_id,))
                existing = cur.fetchone()
                if existing:
                    return ("DUPLICATE_SUPPRESSED", "DUPLICATE")

                # Insert as RECEIVED
                cur.execute(
                    """
                    INSERT INTO prompt_delivery_queue (
                        project_uuid, message_id, target_window, payload, sequence_num, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'RECEIVED', ?, ?);
                    """,
                    (project_uuid, message_id, target_window, prompt_text, seq, now_iso, now_iso)
                )

            # 2. Check network connectivity
            if not self.is_network_connected:
                return ("OFFLINE_QUEUED", "RECEIVED")

            # 3. Check ZIP Gate
            gate_info = self.check_gate(project_uuid)
            gate_state = gate_info.get("zip_gate", "ZIP_GATE_OPEN")

            if gate_state == "ZIP_GATE_CLOSED":
                # Mark HELD_FOR_ZIP
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "UPDATE prompt_delivery_queue SET status = 'HELD_FOR_ZIP', updated_at = ? WHERE message_id = ?;",
                        (now_iso, message_id)
                    )
                # Send Bangla queued notification
                self.emitted_notifications.append({
                    "type": "ZIP_HOLD",
                    "project_uuid": project_uuid,
                    "message_id": message_id,
                    "text": BANGLA_ZIP_HOLD_NOTICE,
                    "timestamp": now_iso
                })
                return ("HELD_FOR_ZIP", "HELD_FOR_ZIP")

            # 4. Check if agent is busy (Native safe queue boundary)
            if self.agent_busy_map.get(target_window, False):
                # Accepted into durable queue without transport rejection
                return ("ACCEPTED_AGENT_BUSY", "RECEIVED")

            # 5. Execute terminal injection (Single Delivery Owner)
            return self._attempt_terminal_delivery(project_uuid, target_window, message_id, prompt_text)

    def _attempt_terminal_delivery(
        self, project_uuid: str, target_window: str, message_id: str, prompt_text: str
    ) -> Tuple[str, str]:
        """Performs atomic delivery to the target tmux terminal."""
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.in_flight_locks[project_uuid] = True
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE prompt_delivery_queue SET status = 'DELIVERING', updated_at = ? WHERE message_id = ?;",
                    (now_iso, message_id)
                )

            success = self.tmux_harness.send_prompt(target_window, prompt_text)
            if success:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "UPDATE prompt_delivery_queue SET status = 'DELIVERED', updated_at = ? WHERE message_id = ?;",
                        (now_iso, message_id)
                    )
                return ("DELIVERED", "DELIVERED")
            else:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        UPDATE prompt_delivery_queue
                        SET status = 'RETRYING', retry_count = retry_count + 1, last_error = 'TARGET_TERMINAL_UNAVAILABLE', updated_at = ?
                        WHERE message_id = ?;
                        """,
                        (now_iso, message_id)
                    )
                return ("RETRYING", "RETRYING")
        finally:
            self.in_flight_locks.pop(project_uuid, None)

    def drain_held_prompts(self, project_uuid: str) -> List[str]:
        """
        Drains all HELD_FOR_ZIP prompts strictly in FIFO order when ZIP finishes.
        """
        delivered_ids: List[str] = []
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT message_id, target_window, payload
                    FROM prompt_delivery_queue
                    WHERE project_uuid = ? AND status = 'HELD_FOR_ZIP'
                    ORDER BY sequence_num ASC;
                    """,
                    (project_uuid,)
                )
                held_items = cur.fetchall()

            for item in held_items:
                m_id = item["message_id"]
                target = item["target_window"]
                payload = item["payload"]
                action, status = self._attempt_terminal_delivery(project_uuid, target, m_id, payload)
                if status == "DELIVERED":
                    delivered_ids.append(m_id)

            if delivered_ids:
                now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.emitted_notifications.append({
                    "type": "ZIP_RELEASE",
                    "project_uuid": project_uuid,
                    "text": BANGLA_ZIP_COMPLETE_NOTICE,
                    "count": len(delivered_ids),
                    "timestamp": now_iso
                })

        return delivered_ids

    def reconnect_network(self) -> int:
        """
        Reconciles missed/waiting messages after network reconnection.
        """
        with self._lock:
            self.is_network_connected = True
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT message_id, project_uuid, target_window, payload FROM prompt_delivery_queue WHERE status = 'RECEIVED' ORDER BY sequence_num ASC;"
                )
                pending = cur.fetchall()

            if pending:
                now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                notice_text = BANGLA_RECONNECT_TEMPLATE.format(count=len(pending))
                self.emitted_notifications.append({
                    "type": "RECONNECT_RECOVERY",
                    "count": len(pending),
                    "text": notice_text,
                    "timestamp": now_iso
                })

            delivered_count = 0
            for item in pending:
                action, status = self._attempt_terminal_delivery(
                    item["project_uuid"], item["target_window"], item["message_id"], item["payload"]
                )
                if status == "DELIVERED":
                    delivered_count += 1

            return delivered_count

    def retry_pending_delivery(self, target_window: Optional[str] = None) -> int:
        """Watchdog: retries RETRYING messages once terminal becomes available."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                if target_window:
                    cur.execute(
                        "SELECT message_id, project_uuid, target_window, payload FROM prompt_delivery_queue WHERE status = 'RETRYING' AND target_window = ? ORDER BY sequence_num ASC;",
                        (target_window,)
                    )
                else:
                    cur.execute(
                        "SELECT message_id, project_uuid, target_window, payload FROM prompt_delivery_queue WHERE status = 'RETRYING' ORDER BY sequence_num ASC;"
                    )
                items = cur.fetchall()

            count = 0
            for item in items:
                action, status = self._attempt_terminal_delivery(
                    item["project_uuid"], item["target_window"], item["message_id"], item["payload"]
                )
                if status == "DELIVERED":
                    count += 1
            return count

    def get_prompt_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Queries stored message state."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM prompt_delivery_queue WHERE message_id = ?;", (message_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def simulate_crash_and_restart(self) -> "WhatsAppBridgeBroker":
        """
        Simulates bridge process crash and restart:
        Reconciles in-flight DELIVERING messages to UNCERTAIN/RETRYING.
        Preserves HELD_FOR_ZIP and RECEIVED messages.
        """
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE prompt_delivery_queue SET status = 'UNCERTAIN', updated_at = ? WHERE status = 'DELIVERING';",
                (now_iso,)
            )

        new_broker = WhatsAppBridgeBroker(
            db_path=self.db_path,
            tmux_harness=self.tmux_harness,
            gate_checker=self.gate_checker,
            sot_path=self.sot_path
        )
        return new_broker
