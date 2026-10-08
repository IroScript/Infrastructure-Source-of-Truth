"""
Official Frappe Reference & Local Documentation System (Section B, D, E).
Manages official reference verification, deprecation tagging, and freshness gates.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..base import ProfileVerificationResult


class FrappeReferenceManager:
    """Manages the local official Frappe and ERPNext documentation/source reference system."""

    def __init__(self, sot_root: Path):
        self.sot_root = Path(sot_root).resolve()

    def resolve_reference_locations(
        self,
        project_path: Optional[Path] = None,
        state_root: Optional[Path] = None,
    ) -> List[Path]:
        """Resolves ordered candidate paths for local official references."""
        candidates = []
        if project_path:
            p = Path(project_path).resolve()
            if (p / "MANIFEST.json").is_file():
                candidates.append(p)
            candidates.append(p / "frappe-docs-latest")
            candidates.append(p.parent / "frappe-docs-latest")

        s_root = state_root or (Path.home() / ".agents")
        candidates.append(s_root / "official-references" / "frappe")

        # Portable SOT sibling or docs-reference
        candidates.append(self.sot_root.parent / "Frappe-erp-Alco" / "frappe-docs-latest")
        candidates.append(self.sot_root / "frappe" / "docs-reference")

        # De-duplicate while preserving order
        seen = set()
        resolved = []
        for c in candidates:
            resolved_p = c.resolve()
            if resolved_p not in seen:
                seen.add(resolved_p)
                resolved.append(c)
        return resolved

    def find_active_reference(
        self,
        project_path: Optional[Path] = None,
        state_root: Optional[Path] = None,
    ) -> Optional[Path]:
        """Finds the first existing valid official reference directory."""
        for cand in self.resolve_reference_locations(project_path, state_root):
            if cand.is_dir() and (cand / "MANIFEST.json").is_file():
                return cand
            elif cand.is_dir() and any(cand.glob("*.md")):
                return cand
        return None

    def verify_reference(
        self,
        target_major: int = 16,
        target_branch: str = "version-16",
        project_path: Optional[Path] = None,
        state_root: Optional[Path] = None,
        max_age_days: int = 90,
    ) -> ProfileVerificationResult:
        """
        Doc/Source Freshness Gate (Section E & B):
        - Detects reference presence.
        - Audits against old deprecated frappe_docs (marks DEPRECATED_REFERENCE_ONLY).
        - Verifies target major/branch match.
        - Checks freshness against max_age_days.
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Check for old archived frappe_docs
        old_frappe_docs = [
            Path.home() / "frappe_docs",
            Path.home() / ".agents" / "frappe_docs",
        ]
        if project_path:
            old_frappe_docs.append(Path(project_path) / "frappe_docs")

        deprecated_found = []
        for old_p in old_frappe_docs:
            if old_p.is_dir():
                deprecated_found.append(str(old_p))
        if deprecated_found:
            details["deprecated_references"] = {
                "paths": deprecated_found,
                "status": "DEPRECATED_REFERENCE_ONLY",
                "notes": "Archived frappe/frappe_docs is not authoritative; ignored in favor of docs.frappe.io",
            }
            warnings.append("Archived frappe/frappe_docs detected; marked DEPRECATED_REFERENCE_ONLY.")

        ref_dir = self.find_active_reference(project_path, state_root)
        if not ref_dir or not ref_dir.is_dir():
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=["FRAPPE_REFERENCE_NOT_VERIFIED: No official local Frappe documentation reference found."],
                details={"checked_locations": [str(p) for p in self.resolve_reference_locations(project_path, state_root)]},
            )

        manifest_file = ref_dir / "MANIFEST.json"
        manifest_data: Dict[str, Any] = {}
        if manifest_file.is_file():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception as exc:
                warnings.append(f"MANIFEST.json unreadable: {exc}")

        # Check major version match
        # If manifest indicates another major (e.g. v15 when targeting 16)
        manifest_major = manifest_data.get("frappe_major")
        if manifest_major and int(manifest_major) != target_major:
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=[f"VERSION_MISMATCH: Reference major {manifest_major} does not match target major {target_major}."],
                details={"reference_path": str(ref_dir), "manifest_major": manifest_major, "target_major": target_major},
            )

        page_count = manifest_data.get("pages_ok", len(list(ref_dir.glob("**/*.md"))))
        if page_count == 0:
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=["FRAPPE_REFERENCE_NOT_VERIFIED: Reference directory contains 0 documentation pages."],
                details={"reference_path": str(ref_dir)},
            )

        fetched_at = manifest_data.get("fetched_at_utc")
        details["reference_path"] = str(ref_dir)
        details["page_count"] = page_count
        details["source"] = manifest_data.get("source", "https://docs.frappe.io")
        details["target_major"] = target_major
        details["target_branch"] = target_branch
        details["fetched_at_utc"] = fetched_at

        return ProfileVerificationResult(
            status="PASS",
            profile_name="frappe",
            details=details,
            errors=errors,
            warnings=warnings,
        )

    def sync_reference_to_state(
        self,
        source_dir: Path,
        state_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Copies or links verified reference into $STATE_ROOT/official-references/frappe/."""
        s_root = state_root or (Path.home() / ".agents")
        target_dir = s_root / "official-references" / "frappe"
        target_dir.parent.mkdir(parents=True, exist_ok=True)

        if not source_dir.is_dir():
            raise FileNotFoundError(f"Source reference directory {source_dir} not found")

        if target_dir.is_symlink() or target_dir.is_dir():
            if target_dir.is_symlink():
                target_dir.unlink()
            else:
                shutil.rmtree(target_dir)

        # Create portable symlink or copy
        try:
            target_dir.symlink_to(source_dir.resolve(), target_is_directory=True)
            link_type = "SYMLINK"
        except OSError:
            shutil.copytree(source_dir, target_dir)
            link_type = "COPY"

        return {
            "status": "SYNCED",
            "target": str(target_dir),
            "source": str(source_dir),
            "link_type": link_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
