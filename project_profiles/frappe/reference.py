"""
Official Frappe Reference & Local Documentation System (Section B, D, E).
Manages official reference verification, deprecation tagging, and freshness gates.
"""
from __future__ import annotations

import datetime
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
        """Finds the first existing valid official reference directory containing a MANIFEST.json."""
        for cand in self.resolve_reference_locations(project_path, state_root):
            if cand.is_dir() and (cand / "MANIFEST.json").is_file():
                return cand
        return None

    def verify_reference(
        self,
        target_major: int = 16,
        target_branch: str = "version-16",
        project_path: Optional[Path] = None,
        state_root: Optional[Path] = None,
        max_age_days: int = 90,
        reference_override: Optional[Path] = None,
    ) -> ProfileVerificationResult:
        """
        Doc/Source Freshness Gate (Section E & B):
        - Detects reference presence with mandatory MANIFEST.json.
        - Audits against old deprecated frappe_docs (marks DEPRECATED_REFERENCE_ONLY).
        - Verifies target major/branch match explicitly without guessing.
        - Checks freshness against max_age_days and validates UTC ISO timestamps.
        - Verifies physical page existence and artifact hash integrity.
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

        ref_dir = Path(reference_override).resolve() if reference_override else self.find_active_reference(project_path, state_root)
        if not ref_dir or not ref_dir.is_dir():
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=["FRAPPE_REFERENCE_NOT_VERIFIED: No official local Frappe documentation reference found with valid MANIFEST.json."],
                details={"checked_locations": [str(p) for p in self.resolve_reference_locations(project_path, state_root)]},
            )

        manifest_file = ref_dir / "MANIFEST.json"
        if not manifest_file.is_file():
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=["FRAPPE_REFERENCE_NOT_VERIFIED: Reference directory missing required MANIFEST.json."],
                details={"reference_path": str(ref_dir)},
            )

        try:
            manifest_data: Dict[str, Any] = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as exc:
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=[f"FRAPPE_REFERENCE_CORRUPT: MANIFEST.json unreadable: {exc}"],
                details={"reference_path": str(ref_dir)},
            )

        # 1. Check source domain (must explicitly declare source from docs.frappe.io)
        source = manifest_data.get("source")
        if not source or not (source.startswith("https://docs.frappe.io") or source.startswith("http://docs.frappe.io")):
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=[f"FRAPPE_REFERENCE_NOT_VERIFIED: INVALID_SOURCE_DOMAIN: Reference source '{source}' missing or not from docs.frappe.io."],
                details={"reference_path": str(ref_dir), "source": source},
            )

        # 2. Check major version match (MUST be explicitly declared, NO guessing!)
        manifest_major = manifest_data.get("frappe_major")
        if manifest_major is None:
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=[f"FRAPPE_REFERENCE_NOT_VERIFIED: VERSION_MISMATCH: Manifest missing required explicit 'frappe_major' declaration."],
                details={"reference_path": str(ref_dir), "manifest_major": None, "target_major": target_major},
            )
        try:
            if int(manifest_major) != target_major:
                return ProfileVerificationResult(
                    status="FAIL",
                    profile_name="frappe",
                    errors=[f"FRAPPE_REFERENCE_NOT_VERIFIED: VERSION_MISMATCH: Reference major {manifest_major} does not match target major {target_major}."],
                    details={"reference_path": str(ref_dir), "manifest_major": manifest_major, "target_major": target_major},
                )
        except (ValueError, TypeError):
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=[f"FRAPPE_REFERENCE_NOT_VERIFIED: VERSION_MISMATCH: Malformed 'frappe_major' declaration: {manifest_major}"],
                details={"reference_path": str(ref_dir), "manifest_major": manifest_major},
            )

        # 3. Check branch match (MUST be explicitly declared and match target branch!)
        manifest_branch = manifest_data.get("branch") or manifest_data.get("target_branch")
        if not manifest_branch:
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=[f"FRAPPE_REFERENCE_NOT_VERIFIED: BRANCH_MISMATCH: Manifest missing required 'branch' declaration."],
                details={"reference_path": str(ref_dir), "manifest_branch": None, "target_branch": target_branch},
            )
        if manifest_branch.strip().lower() != target_branch.strip().lower():
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=[f"FRAPPE_REFERENCE_NOT_VERIFIED: BRANCH_MISMATCH: Reference branch '{manifest_branch}' does not match target branch '{target_branch}'."],
                details={"reference_path": str(ref_dir), "manifest_branch": manifest_branch, "target_branch": target_branch},
            )

        # 4. Check physical markdown documentation pages on disk (fail closed, never trust manifest blindly)
        physical_pages = list(ref_dir.glob("**/*.md"))
        page_count = len(physical_pages)
        if page_count == 0:
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=["FRAPPE_REFERENCE_NOT_VERIFIED: Reference directory contains 0 physical markdown documentation pages on disk."],
                details={"reference_path": str(ref_dir), "physical_pages": 0},
            )

        # 5. Check freshness age and valid timestamp
        fetched_at = manifest_data.get("fetched_at_utc")
        if not fetched_at:
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=["INVALID_TIMESTAMP: Manifest missing required 'fetched_at_utc' timestamp."],
                details={"reference_path": str(ref_dir)},
            )
        try:
            clean_ts = fetched_at.replace("Z", "+00:00")
            parsed_dt = datetime.datetime.fromisoformat(clean_ts)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            diff_sec = (now_dt - parsed_dt).total_seconds()
            if diff_sec < 0:
                return ProfileVerificationResult(
                    status="FAIL",
                    profile_name="frappe",
                    errors=[f"INVALID_TIMESTAMP: Manifest timestamp '{fetched_at}' is in the future."],
                    details={"reference_path": str(ref_dir), "fetched_at_utc": fetched_at},
                )
            age_days = diff_sec / 86400
            if max_age_days > 0 and age_days > max_age_days:
                return ProfileVerificationResult(
                    status="FAIL",
                    profile_name="frappe",
                    errors=[f"REFERENCE_STALE: Reference age ({age_days:.1f} days) exceeds maximum allowed age ({max_age_days} days)."],
                    details={"reference_path": str(ref_dir), "age_days": age_days, "max_age_days": max_age_days},
                )
        except Exception as exc:
            return ProfileVerificationResult(
                status="FAIL",
                profile_name="frappe",
                errors=[f"INVALID_TIMESTAMP: Malformed ISO-8601 timestamp '{fetched_at}': {exc}"],
                details={"reference_path": str(ref_dir), "fetched_at_utc": fetched_at},
            )

        # 6. Check artifact integrity if page hashes are declared in manifest
        pages_list = manifest_data.get("pages")
        if isinstance(pages_list, list) and pages_list:
            import hashlib
            sample_pages = pages_list[:10]
            for p_info in sample_pages:
                rel_path = p_info.get("path")
                expected_sha = p_info.get("sha256")
                if rel_path and expected_sha:
                    f_on_disk = ref_dir / rel_path
                    if f_on_disk.is_file():
                        actual_sha = hashlib.sha256(f_on_disk.read_bytes()).hexdigest()
                        if actual_sha != expected_sha:
                            return ProfileVerificationResult(
                                status="FAIL",
                                profile_name="frappe",
                                errors=[f"ARTIFACT_INTEGRITY_FAILED: Page '{rel_path}' sha256 mismatch."],
                                details={"file": str(f_on_disk), "expected": expected_sha, "actual": actual_sha},
                            )

        details["reference_path"] = str(ref_dir)
        details["page_count"] = page_count
        details["source"] = source
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
            "page_count": len(list(source_dir.glob("**/*.md"))),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
