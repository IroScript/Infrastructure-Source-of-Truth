"""
Frappe Blank-VM Recovery & Bootstrap Engine (Sections R, S, T).
Reconstructs Frappe project governance, official reference mappings, and agent rules
on a fresh Linux VM without /home/azureuser dependencies.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional


class FrappeBootstrapEngine:
    """Restores Frappe project profile and rules from SOT on fresh hosts."""

    def __init__(self, sot_root: Path):
        self.sot_root = Path(sot_root).resolve()

    def bootstrap(
        self,
        profile_roots: Dict[str, Any],
        auto: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes blank-VM bootstrap for Frappe governance:
        - Creates state directories: official-references, frappe_evidence
        - Installs Frappe coding rules into agent directories
        - Links or copies canonical compatibility contract
        - Lists required external data restorations (database, secrets, site files)
        """
        home = Path(profile_roots.get("HOME", Path.home())).resolve()
        state_root = Path(profile_roots.get("STATE_ROOT", home / ".agents")).resolve()
        projects_root = Path(profile_roots.get("PROJECTS_ROOT", home / "projects")).resolve()

        report: Dict[str, Any] = {
            "status": "BOOTSTRAP_COMPLETE" if not dry_run else "DRY_RUN",
            "home": str(home),
            "state_root": str(state_root),
            "projects_root": str(projects_root),
            "rules_installed": [],
            "directories_created": [],
            "external_data_required": [
                {
                    "asset_id": "alco_localhost_mariadb",
                    "description": "MariaDB database dump for site alco.localhost (_b4b30e57a5907bea)",
                    "type": "database_dump",
                    "storage": "external_encrypted_backup",
                },
                {
                    "asset_id": "alco_site_config_secrets",
                    "description": "Database passwords and encryption keys for site_config.json",
                    "type": "secret_config",
                    "storage": "external_encrypted_backup",
                },
                {
                    "asset_id": "alco_site_files",
                    "description": "Public and private uploads in sites/alco.localhost/{public,private}/files",
                    "type": "persistent_media",
                    "storage": "external_cloud_backup",
                },
            ],
        }

        if dry_run:
            return report

        # 1. Create directories
        for d in (
            state_root / "official-references" / "frappe",
            state_root / "frappe_evidence",
            state_root / "rules",
            home / ".codex" / "rules",
        ):
            d.mkdir(parents=True, exist_ok=True)
            report["directories_created"].append(str(d))

        # 2. Install Frappe agent rules
        rules_src = self.sot_root / "project_profiles" / "frappe" / "rules.md"
        if rules_src.is_file():
            # Install to .agents/rules/frappe.md
            dest_agent = state_root / "rules" / "frappe.md"
            dest_codex = home / ".codex" / "rules" / "frappe.md"
            content = rules_src.read_text(encoding="utf-8")
            dest_agent.write_text(content, encoding="utf-8")
            dest_codex.write_text(content, encoding="utf-8")
            report["rules_installed"].extend([str(dest_agent), str(dest_codex)])

        # 3. Restore local official reference link if source is available
        cand_docs = [
            self.sot_root / "frappe" / "docs-reference",
        ]
        if projects_root.is_dir():
            for p_sub in projects_root.iterdir():
                if p_sub.is_dir():
                    cand_docs.append(p_sub / "frappe-docs-latest")
        if home.is_dir():
            for h_sub in home.iterdir():
                if h_sub.is_dir():
                    cand_docs.append(h_sub / "frappe-docs-latest")
        target_ref = state_root / "official-references" / "frappe"
        for cand in cand_docs:
            if cand.is_dir() and (cand / "MANIFEST.json").is_file():
                try:
                    if target_ref.is_symlink():
                        target_ref.unlink()
                    elif target_ref.is_dir():
                        shutil.rmtree(target_ref)
                    try:
                        target_ref.symlink_to(cand.resolve(), target_is_directory=True)
                    except Exception:
                        shutil.copytree(cand.resolve(), target_ref)
                    report["official_reference_linked"] = str(cand)
                    break
                except Exception:
                    pass

        # 4. Mandatory reference verification before declaring BOOTSTRAP_COMPLETE
        from .reference import FrappeReferenceManager
        ref_mgr = FrappeReferenceManager(self.sot_root)
        ref_res = ref_mgr.verify_reference(state_root=state_root)
        if not ref_res.is_pass:
            report["status"] = "BOOTSTRAP_INCOMPLETE"
            report["failed_stage"] = "REFERENCE_VERIFICATION"
            report["error"] = ref_res.errors[0] if ref_res.errors else "Official reference verification failed"
        else:
            report["status"] = "BOOTSTRAP_COMPLETE" if not dry_run else "DRY_RUN"
            report["reference_verified"] = True

        return report
