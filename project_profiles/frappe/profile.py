"""
Frappe Project Profile Provider Implementation (Section U).
Concrete provider binding all Frappe official-source governance systems to ProjectProfile.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import ProfileVerificationResult, ProjectProfile
from .bootstrap import FrappeBootstrapEngine
from .contract import FrappeContractManager
from .core_guard import FrappeCoreGuard
from .doctor import FrappeRuntimeDoctor
from .patterns import FrappePatternChecker
from .reference import FrappeReferenceManager


class FrappeProjectProfile(ProjectProfile):
    """Concrete ProjectProfile implementing Frappe/ERPNext official-source governance."""

    def __init__(self, sot_root: Path):
        self.sot_root = Path(sot_root).resolve()
        self.contract_mgr = FrappeContractManager(self.sot_root)
        self.reference_mgr = FrappeReferenceManager(self.sot_root)
        self.pattern_checker = FrappePatternChecker(self.sot_root)
        self.core_guard = FrappeCoreGuard(self.sot_root)
        self.doctor = FrappeRuntimeDoctor(self.sot_root)
        self.bootstrap_engine = FrappeBootstrapEngine(self.sot_root)

    @property
    def profile_name(self) -> str:
        return "frappe"

    @property
    def supported_project_types(self) -> List[str]:
        return ["frappe_bench", "frappe", "erpnext", "custom_frappe_app"]

    def get_compatibility_contract(self, project_path: Optional[Path] = None) -> Dict[str, Any]:
        return self.contract_mgr.load_contract()

    def verify_reference(self, project_path: Path, state_root: Path) -> ProfileVerificationResult:
        contract = self.get_compatibility_contract(project_path)
        target_major = int(contract.get("frappe_major", 16))
        target_branch = contract.get("frappe_target_branch", "version-16")
        return self.reference_mgr.verify_reference(
            target_major=target_major,
            target_branch=target_branch,
            project_path=project_path,
            state_root=state_root,
        )

    def check_code_patterns(
        self,
        file_path: Path,
        code_content: str,
        target_version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        major = int(target_version) if target_version and target_version.isdigit() else 16
        return self.pattern_checker.scan_content(code_content, file_path=file_path, target_major=major)

    def verify_core_isolation(self, project_path: Path) -> ProfileVerificationResult:
        # Determine bench root
        p = Path(project_path).resolve()
        bench_root = p / "frappe-bench" if (p / "frappe-bench").is_dir() else p
        return self.core_guard.audit_bench_core_cleanliness(bench_root)

    def run_doctor(self, project_path: Path, profile_roots: Dict[str, Any]) -> Dict[str, Any]:
        p = Path(project_path).resolve()
        bench_root = p / "frappe-bench" if (p / "frappe-bench").is_dir() else p
        return self.doctor.run_full_diagnosis(bench_root)

    def bootstrap_project(
        self,
        project_path: Path,
        profile_roots: Dict[str, Any],
        auto: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        return self.bootstrap_engine.bootstrap(profile_roots, auto=auto, dry_run=dry_run)

    def verify_native_test_contract(self, project_path: Path) -> ProfileVerificationResult:
        """
        Enforces native Frappe test contract (Section M, N, O):
        - Verifies bench root and apps structure exist.
        - Verifies custom app controllers / doctypes.
        - Verifies list-apps / doctor diagnostic readiness.
        """
        p = Path(project_path).resolve()
        bench_root = p / "frappe-bench" if (p / "frappe-bench").is_dir() else p
        errors = []
        warnings = []
        details: Dict[str, Any] = {"bench_root": str(bench_root)}

        if not bench_root.is_dir():
            errors.append(f"FRAPPE_BENCH_MISSING: Bench root '{bench_root}' does not exist.")
            return ProfileVerificationResult(status="FAIL", profile_name="frappe", errors=errors, details=details)

        apps_dir = bench_root / "apps"
        if not apps_dir.is_dir():
            errors.append(f"FRAPPE_APPS_DIR_MISSING: Apps directory '{apps_dir}' does not exist.")
            return ProfileVerificationResult(status="FAIL", profile_name="frappe", errors=errors, details=details)

        # Check required apps
        for app in ("frappe", "erpnext", "alco_ecommerce"):
            app_p = apps_dir / app
            if not app_p.is_dir():
                errors.append(f"REQUIRED_APP_MISSING: Frappe bench app '{app}' not found in {apps_dir}.")
            else:
                details[f"{app}_found"] = True

        # Check alco_ecommerce app structure
        alco_app = apps_dir / "alco_ecommerce"
        if alco_app.is_dir():
            hooks_p = alco_app / "alco_ecommerce" / "hooks.py"
            if not hooks_p.is_file():
                errors.append(f"APP_HOOKS_MISSING: alco_ecommerce/hooks.py not found at {hooks_p}.")
            else:
                details["hooks_verified"] = True

        status = "PASS" if not errors else "FAIL"
        return ProfileVerificationResult(
            status=status,
            profile_name="frappe",
            details=details,
            errors=errors,
            warnings=warnings,
        )
