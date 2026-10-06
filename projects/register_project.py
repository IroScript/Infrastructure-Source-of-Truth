#!/usr/bin/env python3
"""
register_project.py — Automatic Project Onboarding & Registration Engine.
Part of the AGY Universal Project Lifecycle & Backup Control System.

Usage:
    python3 register_project.py --path "/path/to/project" --name "Project Name" [options]

Options:
    --id PROJECT_ID           Explicit project_id (default: derived from name/folder)
    --type PROJECT_TYPE       Type: application, service, library, web, etc. (default: application)
    --remote REMOTE_URL       GitHub remote URL (auto-detected if git repo)
    --branch BRANCH           Default branch (default: main)
    --visibility VISIBILITY   private or public (default: private)
    --local-only              Explicitly mark as local-only (skips remote requirement)
    --tmux TMUX_WINDOW        e.g. agy:3
    --whatsapp-group GROUP    WhatsApp group name/id
    --whatsapp-route ROUTE    WhatsApp agent route, e.g. agy:custom
    --data-files FILES        Comma-separated relative data paths
    --verification-profile    e.g. standard_project, rust_task, etc.
    --dry-run                 Preview registration without writing changes
"""

import os
import sys
import json
import re
import argparse
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_FILE = os.path.join(SCRIPT_DIR, "PROJECT_REGISTRY.json")

# Import generator from same directory
sys.path.insert(0, SCRIPT_DIR)
import generate_derived_mappings


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[\s\-_]+', '_', text)
    text = re.sub(r'[^a-z0-9_]', '', text)
    return text.strip('_')


def inspect_git(path):
    git_dir = os.path.join(path, ".git")
    if not os.path.exists(git_dir):
        return {"is_git": False, "remote": "", "branch": "", "head": "", "clean": True}
    
    remote = ""
    try:
        p = subprocess.run(["git", "-C", path, "config", "--get", "remote.origin.url"], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            remote = p.stdout.strip()
        else:
            p = subprocess.run(["git", "-C", path, "config", "--get", "remote.upstream.url"], capture_output=True, text=True)
            if p.returncode == 0 and p.stdout.strip():
                remote = p.stdout.strip()
    except Exception:
        pass

    branch = "main"
    try:
        p = subprocess.run(["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            branch = p.stdout.strip()
    except Exception:
        pass

    head = ""
    try:
        p = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            head = p.stdout.strip()
    except Exception:
        pass

    clean = True
    try:
        p = subprocess.run(["git", "-C", path, "status", "-s"], capture_output=True, text=True)
        clean = (len(p.stdout.strip()) == 0)
    except Exception:
        pass

    return {"is_git": True, "remote": remote, "branch": branch, "head": head, "clean": clean}


def register_project(args):
    raw_path = os.path.expanduser(args.path)
    real_path = os.path.realpath(raw_path)

    if not os.path.exists(real_path):
        print(f"[-] ERROR: Path does not exist physically: {real_path}")
        sys.exit(1)

    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    projects = registry.get("projects", [])

    # Check duplicate
    for p in projects:
        if os.path.realpath(p.get("canonical_path", "")) == real_path:
            print(f"[-] DUPLICATE DETECTED: Path '{real_path}' is already registered as project_id='{p['project_id']}'")
            return p

    # Assign project_id
    if args.id:
        project_id = slugify(args.id)
    else:
        name_seed = args.name or os.path.basename(real_path)
        project_id = slugify(name_seed)

    # Ensure project_id is unique
    existing_ids = {p["project_id"] for p in projects}
    if project_id in existing_ids:
        counter = 2
        while f"{project_id}_{counter}" in existing_ids:
            counter += 1
        project_id = f"{project_id}_{counter}"

    display_name = args.name or os.path.basename(real_path).replace("_", " ").title()

    # Git Inspection
    git_info = inspect_git(real_path)
    remote = args.remote or git_info["remote"]
    branch = args.branch or git_info["branch"] or "main"
    is_git = git_info["is_git"]

    # Safe Git Init if not git
    if not is_git and not args.dry_run:
        print(f"[*] Initializing Git repository in {real_path}...")
        subprocess.run(["git", "-C", real_path, "init"], check=True)
        is_git = True

    # Determine Lifecycle Stage
    # DISCOVERED -> REGISTERED -> GIT_INITIALIZED -> REMOTE_BACKED -> CONNECTIONS_REGISTERED -> DATA_CLASSIFIED -> VERIFICATION_CONFIGURED -> BACKUP_CONFIGURED -> ACTIVE
    stages = ["DISCOVERED", "REGISTERED"]
    if is_git:
        stages.append("GIT_INITIALIZED")
    if remote or args.local_only:
        stages.append("REMOTE_BACKED")

    wa_enabled = bool(args.whatsapp_group or args.whatsapp_route)
    tmux_enabled = bool(args.tmux)
    if wa_enabled or tmux_enabled:
        stages.append("CONNECTIONS_REGISTERED")

    data_files = [f.strip() for f in args.data_files.split(",") if f.strip()] if args.data_files else []
    stages.append("DATA_CLASSIFIED")
    stages.append("VERIFICATION_CONFIGURED")
    stages.append("BACKUP_CONFIGURED")

    status = "ACTIVE" if ("REMOTE_BACKED" in stages or args.local_only) else "INCOMPLETE"

    entry = {
        "project_id": project_id,
        "display_name": display_name,
        "canonical_path": real_path,
        "aliases": [raw_path] if raw_path != real_path else [],
        "project_type": args.type or "application",
        "git": {
            "enabled": is_git,
            "remote": remote,
            "branch": branch,
            "remote_visibility": "local_only" if args.local_only else (args.visibility or "private"),
            "backup_required": not args.local_only
        },
        "runtime": {
            "tmux_window": args.tmux or "",
            "services": [],
            "ports": []
        },
        "connections": {
            "whatsapp": {
                "enabled": wa_enabled,
                "group_id": args.whatsapp_group or "",
                "agent_route": args.whatsapp_route or ""
            }
        },
        "data": data_files,
        "verification": {
            "required": True,
            "profile": args.verification_profile or "standard_project"
        },
        "lifecycle_stages": stages,
        "status": status
    }

    if args.dry_run:
        print(f"[DRY-RUN] Would register project: {json.dumps(entry, indent=2)}")
        return entry

    # Commit entry to registry
    projects.append(entry)
    registry["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    print(f"[+] REGISTERED: project_id='{project_id}' ('{display_name}') -> {real_path} (Status: {status})")

    # Regenerate derived mappings
    print("[*] Regenerating downstream derived mappings...")
    generate_derived_mappings.generate_all()

    return entry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register a new or existing project into AGY Canonical Registry")
    parser.add_argument("--path", required=True, help="Filesystem path of the project")
    parser.add_argument("--name", default="", help="Display name of the project")
    parser.add_argument("--id", default="", help="Explicit immutable project_id")
    parser.add_argument("--type", default="application", help="Project type")
    parser.add_argument("--remote", default="", help="GitHub remote URL")
    parser.add_argument("--branch", default="main", help="Git branch")
    parser.add_argument("--visibility", default="private", help="Remote visibility (private/public)")
    parser.add_argument("--local-only", action="store_true", help="Mark project as local-only (skip remote backup)")
    parser.add_argument("--tmux", default="", help="tmux window route (e.g. agy:3)")
    parser.add_argument("--whatsapp-group", default="", help="WhatsApp notification group ID")
    parser.add_argument("--whatsapp-route", default="", help="WhatsApp agent route (e.g. agy:custom)")
    parser.add_argument("--data-files", default="", help="Comma-separated relative data paths")
    parser.add_argument("--verification-profile", default="standard_project", help="Verification profile name")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without modifying files")
    args = parser.parse_args()

    register_project(args)
