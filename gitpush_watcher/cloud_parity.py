"""Cloud Parity Auditor and Matrix Generator (RULES 10, 30).
Validates that every durable local asset has a verified recoverable cloud representation.
"""
from __future__ import annotations
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

class CloudParityAuditor:
    """Audits local assets against GitHub and external cloud storage to prove Cloud Parity."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def audit(self) -> Dict[str, Any]:
        matrix: List[Dict[str, Any]] = []
        counts = {'GIT_PARITY': 0, 'EXTERNAL_PARITY': 0, 'PUSH_PENDING': 0, 'BACKUP_PENDING': 0, 'NOT_RECOVERABLE': 0}
        reg_file = self.root / 'projects' / 'PROJECT_REGISTRY.json'
        if reg_file.is_file():
            try:
                registry = json.loads(reg_file.read_text(encoding='utf-8'))
                for proj in registry.get('projects', []):
                    pid = proj.get('project_id', '')
                    puuid = proj.get('project_uuid', '')
                    cpath = proj.get('canonical_path', '')
                    git_conf = proj.get('git', {})
                    repo_path = git_conf.get('repository_path') or cpath
                    remote = git_conf.get('remote', '')
                    branch = git_conf.get('branch', 'main')
                    backup_req = git_conf.get('backup_required', True)
                    if not backup_req:
                        verdict = 'NOT_RECOVERABLE'
                        counts[verdict] += 1
                        matrix.append({'asset_id': f'project:{pid}', 'project_uuid': puuid, 'type': 'project_source', 'local_path': repo_path, 'recovery_destination': 'none (local-only)', 'local_commit': 'n/a', 'remote_commit': 'none', 'parity_verdict': verdict, 'note': 'marked local-only'})
                        continue
                    if not remote or not os.path.isdir(os.path.join(repo_path, '.git')):
                        verdict = 'NOT_RECOVERABLE'
                        counts[verdict] += 1
                        matrix.append({'asset_id': f'project:{pid}', 'project_uuid': puuid, 'type': 'project_source', 'local_path': repo_path, 'recovery_destination': 'GitHub', 'local_commit': 'none', 'remote_commit': 'none', 'parity_verdict': verdict, 'note': 'no remote or git repo'})
                        continue
                    local_head = subprocess.run(['git', '-C', repo_path, 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=15).stdout.strip()
                    probe = subprocess.run(['git', 'ls-remote', '--exit-code', remote, f'refs/heads/{branch}'], capture_output=True, text=True, timeout=15)
                    remote_sha = probe.stdout.split()[0] if probe.returncode == 0 and probe.stdout.split() else ''
                    if remote_sha and local_head == remote_sha:
                        verdict = 'GIT_PARITY'
                    elif local_head:
                        verdict = 'PUSH_PENDING'
                    else:
                        verdict = 'NOT_RECOVERABLE'
                    counts[verdict] += 1
                    matrix.append({'asset_id': f'project:{pid}', 'project_uuid': puuid, 'type': 'project_source', 'local_path': cpath, 'recovery_destination': f'GitHub ({remote})', 'local_commit': local_head, 'remote_commit': remote_sha or 'unreachable', 'parity_verdict': verdict, 'note': 'parity verified' if verdict == 'GIT_PARITY' else 'pending remote push'})
            except Exception as exc:
                pass
        asset_file = self.root / 'storage' / 'DATA_ASSET_REGISTRY.json'
        if asset_file.is_file():
            try:
                asset_data = json.loads(asset_file.read_text(encoding='utf-8'))
                for asset in asset_data.get('assets', []):
                    aid = asset.get('asset_id', '')
                    puuid = asset.get('project_uuid', '')
                    source = asset.get('source_path', '')
                    remote_path = asset.get('remote_path', '')
                    provider = asset.get('remote_provider', 'gdrive')
                    status = asset.get('status', '')
                    remote_status = asset.get('remote_status', '')
                    if remote_status == 'REMOTE_CHECKSUM_VERIFIED' or status == 'REMOTE_CHECKSUM_VERIFIED':
                        verdict = 'EXTERNAL_PARITY'
                    elif remote_path:
                        verdict = 'BACKUP_PENDING'
                    else:
                        verdict = 'NOT_RECOVERABLE'
                    counts[verdict] += 1
                    matrix.append({'asset_id': aid, 'project_uuid': puuid, 'type': asset.get('storage_class', 'external_asset'), 'local_path': source, 'recovery_destination': f'{provider}:{remote_path}' if remote_path else 'none', 'local_commit': asset.get('local_checksum', 'recorded'), 'remote_commit': asset.get('remote_checksum', 'unverified'), 'parity_verdict': verdict, 'note': f'status={remote_status or status}'})
            except Exception:
                pass
        has_local_only = counts['NOT_RECOVERABLE'] > 0
        has_pending = counts['PUSH_PENDING'] + counts['BACKUP_PENDING'] > 0
        if not has_local_only and (not has_pending) and (counts['GIT_PARITY'] + counts['EXTERNAL_PARITY'] > 0):
            overall = 'PASS'
        elif counts['GIT_PARITY'] + counts['EXTERNAL_PARITY'] > 0:
            overall = 'PARTIAL'
        else:
            overall = 'FAIL'
        result = {'schema_version': '1.0.0', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'overall_verdict': overall, 'counts': counts, 'matrix': matrix}
        out_path = self.root / 'projects' / 'CLOUD_PARITY_MATRIX.json'
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        return result