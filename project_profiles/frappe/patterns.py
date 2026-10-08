"""
Frappe Version-Aware Pattern Linter & Anti-Pattern Detection (Section J).
Scans proposed Python code for deprecated, insecure, or obsolete Frappe APIs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class FrappePatternChecker:
    """Detects outdated, removed, and anti-pattern Frappe constructs."""

    def __init__(self, sot_root: Path):
        self.sot_root = Path(sot_root).resolve()
        self.patterns_file = self.sot_root / "project_profiles" / "frappe" / "outdated_patterns.json"
        self._patterns = self._load_patterns()

    def _load_patterns(self) -> List[Dict[str, Any]]:
        if not self.patterns_file.is_file():
            return []
        try:
            data = json.loads(self.patterns_file.read_text(encoding="utf-8"))
            return data.get("patterns", [])
        except Exception:
            return []

    def scan_content(
        self,
        code_content: str,
        file_path: Optional[Path] = None,
        target_major: int = 16,
    ) -> List[Dict[str, Any]]:
        """Scans code string against version-aware pattern database."""
        findings = []
        filename = str(file_path) if file_path else "<inline_code>"

        for entry in self._patterns:
            pat_regex = entry.get("regex", "")
            if not pat_regex:
                continue

            # Check multiline or singleline matches
            matches = list(re.finditer(pat_regex, code_content, re.MULTILINE))
            for m in matches:
                # Calculate line number
                line_no = code_content[: m.start()].count("\n") + 1
                matched_snippet = m.group(0).strip()
                findings.append({
                    "pattern_id": entry.get("pattern_id"),
                    "severity": entry.get("severity", "HIGH"),
                    "file": filename,
                    "line": line_no,
                    "matched_snippet": matched_snippet,
                    "description": entry.get("description"),
                    "alternative": entry.get("alternative"),
                    "official_reference": entry.get("official_reference"),
                    "verdict": "OUTDATED_FRAPPE_PATTERN",
                })

        return findings

    def scan_file(self, file_path: Path, target_major: int = 16) -> List[Dict[str, Any]]:
        """Reads and scans a file on disk."""
        p = Path(file_path).resolve()
        if not p.is_file():
            return []
        try:
            content = p.read_text(encoding="utf-8")
            return self.scan_content(content, file_path=p, target_major=target_major)
        except Exception:
            return []
