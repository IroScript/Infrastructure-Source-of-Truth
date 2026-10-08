"""
CLI Handlers for SOT Frappe & Project Profile Governance (Section E, T, U).
Provides CLI subcommands:
  sot frappe doctor
  sot frappe verify
  sot frappe sync-reference
  sot frappe bootstrap
  sot frappe check-code
  sot profile list
  sot profile verify
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from .base import ProfileRegistry
from .manager import ProjectProfileManager


def handle_frappe_cli(args, sot_root: Path) -> int:
    """Handles 'sot frappe' subcommands."""
    manager = ProjectProfileManager(sot_root)
    profile = ProfileRegistry.get("frappe")
    if not profile:
        print(json.dumps({"error": "Frappe profile not registered"}))
        return 1

    action = getattr(args, "frappe_action", "doctor")
    home = Path(args.home).resolve() if getattr(args, "home", None) else Path(os.environ.get("HOME", Path.home())).resolve()
    state_root = Path(getattr(args, "state_root", None) or os.environ.get("STATE_ROOT") or (home / ".agents")).resolve()
    projects_root = Path(getattr(args, "projects_root", None) or os.environ.get("PROJECTS_ROOT") or (home / "projects")).resolve()
    profile_roots = {"HOME": str(home), "STATE_ROOT": str(state_root), "PROJECTS_ROOT": str(projects_root)}

    # Resolve project path with dynamic root mapping
    proj = manager.resolve_project(getattr(args, "project_id", "frappe_erp_alco") or "frappe_erp_alco", state_root=state_root)
    proj_path = None
    if getattr(args, "project_path", None):
        proj_path = Path(args.project_path).resolve()
    elif getattr(args, "bench_root", None):
        proj_path = Path(args.bench_root).resolve()
    elif proj:
        raw_cpath = proj.get("canonical_path", "")
        proj_name = Path(raw_cpath).name or "Frappe-erp-Alco"
        target_candidate = projects_root / proj_name
        if target_candidate.exists():
            proj_path = target_candidate
        elif (projects_root / "frappe-bench").exists():
            proj_path = projects_root / "frappe-bench"
        elif (home / proj_name).exists():
            proj_path = home / proj_name
        elif (home / "frappe-bench").exists():
            proj_path = home / "frappe-bench"
        elif Path(raw_cpath).exists() and str(home) == "/home/azureuser":
            proj_path = Path(raw_cpath)
        else:
            proj_path = target_candidate
    else:
        for alt in [projects_root / "frappe-bench", home / "frappe-bench"]:
            if alt.exists():
                proj_path = alt
                break
        if not proj_path:
            proj_path = projects_root / "frappe-bench"

    if action == "doctor":
        report = profile.run_doctor(proj_path, profile_roots)
        if getattr(args, "format", "json") == "json":
            print(json.dumps(report, indent=2))
        else:
            print(f"FRAPPE DOCTOR: {report.get('status')}")
            print(f"Site: {report.get('site')} (Online: {report.get('site_online')})")
            print(f"Alco Ecommerce Installed: {report.get('alco_ecommerce_installed')}")
            print(f"Integration Model: {report.get('integration_model')}")
        return 0 if report.get("status") in ("PASS", "HEALTHY") else 1

    elif action == "verify":
        contract = profile.get_compatibility_contract(proj_path)
        ref_res = profile.verify_reference(proj_path, state_root)
        core_res = profile.verify_core_isolation(proj_path)
        test_res = profile.verify_native_test_contract(proj_path)
        passed = bool(contract) and ref_res.is_pass and core_res.is_pass and test_res.is_pass
        payload = {
            "status": "PASS" if passed else "FAIL",
            "contract": contract,
            "reference": ref_res.details,
            "core_isolation": core_res.details,
            "test_contract": test_res.details,
            "errors": ref_res.errors + core_res.errors + test_res.errors,
        }
        if getattr(args, "format", "json") == "json":
            print(json.dumps(payload, indent=2))
        else:
            print(f"FRAPPE VERIFY: {payload['status']}")
            for err in payload["errors"]:
                print(f"  [-] {err}")
        return 0 if passed else 2

    elif action == "sync-reference":
        source_dir = getattr(args, "source_dir", None)
        if not source_dir:
            candidates = [
                sot_root / "frappe" / "docs-reference",
                proj_path / "frappe-docs-latest",
            ]
            if projects_root.is_dir():
                for p_sub in projects_root.iterdir():
                    if p_sub.is_dir():
                        candidates.append(p_sub / "frappe-docs-latest")
            if home.is_dir():
                for h_sub in home.iterdir():
                    if h_sub.is_dir():
                        candidates.append(h_sub / "frappe-docs-latest")
            source_dir = next((c for c in candidates if c.is_dir() and (c / "MANIFEST.json").is_file()), None)
        if not source_dir or not Path(source_dir).is_dir():
            print(json.dumps({"status": "FAIL", "error": "No valid reference source found with MANIFEST.json"}))
            return 1
        source_p = Path(source_dir).resolve()
        from .frappe import FrappeReferenceManager
        ref_mgr = FrappeReferenceManager(sot_root)
        try:
            res = ref_mgr.sync_reference_to_state(source_p, state_root)
            print(json.dumps(res, indent=2))
            return 0
        except Exception as exc:
            print(json.dumps({"status": "FAIL", "error": str(exc)}))
            return 1

    elif action == "bootstrap":
        auto = getattr(args, "auto", False)
        dry_run = getattr(args, "dry_run", False)
        res = profile.bootstrap_project(proj_path, profile_roots, auto=auto, dry_run=dry_run)
        print(json.dumps(res, indent=2))
        return 0 if res.get("status") in ("BOOTSTRAP_COMPLETE", "DRY_RUN") else 1

    elif action == "check-code":
        file_arg = getattr(args, "file", None)
        code_arg = getattr(args, "code", None)
        fpath = Path(file_arg).resolve() if file_arg else None
        code = code_arg
        if not code and fpath and fpath.is_file():
            code = fpath.read_text(encoding="utf-8")
        if not code:
            print(json.dumps({"error": "No code or file specified for checking"}))
            return 1

        findings = profile.check_code_patterns(fpath or Path("unnamed.py"), code)
        status = "OUTDATED_FRAPPE_PATTERN" if findings else "CLEAN"
        print(json.dumps({"status": status, "findings": findings}, indent=2))
        return 2 if findings else 0

    return 0


def handle_profile_cli(args, sot_root: Path) -> int:
    """Handles 'sot profile' subcommands."""
    manager = ProjectProfileManager(sot_root)
    action = getattr(args, "profile_action", "list")
    home = Path(args.home).resolve() if getattr(args, "home", None) else Path(os.environ.get("HOME", Path.home())).resolve()
    state_root = Path(getattr(args, "state_root", None) or os.environ.get("STATE_ROOT") or (home / ".agents")).resolve()
    projects_root = Path(getattr(args, "projects_root", None) or os.environ.get("PROJECTS_ROOT") or (home / "projects")).resolve()

    if action == "list":
        profiles = ProfileRegistry.list_profiles()
        print(json.dumps({"profiles": profiles}, indent=2))
        return 0

    elif action == "verify":
        pid = getattr(args, "project_id", "")
        if not pid:
            print(json.dumps({"error": "Missing --project-id"}))
            return 1
        proj = manager.resolve_project(pid, state_root=state_root)
        if not proj:
            print(json.dumps({"error": f"Project not found: {pid}"}))
            return 1
        file_arg = getattr(args, "file", None)
        proposed = [Path(file_arg).resolve()] if file_arg else None
        ok, reason, details = manager.evaluate_coding_gate(proj, proposed_files=proposed, state_root=state_root)
        print(json.dumps({"passed": ok, "verdict": reason, "details": details}, indent=2))
        return 0 if ok else 2

    return 0
