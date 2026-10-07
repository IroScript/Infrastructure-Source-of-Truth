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

CLASS_A_GIT = "CLASS_A_GIT"
CLASS_B_DATABASE = "CLASS_B_DATABASE"
CLASS_C_LARGE_ASSET = "CLASS_C_LARGE_ASSET"
CLASS_D_SECRET = "CLASS_D_SECRET"
CLASS_E_EPHEMERAL = "CLASS_E_EPHEMERAL"


class AssetClassifier:
    """Classifies files into Cloud Parity classes and routes them appropriately."""

    def __init__(self, root: Path, large_file_threshold_bytes: int = 52428800):
        self.root = Path(root).resolve()
        self.large_threshold = large_file_threshold_bytes
        self.secret_patterns = [
            ".env.prod",
            ".env.production",
            "id_rsa*",
            "id_ecdsa*",
            "id_ed25519*",
            "*.pem",
            "*.key",
            "*.p12",
            "*.pkcs12"
        ]
        self.db_extensions = {".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm"}
        self.ephemeral_patterns = [
            "*.tmp",
            "*.swp",
            "*.swo",
            "*~",
            "*.lock",
            ".DS_Store"
        ]

    def classify_file(self, full_path: Path) -> str:
        """Determines the Cloud Parity class for a single file path."""
        name = full_path.name
        
        # Class D: Secrets
        for pat in self.secret_patterns:
            if fnmatch.fnmatch(name, pat):
                return CLASS_D_SECRET
        
        # Class B: Live Database files
        if full_path.suffix.lower() in self.db_extensions:
            return CLASS_B_DATABASE

        # Ephemeral
        for pat in self.ephemeral_patterns:
            if fnmatch.fnmatch(name, pat):
                return CLASS_E_EPHEMERAL

        # Class C: Large files
        try:
            if full_path.is_file() and full_path.stat().st_size > self.large_threshold:
                return CLASS_C_LARGE_ASSET
        except OSError:
            pass

        # Class A: Normal source, docs, configs, logs, archives
        return CLASS_A_GIT

    def inspect_and_filter_staged(self, repo_path: Path, project_id: str, project_uuid: str) -> Dict[str, List[str]]:
        """Inspects all currently staged files in repo.
        Un-stages any Class B, C, D, or E files so only Class A remains staged for Git commit.
        Records non-Git files into appropriate metadata registries.
        """
        repo = Path(repo_path).resolve()
        res = subprocess.run(
            ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True
        )
        staged_files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        
        classified: Dict[str, List[str]] = {
            CLASS_A_GIT: [],
            CLASS_B_DATABASE: [],
            CLASS_C_LARGE_ASSET: [],
            CLASS_D_SECRET: [],
            CLASS_E_EPHEMERAL: []
        }

        unstage_paths: List[str] = []

        for rel in staged_files:
            full = repo / rel
            if not full.exists():
                # Deleted file staged for removal in Git
                classified[CLASS_A_GIT].append(rel)
                continue
            
            c_type = self.classify_file(full)
            classified[c_type].append(rel)

            if c_type != CLASS_A_GIT:
                unstage_paths.append(rel)

        # Un-stage non-Git files from index
        if unstage_paths:
            head_check = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
                capture_output=True
            )
            if head_check.returncode == 0:
                subprocess.run(
                    ["git", "-C", str(repo), "restore", "--staged", "--", *unstage_paths],
                    capture_output=True
                )
            else:
                subprocess.run(
                    ["git", "-C", str(repo), "rm", "--cached", "-r", "--", *unstage_paths],
                    capture_output=True
                )

        # Register external assets if any Class B or Class C detected
        if classified[CLASS_B_DATABASE] or classified[CLASS_C_LARGE_ASSET]:
            self._register_external_assets(repo, project_id, project_uuid, classified)

        return classified

    def _register_external_assets(self, repo: Path, project_id: str, project_uuid: str, classified: Dict[str, List[str]]) -> None:
        """Updates storage/DATA_ASSET_REGISTRY.json with discovered databases and large assets."""
        registry_file = self.root / "storage" / "DATA_ASSET_REGISTRY.json"
        if not registry_file.exists():
            return
        
        try:
            data = json.loads(registry_file.read_text(encoding="utf-8"))
            assets = data.setdefault("assets", [])
            existing_sources = {a.get("source_path") for a in assets if a.get("source_path")}

            for rel in classified[CLASS_B_DATABASE]:
                full = str(repo / rel)
                if full not in existing_sources:
                    assets.append({
                        "asset_id": f"{project_id}-db-{rel.replace('/', '_')}",
                        "project_id": project_id,
                        "project_uuid": project_uuid,
                        "storage_class": "database_snapshot",
                        "source_path": full,
                        "backup_required": True,
                        "remote_provider": "gdrive",
                        "remote_path": f"gdrive:IroScript_Backups/projects/{project_id}/databases/{rel}",
                        "status": "BACKUP_PENDING"
                    })
                    existing_sources.add(full)

            for rel in classified[CLASS_C_LARGE_ASSET]:
                full = str(repo / rel)
                if full not in existing_sources:
                    assets.append({
                        "asset_id": f"{project_id}-large-{rel.replace('/', '_')}",
                        "project_id": project_id,
                        "project_uuid": project_uuid,
                        "storage_class": "large_asset",
                        "source_path": full,
                        "backup_required": True,
                        "remote_provider": "gdrive",
                        "remote_path": f"gdrive:IroScript_Backups/projects/{project_id}/assets/{rel}",
                        "status": "BACKUP_PENDING"
                    })
                    existing_sources.add(full)

            registry_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
