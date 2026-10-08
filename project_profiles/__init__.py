"""
Generic Project Knowledge-Policy Profile Framework (Section U).
Enables framework-specific official source enforcement, compatibility contracts,
agent coding rules, and blank-VM recovery across heterogeneous project types.
"""
from __future__ import annotations

from .base import (
    ProjectProfile,
    ProfileVerificationResult,
    ProfileRegistry,
)
from .manager import ProjectProfileManager

__all__ = [
    "ProjectProfile",
    "ProfileVerificationResult",
    "ProfileRegistry",
    "ProjectProfileManager",
]
