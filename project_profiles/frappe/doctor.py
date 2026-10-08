"""
Comprehensive Frappe & Alco Ecommerce Runtime Doctor & Auditor (Sections A, L, M, N, O, P).
Executes real empirical runtime diagnostics across bench, apps, database, and endpoints.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class FrappeRuntimeDoctor:
    """Performs deep empirical inspection of Frappe bench and Alco Ecommerce application."""

    def __init__(self, sot_root: Path):
        self.sot_root = Path(sot_root).resolve()

    def run_full_diagnosis(
        self,
        bench_root: Path,
        site_name: str = "alco.localhost",
    ) -> Dict[str, Any]:
        """Runs complete runtime inventory and health check."""
        b = Path(bench_root).resolve()
        report: Dict[str, Any] = {
            "bench_root": str(b),
            "site": site_name,
            "status": "HEALTHY",
            "errors": [],
            "warnings": [],
        }

        if not b.is_dir():
            report["status"] = "BENCH_NOT_FOUND"
            report["errors"].append(f"Bench root does not exist: {b}")
            return report

        # 1. Apps inventory & git status
        apps_dir = b / "apps"
        installed_apps_report: Dict[str, Any] = {}
        for app in ("frappe", "erpnext", "alco_ecommerce"):
            app_path = apps_dir / app
            app_info: Dict[str, Any] = {
                "exists": app_path.is_dir(),
                "path": str(app_path),
            }
            if app_path.is_dir() and (app_path / ".git").exists():
                app_info["is_git_repo"] = True
                app_info["branch"] = self._run_git(["-C", str(app_path), "branch", "--show-current"])
                app_info["head_sha"] = self._run_git(["-C", str(app_path), "rev-parse", "HEAD"])
                app_info["remote_url"] = self._run_git(["-C", str(app_path), "remote", "get-url", "origin"]) or \
                                         self._run_git(["-C", str(app_path), "remote", "get-url", "upstream"])
                diff = self._run_git(["-C", str(app_path), "status", "--porcelain"])
                app_info["dirty"] = bool(diff)
                if diff:
                    app_info["diff_summary"] = diff.split("\n")[:5]
            else:
                app_info["is_git_repo"] = False
            installed_apps_report[app] = app_info
        report["apps"] = installed_apps_report

        # 2. Integration Model Determination (Section L)
        alco_app_dir = apps_dir / "alco_ecommerce"
        if alco_app_dir.is_dir() and (alco_app_dir / "alco_ecommerce" / "hooks.py").is_file():
            report["integration_model"] = "MODEL_A_BENCH_CUSTOM_APP"
        else:
            report["integration_model"] = "UNKNOWN"

        # 3. Environment & Runtime tool versions (Section A & P)
        env_sh = b.parent / "frappe-env.sh"
        cmd_prefix = f"source {env_sh} && " if env_sh.is_file() else ""

        report["runtimes"] = {
            "python_system": self._run_cmd("python3 --version"),
            "python_bench_env": self._run_cmd(f"{cmd_prefix}{b}/env/bin/python --version"),
            "node": self._run_cmd(f"{cmd_prefix}node --version"),
            "npm": self._run_cmd(f"{cmd_prefix}npm --version"),
            "mariadb": self._run_cmd(f"{cmd_prefix}mariadb --version || {b.parent}/runtime/mariadb/bin/mariadbd --version"),
            "redis": self._run_cmd(f"{cmd_prefix}redis-server --version || {b.parent}/runtime/redis/bin/redis-server --version"),
            "bench": self._run_cmd(f"{cmd_prefix}bench --version"),
        }

        # 4. Site Apps & Database Verification (Section M)
        site_dir = b / "sites" / site_name
        report["site_exists"] = site_dir.is_dir()
        if site_dir.is_dir():
            site_conf_path = site_dir / "site_config.json"
            if site_conf_path.is_file():
                try:
                    s_conf = json.loads(site_conf_path.read_text(encoding="utf-8"))
                    report["site_config"] = {
                        "db_name": s_conf.get("db_name"),
                        "db_type": s_conf.get("db_type"),
                        "db_socket": s_conf.get("db_socket"),
                        "installed_apps": s_conf.get("installed_apps", []),
                    }
                except Exception as exc:
                    report["warnings"].append(f"Failed to read site_config.json: {exc}")

            # Query list-apps via bench CLI
            list_apps_out = self._run_cmd(f"{cmd_prefix}bench --site {site_name} list-apps", cwd=b)
            report["site_list_apps_stdout"] = list_apps_out
            report["alco_ecommerce_installed"] = "alco_ecommerce" in list_apps_out

            # Check DocTypes in database via SQL query
            db_sql_out = self._run_cmd(
                f'{cmd_prefix}bench --site {site_name} execute frappe.db.sql --args \'("SELECT name FROM `tabDocType` WHERE module=\\"Alco Ecommerce\\"",)\'',
                cwd=b,
            )
            report["alco_doctypes_in_db"] = db_sql_out

        # 5. Site HTTP Health Check (Section N)
        http_probe = self._run_cmd("curl -I -s --max-time 4 http://127.0.0.1:8000 -H 'Host: alco.localhost'")
        report["http_probe_header"] = http_probe.split("\n")[0] if http_probe else "NO_RESPONSE"
        report["site_online"] = "200 OK" in http_probe or "301" in http_probe or "302" in http_probe

        # 6. Scheduler & Worker Diagnostics
        doctor_out = self._run_cmd(f"{cmd_prefix}bench --site {site_name} doctor || true", cwd=b)
        report["scheduler_status"] = doctor_out.strip()

        # Overall health assessment
        if not report["site_online"] and not report.get("alco_ecommerce_installed"):
            report["status"] = "FAIL"
            report["errors"].append("Site unreachable or Alco Ecommerce not installed")
        elif not report["site_online"]:
            report["status"] = "PARTIAL"
            report["warnings"].append("HTTP service on port 8000 did not respond with 200 OK")
        else:
            report["status"] = "PASS"

        return report

    def _run_git(self, argv: List[str]) -> str:
        try:
            res = subprocess.run(["git", *argv], capture_output=True, text=True, timeout=10)
            return res.stdout.strip()
        except Exception:
            return ""

    def _run_cmd(self, cmd: str, cwd: Optional[Path] = None) -> str:
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                executable="/bin/bash",
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(cwd) if cwd else None,
            )
            return res.stdout.strip() or res.stderr.strip()
        except Exception as exc:
            return f"ERROR: {exc}"
