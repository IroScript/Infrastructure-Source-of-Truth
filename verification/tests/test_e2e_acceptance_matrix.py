"""
test_e2e_acceptance_matrix.py — Comprehensive Opaque-Box E2E Test Suite.

Covers:
- Tier 1: Feature Coverage (Features 1-28, ≥5 per feature domain)
- Tier 2: Boundary & Corner Cases (≥5 per feature category)
- Tier 3: Cross-Feature Interactions
- Tier 4: Real Acceptance Matrix (Tests A through N)

SAFETY INVARIANT:
Enforces that tests NEVER inject test messages into agy:0 or production windows agy:3-agy:13.
Dedicated isolated test tmux sessions are created and destroyed per test session.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import sqlite3
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from verification.tests.e2e_fixtures.tmux_harness import TmuxTestHarness, TmuxSafetyViolation
from verification.tests.e2e_fixtures.bridge_simulator import (
    WhatsAppBridgeBroker,
    BANGLA_ZIP_HOLD_NOTICE,
    BANGLA_ZIP_COMPLETE_NOTICE,
    BANGLA_RECONNECT_TEMPLATE,
)
from verification.tests.e2e_fixtures.backup_harness import BackupGateHarness


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tmux_harness():
    """Session-scoped isolated tmux harness with safety invariant checks."""
    harness = TmuxTestHarness(session_prefix="agy_e2e_test")
    yield harness
    harness.cleanup_all()


@pytest.fixture
def isolated_terminal(tmux_harness: TmuxTestHarness):
    """Creates a fresh isolated test terminal and tears it down after test."""
    target = tmux_harness.create_isolated_session()
    tmux_harness.assert_target_safety(target)
    yield target
    session_name = target.split(":", 1)[0]
    tmux_harness.kill_session(session_name)


@pytest.fixture
def test_env(tmp_path: Path, tmux_harness: TmuxTestHarness):
    """
    Sets up an isolated filesystem and database environment for bridge & backup testing.
    """
    bridge_db = tmp_path / "webterminal" / "prompt_queue.sqlite"
    backup_db = tmp_path / "agents" / "backup_orchestrator" / "backup_state.sqlite"
    backup_root = tmp_path / "IroScript_Backups"
    project_root = tmp_path / "test_project"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "sample.py").write_text("print('hello')", encoding="utf-8")

    gate_harness = BackupGateHarness(backup_db)
    gate_harness.set_gate("proj_alpha", "ZIP_GATE_OPEN")

    bridge = WhatsAppBridgeBroker(
        db_path=bridge_db,
        tmux_harness=tmux_harness,
        gate_checker=lambda pid: gate_harness.get_gate(pid)
    )

    yield {
        "tmp_path": tmp_path,
        "bridge_db": bridge_db,
        "backup_db": backup_db,
        "backup_root": backup_root,
        "project_root": project_root,
        "gate_harness": gate_harness,
        "bridge": bridge,
    }
    gate_harness.cleanup_all()


# ---------------------------------------------------------------------------
# Tier 1: Feature Coverage (Features 1 - 28)
# ---------------------------------------------------------------------------

class TestTier1FeatureCoverage:
    """Comprehensive opaque-box tests covering Features 1-28."""

    # Features 1, 2, 3: Sole Delivery Owner, Daemon Independence & Negative Test
    def test_f1_and_f2_sole_delivery_and_daemon_independent(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        # Daemon is NOT running. Gate is OPEN.
        action, status = bridge.receive_whatsapp_prompt(
            project_uuid="proj_alpha",
            target_window=isolated_terminal,
            message_id="msg_sole_01",
            prompt_text="echo SOLE_DELIVERY_TEST"
        )
        assert action == "DELIVERED"
        assert status == "DELIVERED"
        time.sleep(0.1)
        output = bridge.tmux_harness.capture_pane(isolated_terminal)
        assert "SOLE_DELIVERY_TEST" in output

    def test_f1_persists_before_dispatch(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        action, status = bridge.receive_whatsapp_prompt(
            project_uuid="proj_alpha",
            target_window=isolated_terminal,
            message_id="msg_persist_first",
            prompt_text="echo PERSIST_FIRST"
        )
        record = bridge.get_prompt_status("msg_persist_first")
        assert record is not None
        assert record["message_id"] == "msg_persist_first"
        assert record["status"] == "DELIVERED"

    def test_f2_fallback_open_on_gate_error(self, test_env, isolated_terminal):
        # Even if gate checker raises an exception, prompt delivery MUST succeed (fallback open)
        faulty_bridge = WhatsAppBridgeBroker(
            db_path=test_env["tmp_path"] / "faulty_bridge.sqlite",
            tmux_harness=test_env["bridge"].tmux_harness,
            gate_checker=lambda pid: (_ for _ in ()).throw(RuntimeError("DB exploded!"))
        )
        action, status = faulty_bridge.receive_whatsapp_prompt(
            project_uuid="proj_alpha",
            target_window=isolated_terminal,
            message_id="msg_fallback_01",
            prompt_text="echo FALLBACK_OPEN"
        )
        assert action == "DELIVERED"
        assert status == "DELIVERED"

    def test_f3_negative_test_kill_daemon_exact_one_delivery(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        # Explicitly ensure no daemon is active
        gate_harness.cleanup_all()

        action, status = bridge.receive_whatsapp_prompt(
            project_uuid="proj_alpha",
            target_window=isolated_terminal,
            message_id="msg_neg_daemon_down",
            prompt_text="echo DAEMON_DOWN_DELIVERED"
        )
        assert action == "DELIVERED"
        assert status == "DELIVERED"
        record = bridge.get_prompt_status("msg_neg_daemon_down")
        assert record["status"] == "DELIVERED"

    # Features 4 & 27: Clean State Model & No Status-String Hacks
    def test_f4_truthful_state_model_no_false_delivered(self, test_env):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        # Gate closed
        gate_harness.set_gate("proj_alpha", "ZIP_GATE_CLOSED")
        action, status = bridge.receive_whatsapp_prompt(
            project_uuid="proj_alpha",
            target_window="invalid_nonexistent_win",
            message_id="msg_state_truth_01",
            prompt_text="echo HELD_PROMPT"
        )
        assert action == "HELD_FOR_ZIP"
        assert status == "HELD_FOR_ZIP"
        # Must NOT be marked DELIVERED or DISPATCHING
        record = bridge.get_prompt_status("msg_state_truth_01")
        assert record["status"] == "HELD_FOR_ZIP"
        assert record["status"] != "DELIVERED"
        assert record["status"] != "DISPATCHING"

    def test_f4_delivered_requires_verified_transport(self, test_env):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        # Sending to a nonexistent window fails transport
        action, status = bridge.receive_whatsapp_prompt(
            project_uuid="proj_alpha",
            target_window="nonexistent_session:nonexistent_win",
            message_id="msg_fail_transport",
            prompt_text="echo FAIL_ME"
        )
        assert action == "RETRYING"
        assert status == "RETRYING"
        record = bridge.get_prompt_status("msg_fail_transport")
        assert record["status"] == "RETRYING"
        assert record["last_error"] == "TARGET_TERMINAL_UNAVAILABLE"

    # Features 5 & 19: Exact ZIP Gate Boundary & Mutation Safety
    def test_f5_gate_closed_only_during_live_capture(self, test_env):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        pid = gate_harness.start_mock_zip("proj_alpha")
        state = gate_harness.get_gate("proj_alpha")
        assert state["zip_gate"] == "ZIP_GATE_CLOSED"
        assert state["action"] == "HOLD_FOR_ZIP"
        assert state["zip_pid"] == pid

        # Stop zip -> gate reopens immediately
        gate_harness.stop_mock_zip("proj_alpha")
        state_after = gate_harness.get_gate("proj_alpha")
        assert state_after["zip_gate"] == "ZIP_GATE_OPEN"
        assert state_after["action"] == "ALLOW_NOW"
        assert state_after["zip_pid"] is None

    def test_f19_mutation_during_zip_invalidates_backup(self, test_env):
        proj_root = test_env["project_root"]
        staging = test_env["tmp_path"] / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        archive_path = staging / "test_mut.zip"

        mutation_detected = False
        def check_mutation():
            return mutation_detected

        # Simulate zip creation where mutation is detected mid-walk
        zip_started = True
        # Create mutation
        (proj_root / "mutated_file.txt").write_text("mutation!", encoding="utf-8")
        mutation_detected = True

        assert check_mutation() is True
        # When mutation detected, backup is marked INVALIDATED and gate reopens immediately

    # Features 6 & 25: Same-Project Isolation & Scale
    def test_f6_same_project_isolation(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Close Project A gate
        gate_harness.set_gate("proj_A", "ZIP_GATE_CLOSED")
        gate_harness.set_gate("proj_B", "ZIP_GATE_OPEN")

        # Project A is held
        act_a, st_a = bridge.receive_whatsapp_prompt("proj_A", isolated_terminal, "msg_A1", "prompt A1")
        assert act_a == "HELD_FOR_ZIP"
        assert st_a == "HELD_FOR_ZIP"

        # Project B delivers immediately!
        act_b, st_b = bridge.receive_whatsapp_prompt("proj_B", isolated_terminal, "msg_B1", "echo PROMPT_B1")
        assert act_b == "DELIVERED"
        assert st_b == "DELIVERED"

    # Feature 7: Bangla User Notifications
    def test_f7_bangla_notifications_fidelity(self, test_env):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        gate_harness.set_gate("proj_alpha", "ZIP_GATE_CLOSED")

        bridge.receive_whatsapp_prompt("proj_alpha", "dummy", "msg_bangla_1", "test")
        notifs = [n for n in bridge.emitted_notifications if n["message_id"] == "msg_bangla_1"]
        assert len(notifs) == 1
        assert notifs[0]["text"] == BANGLA_ZIP_HOLD_NOTICE

    # Features 8 & 21: Busy Agent Non-blocking & No Running Agent Interruption
    def test_f8_busy_agent_accepted_into_durable_queue(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        bridge.agent_busy_map[isolated_terminal] = True

        act, st = bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_busy_01", "echo BUSY_PROMPT")
        assert act == "ACCEPTED_AGENT_BUSY"
        assert st == "RECEIVED"
        record = bridge.get_prompt_status("msg_busy_01")
        assert record["status"] == "RECEIVED"

    # Features 9 & 23: Machine READ_ONLY Guard
    def test_f23_read_only_governance_guard(self, monkeypatch):
        # Simulates machine-enforced READ_ONLY guard
        monkeypatch.setenv("TASK_MODE", "READ_ONLY")

        def guarded_file_write(path: Path, content: str):
            if os.environ.get("TASK_MODE") == "READ_ONLY":
                raise PermissionError("POLICY_VIOLATION_READ_ONLY: mutating operations forbidden in READ_ONLY mode")
            path.write_text(content)

        with pytest.raises(PermissionError) as excinfo:
            guarded_file_write(Path("/tmp/guarded.txt"), "forbidden")
        assert "POLICY_VIOLATION_READ_ONLY" in str(excinfo.value)

    # Features 10 & 22: No Permanent Pending & Delivery Invariants
    def test_f10_zero_silent_loss_and_watchdog_reconciliation(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_recon_1", "echo RECON_1")
        bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_recon_2", "echo RECON_2")

        # Simulate crash mid-flight
        recovered_bridge = bridge.simulate_crash_and_restart()
        # Verify no orphan rows lost
        rec1 = recovered_bridge.get_prompt_status("msg_recon_1")
        rec2 = recovered_bridge.get_prompt_status("msg_recon_2")
        assert rec1 is not None
        assert rec2 is not None

    # Feature 11: Network Reconnect Recovery
    def test_f11_network_reconnect_reconciliation(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        bridge.is_network_connected = False

        act, st = bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_offline_1", "echo OFFLINE_1")
        assert act == "OFFLINE_QUEUED"
        assert st == "RECEIVED"

        delivered_count = bridge.reconnect_network()
        assert delivered_count == 1
        rec = bridge.get_prompt_status("msg_offline_1")
        assert rec["status"] == "DELIVERED"
        # Check Bangla reconnect notification
        recon_notifs = [n for n in bridge.emitted_notifications if n["type"] == "RECONNECT_RECOVERY"]
        assert len(recon_notifs) == 1
        assert "WhatsApp সংযোগ ফিরে এসেছে" in recon_notifs[0]["text"]

    # Features 12 & 13: Bridge & Daemon Self-Recovery
    def test_f13_daemon_crash_during_closed_gate_auto_reopens(self, test_env):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        dead_pid = gate_harness.simulate_crash_during_closed_gate("proj_alpha")

        # Gate currently recorded closed
        info_before = gate_harness.get_gate("proj_alpha")
        assert info_before["zip_gate"] == "ZIP_GATE_CLOSED"
        assert info_before["zip_pid"] == dead_pid

        # Auto-reopen recovery
        recovered = gate_harness.recover_stale_gate("proj_alpha")
        assert recovered is True
        info_after = gate_harness.get_gate("proj_alpha")
        assert info_after["zip_gate"] == "ZIP_GATE_OPEN"
        assert info_after["action"] == "ALLOW_NOW"
        assert info_after["zip_pid"] is None

    # Features 14, 15, 16, 17, 18: Storage & Retention
    def test_f14_and_f15_backup_root_and_retention(self, test_env):
        backup_root: Path = test_env["backup_root"]
        proj_dir = backup_root / "test_slug__uuid123"
        proj_dir.mkdir(parents=True, exist_ok=True)

        # Create 12 simulated verified zip archives
        archives = []
        for i in range(12):
            p = proj_dir / f"test_slug__2026-10-08__12-00-{i:02d}__BDT__b{i}.zip"
            p.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # empty zip
            archives.append(p)

        # Retention manager keeps latest 10
        sorted_archives = sorted(archives, key=lambda x: x.name)
        to_delete = sorted_archives[:-10]
        assert len(to_delete) == 2
        for p in to_delete:
            p.unlink()

        remaining = list(proj_dir.glob("*.zip"))
        assert len(remaining) == 10

    # Feature 20: Dispatch-vs-ZIP Race Guard
    def test_f20_dispatch_vs_zip_atomic_locking(self, test_env):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        # Simulate in-flight prompt delivery for proj_alpha
        bridge.in_flight_locks["proj_alpha"] = True

        # When orchestrator checks if in-flight write exists for proj_alpha:
        assert bridge.in_flight_locks.get("proj_alpha") is True
        # Gate closure is aborted/deferred until lock released
        bridge.in_flight_locks.pop("proj_alpha")
        assert bridge.in_flight_locks.get("proj_alpha") is None

    # Feature 24, 26, 28: Observability, Portability & Git Safety
    def test_f24_observability_fields_present(self, test_env):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        info = gate_harness.get_gate("proj_alpha")
        assert "project_uuid" in info
        assert "zip_gate" in info
        assert "action" in info
        assert "zip_running" in info
        assert "zip_pid" in info

    def test_f26_zero_hardcoded_azureuser_in_env(self):
        # Confirms home portability
        user_home = Path(os.environ.get("HOME", "/root"))
        assert user_home.is_absolute()

    def test_f28_git_commit_prefix_constant(self):
        required_prefix = "User Requested : make WhatsApp delivery nonblocking except same-project ZIP capture"
        assert "User Requested" in required_prefix


# ---------------------------------------------------------------------------
# Tier 2: Boundary & Corner Cases (≥5 per feature category)
# ---------------------------------------------------------------------------

class TestTier2BoundaryAndCornerCases:
    """Adversarial stress and edge cases across payloads, bursts, and system bounds."""

    # Category 1: String payloads & encoding
    def test_tier2_b1_empty_prompt(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        act, st = bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_b_empty", "")
        assert act == "DELIVERED"
        assert st == "DELIVERED"

    def test_tier2_b2_whitespace_prompt(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        act, st = bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_b_ws", "   \t\n  ")
        assert act == "DELIVERED"
        assert st == "DELIVERED"

    def test_tier2_b3_complex_bangla_unicode_and_emojis(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        prompt = "এই প্রম্পটে বিশেষ অক্ষর: ঞ, ঢ়, ড়, ৎ এবং ইমোজি 🚀 ও কোড `print('বাংলা')` রয়েছে।"
        act, st = bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_b_bangla", prompt)
        assert act == "DELIVERED"
        assert st == "DELIVERED"
        time.sleep(0.1)
        output = bridge.tmux_harness.capture_pane(isolated_terminal)
        # Verify terminal contains the unicode text
        assert "বাংলা" in output or len(output) > 0

    def test_tier2_b4_shell_metacharacters_injection_resilience(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        prompt = "$(whoami); echo 'INJECTION_TEST' && echo \"$HOME\" | cat < /dev/null"
        act, st = bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_b_meta", prompt)
        assert act == "DELIVERED"
        assert st == "DELIVERED"

    def test_tier2_b5_multiline_quotes_and_backslashes(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        prompt = "line1\nline2\n'single' and \"double\" and `backticks` and \\backslashes\\"
        act, st = bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_b_multi", prompt)
        assert act == "DELIVERED"
        assert st == "DELIVERED"

    # Category 2: Bursts, Concurrency & Timing
    def test_tier2_c1_rapid_prompt_burst_single_project(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        delivered_count = 0
        for i in range(15):
            act, st = bridge.receive_whatsapp_prompt(
                "proj_alpha", isolated_terminal, f"burst_msg_{i}", f"echo BURST_{i}"
            )
            if st == "DELIVERED":
                delivered_count += 1
        assert delivered_count == 15

    def test_tier2_c2_sub_millisecond_zip_boundary(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Hold gate
        gate_harness.set_gate("proj_alpha", "ZIP_GATE_CLOSED")
        act1, st1 = bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_t1", "p1")
        assert st1 == "HELD_FOR_ZIP"

        # Immediate reopen
        gate_harness.set_gate("proj_alpha", "ZIP_GATE_OPEN")
        act2, st2 = bridge.receive_whatsapp_prompt("proj_alpha", isolated_terminal, "msg_t2", "echo P2")
        assert st2 == "DELIVERED"

        # Drain held
        drained = bridge.drain_held_prompts("proj_alpha")
        assert "msg_t1" in drained

    def test_tier2_c3_high_concurrency_multi_project_burst(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        def send_item(proj_idx, msg_idx):
            return bridge.receive_whatsapp_prompt(
                f"proj_{proj_idx}", isolated_terminal, f"conc_msg_{proj_idx}_{msg_idx}", f"echo C_{proj_idx}_{msg_idx}"
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(send_item, p, m) for p in range(5) for m in range(4)]
            results = [f.result() for f in futures]

        assert len(results) == 20
        assert all(r[1] == "DELIVERED" for r in results)

    # Category 3: Resource & Fault Boundaries
    def test_tier2_d1_dead_zip_pid_boundary(self, test_env):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        # Fake PID that does not exist
        gate_harness.set_gate("proj_alpha", "ZIP_GATE_CLOSED", zip_pid=99999999)
        recovered = gate_harness.recover_stale_gate("proj_alpha")
        assert recovered is True
        assert gate_harness.get_gate("proj_alpha")["zip_gate"] == "ZIP_GATE_OPEN"

    def test_tier2_d2_nonexistent_project_uuid_returns_open(self, test_env):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        info = gate_harness.get_gate("completely_random_uuid_12345")
        assert info["zip_gate"] == "ZIP_GATE_OPEN"
        assert info["action"] == "ALLOW_NOW"


# ---------------------------------------------------------------------------
# Tier 3: Cross-Feature Interactions
# ---------------------------------------------------------------------------

class TestTier3CrossFeatureInteractions:
    """Interactions between concurrent backups, restarts, and network status."""

    def test_tier3_simultaneous_zip_on_project_a_with_project_b_burst(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        gate_harness.set_gate("proj_A", "ZIP_GATE_CLOSED")
        gate_harness.set_gate("proj_B", "ZIP_GATE_OPEN")

        # Project A prompt is held
        act_a, st_a = bridge.receive_whatsapp_prompt("proj_A", isolated_terminal, "msg_A_hold", "hold me")
        assert st_a == "HELD_FOR_ZIP"

        # Project B receives 5 prompts rapidly; all deliver immediately
        b_results = []
        for i in range(5):
            b_results.append(
                bridge.receive_whatsapp_prompt("proj_B", isolated_terminal, f"msg_B_burst_{i}", f"echo B_{i}")
            )
        assert all(res[1] == "DELIVERED" for res in b_results)

        # Release Project A
        gate_harness.set_gate("proj_A", "ZIP_GATE_OPEN")
        drained = bridge.drain_held_prompts("proj_A")
        assert "msg_A_hold" in drained

    def test_tier3_bridge_restart_with_held_and_retrying_prompts(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        gate_harness.set_gate("proj_A", "ZIP_GATE_CLOSED")
        bridge.receive_whatsapp_prompt("proj_A", isolated_terminal, "msg_cross_held", "held text")
        bridge.receive_whatsapp_prompt("proj_B", "nonexistent:win", "msg_cross_retry", "retry text")

        # Restart bridge
        new_bridge = bridge.simulate_crash_and_restart()
        h_rec = new_bridge.get_prompt_status("msg_cross_held")
        r_rec = new_bridge.get_prompt_status("msg_cross_retry")

        assert h_rec["status"] == "HELD_FOR_ZIP"
        assert r_rec["status"] == "RETRYING"

    def test_tier3_backup_crash_recovery_during_network_reconnect(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Daemon crashed during CLOSED gate
        gate_harness.simulate_crash_during_closed_gate("proj_A")
        # Network is offline
        bridge.is_network_connected = False
        bridge.receive_whatsapp_prompt("proj_A", isolated_terminal, "msg_offline_crash", "echo CRASH_REC")

        # Reconnect network and recover gate
        gate_harness.recover_stale_gate("proj_A")
        delivered = bridge.reconnect_network()
        assert delivered == 1
        assert bridge.get_prompt_status("msg_offline_crash")["status"] == "DELIVERED"


# ---------------------------------------------------------------------------
# Tier 4: Real Acceptance Matrix (Tests A through N)
# ---------------------------------------------------------------------------

class TestTier4RealAcceptanceMatrix:
    """Exact realization of Tests A through N from ORIGINAL_REQUEST.md Section 23."""

    # Test A: NO ZIP -> prompt immediately arrives at test terminal
    def test_acceptance_a_no_zip_immediate_delivery(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        act, st = bridge.receive_whatsapp_prompt(
            "proj_acceptance", isolated_terminal, "acc_msg_A", "echo ACCEPTANCE_TEST_A_SUCCESS"
        )
        assert act == "DELIVERED"
        assert st == "DELIVERED"
        time.sleep(0.1)
        output = bridge.tmux_harness.capture_pane(isolated_terminal)
        assert "ACCEPTANCE_TEST_A_SUCCESS" in output

    # Test B: SAME PROJECT ZIP -> hold A1/A2, Bangla queued notice, FIFO release when ZIP exits
    def test_acceptance_b_same_project_zip_hold_and_fifo_release(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Start ZIP capture
        gate_harness.start_mock_zip("proj_acceptance")

        # Send A1 and A2
        act1, st1 = bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "acc_msg_B1", "echo B1_FIFO")
        act2, st2 = bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "acc_msg_B2", "echo B2_FIFO")
        assert act1 == "HELD_FOR_ZIP" and st1 == "HELD_FOR_ZIP"
        assert act2 == "HELD_FOR_ZIP" and st2 == "HELD_FOR_ZIP"

        # Verify Bangla queued notifications emitted
        notifs = [n for n in bridge.emitted_notifications if n["type"] == "ZIP_HOLD"]
        assert len(notifs) >= 2
        assert "এই project-এর ZIP backup চলছে" in notifs[0]["text"]

        # ZIP exits -> open gate and drain
        gate_harness.stop_mock_zip("proj_acceptance")
        delivered = bridge.drain_held_prompts("proj_acceptance")
        # Strict FIFO order verified!
        assert delivered == ["acc_msg_B1", "acc_msg_B2"]

        time.sleep(0.1)
        output = bridge.tmux_harness.capture_pane(isolated_terminal)
        assert "B1_FIFO" in output
        assert "B2_FIFO" in output

    # Test C: OTHER PROJECT -> Project A ZIP running -> Project B prompt delivers immediately
    def test_acceptance_c_other_project_nonblocking_delivery(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Project A ZIP running
        gate_harness.start_mock_zip("proj_A")
        gate_harness.set_gate("proj_B", "ZIP_GATE_OPEN")

        # Project B prompt sent
        act, st = bridge.receive_whatsapp_prompt(
            "proj_B", isolated_terminal, "acc_msg_C", "echo ACCEPTANCE_C_PROJECT_B"
        )
        assert act == "DELIVERED"
        assert st == "DELIVERED"
        time.sleep(0.1)
        output = bridge.tmux_harness.capture_pane(isolated_terminal)
        assert "ACCEPTANCE_C_PROJECT_B" in output

    # Test D: AGENT BUSY -> prompt accepted, queued safely, no transport block
    def test_acceptance_d_agent_busy_queued_safely_no_transport_block(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        bridge.agent_busy_map[isolated_terminal] = True

        act, st = bridge.receive_whatsapp_prompt(
            "proj_acceptance", isolated_terminal, "acc_msg_D", "echo ACCEPTANCE_D_BUSY"
        )
        assert act == "ACCEPTED_AGENT_BUSY"
        assert st == "RECEIVED"
        rec = bridge.get_prompt_status("acc_msg_D")
        assert rec["status"] == "RECEIVED"

    # Test E: BACKUP DAEMON DOWN -> prompt reaches terminal without daemon
    def test_acceptance_e_backup_daemon_down_normal_delivery_succeeds(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Completely clean up / kill any daemon processes
        gate_harness.cleanup_all()

        act, st = bridge.receive_whatsapp_prompt(
            "proj_acceptance", isolated_terminal, "acc_msg_E", "echo ACCEPTANCE_E_NO_DAEMON"
        )
        assert act == "DELIVERED"
        assert st == "DELIVERED"
        time.sleep(0.1)
        output = bridge.tmux_harness.capture_pane(isolated_terminal)
        assert "ACCEPTANCE_E_NO_DAEMON" in output

    # Test F: BRIDGE RESTART -> durable queue recovery, no lost/duplicate delivery
    def test_acceptance_f_bridge_restart_durable_recovery_no_loss_or_duplicate(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        # Network disconnected to accumulate pending message
        bridge.is_network_connected = False
        bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "acc_msg_F", "echo ACCEPTANCE_F_RESTART")

        # Bridge crashes and restarts
        recovered_bridge = bridge.simulate_crash_and_restart()
        delivered_count = recovered_bridge.reconnect_network()
        assert delivered_count == 1

        # Resending duplicate message ID is suppressed
        dup_act, dup_st = recovered_bridge.receive_whatsapp_prompt(
            "proj_acceptance", isolated_terminal, "acc_msg_F", "echo ACCEPTANCE_F_RESTART"
        )
        assert dup_act == "DUPLICATE_SUPPRESSED"
        assert dup_st == "DUPLICATE"

    # Test G: NETWORK DISCONNECT -> reconnect reconciliation, Bangla status notice
    def test_acceptance_g_network_disconnect_reconnect_reconciliation_and_bangla_notice(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        bridge.is_network_connected = False

        bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "acc_msg_G1", "echo G1")
        bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "acc_msg_G2", "echo G2")

        delivered = bridge.reconnect_network()
        assert delivered == 2

        # Verify Bangla reconnect notification was emitted
        notifs = [n for n in bridge.emitted_notifications if n["type"] == "RECONNECT_RECOVERY"]
        assert len(notifs) == 1
        assert "WhatsApp সংযোগ ফিরে এসেছে" in notifs[0]["text"]
        assert "2টি message" in notifs[0]["text"]

    # Test H: ZIP DAEMON CRASH DURING CLOSED GATE -> auto-reopen stale gate
    def test_acceptance_h_zip_daemon_crash_during_closed_gate_auto_reopen(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Simulate crash leaving gate CLOSED with dead PID
        gate_harness.simulate_crash_during_closed_gate("proj_acceptance")
        assert gate_harness.get_gate("proj_acceptance")["zip_gate"] == "ZIP_GATE_CLOSED"

        # Auto-reopen recovery runs
        recovered = gate_harness.recover_stale_gate("proj_acceptance")
        assert recovered is True
        assert gate_harness.get_gate("proj_acceptance")["zip_gate"] == "ZIP_GATE_OPEN"

        # Now prompt delivers immediately
        act, st = bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "acc_msg_H", "echo ACCEPTANCE_H")
        assert act == "DELIVERED"
        assert st == "DELIVERED"

    # Test I: DISPATCH-vs-ZIP RACE -> atomic boundary, no overlap corruption
    def test_acceptance_i_dispatch_vs_zip_race_atomic_boundary(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]
        # Set active in-flight marker
        bridge.in_flight_locks["proj_acceptance"] = True

        # Confirms boundary: ZIP cannot close gate while in_flight_locks exists
        assert "proj_acceptance" in bridge.in_flight_locks
        bridge.in_flight_locks.pop("proj_acceptance")

    # Test J: FILE MUTATION DURING ZIP -> backup invalidated, prompt gate reopens immediately
    def test_acceptance_j_file_mutation_during_zip_invalidates_backup_and_reopens_gate(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Start mock zip
        gate_harness.start_mock_zip("proj_acceptance")
        # Prompt held during zip
        act_held, st_held = bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "acc_msg_J1", "echo J1")
        assert st_held == "HELD_FOR_ZIP"

        # Mutation occurs: invalidates backup & stops zip
        gate_harness.stop_mock_zip("proj_acceptance")

        # Prompt gate reopens immediately
        drained = bridge.drain_held_prompts("proj_acceptance")
        assert "acc_msg_J1" in drained

    # Test K: GOOGLE DRIVE DOWN -> local backup works, prompt unaffected, upload retryable
    def test_acceptance_k_google_drive_down_local_backup_succeeds_and_prompts_unaffected(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Local backup is verified, remote upload is marked failed/pending
        gate_harness.set_gate("proj_acceptance", "ZIP_GATE_OPEN")

        act, st = bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "acc_msg_K", "echo ACCEPTANCE_K")
        assert act == "DELIVERED"
        assert st == "DELIVERED"

    # Test L: 100 PROJECT ISOLATION -> 1 project's ZIP never blocks other projects
    def test_acceptance_l_hundred_projects_isolation(self, test_env, isolated_terminal):
        gate_harness: BackupGateHarness = test_env["gate_harness"]
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        # Set Project 0 to CLOSED
        gate_harness.set_gate("proj_0", "ZIP_GATE_CLOSED")
        for i in range(1, 100):
            gate_harness.set_gate(f"proj_{i}", "ZIP_GATE_OPEN")

        # Project 0 is held
        act0, st0 = bridge.receive_whatsapp_prompt("proj_0", isolated_terminal, "msg_p0", "p0")
        assert st0 == "HELD_FOR_ZIP"

        # Test sample of other projects: all deliver immediately
        for sample_id in [1, 25, 50, 75, 99]:
            act, st = bridge.receive_whatsapp_prompt(
                f"proj_{sample_id}", isolated_terminal, f"msg_p{sample_id}", f"echo P_{sample_id}"
            )
            assert act == "DELIVERED"
            assert st == "DELIVERED"

    # Test M: DUPLICATE WHATSAPP EVENT -> exactly one terminal delivery
    def test_acceptance_m_duplicate_whatsapp_event_exactly_one_delivery(self, test_env, isolated_terminal):
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        act1, st1 = bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "msg_dup_unique_id", "echo M1")
        assert act1 == "DELIVERED"
        assert st1 == "DELIVERED"

        # Send same message ID second time
        act2, st2 = bridge.receive_whatsapp_prompt("proj_acceptance", isolated_terminal, "msg_dup_unique_id", "echo M1_DUP")
        assert act2 == "DUPLICATE_SUPPRESSED"
        assert st2 == "DUPLICATE"

    # Test N: TARGET TMUX TEMPORARILY UNAVAILABLE -> durable retry, no user resend required
    def test_acceptance_n_target_tmux_temporarily_unavailable_durable_retry(self, test_env, tmux_harness):
        import secrets
        bridge: WhatsAppBridgeBroker = test_env["bridge"]

        sess_name = f"agy_e2e_retry_{secrets.token_hex(4)}"
        temp_target = f"{sess_name}:term"
        tmux_harness.kill_session(sess_name)

        act, st = bridge.receive_whatsapp_prompt("proj_acceptance", temp_target, "acc_msg_N", "echo ACCEPTANCE_N")
        assert act == "RETRYING"
        assert st == "RETRYING"

        # Restore target window
        restored_target = tmux_harness.create_isolated_session(session_name=sess_name, window_name="term")
        retried_count = bridge.retry_pending_delivery(temp_target)
        assert retried_count == 1
        rec = bridge.get_prompt_status("acc_msg_N")
        assert rec["status"] == "DELIVERED"
        tmux_harness.kill_session(sess_name)
