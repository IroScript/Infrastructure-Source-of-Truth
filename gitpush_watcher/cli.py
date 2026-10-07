"""CLI handlers for gitpush_watcher commands."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cloud_parity import CloudParityAuditor
from .watcher import GitPushWatcher


def handle_watcher_cli(args: argparse.Namespace, sot_root: Path) -> int:
    watcher = GitPushWatcher(sot_root)
    action = getattr(args, "watcher_action", "status")

    if action == "status":
        report = watcher.get_health_report()
        print(json.dumps(report, indent=2))
        return 0

    if action == "sync-once":
        results = watcher.sync_all_once(explicit_message=getattr(args, "message", ""))
        formatted = {k: {"success": v[0], "reason": v[1]} for k, v in results.items()}
        print(json.dumps(formatted, indent=2))
        return 0 if all(v[0] for v in results.values()) else 1

    if action == "run-daemon":
        watcher.run_daemon()
        return 0

    if action == "cloud-parity":
        auditor = CloudParityAuditor(sot_root)
        report = auditor.audit()
        print(json.dumps(report, indent=2))
        return 0 if report.get("overall_verdict") in ("PASS", "PARTIAL") else 1

    print(f"Unknown watcher action: {action}", file=sys.stderr)
    return 2
