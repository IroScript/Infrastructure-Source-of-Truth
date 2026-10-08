"""
Frappe Version Compatibility Contract Manager (Section C & Q).
Loads, validates, and enforces version invariants and update policies.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class FrappeContractManager:
    """Manages the canonical Frappe compatibility contract."""

    def __init__(self, sot_root: Path):
        self.sot_root = Path(sot_root).resolve()
        self.contract_file = self.sot_root / "project_profiles" / "frappe" / "compatibility_contract.json"
        if not self.contract_file.is_file():
            self.contract_file = self.sot_root / "frappe" / "FRAPPE_COMPATIBILITY_CONTRACT.json"

    def load_contract(self) -> Dict[str, Any]:
        """Loads canonical contract from disk."""
        if not self.contract_file.is_file():
            return {}
        try:
            return json.loads(self.contract_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def validate_contract_integrity(self, contract: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validates all required contract fields."""
        required_keys = [
            "project_uuid",
            "project_id",
            "bench_identity",
            "site",
            "frappe_major",
            "frappe_target_branch",
            "frappe_current_commit",
            "erpnext_major",
            "erpnext_target_branch",
            "erpnext_current_commit",
            "alco_ecommerce_commit",
            "bench_version",
            "python_required",
            "node_required",
            "database_required",
            "official_docs_source",
            "official_framework_source",
            "official_erpnext_source",
            "docs_version_policy",
            "compatibility_status",
        ]
        missing = [k for k in required_keys if k not in contract or contract[k] in ("", None)]
        if missing:
            return False, [f"Missing required contract key: {k}" for k in missing]
        return True, []

    def check_upgrade_authorization(
        self,
        current_contract: Dict[str, Any],
        proposed_major: int,
    ) -> Tuple[bool, str]:
        """
        Enforces update policy (Section Q):
        A new major version requires explicit version-policy change in SOT.
        If major upgrade is not authorized: returns (False, 'MAJOR_UPGRADE_NOT_AUTHORIZED').
        """
        pinned_major = int(current_contract.get("frappe_major", 16))
        upgrade_policy = current_contract.get("upgrade_policy", {})
        allow_major = upgrade_policy.get("allow_major_upgrade", False)

        if proposed_major > pinned_major:
            if not allow_major:
                return False, "MAJOR_UPGRADE_NOT_AUTHORIZED"
        return True, "UPGRADE_AUTHORIZED"
