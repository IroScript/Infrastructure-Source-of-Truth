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
from pathlib import Path
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

def resolve_encryption_key(explicit_key=None) -> str:
    """Resolves externally provisioned encryption key; rejects tracked fallback."""
    if explicit_key:
        return str(explicit_key).strip()
    env_key = os.environ.get('BACKUP_ENCRYPTION_KEY') or os.environ.get('AGY_BACKUP_KEY')
    if env_key:
        return env_key.strip()
    key_file = os.environ.get('BACKUP_KEY_FILE')
    if not key_file:
        candidate = Path.home() / '.agents/.verification_secret.key'
        if candidate.is_file():
            key_file = str(candidate)
    if key_file and os.path.isfile(key_file):
        try:
            with open(key_file, 'r', encoding='utf-8') as f:
                k = f.read().strip()
                if k:
                    return k
        except OSError:
            pass
    return ""

DEFAULT_ENCRYPTION_KEY = resolve_encryption_key()

def encrypt_file(src_path, dst_path, key=None):
    encryption_key = resolve_encryption_key(key)
    if not encryption_key:
        raise ValueError("Encryption key required but not provisioned (set BACKUP_ENCRYPTION_KEY or AGY_BACKUP_KEY)")
    cmd = ['openssl', 'enc', '-aes-256-cbc', '-salt', '-pbkdf2', '-in', str(src_path), '-out', str(dst_path), '-pass', f'pass:{encryption_key}']
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError(f"OpenSSL encryption failed: {p.stderr.strip()}")
    return dst_path

def decrypt_file(src_path, dst_path, key=None):
    decryption_key = resolve_encryption_key(key)
    if not decryption_key:
        raise ValueError("Decryption key required but not provisioned (set BACKUP_ENCRYPTION_KEY or AGY_BACKUP_KEY)")
    cmd = ['openssl', 'enc', '-d', '-aes-256-cbc', '-salt', '-pbkdf2', '-in', str(src_path), '-out', str(dst_path), '-pass', f'pass:{decryption_key}']
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError(f"OpenSSL decryption failed: {p.stderr.strip()}")
    return dst_path

def restore_asset(asset, target_path, key=None):
    remote_path = asset.get('remote_path')
    if not remote_path:
        raise ValueError(f"No remote path declared for asset {asset.get('asset_id')}")
    encryption = asset.get('encryption', 'none')
    is_encrypted = encryption in {'aes-256-cbc', 'required'} or asset.get('classification') == 'secret'
    if is_encrypted:
        fd, enc_path = tempfile.mkstemp(prefix='agy-restore-enc-', suffix='.enc')
        os.close(fd)
        try:
            cmd = ['rclone', 'copyto', remote_path, enc_path]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if p.returncode != 0:
                raise RuntimeError(f"rclone restore download failed: {p.stderr.strip()}")
            decrypt_file(enc_path, target_path, key=key)
        finally:
            if os.path.exists(enc_path):
                os.unlink(enc_path)
    else:
        cmd = ['rclone', 'copyto', remote_path, str(target_path)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if p.returncode != 0:
            raise RuntimeError(f"rclone restore download failed: {p.stderr.strip()}")
    return target_path

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

    upload_path = snapshot_path
    temp_enc = None
    is_encrypted = False
    encryption_setting = asset.get('encryption', 'none')
    if asset.get('encryption') in {'aes-256-cbc', 'required'} or asset.get('classification') == 'secret':
        key = resolve_encryption_key()
        if not key:
            print('[-] Encryption key missing for encrypted asset; failing immediately before upload')
            return {'asset_id': asset_id, 'status': 'FAILED', 'reason': 'ENCRYPTION_KEY_MISSING: Externally provisioned encryption key required'}
        try:
            fd, temp_enc = tempfile.mkstemp(prefix='agy-backup-enc-', suffix='.enc')
            os.close(fd)
            encrypt_file(snapshot_path, temp_enc, key=key)
            upload_path = temp_enc
            is_encrypted = True
            encryption_setting = 'aes-256-cbc'
        except Exception as enc_err:
            print(f'[-] Encryption enforcement failed: {enc_err}')
            if temp_enc and os.path.exists(temp_enc):
                os.unlink(temp_enc)
            return {'asset_id': asset_id, 'status': 'FAILED', 'reason': f'ENCRYPTION_ENFORCEMENT_FAILED: {enc_err}'}

    size = os.path.getsize(upload_path)
    checksum = sha256_file(upload_path)
    md5_checksum = md5_file(upload_path)
    source_checksum = sha256_file(snapshot_path)
    print(f'    Size: {size} bytes | SHA256: {checksum[:16]}...')
    if dry_run:
        if temp_enc and os.path.exists(temp_enc):
            os.unlink(temp_enc)
        print('    [DRY-RUN] Would execute rclone copy to remote.')
        return {'asset_id': asset_id, 'status': 'BACKUP REQUIRED', 'checksum': checksum, 'size': size}
    print(f'    [*] Uploading to {target_remote}...')
    remote_object = os.path.basename(source_path)
    remote_destination = asset.get('remote_path') or target_remote.rstrip('/') + '/' + remote_object
    cmd = ['rclone', 'copyto', upload_path, remote_destination]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if temp_enc and os.path.exists(temp_enc):
        os.unlink(temp_enc)
    if p.returncode != 0:
        print(f'[-] Backup upload failed: {p.stderr.strip()}')
        return {'asset_id': asset_id, 'status': 'FAILED', 'reason': p.stderr.strip()}
    print('    [+] Upload completed with rc=0 (Status: REMOTE_UPLOAD_COMPLETE)')
    status = 'REMOTE_UPLOAD_COMPLETE'
    match = None
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
    catalog_entry = {'backup_id': f'bak_{asset_id}_{int(time.time())}', 'asset_id': asset_id, 'project_id': asset.get('project_id', 'unknown'), 'source_checksum': source_checksum, 'encrypted_checksum': checksum if is_encrypted else None, 'remote_checksum_algorithm': 'md5' if verify_remote and match and match.get('Hashes', {}).get('md5') else '', 'remote_checksum': match.get('Hashes', {}).get('md5', '') if verify_remote and match else '', 'remote_destination': os.path.dirname(remote_destination), 'remote_object': remote_object, 'remote_path': remote_destination, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'size': size, 'encryption': encryption_setting, 'status': status, 'remote_object_id': match.get('ID', '') if verify_remote and match else '', 'remote_size': match.get('Size') if verify_remote and match else None, 'restore_verification': 'PENDING_RESTORE_TEST'}
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