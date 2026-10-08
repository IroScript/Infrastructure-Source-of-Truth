"""
Project Profile Manager (Section U & F).
Coordinates profile resolution, official reference enforcement, and pre-coding gates.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import ProfileRegistry, ProfileVerificationResult, ProjectProfile


class ProjectProfileManager:
    """Manages project profile resolution and enforcement across managed workspaces."""

    def __init__(self, sot_root: Path):
        self.sot_root = Path(sot_root).resolve()
        self._ensure_profiles_registered()

    def _ensure_profiles_registered(self) -> None:
        """Autodiscover and register built-in profiles."""
        try:
            from .frappe import FrappeProjectProfile
            if not ProfileRegistry.get("frappe"):
                ProfileRegistry.register(FrappeProjectProfile(self.sot_root))
        except ImportError:
            pass

    def load_project_registry(self, state_root: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Loads PROJECT_REGISTRY.json from state root or SOT fallback."""
        candidates = []
        if state_root:
            candidates.append(Path(state_root) / "PROJECT_REGISTRY.json")
        candidates.extend([
            self.sot_root / "projects" / "PROJECT_REGISTRY.json",
            Path.home() / ".agents" / "PROJECT_REGISTRY.json",
        ])
        for cand in candidates:
            if cand.is_file():
                try:
                    data = json.loads(cand.read_text(encoding="utf-8"))
                    return data.get("projects", [])
                except Exception:
                    continue
        return []

    def resolve_project(
        self,
        identifier: str,
        state_root: Optional[Path] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolves a project by project_id, project_uuid, or canonical_path."""
        projects = self.load_project_registry(state_root)
        target = str(identifier).strip()
        # Direct match on ID or UUID
        for p in projects:
            if p.get("project_id") == target or p.get("project_uuid") == target:
                return p
        # Match on path or alias
        target_path = Path(target).resolve()
        for p in projects:
            cpath = Path(p.get("canonical_path", "")).resolve()
            if cpath == target_path:
                return p
            for alias in p.get("aliases", []):
                if Path(alias).resolve() == target_path:
                    return p
        return None

    def get_profile_for_project(self, project: Dict[str, Any]) -> Optional[ProjectProfile]:
        """Resolves the active ProjectProfile for a project dictionary."""
        ptype = project.get("project_type", "")
        return ProfileRegistry.get_for_project_type(ptype)

    def evaluate_coding_gate(
        self,
        project: Dict[str, Any],
        proposed_files: Optional[List[Path]] = None,
        code_snippets: Optional[Dict[Path, str]] = None,
        state_root: Optional[Path] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Enforces the pre-coding gate (Section E, F, G, H, J, K):
        1. Resolves project profile. If no profile, passes as generic project.
        2. Verifies compatibility contract.
        3. Verifies official reference freshness and matching major.
        4. Audits core modification protection.
        5. Lints code for outdated/forbidden patterns.
        """
        profile = self.get_profile_for_project(project)
        if not profile:
            return True, "GENERIC_PROJECT_GATE_PASS", {}

        proj_path = Path(project.get("canonical_path", "")).resolve()
        s_root = state_root or (Path.home() / ".agents")

        # 1. Compatibility Contract
        contract = profile.get_compatibility_contract(proj_path)
        if not contract:
            return False, "COMPATIBILITY_CONTRACT_MISSING", {"error": "No compatibility contract found"}

        # 2. Reference Verification
        ref_res = profile.verify_reference(proj_path, s_root)
        if not ref_res.is_pass:
            err = ref_res.errors[0] if ref_res.errors else "FRAPPE_REFERENCE_NOT_VERIFIED"
            return False, err, {"reference_verification": ref_res.details, "errors": ref_res.errors}

        # 3. Core Framework Modification Protection
        core_res = profile.verify_core_isolation(proj_path)
        if not core_res.is_pass:
            err = core_res.errors[0] if core_res.errors else "CORE_MODIFICATION_PROHIBITED"
            return False, err, {"core_isolation": core_res.details, "errors": core_res.errors}

        # 4. Pattern Checks on Proposed Files/Code
        findings: List[Dict[str, Any]] = []
        if code_snippets:
            for fpath, code in code_snippets.items():
                p_findings = profile.check_code_patterns(fpath, code)
                findings.extend(p_findings)
        elif proposed_files:
            for fpath in proposed_files:
                if fpath.is_file() and fpath.suffix == ".py":
                    try:
                        code = fpath.read_text(encoding="utf-8")
                        p_findings = profile.check_code_patterns(fpath, code)
                        findings.extend(p_findings)
                    except Exception:
                        pass

        if findings:
            return False, "OUTDATED_FRAPPE_PATTERN", {"pattern_findings": findings}

        # 5. Native Test and Component Structure Verification
        if hasattr(profile, "verify_native_test_contract"):
            test_res = profile.verify_native_test_contract(proj_path)
            if not test_res.is_pass:
                err = test_res.errors[0] if test_res.errors else "FRAPPE_TEST_CONTRACT_FAILED"
                return False, err, {"test_contract": test_res.details, "errors": test_res.errors}

        return True, "OFFICIAL_SOURCE_GATE_PASS", {
            "profile": profile.profile_name,
            "contract": contract,
            "reference": ref_res.details,
        }
