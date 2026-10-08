"""
Frappe Project Profile Package.
Implements version-locked Frappe official-source coding and VM recovery.
"""
from __future__ import annotations

from .contract import FrappeContractManager
from .core_guard import FrappeCoreGuard
from .doctor import FrappeRuntimeDoctor
from .evidence import FrappeEvidenceRecorder
from .patterns import FrappePatternChecker
from .profile import FrappeProjectProfile
from .reference import FrappeReferenceManager

__all__ = [
    "FrappeProjectProfile",
    "FrappeContractManager",
    "FrappeReferenceManager",
    "FrappePatternChecker",
    "FrappeCoreGuard",
    "FrappeEvidenceRecorder",
    "FrappeRuntimeDoctor",
]
