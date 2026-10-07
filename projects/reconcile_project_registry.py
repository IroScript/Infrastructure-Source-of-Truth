"""
reconcile_project_registry.py — Complete Multi-Dimensional Project Registry Reconciler.
Compares canonical PROJECT_REGISTRY.json against:
1. Filesystem existence of canonical paths and aliases
2. Physical Git root verification (.git present)
3. Live Git remote alignment (local git config vs registry remote)
4. WhatsApp connections alignment (WHATSAPP_CONNECTIONS.json vs registry)
5. Tmux window connections alignment (TMUX_CONNECTIONS.json vs registry)
6. Service & Port connections alignment (SERVICE_CONNECTIONS.json vs registry)
7. Operational gitpush_folder_mapping.json alignment
Reports any mismatch as PROJECT REGISTRY DRIFT.
"""
import os
import sys
import json
import subprocess
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
import discover_unregistered_projects
REGISTRY_FILE = os.path.join(SCRIPT_DIR, 'PROJECT_REGISTRY.json')
WHATSAPP_FILE = os.path.join(SOT_ROOT, 'connections', 'WHATSAPP_CONNECTIONS.json')
TMUX_FILE = os.path.join(SOT_ROOT, 'connections', 'TMUX_CONNECTIONS.json')
SERVICE_FILE = os.path.join(SOT_ROOT, 'connections', 'SERVICE_CONNECTIONS.json')
OPERATIONAL_MAPPING = '/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/gitpush_folder_mapping.json'

def get_git_remote(path):
    try:
        p = subprocess.run(['git', '-C', path, 'config', '--get', 'remote.origin.url'], capture_output=True, text=True, timeout=15)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
        p = subprocess.run(['git', '-C', path, 'config', '--get', 'remote.upstream.url'], capture_output=True, text=True, timeout=15)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except Exception:
        pass
    return ''

def reconcile():
    print('=== MULTI-DIMENSIONAL PROJECT REGISTRY RECONCILER ===')
    if not os.path.exists(REGISTRY_FILE):
        print(f'[-] Registry missing: {REGISTRY_FILE}')
        return False
    with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    projects = registry.get('projects', [])
    drift_detected = False
    dimensions = {name: False for name in ('METADATA', 'GIT', 'RUNTIME', 'BACKUP', 'TRUST')}
    print('[*] Reconciling Filesystem & Physical Git Repositories...')
    for p in projects:
        pid = p['project_id']
        cpath = p.get('canonical_path', '')
        if not os.path.exists(cpath):
            print(f'  [-] DRIFT: Path does not exist physically: {cpath} (project_id={pid})')
            drift_detected = True
            dimensions['METADATA'] = True
            continue
        git_conf = p.get('git', {})
        if git_conf.get('enabled'):
            repo_path = git_conf.get('repository_path') or cpath
            git_dir = os.path.join(repo_path, '.git')
            if not os.path.exists(git_dir):
                print(f'  [-] DRIFT: Git enabled but .git missing at: {repo_path} (project_id={pid})')
                drift_detected = True
                dimensions['GIT'] = True
            else:
                live_remote = get_git_remote(repo_path)
                expected_remote = git_conf.get('remote', '')
                if expected_remote and live_remote and (live_remote != expected_remote):
                    norm_live = live_remote.replace('https://github.com/', '').replace('git@github.com:', '').rstrip('.git')
                    norm_exp = expected_remote.replace('https://github.com/', '').replace('git@github.com:', '').rstrip('.git')
                    if norm_live != norm_exp:
                        print(f"  [-] DRIFT: Git remote mismatch for {pid}: live='{live_remote}' vs registry='{expected_remote}'")
                        drift_detected = True
                        dimensions['GIT'] = True
                if git_conf.get('backup_required', True):
                    branch = git_conf.get('branch', '')
                    head = subprocess.run(['git', '-C', repo_path, 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=15)
                    remote = git_conf.get('remote', '')
                    try:
                        ref = subprocess.run(['git', 'ls-remote', '--exit-code', remote, f'refs/heads/{branch}'], capture_output=True, text=True, timeout=15) if remote and branch else None
                    except subprocess.TimeoutExpired:
                        ref = None
                    remote_sha = ref.stdout.split()[0] if ref and ref.returncode == 0 and ref.stdout.split() else ''
                    status = subprocess.run(['git', '-C', repo_path, 'status', '--porcelain'], capture_output=True, text=True, timeout=15)
                    if not remote_sha or head.returncode or head.stdout.strip() != remote_sha or status.stdout.strip():
                        print(f'  [-] GIT DRIFT: {pid} lacks verified clean remote SHA parity')
                        drift_detected = True
                        dimensions['GIT'] = True
    print('[*] Reconciling WhatsApp Routing Connections...')
    if os.path.exists(WHATSAPP_FILE):
        with open(WHATSAPP_FILE, 'r', encoding='utf-8') as f:
            wa_data = json.load(f)
        wa_map = {c['project_id']: c for c in wa_data.get('connections', [])}
        for p in projects:
            pid = p['project_id']
            reg_wa = p.get('connections', {}).get('whatsapp', {})
            if reg_wa.get('enabled'):
                if pid not in wa_map:
                    print(f'  [-] DRIFT: WhatsApp enabled in registry for {pid}, but missing in WHATSAPP_CONNECTIONS.json')
                    drift_detected = True
                    dimensions['RUNTIME'] = True
    elif any((p.get('connections', {}).get('whatsapp', {}).get('enabled') for p in projects)):
        print('  [-] RUNTIME DRIFT: required WhatsApp connection registry is missing')
        drift_detected = True
        dimensions['RUNTIME'] = True
    print('[*] Reconciling Tmux Window Routes...')
    if os.path.exists(TMUX_FILE):
        with open(TMUX_FILE, 'r', encoding='utf-8') as f:
            tmux_data = json.load(f)
        tmux_map = {c['project_id']: c for c in tmux_data.get('connections', [])}
        for p in projects:
            pid = p['project_id']
            reg_tmux = p.get('runtime', {}).get('tmux_window', '')
            if reg_tmux:
                if pid not in tmux_map:
                    print(f'  [-] DRIFT: Tmux window defined for {pid}, but missing in TMUX_CONNECTIONS.json')
                    drift_detected = True
                    dimensions['RUNTIME'] = True
    elif any((p.get('runtime', {}).get('tmux_window') for p in projects)):
        print('  [-] RUNTIME DRIFT: required tmux connection registry is missing')
        drift_detected = True
        dimensions['RUNTIME'] = True
    print('[*] Reconciling service and port mappings...')
    if os.path.exists(SERVICE_FILE):
        with open(SERVICE_FILE, 'r', encoding='utf-8') as f:
            service_data = json.load(f)
        service_map = {c.get('project_id'): c for c in service_data.get('connections', [])}
        for project in projects:
            expected_services = project.get('runtime', {}).get('services', [])
            expected_ports = project.get('runtime', {}).get('ports', [])
            if (expected_services or expected_ports) and project['project_id'] not in service_map:
                print(f"  [-] RUNTIME DRIFT: service/port mapping missing for {project['project_id']}")
                drift_detected = True
                dimensions['RUNTIME'] = True
    elif any((p.get('runtime', {}).get('services') or p.get('runtime', {}).get('ports') for p in projects)):
        print('  [-] RUNTIME DRIFT: required service registry is missing')
        drift_detected = True
        dimensions['RUNTIME'] = True
    print('[*] Reconciling Operational Webterminal Mapping...')
    if os.path.exists(OPERATIONAL_MAPPING):
        with open(OPERATIONAL_MAPPING, 'r', encoding='utf-8') as f:
            op_data = json.load(f)
        op_map = {c['key']: c for c in op_data.get('projects', [])}
        for p in projects:
            pid = p['project_id']
            if pid not in op_map:
                print(f'  [-] DRIFT: {pid} is registered in PROJECT_REGISTRY but missing in operational mapping')
                drift_detected = True
                dimensions['RUNTIME'] = True
            elif os.path.realpath(op_map[pid].get('folder_path', '')) != os.path.realpath(p.get('canonical_path', '')):
                print(f'  [-] RUNTIME DRIFT: operational path mismatch for {pid}')
                drift_detected = True
                dimensions['RUNTIME'] = True
    else:
        print('  [-] RUNTIME DRIFT: operational webterminal mapping is missing')
        drift_detected = True
        dimensions['RUNTIME'] = True
    group_file = os.path.join(os.path.dirname(OPERATIONAL_MAPPING), 'project_groups.json')
    if os.path.isfile(group_file):
        try:
            with open(group_file, encoding='utf-8') as f:
                runtime_groups = json.load(f)
            canonical = {os.path.realpath(p.get('canonical_path', '')) for p in projects}
            for key, group in runtime_groups.items():
                cwd = group.get('cwd') if isinstance(group, dict) else None
                if cwd and os.path.realpath(cwd) not in canonical:
                    print(f"  [-] RUNTIME DRIFT: WhatsApp group '{key}' points outside the canonical registry")
                    drift_detected = True
                    dimensions['RUNTIME'] = True
        except (OSError, ValueError):
            drift_detected = True
            dimensions['RUNTIME'] = True
    elif any((p.get('connections', {}).get('whatsapp', {}).get('enabled') for p in projects)):
        print('  [-] RUNTIME DRIFT: operational WhatsApp group mapping is missing')
        drift_detected = True
        dimensions['RUNTIME'] = True
    registered_paths = discover_unregistered_projects.load_registered_paths()
    orphans = []
    for root in discover_unregistered_projects.load_managed_roots():
        for candidate in discover_unregistered_projects.scan_for_projects(root):
            if candidate['path'] not in registered_paths:
                orphans.append(candidate['path'])
    if orphans:
        print(f'[-] METADATA DRIFT: {len(set(orphans))} unregistered project candidates')
        drift_detected = True
        dimensions['METADATA'] = True
    catalog_file = os.path.join(SOT_ROOT, 'storage', 'BACKUP_CATALOG.json')
    try:
        with open(catalog_file, encoding='utf-8') as f:
            catalog = json.load(f)
        current_entries = [item for item in catalog.get('backups', []) if not str(item.get('status', '')).startswith('STALE_')]
        if any((item.get('status') not in {'REMOTE_CHECKSUM_VERIFIED', 'REMOTE_RESTORE_VERIFIED'} for item in current_entries)):
            print('[-] BACKUP DRIFT: one or more catalog entries lack remote checksum/restore evidence')
            drift_detected = True
            dimensions['BACKUP'] = True
    except (OSError, ValueError):
        drift_detected = True
        dimensions['BACKUP'] = True
    trust = subprocess.run(['bash', os.path.join(SOT_ROOT, 'trust', 'verify_trust_baseline.sh')], capture_output=True, text=True, timeout=15)
    if trust.returncode:
        print('[-] TRUST DRIFT: installed baseline differs from SOT or is incomplete')
        drift_detected = True
        dimensions['TRUST'] = True
    for dimension, failed in dimensions.items():
        print(f"{dimension} DRIFT: {('DETECTED' if failed else 'NOT DETECTED')}")
    if drift_detected:
        print('\n==========================================')
        print('  RESULT: PROJECT REGISTRY DRIFT DETECTED')
        print('==========================================')
        print('Remediate by running: python3 projects/generate_derived_mappings.py')
        return False
    else:
        print('\n==========================================')
        print('  RESULT: ZERO DRIFT (ALL SYSTEMS IN PARITY)')
        print(f'  Total Projects Reconciled: {len(projects)}')
        print('==========================================')
        return True
if __name__ == '__main__':
    success = reconcile()
    sys.exit(0 if success else 1)