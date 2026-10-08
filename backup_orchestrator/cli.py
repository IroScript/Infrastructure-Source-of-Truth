"""CLI command handlers for Backup Orchestrator."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from .config import BackupOrchestratorConfig
from .db import Database
from .orchestrator import BackupOrchestrator


def handle_backup_orchestrator_cli(args: argparse.Namespace, sot_root: Path) -> int:
    config = BackupOrchestratorConfig.resolve(
        sot_root=sot_root,
        home=Path(args.home) if getattr(args, "home", None) else None,
    )
    action = getattr(args, "orchestrator_action", "status")

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

        # Resolve route to project_id via connection mappings
        wa_file = sot_root / "connections" / "WHATSAPP_CONNECTIONS.json"
        if wa_file.is_file():
            try:
                wa_data = json.loads(wa_file.read_text(encoding="utf-8"))
                for conn in wa_data.get("connections", []):
                    p_id = conn.get("project_id")
                    if not p_id:
                        continue
                    if project_uuid.strip().lower() in (
                        (conn.get("group_id") or "").strip().lower(),
                        (conn.get("agent_name") or "").strip().lower(),
                        (conn.get("agent_route") or "").strip().lower(),
                        p_id.lower(),
                    ):
                        project_uuid = p_id
                        break
            except Exception:
                pass

        if ":" in project_uuid:
            target = project_uuid.split(":", 1)[1].strip()
            if target:
                project_uuid = target

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

        # Resolve route to project_id via connection mappings
        project_id = route
        wa_file = sot_root / "connections" / "WHATSAPP_CONNECTIONS.json"
        if wa_file.is_file():
            try:
                wa_data = json.loads(wa_file.read_text(encoding="utf-8"))
                for conn in wa_data.get("connections", []):
                    p_id = conn.get("project_id")
                    if not p_id:
                        continue
                    if route.strip().lower() in (
                        (conn.get("group_id") or "").strip().lower(),
                        (conn.get("agent_name") or "").strip().lower(),
                        (conn.get("agent_route") or "").strip().lower(),
                        p_id.lower(),
                    ):
                        project_id = p_id
                        break
            except Exception:
                pass

        if project_id == route and ":" in route:
            target = route.split(":", 1)[1].strip()
            if target:
                project_id = target

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
        report = orchestrator.get_health_report()
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
