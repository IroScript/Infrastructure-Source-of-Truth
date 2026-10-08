"""CLI command handlers for Backup Orchestrator."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from .config import BackupOrchestratorConfig
from .orchestrator import BackupOrchestrator


def handle_backup_orchestrator_cli(args: argparse.Namespace, sot_root: Path) -> int:
    config = BackupOrchestratorConfig.resolve(
        sot_root=sot_root,
        home=Path(args.home) if getattr(args, "home", None) else None,
    )
    orchestrator = BackupOrchestrator(config)

    action = getattr(args, "orchestrator_action", "status")

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
        from .bridge_adapter import BridgeAdapter
        adapter = BridgeAdapter(orchestrator.gate_coordinator, sot_root)
        ack = adapter.handle_incoming_message(route_spec=route, message_id=msg_id, payload=payload, is_arbitrary_cli=False)
        print(json.dumps(ack.__dict__, indent=2))
        return 0 if ack.status in ("DELIVERED", "HELD") else 1

    print(f"Unknown action: {action}", file=sys.stderr)
    return 2
