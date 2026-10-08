"""
Core Framework Modification Guard (Section K).
Prevents accidental or unauthorized modifications to upstream apps/frappe and apps/erpnext.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..base import ProfileVerificationResult


class FrappeCoreGuard:
    """Enforces strict isolation between upstream framework core and custom apps."""

    CORE_APPS = ("frappe", "erpnext")

    def __init__(self, sot_root: Path):
        self.sot_root = Path(sot_root).resolve()

    def check_proposed_path(self, proposed_file: Path, bench_root: Path) -> Tuple[bool, str]:
        """
        Validates whether a file target is an upstream core framework file.
        Returns (False, 'CORE_MODIFICATION_PROHIBITED') if inside core app.
        """
        p = Path(proposed_file).resolve()
        b = Path(bench_root).resolve()

        for core in self.CORE_APPS:
            core_app_dir = (b / "apps" / core).resolve()
            try:
                p.relative_to(core_app_dir)
                return False, f"CORE_MODIFICATION_PROHIBITED: Direct modification of upstream {core} ({p}) is forbidden. Business logic must reside in custom apps."
            except ValueError:
                pass
        return True, "ALLOWED"

    def audit_bench_core_cleanliness(self, bench_root: Path) -> ProfileVerificationResult:
        """Audits current git status of apps/frappe and apps/erpnext."""
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        b = Path(bench_root).resolve()
        for core in self.CORE_APPS:
            app_dir = b / "apps" / core
            if not app_dir.is_dir() or not (app_dir / ".git").exists():
                continue

            # 1. Unstaged modifications
            diff_proc = subprocess.run(
                ["git", "-C", str(app_dir), "diff", "--name-status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # 2. Staged modifications
            cached_proc = subprocess.run(
                ["git", "-C", str(app_dir), "diff", "--cached", "--name-status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # 3. Untracked files
            status_proc = subprocess.run(
                ["git", "-C", str(app_dir), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            all_entries = []
            for line in diff_proc.stdout.strip().split("\n"):
                if line.strip():
                    all_entries.append((line.strip(), "unstaged"))
            for line in cached_proc.stdout.strip().split("\n"):
                if line.strip():
                    all_entries.append((line.strip(), "staged"))
            for line in status_proc.stdout.strip().split("\n"):
                clean_l = line.strip()
                if clean_l.startswith("??"):
                    all_entries.append((clean_l[2:].strip(), "untracked"))

            code_mods = []
            for item, kind in all_entries:
                parts = item.split(None, 1)
                fname = parts[1] if len(parts) > 1 else parts[0]
                if fname.endswith(".py") or fname.startswith(core) or fname.endswith(".js"):
                    code_mods.append(f"{fname} ({kind})")
                else:
                    warnings.append(f"{core} non-code working tree modification: {fname} ({kind})")

            if code_mods:
                errors.append(f"CORE_MODIFICATION_PROHIBITED: Upstream {core} contains code edits: {code_mods}")
                details[f"{core}_modified_code"] = code_mods
            else:
                details[f"{core}_status"] = "CLEAN"

        status = "FAIL" if errors else "PASS"
        return ProfileVerificationResult(
            status=status,
            profile_name="frappe",
            details=details,
            errors=errors,
            warnings=warnings,
        )
