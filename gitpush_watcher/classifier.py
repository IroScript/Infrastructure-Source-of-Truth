"""Asset Classification & Cloud Parity Routing Engine (RULES 9, 10, 11, 12, 13, 14).
Classifies assets into Classes A through E and un-stages non-Git assets before commit.
"""
from __future__ import annotations
import fnmatch
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple
CLASS_A_GIT = 'CLASS_A_GIT'
CLASS_B_DATABASE = 'CLASS_B_DATABASE'
CLASS_C_LARGE_ASSET = 'CLASS_C_LARGE_ASSET'
CLASS_D_SECRET = 'CLASS_D_SECRET'
CLASS_E_EPHEMERAL = 'CLASS_E_EPHEMERAL'

class AssetClassifier:
    """Classifies files into Cloud Parity classes and routes them appropriately (FIX 9)."""

    def __init__(self, root: Path, large_file_threshold_bytes: int=52428800):
        self.root = Path(root).resolve()
        self.large_threshold = large_file_threshold_bytes
        self.secret_name_patterns = ['.env', '.env.*', '*.env', '*credential*', '*secret*', '*token*', 'id_rsa*', 'id_ecdsa*', 'id_ed25519*', '*.pem', '*.key', '*.p12', '*.pkcs12', 'cookies*', '*session*', '*auth_token*']
        self.secret_content_signatures = [b'-----BEGIN PRIVATE KEY', b'-----BEGIN RSA PRIVATE', b'-----BEGIN OPENSSH PRIVATE', b'-----BEGIN EC PRIVATE', b'AIzaSy', b'aws_secret_access_key']
        self.media_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a'}
        self.archive_extensions = {'.zip', '.tar', '.gz', '.tgz', '.bz2', '.7z', '.iso'}
        self.db_extensions = {'.db', '.sqlite', '.sqlite3', '.db-wal', '.db-shm', '.dump'}
        self.ephemeral_patterns = ['*.tmp', '*.swp', '*.swo', '*~', '*.lock', '.DS_Store']

    def _has_secret_content(self, path: Path) -> bool:
        """Inspects first 64KB of file for common secret and credential signatures."""
        try:
            with open(path, 'rb') as f:
                header = f.read(65536)
            for sig in self.secret_content_signatures:
                if sig.lower() in header.lower():
                    return True
        except OSError:
            pass
        return False

    def _is_suspicious_binary(self, path: Path) -> bool:
        """Detects unknown non-text binaries that should not be blindly added to Git."""
        try:
            with open(path, 'rb') as f:
                chunk = f.read(4096)
            return b'\x00' in chunk
        except OSError:
            pass
        return False

    def classify_file(self, full_path: Path) -> str:
        """Determines Cloud Parity class with fail-closed priority (FIX 9)."""
        name = full_path.name.lower()
        suffix = full_path.suffix.lower()
        for pat in self.secret_name_patterns:
            if fnmatch.fnmatch(name, pat):
                return CLASS_D_SECRET
        if full_path.is_file() and full_path.stat().st_size <= 2 * 1024 * 1024:
            if self._has_secret_content(full_path):
                return CLASS_D_SECRET
        if suffix in self.db_extensions:
            return CLASS_B_DATABASE
        if suffix in self.media_extensions:
            return CLASS_C_LARGE_ASSET
        for pat in self.ephemeral_patterns:
            if fnmatch.fnmatch(name, pat):
                return CLASS_E_EPHEMERAL
        try:
            if full_path.is_file():
                if full_path.stat().st_size > self.large_threshold or suffix in self.archive_extensions:
                    return CLASS_C_LARGE_ASSET
                if suffix not in {'.pyc', '.so', '.o', '.a'} and self._is_suspicious_binary(full_path):
                    if suffix not in {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp'}:
                        return CLASS_C_LARGE_ASSET
        except OSError:
            pass
        return CLASS_A_GIT

    def inspect_and_filter_staged(self, repo_path: Path, project_id: str, project_uuid: str) -> Dict[str, List[str]]:
        """Inspects all currently staged files in repo.
        Un-stages any Class B, C, D, or E files so only Class A remains staged for Git commit.
        Records non-Git files into appropriate metadata registries.
        """
        repo = Path(repo_path).resolve()
        res = subprocess.run(['git', '-C', str(repo), 'diff', '--cached', '--name-only'], capture_output=True, text=True, timeout=15)
        staged_files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        classified: Dict[str, List[str]] = {CLASS_A_GIT: [], CLASS_B_DATABASE: [], CLASS_C_LARGE_ASSET: [], CLASS_D_SECRET: [], CLASS_E_EPHEMERAL: []}
        unstage_paths: List[str] = []
        for rel in staged_files:
            full = repo / rel
            if not full.exists():
                classified[CLASS_A_GIT].append(rel)
                continue
            c_type = self.classify_file(full)
            classified[c_type].append(rel)
            if c_type != CLASS_A_GIT:
                unstage_paths.append(rel)
        if unstage_paths:
            head_check = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--verify', 'HEAD'], capture_output=True, timeout=15)
            if head_check.returncode == 0:
                subprocess.run(['git', '-C', str(repo), 'restore', '--staged', '--', *unstage_paths], capture_output=True, timeout=15)
            else:
                subprocess.run(['git', '-C', str(repo), 'rm', '--cached', '-r', '--', *unstage_paths], capture_output=True, timeout=15)
        if classified[CLASS_B_DATABASE] or classified[CLASS_C_LARGE_ASSET]:
            self._register_external_assets(repo, project_id, project_uuid, classified)
        return classified

    def _register_external_assets(self, repo: Path, project_id: str, project_uuid: str, classified: Dict[str, List[str]]) -> None:
        """Updates storage/DATA_ASSET_REGISTRY.json with discovered databases and large assets."""
        registry_file = self.root / 'storage' / 'DATA_ASSET_REGISTRY.json'
        if not registry_file.exists():
            return
        try:
            data = json.loads(registry_file.read_text(encoding='utf-8'))
            assets = data.setdefault('assets', [])
            existing_sources = {a.get('source_path') for a in assets if a.get('source_path')}
            for rel in classified[CLASS_B_DATABASE]:
                full = str(repo / rel)
                if full not in existing_sources:
                    assets.append({'asset_id': f"{project_id}-db-{rel.replace('/', '_')}", 'project_id': project_id, 'project_uuid': project_uuid, 'storage_class': 'database_snapshot', 'source_path': full, 'backup_required': True, 'remote_provider': 'gdrive', 'remote_path': f'gdrive:IroScript_Backups/projects/{project_id}/databases/{rel}', 'status': 'BACKUP_PENDING'})
                    existing_sources.add(full)
            for rel in classified[CLASS_C_LARGE_ASSET]:
                full = str(repo / rel)
                if full not in existing_sources:
                    assets.append({'asset_id': f"{project_id}-large-{rel.replace('/', '_')}", 'project_id': project_id, 'project_uuid': project_uuid, 'storage_class': 'large_asset', 'source_path': full, 'backup_required': True, 'remote_provider': 'gdrive', 'remote_path': f'gdrive:IroScript_Backups/projects/{project_id}/assets/{rel}', 'status': 'BACKUP_PENDING'})
                    existing_sources.add(full)
            registry_file.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        except Exception:
            pass