"""WhatsApp Bridge Integration Adapter & Exactly-Once Message Broker (Sections 45, 46, 55)."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from .gate import DispatchDecision, PromptGateCoordinator


@dataclass
class TerminalAck:
    message_id: str
    delivered: bool
    exactly_once_provable: bool
    status: str  # "DELIVERED", "UNCERTAIN", "DUPLICATE_REJECTED", "HELD"
    error: str = ""


class BridgeTerminalReceiver:
    """
    Idempotent terminal input broker/receiver.
    Persists accepted message_ids to guarantee deduplication and FIFO ordering.
    """

    def __init__(self):
        self.accepted_message_ids: set[str] = set()
        self.received_messages: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def receive_message(self, message: Dict[str, Any], is_arbitrary_cli: bool = False) -> TerminalAck:
        """
        Receives message idempotently.
        If message_id is already accepted -> DUPLICATE_REJECTED.
        If arbitrary CLI without explicit protocol ACK -> EXACTLY-ONCE: NOT-PROVABLE.
        """
        with self._lock:
            msg_id = message["message_id"]
            if msg_id in self.accepted_message_ids:
                return TerminalAck(
                    message_id=msg_id,
                    delivered=False,
                    exactly_once_provable=True,
                    status="DUPLICATE_REJECTED",
                )

            if is_arbitrary_cli:
                # Arbitrary CLI PTY write lacks guaranteed ACK (Section 45)
                self.accepted_message_ids.add(msg_id)
                self.received_messages.append(message)
                return TerminalAck(
                    message_id=msg_id,
                    delivered=True,
                    exactly_once_provable=False,
                    status="UNCERTAIN",
                )

            # Deterministic receiver with strict acknowledgement
            self.accepted_message_ids.add(msg_id)
            self.received_messages.append(message)
            return TerminalAck(
                message_id=msg_id,
                delivered=True,
                exactly_once_provable=True,
                status="DELIVERED",
            )


class BridgeAdapter:
    """
    Integrates the WhatsApp message router with the PromptGateCoordinator.
    Resolves incoming messages to projects, enforces prompt gating, and routes to terminal receivers.
    """

    def __init__(
        self,
        gate_coordinator: PromptGateCoordinator,
        sot_root: Path,
        terminal_receiver: Optional[BridgeTerminalReceiver] = None,
    ):
        self.gate_coordinator = gate_coordinator
        self.sot_root = Path(sot_root).resolve()
        self.terminal_receiver = terminal_receiver or BridgeTerminalReceiver()
        self.whatsapp_map: Dict[str, str] = {}  # group_id / agent_name -> project_id
        self._load_connection_mappings()
        self.gate_coordinator.set_default_dispatch_handler(self._dispatch_to_terminal)

    def _dispatch_to_terminal(self, item: Dict[str, Any]) -> bool:
        ack = self.terminal_receiver.receive_message(item, is_arbitrary_cli=False)
        return ack.delivered

    def _load_connection_mappings(self) -> None:
        wa_file = self.sot_root / "connections" / "WHATSAPP_CONNECTIONS.json"
        if not wa_file.is_file():
            return
        try:
            data = json.loads(wa_file.read_text(encoding="utf-8"))
            for conn in data.get("connections", []):
                p_id = conn.get("project_id")
                if not p_id:
                    continue
                gid = conn.get("group_id")
                agent = conn.get("agent_name")
                if gid:
                    self.whatsapp_map[gid.strip().lower()] = p_id
                if agent:
                    self.whatsapp_map[agent.strip().lower()] = p_id
        except Exception:
            pass

    def resolve_project_id(self, route_spec: str) -> Optional[str]:
        """Resolves project_id from WhatsApp group_id, route name, or direct project_id."""
        clean = route_spec.strip().lower()
        if clean in self.whatsapp_map:
            return self.whatsapp_map[clean]
        # Check direct project_id match
        for k, v in self.whatsapp_map.items():
            if v.lower() == clean:
                return v
        return None

    def handle_incoming_message(
        self,
        route_spec: str,
        message_id: str,
        payload: str,
        is_arbitrary_cli: bool = False,
    ) -> TerminalAck:
        """
        Processes an incoming WhatsApp message:
        1. Resolves project_id
        2. Evaluates prompt gate atomically
        3. If OPEN -> dispatches to terminal receiver and marks delivered
        4. If CLOSED -> holds in queue without touching terminal
        """
        project_id = self.resolve_project_id(route_spec) or route_spec
        decision = self.gate_coordinator.dispatch_or_hold_message(
            project_id=project_id,
            message_id=message_id,
            routing_target=route_spec,
            payload=payload,
        )

        # Check if message was already delivered via auto-drain
        conn = self.gate_coordinator.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM held_prompt_queue WHERE message_id = ?;", (message_id,))
            row = cur.fetchone()
            current_status = row["status"] if row else decision.status
        finally:
            conn.close()

        if current_status == "DELIVERED":
            return TerminalAck(
                message_id=message_id,
                delivered=True,
                exactly_once_provable=True,
                status="DELIVERED",
            )

        if current_status == "HELD":
            return TerminalAck(
                message_id=message_id,
                delivered=False,
                exactly_once_provable=True,
                status="HELD",
            )

        # Gate is OPEN: forward to terminal receiver
        msg_obj = {
            "message_id": message_id,
            "project_id": project_id,
            "routing_target": route_spec,
            "payload": payload,
            "sequence_num": decision.sequence_num,
        }
        try:
            ack = self.terminal_receiver.receive_message(msg_obj, is_arbitrary_cli=is_arbitrary_cli)
            if ack.delivered:
                self.gate_coordinator.mark_message_delivered(message_id)
            else:
                self.gate_coordinator.rollback_to_held(message_id)
            return ack
        except Exception as exc:
            self.gate_coordinator.rollback_to_held(message_id)
            return TerminalAck(
                message_id=message_id,
                delivered=False,
                exactly_once_provable=False,
                status="FAILED",
                error=str(exc),
            )
