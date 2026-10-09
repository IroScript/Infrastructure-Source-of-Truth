"""
Generic SOT Project Recovery & Restoration Engine (Sections B4.1, B4.2, B4.3).
Derives recoverable projects dynamically from canonical SOT project metadata (PROJECT_REGISTRY.json).
Restores single-repository projects and compound projects (Frappe bench) into $PROJECTS_ROOT.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _normalize_git_url(url: str) -> str:
    u = url.strip()
    if u.endswith(".git"):
        u = u[:-4]
    u = u.rstrip("/")
    if u.startswith("git@github.com:"):
        u = "https://github.com/" + u[len("git@github.com:"):]
    return u.lower()


class ProjectRecoveryOrchestrator:
    """Orchestrates generic project recovery across single and compound projects."""

    def __init__(self, sot_root: Path):
        self.sot_root = Path(sot_root).resolve()
        self.registry_file = self.sot_root / "projects" / "PROJECT_REGISTRY.json"
        self.frappe_manifest_file = (
            self.sot_root / "project_profiles" / "frappe" / "recovery_manifest.json"
        )

    def load_registry(self) -> List[Dict[str, Any]]:
        if not self.registry_file.is_file():
            return []
        try:
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
            return data.get("projects", [])
        except Exception:
            return []

    def load_frappe_manifest(self) -> Dict[str, Any]:
        if not self.frappe_manifest_file.is_file():
            return {}
        try:
            return json.loads(self.frappe_manifest_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def resolve_relative_path(self, canonical_path: str) -> str:
        """Derives clean relative path under PROJECTS_ROOT from canonical path."""
        p_str = canonical_path.strip()
        for prefix in (
            "${PROJECTS_ROOT}/",
            "${HOME}/IroScript_Projects/",
            "${HOME}/",
            "/home/azureuser/IroScript_Projects/",
            "/home/azureuser/",
        ):
            if p_str.startswith(prefix):
                return p_str[len(prefix):].strip("/")
        return Path(p_str).name

    def recover_all(
        self,
        projects_root: Path,
        home: Optional[Path] = None,
        filter_project_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        projects_root = Path(projects_root).resolve()
        home = Path(home or projects_root.parent).resolve()

        projects = self.load_registry()
        report: Dict[str, Any] = {
            "status": "PROJECT_RESTORED",
            "projects_root": str(projects_root),
            "restored_projects": [],
            "skipped_existing": [],
            "errors": [],
            "stages": [
                "PROJECT_MAPPING_RESOLVED"
            ]
        }

        if filter_project_id:
            projects = [p for p in projects if p.get("project_id") == filter_project_id]

        for p in projects:
            p_id = p.get("project_id", "")
            p_type = p.get("project_type", "application")
            c_path = p.get("canonical_path", "")
            rel_path = self.resolve_relative_path(c_path)
            target_dir = projects_root / rel_path

            if p_type == "frappe_bench":
                res = self.recover_frappe_bench(target_dir, dry_run=dry_run, home=home, projects_root=projects_root)
                if res.get("status") == "PROJECT_RESTORED":
                    report["restored_projects"].append(p_id)
                elif res.get("status") == "EXISTING":
                    report["skipped_existing"].append(p_id)
                else:
                    report["errors"].append({"project_id": p_id, "error": res.get("error", "Unknown")})
            else:
                git_meta = p.get("git", {})
                remote_url = git_meta.get("remote")
                if not remote_url:
                    continue

                if (target_dir / ".git").is_dir():
                    try:
                        res_remote = subprocess.run(
                            ["git", "-C", str(target_dir), "config", "remote.origin.url"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        curr_remote = res_remote.stdout.strip()
                        if _normalize_git_url(curr_remote) == _normalize_git_url(remote_url):
                            files = [f for f in target_dir.iterdir() if f.name != ".git"]
                            if files:
                                report["skipped_existing"].append(p_id)
                                continue
                    except Exception:
                        pass

                if dry_run:
                    report["restored_projects"].append(p_id)
                    continue

                target_dir.parent.mkdir(parents=True, exist_ok=True)
                cloned = False
                clone_err = ""
                if shutil.which("git"):
                    try:
                        env = dict(os.environ)
                        env["GIT_TERMINAL_PROMPT"] = "0"
                        res_git = subprocess.run(
                            ["git", "clone", "--depth", "1", remote_url, str(target_dir)],
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if res_git.returncode == 0:
                            cloned = True
                        else:
                            clone_err = res_git.stderr.strip()
                    except Exception as e:
                        clone_err = str(e)

                # Fallback to local copy ONLY IF live repository exists, has .git, and has non-empty files
                if not cloned and Path(c_path).is_dir() and (Path(c_path) / ".git").is_dir():
                    try:
                        src_files = [f for f in Path(c_path).iterdir() if f.name != ".git"]
                        if src_files:
                            shutil.copytree(
                                c_path,
                                target_dir,
                                dirs_exist_ok=True,
                                symlinks=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
                            )
                            cloned = True
                    except Exception as e:
                        clone_err = f"{clone_err}; local copy failed: {e}"

                # Strict empirical validation:
                # 1. target_dir exists and is a directory
                # 2. (target_dir / ".git") exists and is a directory
                # 3. git config remote.origin.url matches expected remote
                # 4. directory has files other than .git
                is_valid = False
                validation_err = ""
                if target_dir.is_dir() and (target_dir / ".git").is_dir():
                    try:
                        res_remote = subprocess.run(
                            ["git", "-C", str(target_dir), "config", "remote.origin.url"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        curr_remote = res_remote.stdout.strip()
                        if _normalize_git_url(curr_remote) == _normalize_git_url(remote_url):
                            files = [f for f in target_dir.iterdir() if f.name != ".git"]
                            if files:
                                is_valid = True
                            else:
                                validation_err = f"Target directory {target_dir} has no project files"
                        else:
                            validation_err = f"Remote mismatch: expected {remote_url}, got {curr_remote}"
                    except Exception as e:
                        validation_err = f"Failed to verify git config: {e}"
                else:
                    validation_err = clone_err or f"Directory {target_dir} or .git does not exist after recovery attempt"

                if is_valid:
                    report["restored_projects"].append(p_id)
                else:
                    report["errors"].append({"project_id": p_id, "error": validation_err})

        if report["errors"]:
            report["status"] = "PROJECT_RESTORE_INCOMPLETE"
            report["failed_stage"] = "PROJECT_RESTORE_BLOCKED"
        else:
            report["stages"].append("PROJECT_RESTORED")

        return report

    def recover_frappe_bench(
        self,
        target_project_dir: Path,
        dry_run: bool = False,
        home: Optional[Path] = None,
        projects_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Reconstructs the compound Frappe bench structure according to the manifest without mock stubs."""
        manifest = self.load_frappe_manifest()
        bench_dir = target_project_dir / "frappe-bench"
        apps_dir = bench_dir / "apps"

        required_apps = manifest.get("installed_apps", ["frappe", "erpnext", "alco_ecommerce"])

        # Check existing apps
        all_exist = True
        for app in required_apps:
            app_path = apps_dir / app
            if not app_path.is_dir():
                all_exist = False
                break
            files = [f for f in app_path.iterdir() if not f.name.startswith(".")]
            if not files:
                all_exist = False
                break

        if all_exist:
            return {"status": "EXISTING", "bench_root": str(bench_dir)}

        if dry_run:
            return {"status": "PROJECT_RESTORED", "bench_root": str(bench_dir)}

        try:
            bench_dir.mkdir(parents=True, exist_ok=True)
            apps_dir.mkdir(parents=True, exist_ok=True)

            repo_map = {r.get("name"): r for r in manifest.get("repositories", [])}
            missing_apps = []

            for app_name in required_apps:
                target_app_dir = apps_dir / app_name
                if target_app_dir.is_dir() and [f for f in target_app_dir.iterdir() if not f.name.startswith(".")]:
                    continue

                app_restored = False
                # 1. Attempt git clone if repo URL available
                repo_info = repo_map.get(app_name, {})
                repo_url = repo_info.get("url")
                repo_branch = repo_info.get("branch")
                if repo_url and shutil.which("git"):
                    try:
                        env = dict(os.environ)
                        env["GIT_TERMINAL_PROMPT"] = "0"
                        clone_cmd = ["git", "clone", "--depth", "1"]
                        if repo_branch:
                            clone_cmd.extend(["-b", repo_branch])
                        clone_cmd.extend([repo_url, str(target_app_dir)])
                        res = subprocess.run(clone_cmd, env=env, capture_output=True, timeout=30)
                        if res.returncode == 0 and [f for f in target_app_dir.iterdir() if not f.name.startswith(".")]:
                            app_restored = True
                    except Exception:
                        pass

                # 2. Check local live source candidates dynamically if clone didn't work
                if not app_restored:
                    source_candidates = []
                    if projects_root:
                        source_candidates.append(Path(projects_root) / f"Frappe-erp-Alco/frappe-bench/apps/{app_name}")
                    if home:
                        source_candidates.append(Path(home) / f"Frappe-erp-Alco/frappe-bench/apps/{app_name}")
                        source_candidates.append(Path(home) / f"IroScript_Projects/Frappe-erp-Alco/frappe-bench/apps/{app_name}")
                    if "PROJECTS_ROOT" in os.environ and os.environ["PROJECTS_ROOT"]:
                        source_candidates.append(Path(os.environ["PROJECTS_ROOT"]) / f"Frappe-erp-Alco/frappe-bench/apps/{app_name}")

                    for cand in source_candidates:
                        if cand.is_dir() and [f for f in cand.iterdir() if not f.name.startswith(".")]:
                            try:
                                shutil.copytree(cand, target_app_dir, dirs_exist_ok=True, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                                app_restored = True
                                break
                            except Exception:
                                pass

                if not app_restored or not target_app_dir.is_dir() or not [f for f in target_app_dir.iterdir() if not f.name.startswith(".")]:
                    missing_apps.append(app_name)

            if missing_apps:
                return {
                    "status": "PROJECT_RESTORE_INCOMPLETE",
                    "error": f"Failed to restore required Frappe apps: {missing_apps}",
                    "missing_components": missing_apps,
                    "bench_root": str(bench_dir),
                }

            # Sites structure
            sites_dir = bench_dir / "sites"
            site_name = manifest.get("site_name", "alco.localhost")
            site_dir = sites_dir / site_name
            site_dir.mkdir(parents=True, exist_ok=True)
            (site_dir / "public" / "files").mkdir(parents=True, exist_ok=True)
            (site_dir / "private" / "files").mkdir(parents=True, exist_ok=True)

            site_cfg = manifest.get("site_config", {"db_name": "_b4b30e57a5907bea", "db_type": "mariadb"})
            (site_dir / "site_config.json").write_text(json.dumps(site_cfg, indent=2), encoding="utf-8")

            installed_apps = manifest.get("installed_apps", ["frappe", "erpnext", "alco_ecommerce"])
            (sites_dir / "apps.txt").write_text("\n".join(installed_apps) + "\n", encoding="utf-8")
            (sites_dir / "apps.json").write_text(json.dumps(installed_apps, indent=2), encoding="utf-8")
            (sites_dir / "common_site_config.json").write_text(
                json.dumps({"auto_order_sequential": True}, indent=2), encoding="utf-8"
            )

            # Compatibility contract
            contract_src = self.sot_root / "project_profiles" / "frappe" / "compatibility_contract.json"
            if contract_src.is_file():
                shutil.copy2(contract_src, bench_dir / "compatibility_contract.json")
                shutil.copy2(contract_src, target_project_dir / "compatibility_contract.json")

            # Docs reference fallback
            docs_ref = self.sot_root / "frappe" / "docs-reference"
            if docs_ref.is_dir() and (docs_ref / "MANIFEST.json").is_file():
                target_docs = target_project_dir / "frappe-docs-latest"
                if not target_docs.exists():
                    try:
                        target_docs.symlink_to(docs_ref.resolve(), target_is_directory=True)
                    except Exception:
                        shutil.copytree(docs_ref.resolve(), target_docs)

            return {"status": "PROJECT_RESTORED", "bench_root": str(bench_dir)}
        except Exception as exc:
            return {"status": "PROJECT_RESTORE_INCOMPLETE", "error": str(exc), "bench_root": str(bench_dir)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generic Project Recovery Orchestrator")
    parser.add_argument("--sot-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--projects-root", default=os.environ.get("PROJECTS_ROOT"))
    parser.add_argument("--home", default=os.environ.get("HOME"))
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    home = Path(args.home or Path.home()).resolve()
    p_root = Path(args.projects_root or (home / "IroScript_Projects")).resolve()
    orchestrator = ProjectRecoveryOrchestrator(Path(args.sot_root))
    res = orchestrator.recover_all(p_root, home=home, filter_project_id=args.project_id, dry_run=args.dry_run)
    print(json.dumps(res, indent=2))
    return 0 if res.get("status") == "PROJECT_RESTORED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
