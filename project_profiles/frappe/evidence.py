"""
Frappe Code Evidence Generator & Recorder (Section I).
Records machine-readable evidence bundles for all Frappe-specific tasks without chain-of-thought.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class FrappeEvidenceRecorder:
    """Creates and persists machine-readable task evidence bundles."""

    def __init__(self, state_root: Optional[Path] = None):
        self.state_root = Path(state_root or (Path.home() / ".agents")).resolve()
        self.evidence_dir = self.state_root / "frappe_evidence"

    def record_task_evidence(
        self,
        task_id: str,
        project_uuid: str,
        frappe_version: str,
        erpnext_version: str,
        official_reference_commit: str,
        official_docs_consulted: List[str],
        apis_hooks_used: List[str],
        changed_files: List[str],
        tests_run: List[Dict[str, Any]],
        negative_tests: List[Dict[str, Any]],
        migration_impact: bool,
        verdict: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Saves machine-readable evidence file."""
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        evidence_payload = {
            "schema_version": "1.0.0",
            "task_id": task_id,
            "project_uuid": project_uuid,
            "timestamp": now_utc,
            "frappe_version": frappe_version,
            "erpnext_version": erpnext_version,
            "official_reference_commit": official_reference_commit,
            "official_docs_consulted": official_docs_consulted,
            "apis_hooks_used": apis_hooks_used,
            "changed_files": changed_files,
            "tests_run": tests_run,
            "negative_tests": negative_tests,
            "migration_impact": migration_impact,
            "verdict": verdict,
            "metadata": extra_metadata or {},
        }

        filename = f"{task_id}_{int(time.time())}.json"
        out_file = self.evidence_dir / filename
        out_file.write_text(json.dumps(evidence_payload, indent=2), encoding="utf-8")
        return out_file
