"""
backup_data.py — Registry-Driven Data & Database Backup Engine.
Part of the AGY Universal Project Lifecycle & Backup Control System.

Strict Status Progression:
  DISCOVERED -> BACKUP REQUIRED -> BACKUP CREATED -> REMOTE VERIFIED -> RESTORE VERIFIED
Note: rclone copy returning exit code 0 establishes REMOTE VERIFIED, NOT RESTORE VERIFIED.
RESTORE VERIFIED requires an independent restore and integrity verification run.
"""
import os
import sys
import json
import hashlib
import argparse
import subprocess
import time
import sqlite3
import tempfile
from contextlib import contextmanager
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(SCRIPT_DIR), 'projects'))
from atomic_json import atomic_write_json, read_json, registry_lock, project_lock
REGISTRY_FILE = os.path.join(SCRIPT_DIR, 'DATA_ASSET_REGISTRY.json')
CATALOG_FILE = os.path.join(SCRIPT_DIR, 'BACKUP_CATALOG.json')

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while (chunk := f.read(65536)):
            h.update(chunk)
    return h.hexdigest()

def md5_file(filepath):
    h = hashlib.md5()
    with open(filepath, 'rb') as stream:
        while (chunk := stream.read(1024 * 1024)):
            h.update(chunk)
    return h.hexdigest()

def load_assets():
    if not os.path.exists(REGISTRY_FILE):
        raise FileNotFoundError(f'Asset registry missing: {REGISTRY_FILE}')
    with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f).get('assets', [])

def classify_remote_listing(items, filename, size, checksum, md5_checksum=None):
    match = next((item for item in items if item.get('Name') == filename and item.get('Size') == size), None)
    if not match:
        return ('REMOTE_UPLOAD_COMPLETE', None)
    hashes = match.get('Hashes', {})
    if checksum in hashes.values() or (md5_checksum and hashes.get('md5') == md5_checksum):
        return ('REMOTE_CHECKSUM_VERIFIED', match)
    return ('REMOTE_OBJECT_VERIFIED', match)

@contextmanager
def consistent_snapshot(source_path):
    """Use SQLite's online backup API so committed WAL data enters one consistent snapshot."""
    path = os.path.abspath(source_path)
    if os.path.isdir(path):
        raise ValueError('Directory assets require a per-file manifest and cannot use single-file backup')
    if os.path.splitext(path)[1].lower() not in {'.db', '.sqlite', '.sqlite3'}:
        yield path
        return
    with tempfile.TemporaryDirectory(prefix='agy-sqlite-snapshot-') as temp_dir:
        snapshot = os.path.join(temp_dir, os.path.basename(path))
        source = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=30)
        destination = sqlite3.connect(snapshot)
        try:
            source.backup(destination)
            check = destination.execute('PRAGMA integrity_check').fetchone()
            if not check or check[0] != 'ok':
                raise RuntimeError(f'SQLite snapshot integrity check failed for {os.path.basename(path)}')
        finally:
            destination.close()
            source.close()
        yield snapshot

def backup_asset(asset, dry_run=False, verify_remote=True):
    with project_lock('asset:' + asset['asset_id']):
        return _backup_asset_locked(asset, dry_run, verify_remote)

def _backup_asset_locked(asset, dry_run=False, verify_remote=True):
    source_path = asset['source_path']
    if not os.path.exists(source_path):
        return {'asset_id': asset['asset_id'], 'status': 'FAILED', 'reason': 'SOURCE_NOT_FOUND'}
    try:
        with consistent_snapshot(source_path) as snapshot:
            return _backup_asset_snapshot(asset, snapshot, dry_run, verify_remote)
    except Exception as exc:
        return {'asset_id': asset['asset_id'], 'status': 'FAILED', 'reason': str(exc)}

def _backup_asset_snapshot(asset, snapshot_path, dry_run=False, verify_remote=True):
    asset_id = asset['asset_id']
    source_path = asset['source_path']
    target_remote = asset.get('primary_backup_target', '')
    print(f'\n[*] Processing Asset: {asset_id}')
    print(f'    Source: {source_path}')
    print(f'    Target: {target_remote}')
    size = os.path.getsize(snapshot_path)
    checksum = sha256_file(snapshot_path)
    md5_checksum = md5_file(snapshot_path)
    print(f'    Size: {size} bytes | SHA256: {checksum[:16]}...')
    if dry_run:
        print('    [DRY-RUN] Would execute rclone copy to remote.')
        return {'asset_id': asset_id, 'status': 'BACKUP REQUIRED', 'checksum': checksum, 'size': size}
    print(f'    [*] Uploading to {target_remote}...')
    remote_object = os.path.basename(source_path)
    remote_destination = asset.get('remote_path') or target_remote.rstrip('/') + '/' + remote_object
    cmd = ['rclone', 'copyto', snapshot_path, remote_destination]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if p.returncode != 0:
        print(f'[-] Backup upload failed: {p.stderr.strip()}')
        return {'asset_id': asset_id, 'status': 'FAILED', 'reason': p.stderr.strip()}
    print('    [+] Upload completed with rc=0 (Status: REMOTE_UPLOAD_COMPLETE)')
    status = 'REMOTE_UPLOAD_COMPLETE'
    if verify_remote:
        dest_filename = remote_object
        check_p = subprocess.run(['rclone', 'lsjson', '--hash', os.path.dirname(remote_destination)], capture_output=True, text=True, timeout=15)
        try:
            items = json.loads(check_p.stdout) if check_p.returncode == 0 else []
        except json.JSONDecodeError:
            items = []
        status, match = classify_remote_listing(items, dest_filename, size, checksum, md5_checksum)
        if match:
            print(f"    [+] Exact remote object and size verified for '{dest_filename}' (Status: {status})")
        else:
            print(f'    [!] Exact remote object/size could not be confirmed: {dest_filename}')
    catalog_entry = {'backup_id': f'bak_{asset_id}_{int(time.time())}', 'asset_id': asset_id, 'project_id': asset.get('project_id', 'unknown'), 'source_checksum': checksum, 'remote_checksum_algorithm': 'md5' if verify_remote and match and match.get('Hashes', {}).get('md5') else '', 'remote_checksum': match.get('Hashes', {}).get('md5', '') if verify_remote and match else '', 'remote_destination': os.path.dirname(remote_destination), 'remote_object': remote_object, 'remote_path': remote_destination, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'size': size, 'encryption': asset.get('encryption', 'none'), 'status': status, 'remote_object_id': match.get('ID', '') if verify_remote and match else '', 'remote_size': match.get('Size') if verify_remote and match else None, 'restore_verification': 'PENDING_RESTORE_TEST'}
    if os.path.exists(CATALOG_FILE):
        with registry_lock(CATALOG_FILE):
            cat = read_json(CATALOG_FILE)
            cat.setdefault('backups', []).append(catalog_entry)
            cat['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            atomic_write_json(CATALOG_FILE, cat)
    with registry_lock(REGISTRY_FILE):
        assets_registry = read_json(REGISTRY_FILE)
        for registered in assets_registry.get('assets', []):
            if registered.get('asset_id') == asset_id:
                registered.update({'last_backup_checksum': checksum, 'last_backup_time': catalog_entry['timestamp'], 'remote_status': status, 'remote_path': remote_destination, 'remote_object_id': catalog_entry['remote_object_id'], 'remote_size': catalog_entry['remote_size'], 'remote_checksum_algorithm': catalog_entry['remote_checksum_algorithm'], 'remote_checksum': catalog_entry['remote_checksum'], 'restore_status': 'PENDING_RESTORE_TEST'})
        atomic_write_json(REGISTRY_FILE, assets_registry)
    return catalog_entry

def main():
    parser = argparse.ArgumentParser(description='Universal Data & Database Backup Engine')
    parser.add_argument('--asset', default='', help='Specific asset_id to back up (default: all)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without uploading')
    parser.add_argument('--no-verify', action='store_true', help='Skip remote existence verification')
    args = parser.parse_args()
    assets = load_assets()
    target_assets = [a for a in assets if a['asset_id'] == args.asset] if args.asset else [a for a in assets if a.get('backup_required')]
    print(f'=== UNIVERSAL BACKUP ENGINE (Assets to evaluate: {len(target_assets)}) ===')
    results = []
    for a in target_assets:
        res = backup_asset(a, dry_run=args.dry_run, verify_remote=not args.no_verify)
        results.append(res)
    print('\n==========================================')
    print('  BACKUP RUN SUMMARY')
    print('==========================================')
    for r in results:
        print(f"  - {r['asset_id']}: {r.get('status', 'ERROR')}")
if __name__ == '__main__':
    main()