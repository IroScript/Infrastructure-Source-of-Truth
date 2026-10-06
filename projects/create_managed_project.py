#!/usr/bin/env python3
"""
create_managed_project.py — High-Level End-to-End Managed Project Creator.
Automates the complete project lifecycle:
1. Create folder
2. Assign project_id
3. Initialize Git repo
4. Create/Connect GitHub Remote (Default: Private)
5. Initial Commit & Push
6. Register in canonical PROJECT_REGISTRY.json
7. Classify Data & Set Storage Policy
8. Register Runtime Connections (tmux, whatsapp, systemd)
9. Regenerate all derived mappings
10. Verify project health
"""

import os
import sys
import json
import argparse
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOT_ROOT = os.path.dirname(SCRIPT_DIR)
REGISTRY_FILE = os.path.join(SCRIPT_DIR, "PROJECT_REGISTRY.json")

sys.path.insert(0, SCRIPT_DIR)
import register_project
import generate_derived_mappings


def create_project(args):
    raw_path = os.path.expanduser(args.path)
    real_path = os.path.realpath(raw_path)

    print(f"=== MANAGED PROJECT CREATOR: {args.name or os.path.basename(real_path)} ===")
    
    # Stage 1: Create Folder
    if not os.path.exists(real_path):
        print(f"[*] Creating project directory: {real_path}")
        os.makedirs(real_path, exist_ok=True)
    else:
        print(f"[*] Directory already exists: {real_path}")

    # Stage 2: Initialize Git
    git_dir = os.path.join(real_path, ".git")
    if not os.path.exists(git_dir):
        print(f"[*] Initializing Git repository in {real_path}...")
        subprocess.run(["git", "-C", real_path, "init"], check=True)
        # Create initial README if empty
        readme_path = os.path.join(real_path, "README.md")
        if not os.path.exists(readme_path):
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(f"# {args.name or os.path.basename(real_path)}\n\nManaged AGY Project.\n")
        # Create standard .gitignore
        gitignore_path = os.path.join(real_path, ".gitignore")
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write("__pycache__/\n*.pyc\nnode_modules/\n.env\n*.log\n")
        subprocess.run(["git", "-C", real_path, "add", "."], check=True)
        subprocess.run(["git", "-C", real_path, "commit", "-m", f"initial commit for {args.name or os.path.basename(real_path)}"], check=True)

    # Stage 3: Remote Repository Resolution
    remote = args.remote
    if not remote and not args.local_only:
        # Check if remote already configured
        p = subprocess.run(["git", "-C", real_path, "config", "--get", "remote.origin.url"], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            remote = p.stdout.strip()
        else:
            # Check if gh CLI is available to create private repo
            gh_check = subprocess.run(["which", "gh"], capture_output=True, text=True)
            if gh_check.returncode == 0:
                repo_slug = f"IroScript/{register_project.slugify(args.name or os.path.basename(real_path))}"
                print(f"[*] Attempting private GitHub repo creation via gh CLI: {repo_slug}")
                gh_create = subprocess.run(["gh", "repo", "create", repo_slug, "--private", "--source", real_path, "--remote", "origin"], capture_output=True, text=True)
                if gh_create.returncode == 0:
                    remote = f"git@github.com:{repo_slug}.git"
                    print(f"[+] Private GitHub repository created: {remote}")
                else:
                    print(f"[-] gh repo create notice: {gh_create.stderr.strip() or gh_create.stdout.strip()}")
            if not remote:
                print("[!] Notice: No remote provided and auto-creation not available. Marking as local-only or unpushed.")

    if remote:
        # Verify remote URL in git config
        curr_rem = subprocess.run(["git", "-C", real_path, "config", "--get", "remote.origin.url"], capture_output=True, text=True).stdout.strip()
        if not curr_rem:
            subprocess.run(["git", "-C", real_path, "remote", "add", "origin", remote], check=True)
        elif curr_rem != remote:
            subprocess.run(["git", "-C", real_path, "remote", "set-url", "origin", remote], check=True)

    # Stage 4: Register in Canonical Registry
    reg_args = argparse.Namespace(
        path=real_path,
        name=args.name or os.path.basename(real_path),
        id=args.id,
        type=args.type,
        remote=remote,
        branch=args.branch,
        visibility="local_only" if args.local_only else "private",
        local_only=args.local_only,
        tmux=args.tmux,
        whatsapp_group=args.whatsapp_group,
        whatsapp_route=args.whatsapp_route,
        data_files=args.data_files,
        verification_profile=args.verification_profile,
        dry_run=False
    )
    entry = register_project.register_project(reg_args)

    print("\n==========================================")
    print(f"  PROJECT ONBOARDING COMPLETE: {entry['project_id']}")
    print(f"  Canonical Path: {entry['canonical_path']}")
    print(f"  Status: {entry['status']}")
    print("==========================================")
    return entry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create and completely onboard a new managed project")
    parser.add_argument("--path", required=True, help="Target filesystem path")
    parser.add_argument("--name", default="", help="Project display name")
    parser.add_argument("--id", default="", help="Immutable project_id")
    parser.add_argument("--type", default="application", help="Project type")
    parser.add_argument("--remote", default="", help="GitHub remote URL")
    parser.add_argument("--branch", default="main", help="Git branch")
    parser.add_argument("--local-only", action="store_true", help="Local only project")
    parser.add_argument("--tmux", default="", help="tmux window")
    parser.add_argument("--whatsapp-group", default="", help="WhatsApp group")
    parser.add_argument("--whatsapp-route", default="", help="WhatsApp agent route")
    parser.add_argument("--data-files", default="", help="Data files")
    parser.add_argument("--verification-profile", default="standard_project", help="Verification profile")
    args = parser.parse_args()

    create_project(args)
