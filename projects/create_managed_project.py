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
REGISTRY_FILE = os.path.join(SCRIPT_DIR, 'PROJECT_REGISTRY.json')
sys.path.insert(0, SCRIPT_DIR)
import register_project
import generate_derived_mappings
from precommit_safety import safe_stage
from atomic_json import project_lock

def create_project(args):
    identity = os.path.realpath(os.path.expanduser(args.path))
    with project_lock(identity):
        return _create_project_locked(args)

def _create_project_locked(args):
    raw_path = os.path.expanduser(args.path)
    real_path = os.path.realpath(raw_path)
    print(f'=== MANAGED PROJECT CREATOR: {args.name or os.path.basename(real_path)} ===')
    if not os.path.exists(real_path):
        print(f'[*] Creating project directory: {real_path}')
        os.makedirs(real_path, exist_ok=True)
    else:
        print(f'[*] Directory already exists: {real_path}')
    git_dir = os.path.join(real_path, '.git')
    if not os.path.exists(git_dir):
        print(f'[*] Initializing Git repository in {real_path}...')
        subprocess.run(['git', '-C', real_path, 'init'], check=True, timeout=15)
        readme_path = os.path.join(real_path, 'README.md')
        if not os.path.exists(readme_path):
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f'# {args.name or os.path.basename(real_path)}\n\nManaged AGY Project.\n')
        gitignore_path = os.path.join(real_path, '.gitignore')
        existing = open(gitignore_path, encoding='utf-8').read() if os.path.exists(gitignore_path) else ''
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write(existing + '\n# AGY fail-closed defaults\n.env*\n!.env.example\n!.env.template\n*.pem\n*.key\n*.p12\n*.pfx\n*.db\n*.sqlite\n*.sqlite3\n*.rdb\n*.log\nnode_modules/\n.venv/\nvenv/\ntarget/\nbuild/\ndist/\nwa_auth/\n')
        safe_stage(real_path)
        subprocess.run(['git', '-C', real_path, 'commit', '-m', f'initial commit for {args.name or os.path.basename(real_path)}'], check=True, timeout=15)
    remote = args.remote
    if not remote and (not args.local_only):
        p = subprocess.run(['git', '-C', real_path, 'config', '--get', 'remote.origin.url'], capture_output=True, text=True, timeout=15)
        if p.returncode == 0 and p.stdout.strip():
            remote = p.stdout.strip()
        else:
            gh_check = subprocess.run(['which', 'gh'], capture_output=True, text=True, timeout=15)
            if gh_check.returncode == 0:
                repo_slug = f'IroScript/{register_project.slugify(args.name or os.path.basename(real_path))}'
                print(f'[*] Attempting private GitHub repo creation via gh CLI: {repo_slug}')
                gh_create = subprocess.run(['gh', 'repo', 'create', repo_slug, '--private', '--source', real_path, '--remote', 'origin'], capture_output=True, text=True, timeout=15)
                if gh_create.returncode == 0:
                    remote = f'git@github.com:{repo_slug}.git'
                    print(f'[+] Private GitHub repository created: {remote}')
                else:
                    print(f'[-] gh repo create notice: {gh_create.stderr.strip() or gh_create.stdout.strip()}')
            if not remote:
                print('[!] Notice: No remote provided and auto-creation not available. Marking as local-only or unpushed.')
    push_verified = False
    if remote:
        curr_rem = subprocess.run(['git', '-C', real_path, 'config', '--get', 'remote.origin.url'], capture_output=True, text=True, timeout=15).stdout.strip()
        if not curr_rem:
            subprocess.run(['git', '-C', real_path, 'remote', 'add', 'origin', remote], check=True, timeout=15)
        elif curr_rem != remote:
            subprocess.run(['git', '-C', real_path, 'remote', 'set-url', 'origin', remote], check=True, timeout=15)
        branch = subprocess.run(['git', '-C', real_path, 'branch', '--show-current'], capture_output=True, text=True, check=True, timeout=15).stdout.strip()
        if not branch:
            branch = args.branch or 'main'
            subprocess.run(['git', '-C', real_path, 'checkout', '-B', branch], check=True, timeout=15)
        try:
            subprocess.run(['git', '-C', real_path, 'push', '--set-upstream', 'origin', branch], check=True, timeout=15)
            subprocess.run(['git', '-C', real_path, 'fetch', 'origin', branch], check=True, timeout=15)
            local_sha = subprocess.run(['git', '-C', real_path, 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True, timeout=15).stdout.strip()
            remote_sha = subprocess.run(['git', '-C', real_path, 'rev-parse', f'origin/{branch}'], capture_output=True, text=True, check=True, timeout=15).stdout.strip()
            if local_sha != remote_sha:
                raise RuntimeError('Remote SHA mismatch after push')
            push_verified = True
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            print(f'[-] REMOTE PUSH/VERIFY FAILED: {exc}; recording incomplete onboarding')
    reg_args = argparse.Namespace(path=real_path, name=args.name or os.path.basename(real_path), id=args.id, type=args.type, remote=remote, branch=args.branch, visibility='local_only' if args.local_only else 'private', local_only=args.local_only, tmux=args.tmux, whatsapp_group=args.whatsapp_group, whatsapp_route=args.whatsapp_route, data_files=args.data_files, data_classification=args.data_classification, push_verified=push_verified, verification_profile=args.verification_profile, dry_run=False)
    entry = register_project.register_project(reg_args)
    print('\n==========================================')
    print(f"  PROJECT {('ONBOARDING COMPLETE' if entry['status'] == 'ACTIVE' else 'ONBOARDING INCOMPLETE')}: {entry['project_id']}")
    print(f"  Canonical Path: {entry['canonical_path']}")
    print(f"  Status: {entry['status']}")
    print('==========================================')
    return entry
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create and completely onboard a new managed project')
    parser.add_argument('--path', required=True, help='Target filesystem path')
    parser.add_argument('--name', default='', help='Project display name')
    parser.add_argument('--id', default='', help='Immutable project_id')
    parser.add_argument('--type', default='application', help='Project type')
    parser.add_argument('--remote', default='', help='GitHub remote URL')
    parser.add_argument('--branch', default='main', help='Git branch')
    parser.add_argument('--local-only', action='store_true', help='Local only project')
    parser.add_argument('--tmux', default='', help='tmux window')
    parser.add_argument('--whatsapp-group', default='', help='WhatsApp group')
    parser.add_argument('--whatsapp-route', default='', help='WhatsApp agent route')
    parser.add_argument('--data-files', default='', help='Data files')
    parser.add_argument('--data-classification', choices=['unknown', 'source_only', 'persistent_data', 'mixed'], default='unknown')
    parser.add_argument('--verification-profile', default='deterministic', help='Verification profile')
    args = parser.parse_args()
    create_project(args)