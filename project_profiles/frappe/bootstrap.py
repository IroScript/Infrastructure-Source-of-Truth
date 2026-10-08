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
        - Resolves project root and verifies physical bench presence.
        - Triggers generic project recovery if auto=True and bench is missing.
        - Reports explicit stages: PROJECT_MAPPING_RESOLVED, PROJECT_RESTORED,
          REFERENCE_RESTORED, RULES_RESTORED, EXTERNAL_DATA_PENDING.
        - Never claims BOOTSTRAP_COMPLETE when the physical bench root is missing.
        """
        home = Path(profile_roots.get("HOME", Path.home())).resolve()
        state_root = Path(profile_roots.get("STATE_ROOT", home / ".agents")).resolve()
        projects_root = Path(profile_roots.get("PROJECTS_ROOT", home / "projects")).resolve()

        rule_name = "frappe" + ".md"
        stages = ["PROJECT_MAPPING_RESOLVED"]
        report: Dict[str, Any] = {
            "status": "BOOTSTRAP_INCOMPLETE",
            "stage": "PROJECT_MAPPING_RESOLVED",
            "stages": stages,
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
            report["status"] = "DRY_RUN"
            return report

        # 1. Create state directories
        for d in (
            state_root / "official-references" / "frappe",
            state_root / "frappe_evidence",
            state_root / "rules",
            home / ".codex" / "rules",
            projects_root,
        ):
            d.mkdir(parents=True, exist_ok=True)
            report["directories_created"].append(str(d))

        reg_src = self.sot_root / "projects" / "PROJECT_REGISTRY.json"
        reg_dest = state_root / "PROJECT_REGISTRY.json"
        if reg_src.is_file() and not reg_dest.exists():
            try:
                shutil.copy2(reg_src, reg_dest)
                report["directories_created"].append(str(reg_dest))
            except Exception:
                pass

        # 2. Check or restore physical bench directory
        bench_candidates = [
            projects_root / "Frappe-erp-Alco" / "frappe-bench",
            projects_root / "Frappe-erp-Alco",
            projects_root / "frappe-bench",
        ]
        bench_found = next((b for b in bench_candidates if (b / "apps").is_dir()), None)

        if not bench_found and auto:
            # Automatic generic project recovery handoff (Section B4.3)
            try:
                from bootstrap.project_recovery import ProjectRecoveryOrchestrator
                rec_orch = ProjectRecoveryOrchestrator(self.sot_root)
                rec_res = rec_orch.recover_frappe_bench(projects_root / "Frappe-erp-Alco")
                if rec_res.get("status") in ("PROJECT_RESTORED", "EXISTING"):
                    bench_found = projects_root / "Frappe-erp-Alco" / "frappe-bench"
            except Exception as rec_err:
                report["recovery_error"] = str(rec_err)

        if not bench_found or not bench_found.is_dir():
            report["status"] = "BOOTSTRAP_INCOMPLETE"
            report["failed_stage"] = "PROJECT_RESTORE_BLOCKED"
            report["reason"] = "PROJECT_RESTORE_BLOCKED"
            report["error"] = "Frappe bench root physically missing under deployment root"
            return report

        stages.append("PROJECT_RESTORED")
        report["bench_root"] = str(bench_found)

        # 3. Install Frappe agent rules
        rules_src = self.sot_root / "project_profiles" / "frappe" / "rules.md"
        if rules_src.is_file():
            dest_agent = state_root / "rules" / rule_name
            dest_codex = home / ".codex" / "rules" / rule_name
            content = rules_src.read_text(encoding="utf-8")
            dest_agent.write_text(content, encoding="utf-8")
            dest_codex.write_text(content, encoding="utf-8")
            report["rules_installed"].extend([str(dest_agent), str(dest_codex)])
            stages.append("RULES_RESTORED")

        # 4. Restore local official reference link if source is available
        cand_docs = [
            self.sot_root / "frappe" / "docs-reference",
            bench_found.parent / "frappe-docs-latest",
            bench_found / "frappe-docs-latest",
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
                    stages.append("REFERENCE_RESTORED")
                    break
                except Exception:
                    pass

        # 5. Mandatory reference verification before declaring BOOTSTRAP_COMPLETE
        from .reference import FrappeReferenceManager
        ref_mgr = FrappeReferenceManager(self.sot_root)
        ref_res = ref_mgr.verify_reference(state_root=state_root)
        if not ref_res.is_pass:
            report["status"] = "BOOTSTRAP_INCOMPLETE"
            report["failed_stage"] = "REFERENCE_VERIFICATION"
            report["error"] = ref_res.errors[0] if ref_res.errors else "Official reference verification failed"
        else:
            stages.append("EXTERNAL_DATA_PENDING")
            report["status"] = "BOOTSTRAP_COMPLETE" if not dry_run else "DRY_RUN"
            report["stage"] = "EXTERNAL_DATA_PENDING"
            report["reference_verified"] = True

        return report
