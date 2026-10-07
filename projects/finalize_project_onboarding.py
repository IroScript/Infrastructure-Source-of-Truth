"""Publish a verified onboarding record; pushing requires an explicit --push invocation."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from atomic_json import atomic_write_json, read_json, registry_lock, project_lock, validate_project_registry
from register_project import verify_remote_parity
from precommit_safety import unsafe_paths
import generate_derived_mappings
PUBLISH_PATHS = ['projects/PROJECT_REGISTRY.json', 'projects/PROJECTS.json', 'projects/GIT_REPOSITORIES.json', 'projects/gitpush_folder_mapping.json', 'connections/WHATSAPP_CONNECTIONS.json', 'connections/TMUX_CONNECTIONS.json', 'connections/SERVICE_CONNECTIONS.json', 'infrastructure/SERVICES.json', 'infrastructure/PORTS.json', 'infrastructure/TMUX_WINDOWS.json', 'configuration/settings.json']

def activation_gaps(project, stages=None):
    stages = set(stages if stages is not None else project.get('lifecycle_stages', []))
    required = {'GIT_INITIALIZED', 'DATA_CLASSIFIED', 'BACKUP_POLICY_CONFIGURED', 'VERIFICATION_CONFIGURED', 'SOT_REGISTRATION_PUSHED'}
    if project.get('git', {}).get('backup_required', True):
        required |= {'REMOTE_CONFIGURED', 'REMOTE_REACHABLE', 'PUSH_VERIFIED', 'REMOTE_SHA_VERIFIED'}
    return sorted(required - stages)

def git(*args, check=True):
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, check=check, timeout=15)

def set_state(project_id, active, error=None):
    path = HERE / 'PROJECT_REGISTRY.json'
    with registry_lock(path):
        registry = read_json(path)
        validate_project_registry(registry)
        project = next((p for p in registry['projects'] if p['project_id'] == project_id))
        if active:
            project['status'] = 'ACTIVE'
            stages = project.setdefault('lifecycle_stages', [])
            if 'SOT_REGISTRATION_PUSHED' not in stages:
                stages.append('SOT_REGISTRATION_PUSHED')
            project['runtime']['enabled'] = True
            failed = None
        else:
            project['status'] = 'ONBOARDING_INCOMPLETE'
            project['runtime']['enabled'] = False
            failed = error or 'SOT_REGISTRATION_PUSH_PENDING'
        project['lifecycle_state'] = {'current_stage': 'ACTIVE' if active else failed, 'last_successful_stage': 'SOT_REGISTRATION_PUSHED' if active else 'REMOTE_SHA_VERIFIED', 'failed_stage': failed, 'error': error, 'retryable': not active, 'last_verified_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        registry['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        atomic_write_json(path, registry, validate_project_registry)

def verify_project_push(project):
    conf = project.get('git', {})
    if not conf.get('backup_required', True):
        return (True, 'LOCAL_ONLY_EXPLICIT')
    repo = project['canonical_path']
    branch = conf.get('branch', '')
    remote = conf.get('remote', '')
    if not branch or not remote or (not os.path.isdir(os.path.join(repo, '.git'))):
        return (False, 'GIT_REMOTE_BRANCH_OR_REPOSITORY_MISSING')
    push = subprocess.run(['git', '-C', repo, 'push', '--set-upstream', 'origin', branch], capture_output=True, text=True, timeout=15)
    if push.returncode:
        return (False, 'PROJECT_PUSH_FAILED: ' + (push.stderr.strip() or push.stdout.strip()))
    fetch = subprocess.run(['git', '-C', repo, 'fetch', 'origin', branch], capture_output=True, text=True, timeout=15)
    if fetch.returncode:
        return (False, 'PROJECT_FETCH_FAILED: ' + fetch.stderr.strip())
    ok, reason = verify_remote_parity(repo, remote, branch)
    return (True, 'PROJECT_PUSH_AND_SHA_VERIFIED') if ok else (False, reason)

def validate_data_policy(project):
    classification = project.get('data_classification', 'unknown')
    if classification == 'source_only':
        return (True, 'SOURCE_ONLY')
    if classification not in {'persistent_data', 'mixed'}:
        return (False, 'DATA_CLASSIFICATION_UNKNOWN')
    assets = read_json(ROOT / 'storage/DATA_ASSET_REGISTRY.json').get('assets', [])
    for rel in project.get('data', []):
        expected = os.path.realpath(os.path.join(project['canonical_path'], rel))
        matched = [a for a in assets if a.get('project_id') == project['project_id'] and os.path.realpath(a.get('source_path', '')) == expected]
        if not matched or any((a.get('remote_status') != 'REMOTE_CHECKSUM_VERIFIED' or a.get('restore_status') != 'REMOTE_RESTORE_VERIFIED' for a in matched)):
            return (False, f'PERSISTENT_ASSET_NOT_RESTORE_VERIFIED: {rel}')
    return (True, 'PERSISTENT_ASSETS_VERIFIED')

def publish(paths, message):
    git('add', '--', *paths)
    unsafe = unsafe_paths(ROOT)
    if unsafe:
        raise RuntimeError('SOT secret/data safety check failed: ' + ', '.join(unsafe[:20]))
    check = git('diff', '--cached', '--check', check=False)
    if check.returncode:
        raise RuntimeError(check.stderr or 'staged diff validation failed')
    if git('diff', '--cached', '--quiet', check=False).returncode == 0:
        return
    git('commit', '-m', message)
    branch = git('branch', '--show-current').stdout.strip()
    if not branch:
        raise RuntimeError('SOT branch is detached')
    git('push', '--set-upstream', 'origin', branch)
    git('fetch', 'origin', branch)
    local = git('rev-parse', 'HEAD').stdout.strip()
    remote = git('ls-remote', '--exit-code', 'origin', f'refs/heads/{branch}').stdout.split()
    if not remote or local != remote[0]:
        raise RuntimeError('SOT push completed without exact remote SHA parity')

def finalize(args):
    registry = read_json(HERE / 'PROJECT_REGISTRY.json')
    project = next((p for p in registry.get('projects', []) if p.get('project_id') == args.project_id), None)
    if not project:
        raise SystemExit(f'Unknown project_id: {args.project_id}')
    git_conf = project.get('git', {})
    missing = [stage for stage in ['GIT_INITIALIZED', 'DATA_CLASSIFIED', 'BACKUP_POLICY_CONFIGURED', 'VERIFICATION_CONFIGURED'] if stage not in project.get('lifecycle_stages', [])]
    data_ok, data_reason = validate_data_policy(project)
    if missing or not data_ok:
        reason = data_reason if not data_ok else 'REQUIRED_STAGES_MISSING: ' + ','.join(missing)
        set_state(args.project_id, False, reason)
        raise SystemExit(f'ONBOARDING_INCOMPLETE: {reason}')
    if git_conf.get('backup_required', True) and (not args.push):
        ok, reason = verify_remote_parity(project['canonical_path'], git_conf.get('remote', ''), git_conf.get('branch', ''))
        if not ok:
            set_state(args.project_id, False, reason)
            raise SystemExit(f'ONBOARDING_INCOMPLETE: {reason}')
    if not args.push:
        print('ONBOARDING_INCOMPLETE: SOT registration is not yet committed and pushed')
        return 2
    try:
        project_push_ok, project_push_reason = verify_project_push(project)
        if not project_push_ok:
            set_state(args.project_id, False, project_push_reason)
            raise RuntimeError(project_push_reason)
        if git_conf.get('backup_required', True):
            project.setdefault('lifecycle_stages', [])
            for stage in ['REMOTE_CONFIGURED', 'REMOTE_REACHABLE', 'PUSH_VERIFIED', 'REMOTE_SHA_VERIFIED']:
                if stage not in project['lifecycle_stages']:
                    project['lifecycle_stages'].append(stage)
            with registry_lock(HERE / 'PROJECT_REGISTRY.json'):
                latest = read_json(HERE / 'PROJECT_REGISTRY.json')
                current = next((p for p in latest['projects'] if p['project_id'] == args.project_id))
                current['lifecycle_stages'] = project['lifecycle_stages']
                atomic_write_json(HERE / 'PROJECT_REGISTRY.json', latest, validate_project_registry)
        candidate_stages = set(project.get('lifecycle_stages', [])) | {'SOT_REGISTRATION_PUSHED'}
        gaps = activation_gaps(project, candidate_stages)
        if gaps:
            raise RuntimeError('activation requirements missing: ' + ','.join(gaps))
        set_state(args.project_id, False, 'SOT_REGISTRATION_PUSH_PENDING')
        generate_derived_mappings.generate_all()
        publish(PUBLISH_PATHS, f'unverified: register project {args.project_id}')
        set_state(args.project_id, True)
        generate_derived_mappings.generate_all()
        publish(PUBLISH_PATHS, f'unverified: verify active project {args.project_id}')
    except Exception as exc:
        set_state(args.project_id, False, f'SOT_PUBLISH_FAILED: {exc}')
        generate_derived_mappings.generate_all()
        raise SystemExit(f'ONBOARDING_INCOMPLETE: {exc}')
    print('ACTIVE: project and SOT registration pushed; remote SHA parity verified')
    return 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_id')
    parser.add_argument('--push', action='store_true', help='Commit and push; invoke only after required external approval')
    args = parser.parse_args()
    registry = read_json(HERE / 'PROJECT_REGISTRY.json')
    project = next((p for p in registry.get('projects', []) if p.get('project_id') == args.project_id), None)
    if not project:
        raise SystemExit(f'Unknown project_id: {args.project_id}')
    with project_lock(project.get('canonical_path', args.project_id)):
        return finalize(args)
if __name__ == '__main__':
    raise SystemExit(main())