"""
Frappe Project Profile Provider Implementation (Section U).
Concrete provider binding all Frappe official-source governance systems to ProjectProfile.
"""
from __future__ import annotations

import json
import py_compile
import subprocess
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
        - Compiles (py_compile) all python files in custom apps to prevent syntax regressions.
        - Tests import / runtime execution of custom app hooks.
        - Audits doctype integrity.
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

        # Check core apps
        for app in ("frappe", "erpnext"):
            app_p = apps_dir / app
            if not app_p.is_dir():
                errors.append(f"REQUIRED_APP_MISSING: Frappe core app '{app}' not found in {apps_dir}.")
            else:
                details[f"{app}_found"] = True

        # Check custom apps in apps_dir (any app that is not 'frappe' or 'erpnext')
        custom_apps = [
            d for d in apps_dir.iterdir()
            if d.is_dir() and not d.name.startswith((".", "_")) and d.name not in ("frappe", "erpnext")
        ]
        if not custom_apps:
            alco_p = apps_dir / "alco_ecommerce"
            if not alco_p.is_dir():
                errors.append(f"REQUIRED_APP_MISSING: Custom app 'alco_ecommerce' not found in {apps_dir}.")
        else:
            total_compiled = 0
            for c_app in custom_apps:
                app_name = c_app.name
                pkg_dir = c_app / app_name
                hooks_p = pkg_dir / "hooks.py"
                if not hooks_p.is_file():
                    errors.append(f"APP_HOOKS_MISSING: {app_name}/hooks.py not found at {hooks_p}.")
                else:
                    details[f"{app_name}_hooks_verified"] = True

                # 1. py_compile all python files in custom app
                for py_file in c_app.glob("**/*.py"):
                    if any(part.startswith(".") for part in py_file.parts):
                        continue
                    try:
                        py_compile.compile(str(py_file), doraise=True)
                        total_compiled += 1
                    except py_compile.PyCompileError as pe:
                        errors.append(f"APP_SYNTAX_ERROR: Syntax error in {py_file.name}: {pe}")
                    except Exception as exc:
                        errors.append(f"APP_COMPILE_ERROR: Error compiling {py_file.name}: {exc}")

                # 2. Runtime import of hooks.py to detect synthetic RuntimeErrors or broken imports
                bench_py = bench_root / "env" / "bin" / "python"
                py_exec = str(bench_py) if bench_py.is_file() else "python3"
                test_cmd = [
                    py_exec,
                    "-c",
                    (
                        "import sys; "
                        f"sys.path.insert(0, r'{str(c_app)}'); "
                        f"import {app_name}.hooks as h; "
                        "assert hasattr(h, 'app_name'), 'app_name missing in hooks.py'"
                    ),
                ]
                try:
                    sub_res = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                    if sub_res.returncode != 0:
                        err_msg = (sub_res.stderr or sub_res.stdout or "Import exited with non-zero code").strip()
                        errors.append(f"APP_HOOKS_RUNTIME_ERROR: Failed to load {app_name}.hooks: {err_msg}")
                    else:
                        details[f"{app_name}_hooks_runtime_import"] = "PASS"
                except Exception as exc:
                    errors.append(f"APP_HOOKS_EXEC_FAILED: Execution error importing {app_name} hooks: {exc}")

                # 3. Custom Doctype integrity check
                dt_dir = pkg_dir / "doctype"
                if dt_dir.is_dir():
                    for dt_folder in dt_dir.iterdir():
                        if dt_folder.is_dir() and not dt_folder.name.startswith((".", "_")):
                            json_file = dt_folder / f"{dt_folder.name}.json"
                            if not json_file.is_file():
                                errors.append(f"DOCTYPE_SCHEMA_MISSING: DocType definition missing: {json_file}")
                            else:
                                try:
                                    json.loads(json_file.read_text(encoding="utf-8"))
                                except Exception as je:
                                    errors.append(f"DOCTYPE_SCHEMA_CORRUPT: Invalid JSON in {json_file}: {je}")

            details["total_compiled_python_files"] = total_compiled

        status = "PASS" if not errors else "FAIL"
        return ProfileVerificationResult(
            status=status,
            profile_name="frappe",
            details=details,
            errors=errors,
            warnings=warnings,
        )
