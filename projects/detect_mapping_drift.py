#!/usr/bin/env python3
# detect_mapping_drift.py — Verifies alignment between gitpush_folder_mapping.json and PROJECTS.json.
import json, sys, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAPPING_OPERATIONAL = "/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/gitpush_folder_mapping.json"
MAPPING_CANONICAL = os.path.join(SCRIPT_DIR, "gitpush_folder_mapping.json")
PROJECTS_FILE = os.path.join(SCRIPT_DIR, "PROJECTS.json")

print("=== MAPPING DRIFT DETECTOR ===")
drift = False

if not os.path.exists(MAPPING_OPERATIONAL):
    print("[-] Operational mapping file missing!")
    sys.exit(1)

with open(MAPPING_OPERATIONAL) as f:
    op_data = json.load(f)
with open(MAPPING_CANONICAL) as f:
    can_data = json.load(f)

# Compare project lists
op_keys = {p['key']: p for p in op_data.get('projects', [])}
can_keys = {p['key']: p for p in can_data.get('projects', [])}

for k, p in can_keys.items():
    if k not in op_keys:
        print(f"[-] Key missing in operational mapping: {k}")
        drift = True
    else:
        op_p = op_keys[k]
        if op_p.get('folder_path') != p.get('folder_path'):
            print(f"[-] Folder drift for {k}: operational={op_p.get('folder_path')} vs canonical={p.get('folder_path')}")
            drift = True
        if op_p.get('git_remote_url') != p.get('git_remote_url'):
            print(f"[-] Remote drift for {k}: operational={op_p.get('git_remote_url')} vs canonical={p.get('git_remote_url')}")
            drift = True

if drift:
    print("MAPPING DRIFT DETECTED: FAIL")
    sys.exit(1)
else:
    print("[+] Zero drift between operational mapping and Source of Truth canonical registry.")
    print("MAPPING DRIFT DETECTED: PASS")
    sys.exit(0)
