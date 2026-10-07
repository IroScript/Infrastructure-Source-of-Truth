"""Google Drive/object storage adapter through rclone; no provider ID is an asset identity."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

class RcloneProvider:

    def __init__(self, executable='rclone'):
        self.executable = executable

    def list(self, remote_path):
        result = subprocess.run([self.executable, 'lsjson', '--hash', '--recursive', remote_path], capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'rclone list failed')
        return json.loads(result.stdout)

    def metadata(self, remote_file):
        result = subprocess.run([self.executable, 'lsjson', '--hash', remote_file], capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'rclone metadata failed')
        rows = [x for x in json.loads(result.stdout) if not x.get('IsDir')]
        return rows[0] if len(rows) == 1 else None

    def checksum(self, local_file, remote_file):
        local_file = Path(local_file)
        remote = self.metadata(remote_file)
        if not remote:
            return {'exists': False, 'status': 'BACKUP_REQUIRED'}
        digest = hashlib.md5()
        with local_file.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        local_md5 = digest.hexdigest()
        remote_md5 = remote.get('Hashes', {}).get('md5')
        return {'exists': True, 'size_match': remote.get('Size') == local_file.stat().st_size, 'remote_md5': remote_md5, 'local_md5': local_md5, 'status': 'REMOTE_CHECKSUM_VERIFIED' if remote.get('Size') == local_file.stat().st_size and remote_md5 == local_md5 else 'REMOTE_OBJECT_VERIFIED', 'object_id': remote.get('ID')}

    def upload(self, local_file, remote_file):
        result = subprocess.run([self.executable, 'copyto', str(local_file), remote_file], capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'rclone upload failed')
        return {'status': 'REMOTE_UPLOAD_COMPLETE', 'stdout': result.stdout}

    def download(self, remote_file, local_file):
        result = subprocess.run([self.executable, 'copyto', remote_file, str(local_file)], capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'rclone download failed')
        return {'status': 'REMOTE_OBJECT_DOWNLOADED', 'path': str(local_file)}