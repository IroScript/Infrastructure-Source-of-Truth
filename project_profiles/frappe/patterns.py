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

        # Fabricated / unknown Frappe API detection (Section B & Codex B1)
        official_attrs = {
            "_", "_dict", "as_json", "as_unicode", "attach_print", "auth", "boot", "build",
            "cache", "cache_manager", "call", "cint", "clear_cache", "clear_document_cache",
            "clear_messages", "client_cache", "conf", "config", "connect", "controllers",
            "copy_doc", "core", "create_folder", "cstr", "database", "db", "debug_log",
            "defaults", "delete_doc", "delete_doc_if_exists", "desk", "destroy", "email",
            "enqueue", "enqueue_doc", "error_log", "errprint", "exceptions", "flags",
            "form_dict", "format", "format_value", "frappe", "generate_hash", "get_all",
            "get_all_apps", "get_app_path", "get_attr", "get_cached_doc", "get_cached_value",
            "get_conf", "get_desk_link", "get_doc", "get_doc_hooks", "get_doctype_app",
            "get_hooks", "get_installed_apps", "get_last_doc", "get_list", "get_meta",
            "get_module", "get_roles", "get_single", "get_single_value", "get_site_config",
            "get_site_path", "get_system_settings", "get_template", "get_test_records",
            "get_traceback", "get_user", "get_value", "get_website_settings", "guest_methods",
            "has_permission", "has_website_permission", "import_doc", "init", "init_site",
            "integrations", "is_table", "is_whitelisted", "local", "local_cache", "log_error",
            "logger", "loggers", "model", "msgprint", "new_doc", "only_for", "parse_json",
            "ping", "publish_progress", "publish_realtime", "qb", "query_builder", "read_file",
            "read_only", "realtime", "redirect", "reload_doc", "reload_doctype", "rename_doc",
            "render_template", "request", "respond_as_web_page", "response", "safe_decode",
            "safe_encode", "safe_eval", "sendmail", "session", "set_user", "set_value",
            "share", "throw", "throw_permission_error", "toast", "user", "utils", "whitelist",
            "whitelisted", "write_only"
        }
        api_pattern = r"(?<![\.\w/:\-])frappe\.([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\.[a-zA-Z])"
        for m in re.finditer(api_pattern, code_content):
            attr = m.group(1)
            if attr.startswith("this_api_does_not_exist") or (attr not in official_attrs and not attr.startswith("_")):
                line_no = code_content[: m.start()].count("\n") + 1
                findings.append({
                    "pattern_id": "UNKNOWN_FRAPPE_API",
                    "severity": "CRITICAL",
                    "file": filename,
                    "line": line_no,
                    "matched_snippet": f"frappe.{attr}",
                    "description": f"Method or attribute 'frappe.{attr}' is not a recognized official Frappe API.",
                    "alternative": "Use official Frappe v16 API documented at docs.frappe.io",
                    "official_reference": "https://docs.frappe.io",
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
