"""Agent State Model & Eligibility Determination (Section 39)."""
from __future__ import annotations

import enum
import subprocess
from typing import Any, Dict, List, Optional


class AgentState(str, enum.Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class AgentStateEvaluator:
    """Evaluates agent execution state objectively using bridge/terminal evidence."""

    def __init__(self, tmux_bin: str = "tmux"):
        self.tmux_bin = tmux_bin

    def check_tmux_window_state(self, session: str, window_spec: str) -> AgentState:
        """
        Queries tmux pane status objectively.
        If pane is running a command (not at shell prompt or busy), reports BUSY.
        If session/window does not exist, reports OFFLINE.
        """
        try:
            # Check if session exists
            res = subprocess.run(
                [self.tmux_bin, "has-session", "-t", session],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                return AgentState.OFFLINE

            # List panes and inspect command / child process
            res_panes = subprocess.run(
                [
                    self.tmux_bin,
                    "list-panes",
                    "-t",
                    window_spec,
                    "-F",
                    "#{pane_current_command}:#{pane_pid}:#{pane_dead}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res_panes.returncode != 0:
                return AgentState.OFFLINE

            lines = [l.strip() for l in res_panes.stdout.strip().split("\n") if l.strip()]
            if not lines:
                return AgentState.OFFLINE

            # If any pane is dead or exited
            for line in lines:
                parts = line.split(":")
                cmd = parts[0] if len(parts) > 0 else ""
                is_dead = parts[2] if len(parts) > 2 else "0"
                if is_dead == "1":
                    return AgentState.OFFLINE
                # Active non-shell commands indicate BUSY
                if cmd and cmd not in ("bash", "zsh", "sh", "fish"):
                    return AgentState.BUSY

            return AgentState.IDLE
        except Exception:
            return AgentState.UNKNOWN

    def evaluate_project_agents(
        self,
        project_connections: Dict[str, Any],
        has_in_flight_messages: bool = False,
        mock_override: Optional[AgentState] = None,
    ) -> AgentState:
        """
        Determines composite agent state for a project:
        - If mock_override is provided (e.g. in tests), returns it.
        - If any agent is BUSY -> BUSY.
        - If any agent is UNKNOWN -> UNKNOWN.
        - If OFFLINE: safe only if no terminal/process exists AND no DISPATCHING/IN_FLIGHT message.
        - If IDLE: requires positive evidence from terminal/bridge.
        """
        if mock_override is not None:
            return mock_override

        tmux_info = project_connections.get("tmux", {})
        session = tmux_info.get("session") or "agy"
        windows = tmux_info.get("windows") or []
        if isinstance(windows, str):
            windows = [w.strip() for w in windows.split(",") if w.strip()]

        if not windows:
            # No tmux runtime configured: check in-flight messages
            if has_in_flight_messages:
                return AgentState.BUSY
            return AgentState.OFFLINE

        states: List[AgentState] = []
        for win in windows:
            st = self.check_tmux_window_state(session, win)
            states.append(st)

        if any(s == AgentState.BUSY for s in states):
            return AgentState.BUSY
        if any(s == AgentState.UNKNOWN for s in states):
            return AgentState.UNKNOWN

        # If all offline
        if all(s == AgentState.OFFLINE for s in states):
            if has_in_flight_messages:
                return AgentState.BUSY
            return AgentState.OFFLINE

        # If at least one is IDLE and none are BUSY/UNKNOWN
        if any(s == AgentState.IDLE for s in states):
            if has_in_flight_messages:
                return AgentState.BUSY
            return AgentState.IDLE

        return AgentState.UNKNOWN

    def is_backup_eligible(self, agent_state: AgentState, has_in_flight_messages: bool = False) -> bool:
        """
        Eligibility:
        BUSY -> False
        UNKNOWN -> False
        OFFLINE -> True ONLY WHEN no in-flight messages exist
        IDLE -> True (when not in-flight)
        """
        if has_in_flight_messages:
            return False
        if agent_state == AgentState.BUSY:
            return False
        if agent_state == AgentState.UNKNOWN:
            return False
        if agent_state == AgentState.OFFLINE:
            return True
        if agent_state == AgentState.IDLE:
            return True
        return False
