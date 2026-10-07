#!/usr/bin/env python3
"""
discover_unregistered_projects.py — Orphan Project & Unregistered Directory Scanner.
Scans managed roots defined in MANAGED_ROOTS.json for:
- .git directories
- Recognized project markers: package.json, pyproject.toml, Cargo.toml, pubspec.yaml, bench/apps, requirements.txt
Reports any discovered project not registered in PROJECT_REGISTRY.json.
Zero destructive action.
"""

import os
import sys
import json
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOT_ROOT = os.environ.get("AGY_SOT_ROOT", os.path.dirname(SCRIPT_DIR))
REGISTRY_FILE = os.path.join(SOT_ROOT, "projects", "PROJECT_REGISTRY.json")
ROOTS_FILE = os.path.join(SOT_ROOT, "projects", "MANAGED_ROOTS.json")

PROJECT_MARKERS = [
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "pubspec.yaml",
    "requirements.txt",
    "bench",
    "CMakeLists.txt",
    "pom.xml",
    "build.gradle", "go.mod", "composer.json", "Cargo.toml"
]
DEFAULT_EXCLUDED = {"node_modules", "venv", ".venv", "target", "build", "dist", ".cache", "vendor", "__pycache__", ".git"}


def load_managed_roots():
    roots_file = os.environ.get("SOT_PROJECTS_ROOT_FILE")
    if roots_file and os.path.isfile(roots_file) and not os.environ.get("PROJECTS_ROOT"):
        try:
            os.environ["PROJECTS_ROOT"] = open(roots_file, encoding="utf-8").read().strip()
        except OSError:
            return []
    configured = os.environ.get("SOT_MANAGED_ROOTS")
    if configured:
        return [os.path.realpath(p) for p in configured.split(os.pathsep) if p]
    if not os.path.exists(ROOTS_FILE):
        root = os.environ.get("PROJECTS_ROOT") or os.environ.get("SOT_PROJECTS_ROOT")
        return [os.path.realpath(root)] if root else []
    with open(ROOTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    roots = []
    base = os.environ.get("PROJECTS_ROOT") or os.environ.get("SOT_PROJECTS_ROOT")
    for item in data.get("managed_roots", []):
        if not item.get("enabled", True):
            continue
        path = item.get("path", "")
        if not base and os.path.isabs(path) and path.startswith("/home/azureuser/"):
            path = os.path.join(os.environ.get("HOME", str(Path.home())), os.path.relpath(path, "/home/azureuser"))
        # Absolute paths are accepted only as deployment-profile inputs and rebound by
        # stable root_id for portable profiles.
        if base and item.get("root_id") == "iroscript_projects":
            path = base
        elif base and item.get("root_id") == "frappe_erp_alco":
            path = os.environ.get("FRAPPE_ROOT", os.path.join(base, "frappe"))
        roots.append(os.path.realpath(os.path.expanduser(path)))
    return roots


def load_registered_paths():
    if not os.path.exists(REGISTRY_FILE):
        return set()
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    paths = set()
    for p in data.get("projects", []):
        cp = p.get("canonical_path")
        if cp:
            paths.add(os.path.realpath(cp))
        for a in p.get("aliases", []):
            if os.path.exists(a):
                paths.add(os.path.realpath(a))
    return paths


def load_excluded_patterns():
    if not os.path.exists(ROOTS_FILE):
        return ["*backup*", "node_modules", ".git", "__pycache__", ".cache", ".venv", "env", "venv", "All_Backup", "archived_deletions"]
    with open(ROOTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("excluded_patterns", [])


def scan_for_projects(root, max_depth=None):
    import fnmatch
    discovered = []
    root = os.path.realpath(root)
    if not os.path.exists(root):
        return discovered

    excluded_patterns = load_excluded_patterns()

    for dirpath, dirnames, filenames in os.walk(root):
        # Exclude directories matching patterns
        filtered = []
        for d in dirnames:
            if d in DEFAULT_EXCLUDED:
                continue
            matched = False
            for pat in excluded_patterns:
                if fnmatch.fnmatch(d.lower(), pat.lower()):
                    matched = True
                    break
            if not matched:
                filtered.append(d)
        dirnames[:] = filtered

        depth = len(os.path.relpath(dirpath, root).split(os.sep))
        if max_depth is not None and depth > max_depth:
            dirnames.clear()
            continue

        real_dir = os.path.realpath(dirpath)
        is_git = os.path.isdir(os.path.join(dirpath, ".git"))
        ordinary_markers = [m for m in PROJECT_MARKERS if m != "bench"]
        markers = [m for m in ordinary_markers if m in filenames or m in dirnames]
        has_marker = bool(markers)
        if "bench" in dirnames and os.path.isdir(os.path.join(dirpath, "bench", "apps")):
            has_marker = True
            markers.append("bench/apps")
        if has_marker and _inside_declared_workspace(real_dir, root):
            has_marker = False

        if is_git or has_marker:
            discovered.append({
                "path": real_dir,
                "is_git": is_git,
                "marker": "git" if is_git else markers[0]
            })

    return discovered


def _inside_declared_workspace(path, root):
    """Suppress source subpackages that an enclosing package manager declares as one workspace."""
    import json as _json
    current = os.path.realpath(path)
    root = os.path.realpath(root)
    while current != root and current.startswith(root + os.sep):
        parent = os.path.dirname(current)
        cargo = os.path.join(parent, "Cargo.toml")
        if os.path.isfile(cargo):
            try:
                if "[workspace]" in open(cargo, encoding="utf-8").read():
                    return True
            except OSError:
                pass
        package = os.path.join(parent, "package.json")
        if os.path.isfile(package):
            try:
                with open(package, encoding="utf-8") as stream:
                    package_data = _json.load(stream)
                if package_data.get("workspaces"):
                    return True
            except (OSError, ValueError, AttributeError):
                pass
        current = parent
    return False


def is_registered_project_path(candidate, registered_paths):
    return os.path.realpath(candidate) in {os.path.realpath(path) for path in registered_paths}


def main():
    registered_paths = load_registered_paths()
    managed_roots = load_managed_roots()

    print("=== ORPHAN PROJECT DISCOVERY SCANNER ===")
    print(f"[*] Registered canonical projects: {len(registered_paths)}")
    print(f"[*] Scanning managed roots: {managed_roots}")

    orphans = []
    total_found = 0
    seen_paths = set()

    for root in managed_roots:
        found = scan_for_projects(root)
        total_found += len(found)
        for proj in found:
            p_real = proj["path"]
            if p_real in seen_paths:
                continue
            seen_paths.add(p_real)
            # Only the exact project root is registered. Nested projects are independent.
            matched = is_registered_project_path(p_real, registered_paths)
            if not matched:
                orphans.append(proj)

    print(f"[*] Total project-like candidates evaluated: {total_found}")
    if orphans:
        print(f"[-] UNREGISTERED / ORPHAN PROJECTS DETECTED ({len(orphans)}):")
        for o in orphans:
            print(f"    - {o['path']} (Marker: {o['marker']}, Git: {o['is_git']})")
        print("\n[!] Remediate by registering with:")
        print("    python3 projects/register_project.py --path \"<path>\" --name \"<name>\"")
        return 1
    else:
        print("[+] Zero orphan projects detected. All managed directories are registered.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
