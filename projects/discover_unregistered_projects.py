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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_FILE = os.path.join(SCRIPT_DIR, "PROJECT_REGISTRY.json")
ROOTS_FILE = os.path.join(SCRIPT_DIR, "MANAGED_ROOTS.json")

PROJECT_MARKERS = [
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "pubspec.yaml",
    "requirements.txt",
    "bench",
    "CMakeLists.txt",
    "pom.xml",
    "build.gradle"
]


def load_managed_roots():
    if not os.path.exists(ROOTS_FILE):
        return ["/home/azureuser/IroScript_Projects", "/home/azureuser/Frappe-erp-Alco"]
    with open(ROOTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [r["path"] for r in data.get("managed_roots", []) if r.get("enabled", True)]


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


def scan_for_projects(root, max_depth=3):
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
            if d.startswith("."):
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
        if depth > max_depth:
            dirnames.clear()
            continue

        real_dir = os.path.realpath(dirpath)
        is_git = os.path.isdir(os.path.join(dirpath, ".git"))
        has_marker = any(m in filenames or m in dirnames for m in PROJECT_MARKERS)

        if is_git or has_marker:
            discovered.append({
                "path": real_dir,
                "is_git": is_git,
                "marker": "git" if is_git else [m for m in PROJECT_MARKERS if m in filenames or m in dirnames][0]
            })
            if is_git and "frappe-bench" not in real_dir:
                dirnames.clear()

    return discovered


def main():
    registered_paths = load_registered_paths()
    managed_roots = load_managed_roots()

    print("=== ORPHAN PROJECT DISCOVERY SCANNER ===")
    print(f"[*] Registered canonical projects: {len(registered_paths)}")
    print(f"[*] Scanning managed roots: {managed_roots}")

    orphans = []
    total_found = 0

    for root in managed_roots:
        found = scan_for_projects(root)
        total_found += len(found)
        for proj in found:
            p_real = proj["path"]
            # Check if this path or a parent is already registered
            matched = False
            for reg in registered_paths:
                if p_real == reg or p_real.startswith(reg + "/"):
                    matched = True
                    break
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
