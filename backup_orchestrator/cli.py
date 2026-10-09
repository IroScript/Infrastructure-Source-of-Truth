"""CLI command handlers for Backup Orchestrator."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from .config import BackupOrchestratorConfig
from .db import Database
from .orchestrator import BackupOrchestrator


def resolve_route_to_project_id(target_str: str, sot_root: Path) -> str:
    """
    Resolves route, window, group, project slug, or project_uuid to canonical project_id.
    Checks WHATSAPP_CONNECTIONS.json, PROJECT_REGISTRY.json, and group window mappings.
    """
    target = target_str.strip()
    if not target:
        return target
    target_lower = target.lower()

    # 1. Check WHATSAPP_CONNECTIONS.json (supports group_id, agent_name, agent_route, project_uuid, project_id)
    wa_file = sot_root / "connections" / "WHATSAPP_CONNECTIONS.json"
    if wa_file.is_file():
        try:
            wa_data = json.loads(wa_file.read_text(encoding="utf-8"))
            for conn in wa_data.get("connections", []):
                p_id = conn.get("project_id")
                if not p_id:
                    continue
                if target_lower in (
                    (conn.get("group_id") or "").strip().lower(),
                    (conn.get("agent_name") or "").strip().lower(),
                    (conn.get("agent_route") or "").strip().lower(),
                    (conn.get("project_uuid") or "").strip().lower(),
                    p_id.lower(),
                ):
                    return p_id
        except Exception:
            pass

    # 2. Check PROJECT_REGISTRY.json (supports project_uuid, project_id, display_name, tmux_window)
    reg_file = sot_root / "projects" / "PROJECT_REGISTRY.json"
    if reg_file.is_file():
        try:
            reg_data = json.loads(reg_file.read_text(encoding="utf-8"))
            for proj in reg_data.get("projects", []):
                p_id = proj.get("project_id")
                if not p_id:
                    continue
                p_uuid = (proj.get("project_uuid") or "").strip().lower()
                p_slug = p_id.strip().lower()
                p_name = (proj.get("display_name") or "").strip().lower()
                tmux_win = (proj.get("runtime") or {}).get("tmux_window") or ""
                windows = [w.strip().lower() for w in tmux_win.split(",") if w.strip()]
                if target_lower in (p_uuid, p_slug, p_name, *windows):
                    return p_id
        except Exception:
            pass

    # 3. Strip prefix like agy:xyz -> xyz and match against project slugs
    if ":" in target:
        clean = target.split(":", 1)[1].strip()
        if clean:
            if reg_file.is_file():
                try:
                    reg_data = json.loads(reg_file.read_text(encoding="utf-8"))
                    for proj in reg_data.get("projects", []):
                        p_id = proj.get("project_id", "")
                        if clean.lower() == p_id.lower() or p_id.lower().startswith(clean.lower()):
                            return p_id
                except Exception:
                    pass
            return clean

    return target


def handle_backup_orchestrator_cli(args: argparse.Namespace, sot_root: Path) -> int:
    config = BackupOrchestratorConfig.resolve(
        sot_root=sot_root,
        home=Path(args.home) if getattr(args, "home", None) else None,
    )
    action = getattr(args, "orchestrator_action", "status")
    if os.environ.get("TASK_MODE") == "READ_ONLY":
        if action in ("run-cycle", "run-daemon", "retry-uploads", "import-state"):
            print(f"FAIL: POLICY_VIOLATION_READ_ONLY: {action} forbidden in READ_ONLY mode", file=sys.stderr)
            return 2

    if action == "in-flight-lock":
        p_uuid = getattr(args, "project_uuid", "") or getattr(args, "project", "") or getattr(args, "route", "")
        p_id = resolve_route_to_project_id(p_uuid, sot_root)
        sub_action = getattr(args, "sub_action", "check")
        from .gate import PromptGateCoordinator
        db = Database(config.db_path)
        coordinator = PromptGateCoordinator(db)
        if sub_action == "acquire":
            res = coordinator.acquire_dispatch_claim(p_id)
            print(json.dumps(res))
            return 0 if res.get("acquired") else 1
        elif sub_action == "release":
            res = coordinator.release_dispatch_claim(p_id)
            print(json.dumps(res))
            return 0
        else:
            in_flight = coordinator.has_in_flight_delivery_lock(p_id)
            print(json.dumps({"project_uuid": p_uuid, "project_id": p_id, "in_flight": in_flight}))
            return 0

    if action == "gate-check":
        project_uuid = (
            getattr(args, "project_uuid", "")
            or getattr(args, "project", "")
            or getattr(args, "route", "")
            or getattr(args, "project_id", "")
        )
        if not project_uuid:
            print("Error: --project-uuid or --route is required for gate-check", file=sys.stderr)
            return 2

        # Resolve route or UUID to project_id via connection mappings and registry
        project_uuid = resolve_route_to_project_id(project_uuid, sot_root)

        from .gate import PromptGateCoordinator
        db = Database(config.db_path)
        coordinator = PromptGateCoordinator(db)
        gate_info = coordinator.check_gate(project_uuid)
        print(json.dumps(gate_info, indent=2))
        return 0

    if action == "submit-prompt":
        import base64
        route = getattr(args, "route", "")
        msg_id = getattr(args, "message_id", "") or f"msg-{int(time.time() * 1000)}"
        payload = getattr(args, "payload", "")
        if getattr(args, "base64", False) and payload:
            try:
                payload = base64.b64decode(payload).decode("utf-8")
            except Exception:
                pass
        from .gate import PromptGateCoordinator
        db = Database(config.db_path)
        coordinator = PromptGateCoordinator(db)

        # Resolve route to project_id via connection mappings and registry
        project_id = resolve_route_to_project_id(route, sot_root)

        # Pure transactional enqueue without in-memory receiver
        decision = coordinator.dispatch_or_hold_message(
            project_id=project_id,
            message_id=msg_id,
            routing_target=route,
            payload=payload,
        )

        if decision.status == "DUPLICATE_REJECTED":
            ack = {
                "message_id": msg_id,
                "delivered": False,
                "exactly_once_provable": True,
                "status": "DUPLICATE_REJECTED",
                "delivery_owner": "bridge",
            }
        else:
            ack = {
                "message_id": msg_id,
                "delivered": False,
                "exactly_once_provable": True,
                "status": decision.status,
                "dispatch_state": decision.status,
                "gate_state": decision.gate_state,
                "sequence_num": decision.sequence_num,
                "delivery_owner": "bridge",
            }
        print(json.dumps(ack, indent=2))
        return 0 if ack["status"] in ("ACCEPTED_FOR_DELIVERY", "DISPATCHING", "DELIVERED", "HELD", "DUPLICATE_REJECTED") else 1

    orchestrator = BackupOrchestrator(config)

    if action == "status":
        p_filter = getattr(args, "project", "") or getattr(args, "project_id", "") or getattr(args, "project_uuid", "")
        report = orchestrator.get_health_report(target_project_id=p_filter)
        print(json.dumps(report, indent=2))
        return 0

    if action == "run-cycle":
        p_id = getattr(args, "project_id", "")
        if not p_id:
            print("Error: --project-id is required for run-cycle", file=sys.stderr)
            return 2
        force = getattr(args, "force", False)
        strict = getattr(args, "strict", False)
        result = orchestrator.run_cycle_for_project(
            project_id=p_id,
            force=force,
            strict_download_verify=strict,
        )
        print(json.dumps(result.__dict__, indent=2))
        return 0 if result.action_taken in ("BACKUP_COMPLETED", "SKIPPED_CLEAN", "SKIPPED_NOT_QUIET", "SKIPPED_BUSY") else 2

    if action == "retry-uploads":
        strict = getattr(args, "strict", False)
        results = orchestrator.retry_pending_uploads(strict_download_verify=strict)
        print(json.dumps({"retried_uploads": results}, indent=2))
        return 0

    if action == "client-id-check":
        remote = getattr(args, "remote", config.rclone_remote)
        audit = orchestrator.uploader.audit_rclone_client_id(remote)
        print(json.dumps(audit, indent=2))
        return 0 if audit.get("status") == "PASS" else 1

    if action == "export-state":
        out_file = Path(args.output_file)
        orchestrator.db.export_encrypted_backup(out_file, key=getattr(args, "key", None))
        print(json.dumps({"exported_encrypted_state": str(out_file), "status": "PASS"}, indent=2))
        return 0

    if action == "import-state":
        in_file = Path(args.input_file)
        orchestrator.db.import_encrypted_backup(in_file, key=getattr(args, "key", None))
        print(json.dumps({"imported_encrypted_state": str(in_file), "status": "PASS"}, indent=2))
        return 0

    if action == "run-daemon":
        interval = getattr(args, "interval", 30)
        try:
            orchestrator.run_daemon(interval_seconds=interval)
            return 0
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            print(f"Daemon error: {exc}", file=sys.stderr)
            return 1

    print(f"Unknown action: {action}", file=sys.stderr)
    return 2
