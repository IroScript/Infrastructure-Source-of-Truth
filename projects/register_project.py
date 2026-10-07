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
from atomic_json import atomic_write_json, read_json, registry_lock, project_lock, validate_project_registry

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

    branch = ""
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


def verify_remote_parity(path, remote, branch):
    if not remote or not branch:
        return False, "REMOTE_OR_BRANCH_MISSING"
    probe = subprocess.run(["git", "ls-remote", "--exit-code", remote, f"refs/heads/{branch}"], capture_output=True, text=True)
    if probe.returncode != 0:
        return False, "REMOTE_UNREACHABLE_OR_BRANCH_MISSING"
    remote_sha = probe.stdout.split()[0] if probe.stdout.split() else ""
    local = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True)
    if local.returncode != 0 or not remote_sha or local.stdout.strip() != remote_sha:
        return False, "REMOTE_SHA_MISMATCH"
    return True, "REMOTE_SHA_VERIFIED"


def register_project(args):
    raw_path = os.path.expanduser(args.path)
    real_path = os.path.realpath(raw_path)
    if not os.path.exists(real_path):
        print(f"[-] ERROR: Path does not exist physically: {real_path}")
        sys.exit(1)
    with project_lock(real_path):
        return _register_project_locked(args, raw_path, real_path)


def _register_project_locked(args, raw_path, real_path):
    git_info = inspect_git(real_path)
    if not git_info["is_git"] and not args.dry_run:
        subprocess.run(["git", "-C", real_path, "init"], check=True)
        git_info = inspect_git(real_path)
    remote = args.remote or git_info["remote"]
    branch = git_info["branch"] or args.branch or ""
    is_git = git_info["is_git"]
    remote_ok, remote_reason = verify_remote_parity(real_path, remote, branch) if is_git and git_info["head"] else (False, "LOCAL_COMMIT_MISSING")
    ctx = registry_lock(REGISTRY_FILE) if not args.dry_run else None
    if ctx:
        ctx.__enter__()
    try:
        # Reread only after acquiring the process lock.
        registry = read_json(REGISTRY_FILE)
        validate_project_registry(registry)
        projects = registry.get("projects", [])
        for p in projects:
            if os.path.realpath(p.get("canonical_path", "")) == real_path:
                print(f"[-] DUPLICATE DETECTED: Path '{real_path}' is already registered as project_id='{p['project_id']}'")
                return p

        project_id = slugify(args.id or args.name or os.path.basename(real_path))
        existing_ids = {p["project_id"] for p in projects}
        if project_id in existing_ids:
            suffix = 2
            while f"{project_id}_{suffix}" in existing_ids:
                suffix += 1
            project_id = f"{project_id}_{suffix}"
        display_name = args.name or os.path.basename(real_path).replace("_", " ").title()
        stages = ["DISCOVERED", "REGISTERED"]
        if is_git:
            stages.append("GIT_INITIALIZED")
        if remote:
            stages.append("REMOTE_CONFIGURED")
        if remote_ok or remote_reason == "REMOTE_SHA_MISMATCH":
            stages.append("REMOTE_REACHABLE")
        if remote_ok:
            stages.append("REMOTE_SHA_VERIFIED")
            if getattr(args, "push_verified", False):
                stages.append("PUSH_VERIFIED")
        wa_enabled, tmux_enabled = bool(args.whatsapp_group or args.whatsapp_route), bool(args.tmux)
        if wa_enabled or tmux_enabled:
            stages.append("CONNECTIONS_REGISTERED")
        data_files = [x.strip() for x in args.data_files.split(",") if x.strip()] if args.data_files else []
        data_classification = getattr(args, "data_classification", "unknown")
        if data_classification == "source_only":
            stages += ["DATA_CLASSIFIED", "BACKUP_POLICY_CONFIGURED"]
        elif data_files:
            stages.append("DATA_CLASSIFIED")
        profile_file = os.path.join(os.path.dirname(SCRIPT_DIR), "verification", "VERIFIER_PROFILES.json")
        try:
            profiles = read_json(profile_file).get("profiles", {})
        except (OSError, json.JSONDecodeError):
            profiles = {}
        verifier_profile = args.verification_profile or "deterministic"
        if verifier_profile in profiles:
            stages.append("VERIFICATION_CONFIGURED")
        if args.local_only:
            stages += ["BACKUP_POLICY_CONFIGURED"]
        required = ["DATA_CLASSIFIED", "BACKUP_POLICY_CONFIGURED", "VERIFICATION_CONFIGURED"]
        if not args.local_only:
            required += ["GIT_INITIALIZED", "REMOTE_REACHABLE", "PUSH_VERIFIED", "REMOTE_SHA_VERIFIED"]
        project_ready = all(stage in stages for stage in required)
        # Registration itself is part of SOT; it cannot be ACTIVE until this state is committed and pushed.
        ready = False
        if project_ready:
            stages.append("SOT_REGISTRATION_PUSH_PENDING")
        status = "ONBOARDING_INCOMPLETE"
        entry = {
            "project_id": project_id, "project_uuid": str(__import__("uuid").uuid4()),
            "display_name": display_name, "canonical_path": real_path,
            "aliases": [raw_path] if raw_path != real_path else [], "project_type": args.type or "application",
            "git": {"enabled": is_git, "remote": remote, "branch": branch,
                    "remote_visibility": "local_only" if args.local_only else (args.visibility or "private"),
                    "backup_required": not args.local_only},
            "runtime": {"tmux_window": args.tmux or "", "services": [], "ports": [], "enabled": ready},
            "connections": {"whatsapp": {"enabled": wa_enabled, "group_id": args.whatsapp_group or "",
                                               "agent_route": args.whatsapp_route or ""}},
            "data": data_files, "data_classification": data_classification,
            "verification": {"required": True, "profile": verifier_profile},
            "lifecycle_stages": stages, "status": status,
            "lifecycle_state": {"current_stage": "SOT_REGISTRATION_PUSH_PENDING" if project_ready else ("REMOTE_CONFIGURED" if remote else "REGISTERED"),
                            "last_successful_stage": stages[-2] if project_ready else stages[-1],
                            "failed_stage": "SOT_REGISTRATION_PUSH_PENDING" if project_ready else (remote_reason if not remote_ok and not args.local_only else "ONBOARDING_REQUIREMENTS_INCOMPLETE"),
                            "error": "SOT_REGISTRATION_PUSH_PENDING" if project_ready else (remote_reason if not remote_ok and not args.local_only else "ONBOARDING_REQUIREMENTS_INCOMPLETE"), "retryable": True,
                                "last_verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}
        if args.dry_run:
            print(f"[DRY-RUN] Would register project: {json.dumps(entry, indent=2)}")
            return entry
        projects.append(entry)
        registry["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        atomic_write_json(REGISTRY_FILE, registry, validate_project_registry)
        print(f"[+] REGISTERED: project_id='{project_id}' ('{display_name}') -> {real_path} (Status: {status})")
        if ctx:
            ctx.__exit__(None, None, None)
            ctx = None
        generate_derived_mappings.generate_all()
        return entry
    finally:
        if ctx:
            ctx.__exit__(None, None, None)


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
    parser.add_argument("--data-classification", choices=["unknown", "source_only", "persistent_data", "mixed"], default="unknown")
    parser.add_argument("--verification-profile", default="deterministic", help="Verification profile name")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without modifying files")
    args = parser.parse_args()

    register_project(args)
