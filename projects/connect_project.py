#!/usr/bin/env python3
"""
connect_project.py — Unified Project Integration Connector.
Connects an existing registered project (by project_id) to runtime and cloud integrations:
- GitHub Remote & Backup
- WhatsApp Routing Agent
- Tmux Execution Window
- Systemd Daemon / Ports
- Storage / Data Backup Policy
- Verification Profile

Usage:
    python3 connect_project.py <project_id> [options]

Examples:
    python3 connect_project.py youtube_pipeline --tmux agy:3 --whatsapp "AGY YouTube" --route agy:yt
    python3 connect_project.py rust_task --github "git@github.com:IroScript/Rust_Task.git"
"""

import os
import sys
import json
import argparse
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_FILE = os.path.join(SCRIPT_DIR, "PROJECT_REGISTRY.json")

sys.path.insert(0, SCRIPT_DIR)
import generate_derived_mappings
from atomic_json import atomic_write_json, read_json, registry_lock, project_lock, validate_project_registry


def connect_project(project_id, args):
    snapshot = read_json(REGISTRY_FILE)
    entry = next((p for p in snapshot.get("projects", []) if p.get("project_id") == project_id), None)
    if not entry:
        print(f"[-] ERROR: project_id '{project_id}' not found in canonical registry.")
        return False
    with project_lock(entry.get("canonical_path", project_id)):
        with registry_lock(REGISTRY_FILE):
            result = _connect_project_locked(project_id, args)
        if result and any((args.github, args.whatsapp, args.route, args.tmux, args.service, args.port, args.verifier)):
            generate_derived_mappings.generate_all()
        return result


def _connect_project_locked(project_id, args):
    if not os.path.exists(REGISTRY_FILE):
        print(f"[-] Registry missing: {REGISTRY_FILE}")
        return False

    registry = read_json(REGISTRY_FILE)
    validate_project_registry(registry)

    target = None
    for p in registry.get("projects", []):
        if p["project_id"] == project_id:
            target = p
            break

    if not target:
        print(f"[-] ERROR: project_id '{project_id}' not found in canonical registry.")
        print("    Available projects:")
        for p in registry.get("projects", []):
            print(f"      - {p['project_id']} ({p.get('display_name')})")
        return False

    modified = False

    # 1. GitHub Connection
    if args.github:
        target.setdefault("git", {})["enabled"] = True
        target["git"]["remote"] = args.github
        target["git"]["backup_required"] = True
        target["status"] = "ONBOARDING_INCOMPLETE"
        target["lifecycle_state"] = {"current_stage": "REMOTE_CONFIGURED", "last_successful_stage": "REGISTERED",
                                     "failed_stage": "REMOTE_REVALIDATION_REQUIRED", "error": "Remote changed; push and exact SHA parity must be reverified",
                                     "retryable": True, "last_verified_at": None}
        modified = True
        print(f"[+] Connected GitHub Remote: {args.github}")

    # 2. WhatsApp Connection
    if args.whatsapp or args.route:
        wa = target.setdefault("connections", {}).setdefault("whatsapp", {})
        wa["enabled"] = True
        if args.whatsapp:
            wa["group_id"] = args.whatsapp
        if args.route:
            wa["agent_route"] = args.route
        modified = True
        print(f"[+] Connected WhatsApp Agent: group='{wa.get('group_id')}', route='{wa.get('agent_route')}'")

    # 3. Tmux Connection
    if args.tmux:
        target.setdefault("runtime", {})["tmux_window"] = args.tmux
        modified = True
        print(f"[+] Connected Tmux Window: {args.tmux}")

    # 4. Service Connection
    if args.service:
        services = target.setdefault("runtime", {}).setdefault("services", [])
        if args.service not in services:
            services.append(args.service)
        modified = True
        print(f"[+] Connected System Service: {args.service}")

    # 5. Port Connection
    if args.port:
        ports = target.setdefault("runtime", {}).setdefault("ports", [])
        if args.port not in ports:
            ports.append(args.port)
        modified = True
        print(f"[+] Connected Port: {args.port}")

    # 6. Verification Profile
    if args.verifier:
        target.setdefault("verification", {})["profile"] = args.verifier
        modified = True
        print(f"[+] Configured Verification Profile: {args.verifier}")

    if modified:
        registry["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        atomic_write_json(REGISTRY_FILE, registry, validate_project_registry)

        print(f"[+] Integration updates successfully applied to {project_id}")
        return True
    else:
        print("[!] No integration options specified. Nothing changed.")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Connect a project_id to WhatsApp, Tmux, GitHub, Services, or Verifiers")
    parser.add_argument("project_id", help="Canonical project_id")
    parser.add_argument("--github", default="", help="GitHub remote URL")
    parser.add_argument("--whatsapp", default="", help="WhatsApp group ID / name")
    parser.add_argument("--route", default="", help="WhatsApp agent route (e.g. agy:0)")
    parser.add_argument("--tmux", default="", help="Tmux window specifier (e.g. agy:3)")
    parser.add_argument("--service", default="", help="Systemd service unit name")
    parser.add_argument("--port", type=int, default=0, help="Listening TCP/UDP port")
    parser.add_argument("--verifier", default="", help="Verification profile name")
    args = parser.parse_args()

    connect_project(args.project_id, args)
