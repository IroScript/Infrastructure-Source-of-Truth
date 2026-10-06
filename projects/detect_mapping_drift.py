#!/usr/bin/env python3
"""
detect_mapping_drift.py — Verifies alignment between canonical PROJECT_REGISTRY.json,
derived gitpush_folder_mapping.json, and operational mapping in webterminal.
"""
import json
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_FILE = os.path.join(SCRIPT_DIR, "PROJECT_REGISTRY.json")
MAPPING_OPERATIONAL = "/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/gitpush_folder_mapping.json"
MAPPING_CANONICAL = os.path.join(SCRIPT_DIR, "gitpush_folder_mapping.json")

print("=== PROJECT REGISTRY & MAPPING DRIFT DETECTOR ===")
drift = False

if not os.path.exists(REGISTRY_FILE):
    print(f"[-] Canonical registry missing at {REGISTRY_FILE}")
    sys.exit(1)

if not os.path.exists(MAPPING_OPERATIONAL):
    print(f"[-] Operational mapping file missing at {MAPPING_OPERATIONAL}")
    sys.exit(1)

with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
    reg_data = json.load(f)

with open(MAPPING_OPERATIONAL, "r", encoding="utf-8") as f:
    op_data = json.load(f)

reg_projects = {p["project_id"]: p for p in reg_data.get("projects", [])}
op_projects = {p["key"]: p for p in op_data.get("projects", [])}

# Check all registered projects are in operational mapping
for pid, p in reg_projects.items():
    if pid not in op_projects:
        print(f"[-] project_id missing in operational mapping: {pid}")
        drift = True
    else:
        op_p = op_projects[pid]
        expected_path = p.get("canonical_path")
        actual_path = op_p.get("folder_path")
        if expected_path != actual_path:
            print(f"[-] Path drift for {pid}: operational={actual_path} vs registry={expected_path}")
            drift = True
        expected_remote = p.get("git", {}).get("remote", "")
        actual_remote = op_p.get("git_remote_url", "")
        if expected_remote != actual_remote:
            print(f"[-] Remote drift for {pid}: operational={actual_remote} vs registry={expected_remote}")
            drift = True

# Check if operational mapping has keys not in registry
for op_k in op_projects:
    if op_k not in reg_projects:
        print(f"[-] Unregistered key in operational mapping: {op_k}")
        drift = True

if drift:
    print("MAPPING DRIFT DETECTED: FAIL")
    sys.exit(1)
else:
    print(f"[+] Zero drift between canonical PROJECT_REGISTRY ({len(reg_projects)} projects) and operational mapping.")
    print("MAPPING DRIFT DETECTED: PASS")
    sys.exit(0)
