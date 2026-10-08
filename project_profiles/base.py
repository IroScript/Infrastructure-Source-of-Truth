"""
Base definitions and abstract contracts for generic project knowledge-policy profiles (Section U).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ProfileVerificationResult:
    status: str  # PASS, FAIL, PARTIAL, NOT_VERIFIED
    profile_name: str
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_pass(self) -> bool:
        return self.status == "PASS" and not self.errors


class ProjectProfile(abc.ABC):
    """Abstract interface defining official-source governance for a project type."""

    @property
    @abc.abstractmethod
    def profile_name(self) -> str:
        """Name of the profile (e.g., 'frappe', 'rust', 'flutter')."""
        pass

    @property
    @abc.abstractmethod
    def supported_project_types(self) -> List[str]:
        """Project types in PROJECT_REGISTRY that bind to this profile."""
        pass

    @abc.abstractmethod
    def get_compatibility_contract(self, project_path: Optional[Path] = None) -> Dict[str, Any]:
        """Returns the canonical machine-readable compatibility contract."""
        pass

    @abc.abstractmethod
    def verify_reference(self, project_path: Path, state_root: Path) -> ProfileVerificationResult:
        """Verifies presence, freshness, and version matching of local official references."""
        pass

    @abc.abstractmethod
    def check_code_patterns(
        self,
        file_path: Path,
        code_content: str,
        target_version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Scans code for deprecated/removed/outdated patterns for the pinned version."""
        pass

    @abc.abstractmethod
    def verify_core_isolation(self, project_path: Path) -> ProfileVerificationResult:
        """Audits upstream framework core files to prevent accidental modification."""
        pass

    @abc.abstractmethod
    def run_doctor(self, project_path: Path, profile_roots: Dict[str, Any]) -> Dict[str, Any]:
        """Runs framework-specific runtime diagnostics and health verification."""
        pass

    @abc.abstractmethod
    def bootstrap_project(
        self,
        project_path: Path,
        profile_roots: Dict[str, Any],
        auto: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Restores framework profile, rules, and reference mappings on a fresh VM."""
        pass


class ProfileRegistry:
    """Registry managing available project knowledge profiles."""

    _profiles: Dict[str, ProjectProfile] = {}
    _type_mapping: Dict[str, str] = {}

    @classmethod
    def register(cls, profile: ProjectProfile) -> None:
        cls._profiles[profile.profile_name] = profile
        for ptype in profile.supported_project_types:
            cls._type_mapping[ptype] = profile.profile_name

    @classmethod
    def get(cls, name: str) -> Optional[ProjectProfile]:
        return cls._profiles.get(name)

    @classmethod
    def get_for_project_type(cls, project_type: str) -> Optional[ProjectProfile]:
        profile_name = cls._type_mapping.get(project_type)
        if profile_name:
            return cls._profiles.get(profile_name)
        return cls._profiles.get(project_type)

    @classmethod
    def list_profiles(cls) -> List[str]:
        return list(cls._profiles.keys())
