"""
tmux_harness.py — Dedicated Isolated Tmux Test Harness for E2E Acceptance Suite.

SAFETY INVARIANT:
NEVER inject test messages into agy:0 (active AGY CLI) or production windows agy:3-agy:13.
Only isolated test sessions (e.g. agy_e2e_*) or dedicated test window agy:test are permitted.
"""
from __future__ import annotations

import os
import secrets
import subprocess
import time
from typing import List, Optional, Set


PROTECTED_TARGETS: Set[str] = {
    f"agy:{i}" for i in range(14)
}


class TmuxSafetyViolation(Exception):
    """Raised when a test attempts to target a protected production tmux window."""
    pass


class TmuxTestHarness:
    """
    Manages isolated tmux sessions and windows for non-interfering E2E testing.
    """

    def __init__(self, session_prefix: str = "agy_e2e_test"):
        self.session_prefix = session_prefix
        self.active_sessions: Set[str] = set()

    def assert_target_safety(self, target: str) -> None:
        """Enforces that target is never a protected production window."""
        target_norm = target.strip()
        if target_norm in PROTECTED_TARGETS:
            raise TmuxSafetyViolation(
                f"CRITICAL SAFETY VIOLATION: Attempted to target protected production window '{target}'!"
            )
        if target_norm.startswith("agy:"):
            sub = target_norm.split(":", 1)[1]
            if sub.isdigit() and int(sub) in range(14):
                raise TmuxSafetyViolation(
                    f"CRITICAL SAFETY VIOLATION: Attempted to target protected agy window index '{sub}'!"
                )
            if sub != "test":
                raise TmuxSafetyViolation(
                    f"CRITICAL SAFETY VIOLATION: Only 'agy:test' is permitted on 'agy' session, got '{target}'!"
                )

    def create_isolated_session(self, session_name: Optional[str] = None, window_name: str = "test_term") -> str:
        """Creates an isolated dedicated tmux session for test execution."""
        if not session_name:
            session_name = f"{self.session_prefix}_{secrets.token_hex(4)}"

        target = f"{session_name}:{window_name}"
        self.assert_target_safety(target)

        # Ensure session does not already exist
        subprocess.run(["tmux", "kill-session", "-t", session_name], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        res = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "-n", window_name],
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create tmux test session {session_name}: {res.stderr}")

        self.active_sessions.add(session_name)
        time.sleep(0.05)  # settle
        return target

    def send_prompt(self, target: str, prompt: str) -> bool:
        """
        Injects a prompt into the target terminal using buffer paste + Enter,
        matching the WhatsApp Bridge tmux delivery mechanics.
        """
        self.assert_target_safety(target)
        try:
            # Check target exists
            check = subprocess.run(["tmux", "list-panes", "-t", target], capture_output=True, text=True)
            if check.returncode != 0:
                return False

            if prompt:
                buf_name = f"e2e_buf_{secrets.token_hex(4)}"
                load_cmd = subprocess.run(
                    ["tmux", "set-buffer", "-b", buf_name, "--", prompt],
                    capture_output=True,
                    text=True
                )
                if load_cmd.returncode != 0:
                    return False

                paste_cmd = subprocess.run(
                    ["tmux", "paste-buffer", "-b", buf_name, "-t", target],
                    capture_output=True,
                    text=True
                )
                subprocess.run(["tmux", "delete-buffer", "-b", buf_name], stderr=subprocess.DEVNULL)
                if paste_cmd.returncode != 0:
                    return False

            # Press enter
            enter_cmd = subprocess.run(
                ["tmux", "send-keys", "-t", target, "Enter"],
                capture_output=True,
                text=True
            )
            return enter_cmd.returncode == 0
        except Exception:
            return False

    def capture_pane(self, target: str, lines: int = 100) -> str:
        """Captures visible text from the target tmux pane."""
        self.assert_target_safety(target)
        res = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", target, "-S", f"-{lines}"],
            capture_output=True,
            text=True
        )
        return res.stdout if res.returncode == 0 else ""

    def kill_session(self, session_name: str) -> None:
        """Terminates a test session."""
        if session_name.startswith(self.session_prefix) or session_name == "agy:test":
            subprocess.run(["tmux", "kill-session", "-t", session_name], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            self.active_sessions.discard(session_name)

    def cleanup_all(self) -> None:
        """Cleans up all tracked test sessions."""
        for sess in list(self.active_sessions):
            self.kill_session(sess)
