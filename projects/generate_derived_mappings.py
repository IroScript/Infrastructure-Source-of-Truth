#!/usr/bin/env python3
"""
generate_derived_mappings.py — Universal Derived Mapping Generator for AGY.
Single Canonical Source: Infrastructure-Source-of-Truth/projects/PROJECT_REGISTRY.json
Generates and keeps in sync:
1. projects/gitpush_folder_mapping.json (and operational target)
2. projects/GIT_REPOSITORIES.json
3. projects/PROJECTS.json
4. connections/WHATSAPP_CONNECTIONS.json
5. connections/TMUX_CONNECTIONS.json
6. connections/SERVICE_CONNECTIONS.json
7. infrastructure/SERVICES.json, PORTS.json, TMUX_WINDOWS.json
"""

import os
import sys
import json
import time
from atomic_json import atomic_write_json, read_json, registry_lock, validate_project_registry

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOT_ROOT = os.path.dirname(SCRIPT_DIR)
REGISTRY_FILE = os.path.join(SCRIPT_DIR, "PROJECT_REGISTRY.json")

OPERATIONAL_GITPUSH_MAPPING = "/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/gitpush_folder_mapping.json"
CANONICAL_GITPUSH_MAPPING = os.path.join(SCRIPT_DIR, "gitpush_folder_mapping.json")
GIT_REPOSITORIES_FILE = os.path.join(SCRIPT_DIR, "GIT_REPOSITORIES.json")
PROJECTS_FILE = os.path.join(SCRIPT_DIR, "PROJECTS.json")
SETTINGS_FILE = os.path.join(SOT_ROOT, "configuration", "settings.json")

WHATSAPP_CONN_FILE = os.path.join(SOT_ROOT, "connections", "WHATSAPP_CONNECTIONS.json")
TMUX_CONN_FILE = os.path.join(SOT_ROOT, "connections", "TMUX_CONNECTIONS.json")
SERVICE_CONN_FILE = os.path.join(SOT_ROOT, "connections", "SERVICE_CONNECTIONS.json")

INFRA_SERVICES_FILE = os.path.join(SOT_ROOT, "infrastructure", "SERVICES.json")
INFRA_PORTS_FILE = os.path.join(SOT_ROOT, "infrastructure", "PORTS.json")
INFRA_TMUX_FILE = os.path.join(SOT_ROOT, "infrastructure", "TMUX_WINDOWS.json")


def load_canonical_registry():
    if not os.path.exists(REGISTRY_FILE):
        raise FileNotFoundError(f"Canonical registry not found at {REGISTRY_FILE}")
    data = read_json(REGISTRY_FILE)
    validate_project_registry(data)
    return data


def build_gitpush_entry(project):
    git_info = project.get("git", {})
    return {"key": project["project_id"], "project_uuid": project.get("project_uuid", ""),
            "folder_path": project.get("canonical_path", ""),
            "git_remote_url": git_info.get("remote", ""),
            "enabled": project.get("runtime", {}).get("enabled", True)}


def generate_all(sync_operational=True):
    with registry_lock(os.path.join(SOT_ROOT, ".mapping-generator")):
        return _generate_all_locked(sync_operational)


def _generate_all_locked(sync_operational=True):
    reg = load_canonical_registry()
    projects = reg.get("projects", [])
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    settings_out = read_json(SETTINGS_FILE)
    settings_out["trustedWorkspaces"] = sorted({
        path for project in projects
        for path in ([project.get("canonical_path", "")] + project.get("aliases", []))
        if isinstance(path, str) and path
    })

    # 1. Generate gitpush_folder_mapping.json
    gitpush_projects = []
    git_repos = []
    legacy_projects = []
    whatsapp_conns = []
    tmux_conns = []
    service_conns = []
    infra_services = []
    infra_ports = []
    infra_tmux = []

    for p in projects:
        pid = p["project_id"]
        puid = p.get("project_uuid", "")
        dname = p.get("display_name", pid)
        cpath = p.get("canonical_path", "")
        git_info = p.get("git", {})
        runtime_info = p.get("runtime", {})
        conn_info = p.get("connections", {})

        # Mapping entry
        gp_entry = build_gitpush_entry(p)
        gitpush_projects.append(gp_entry)

        # Git repositories entry
        if git_info.get("enabled"):
            git_repos.append({
                "project_id": pid,
                "project_uuid": puid,
                "display_name": dname,
                "repository_path": cpath,
                "remote_url": git_info.get("remote", ""),
                "branch": git_info.get("branch", "main"),
                "visibility": git_info.get("remote_visibility", "private"),
                "backup_required": git_info.get("backup_required", True),
                "status": p.get("status", "ACTIVE")
            })

        # Legacy PROJECTS.json entry
        legacy_projects.append({
            "project_key": pid,
            "project_uuid": puid,
            "project_name": dname,
            "canonical_physical_path": cpath,
            "symlink_aliases": p.get("aliases", []),
            "git_repository": cpath if git_info.get("enabled") else None,
            "git_remote_fetch": git_info.get("remote", ""),
            "git_remote_push": git_info.get("remote", ""),
            "branch": git_info.get("branch", "main"),
            "github_backed": "REMOTE_SHA_VERIFIED" in p.get("lifecycle_stages", []),
            "tmux_window": runtime_info.get("tmux_window", ""),
            "systemd_services": runtime_info.get("services", []),
            "ports": runtime_info.get("ports", []),
            "databases": p.get("data", []),
            "status": p.get("status", "ACTIVE")
        })

        # WhatsApp connections
        wa = conn_info.get("whatsapp", {})
        if wa.get("enabled"):
            whatsapp_conns.append({
                "project_id": pid,
                "project_uuid": puid,
                "display_name": dname,
                "enabled": True,
                "group_id": wa.get("group_id", ""),
                "agent_name": wa.get("agent_route", ""),
                "working_directory_source": "PROJECT_REGISTRY"
            })

        # Tmux connections
        tmux_win = runtime_info.get("tmux_window", "")
        if tmux_win:
            tmux_conns.append({
                "project_id": pid,
                "project_uuid": puid,
                "session": "agy",
                "windows": [w.strip() for w in tmux_win.split(",") if w.strip()],
                "working_directory_source": "PROJECT_REGISTRY",
                "enabled": True
            })
            infra_tmux.append({
                "window": tmux_win,
                "project_id": pid,
                "project_uuid": puid,
                "working_directory": cpath
            })

        # Service / Port connections
        services = runtime_info.get("services", [])
        ports = runtime_info.get("ports", [])
        if services or ports:
            for s in services:
                service_conns.append({
                    "project_id": pid,
                    "project_uuid": puid,
                    "service_name": s,
                    "ports": ports,
                    "startup_type": "systemd",
                    "enabled": True
                })
                infra_services.append({
                    "service": s,
                    "project_id": pid,
                    "project_uuid": puid,
                    "status": "managed"
                })
            for pt in ports:
                infra_ports.append({
                    "port": pt,
                    "project_id": pid,
                    "project_uuid": puid,
                    "service": services[0] if services else "custom"
                })

    # Output structures
    gitpush_out = {
        "version": "2.0.0",
        "last_updated": now_iso,
        "derived_from": "Infrastructure-Source-of-Truth/projects/PROJECT_REGISTRY.json",
        "projects": gitpush_projects
    }

    git_repos_out = {
        "version": "2.0.0",
        "last_updated": now_iso,
        "derived_from": "Infrastructure-Source-of-Truth/projects/PROJECT_REGISTRY.json",
        "repositories": git_repos
    }

    whatsapp_out = {
        "version": "2.0.0",
        "last_updated": now_iso,
        "derived_from": "PROJECT_REGISTRY.json",
        "connections": whatsapp_conns
    }

    tmux_out = {
        "version": "2.0.0",
        "last_updated": now_iso,
        "derived_from": "PROJECT_REGISTRY.json",
        "connections": tmux_conns
    }

    service_out = {
        "version": "2.0.0",
        "last_updated": now_iso,
        "derived_from": "PROJECT_REGISTRY.json",
        "connections": service_conns
    }

    # Write files
    os.makedirs(os.path.dirname(CANONICAL_GITPUSH_MAPPING), exist_ok=True)
    atomic_write_json(CANONICAL_GITPUSH_MAPPING, gitpush_out)

    if sync_operational and os.path.exists(os.path.dirname(OPERATIONAL_GITPUSH_MAPPING)):
        atomic_write_json(OPERATIONAL_GITPUSH_MAPPING, gitpush_out)

    atomic_write_json(GIT_REPOSITORIES_FILE, git_repos_out)

    atomic_write_json(PROJECTS_FILE, legacy_projects)

    os.makedirs(os.path.dirname(WHATSAPP_CONN_FILE), exist_ok=True)
    atomic_write_json(WHATSAPP_CONN_FILE, whatsapp_out)

    atomic_write_json(TMUX_CONN_FILE, tmux_out)

    atomic_write_json(SERVICE_CONN_FILE, service_out)

    os.makedirs(os.path.dirname(INFRA_SERVICES_FILE), exist_ok=True)
    atomic_write_json(INFRA_SERVICES_FILE, {"services": infra_services})

    atomic_write_json(INFRA_PORTS_FILE, {"ports": infra_ports})

    atomic_write_json(INFRA_TMUX_FILE, {"tmux_windows": infra_tmux})
    atomic_write_json(SETTINGS_FILE, settings_out)

    # WhatsApp Bridge operational project_groups.json
    project_groups = {}
    for p in projects:
        pid = p["project_id"]
        dname = p.get("display_name", pid)
        cpath = p.get("canonical_path", "")
        git_info = p.get("git", {})
        runtime_info = p.get("runtime", {})
        conn_info = p.get("connections", {})
        wa = conn_info.get("whatsapp", {})
        if wa.get("enabled") or runtime_info.get("tmux_window") or conn_info.get("whatsapp"):
            route = wa.get("agent_route", "")
            key = route.split(":")[-1] if ":" in route else pid
            group_id = wa.get("group_id", "") or f"{pid}@g.us"
            project_groups[key] = {
                "id": group_id,
                "name": dname,
                "key": key,
                "window": runtime_info.get("tmux_window", ""),
                "cwd": cpath,
                "git_remote": git_info.get("remote", ""),
                "whatsapp_status": "CONNECTED" if p.get("status") == "ACTIVE" else "DISCOVERED"
            }

    canonical_pg = os.path.join(SOT_ROOT, "connections", "project_groups.json")
    atomic_write_json(canonical_pg, project_groups)

    op_webterminal_pg = "/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/project_groups.json"
    if sync_operational and os.path.exists(os.path.dirname(op_webterminal_pg)):
        try:
            curr_pg = read_json(op_webterminal_pg) if os.path.exists(op_webterminal_pg) else {}
            curr_pg.update(project_groups)
            atomic_write_json(op_webterminal_pg, curr_pg)
        except Exception:
            pass

    home_wt_pg = os.path.expanduser("~/.webterminal/project_groups.json")
    if sync_operational and os.path.exists(os.path.dirname(home_wt_pg)):
        try:
            curr_pg = read_json(home_wt_pg) if os.path.exists(home_wt_pg) else {}
            curr_pg.update(project_groups)
            atomic_write_json(home_wt_pg, curr_pg)
        except Exception:
            pass

    print(f"[+] Successfully generated all derived mappings from {REGISTRY_FILE}")
    print(f"    - Projects tracked: {len(projects)}")
    print(f"    - Git repositories: {len(git_repos)}")
    print(f"    - WhatsApp connections: {len(whatsapp_conns)}")
    print(f"    - Tmux window routes: {len(tmux_conns)}")
    print(f"    - Service connections: {len(service_conns)}")
    return True


if __name__ == "__main__":
    generate_all()
