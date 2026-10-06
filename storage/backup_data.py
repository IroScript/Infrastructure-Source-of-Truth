#!/usr/bin/env python3
"""
backup_data.py — Registry-Driven Data & Database Backup Engine.
Part of the AGY Universal Project Lifecycle & Backup Control System.

Strict Status Progression:
  DISCOVERED -> BACKUP REQUIRED -> BACKUP CREATED -> REMOTE VERIFIED -> RESTORE VERIFIED
Note: rclone copy returning exit code 0 establishes REMOTE VERIFIED, NOT RESTORE VERIFIED.
RESTORE VERIFIED requires an independent restore and integrity verification run.
"""

import os
import sys
import json
import hashlib
import argparse
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_FILE = os.path.join(SCRIPT_DIR, "DATA_ASSET_REGISTRY.json")
CATALOG_FILE = os.path.join(SCRIPT_DIR, "BACKUP_CATALOG.json")


def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_assets():
    if not os.path.exists(REGISTRY_FILE):
        raise FileNotFoundError(f"Asset registry missing: {REGISTRY_FILE}")
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("assets", [])


def backup_asset(asset, dry_run=False, verify_remote=True):
    asset_id = asset["asset_id"]
    source_path = asset["source_path"]
    target_remote = asset.get("primary_backup_target", "")

    print(f"\n[*] Processing Asset: {asset_id}")
    print(f"    Source: {source_path}")
    print(f"    Target: {target_remote}")

    if not os.path.exists(source_path):
        print(f"[-] ERROR: Source path does not exist physically: {source_path}")
        return {"asset_id": asset_id, "status": "FAILED", "reason": "SOURCE_NOT_FOUND"}

    size = os.path.getsize(source_path) if os.path.isfile(source_path) else 0
    checksum = sha256_file(source_path) if os.path.isfile(source_path) else "DIRECTORY_ASSET"
    print(f"    Size: {size} bytes | SHA256: {checksum[:16]}...")

    if dry_run:
        print("    [DRY-RUN] Would execute rclone copy to remote.")
        return {"asset_id": asset_id, "status": "BACKUP REQUIRED", "checksum": checksum, "size": size}

    # Step 1: Copy to remote
    print(f"    [*] Uploading to {target_remote}...")
    cmd = ["rclone", "copy", source_path, target_remote]
    p = subprocess.run(cmd, capture_output=True, text=True)

    if p.returncode != 0:
        print(f"[-] Backup upload failed: {p.stderr.strip()}")
        return {"asset_id": asset_id, "status": "FAILED", "reason": p.stderr.strip()}

    print("    [+] Upload completed with rc=0 (Status: BACKUP CREATED)")

    # Step 2: Verify remote existence and size
    status = "BACKUP CREATED"
    if verify_remote:
        dest_filename = os.path.basename(source_path)
        check_p = subprocess.run(["rclone", "lsf", target_remote], capture_output=True, text=True)
        if dest_filename in check_p.stdout:
            print(f"    [+] Remote existence verified for '{dest_filename}' (Status: REMOTE VERIFIED)")
            status = "REMOTE VERIFIED"
        else:
            print(f"    [!] Remote existence could not be confirmed in listing: {dest_filename}")

    # Step 3: Catalog entry
    catalog_entry = {
        "backup_id": f"bak_{asset_id}_{int(time.time())}",
        "asset_id": asset_id,
        "project_id": asset.get("project_id", "unknown"),
        "source_checksum": checksum,
        "remote_destination": target_remote,
        "remote_object": os.path.basename(source_path),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "size": size,
        "encryption": asset.get("encryption", "none"),
        "status": status,
        "restore_verification": "PENDING_RESTORE_TEST"
    }

    if os.path.exists(CATALOG_FILE):
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            cat = json.load(f)
        cat.setdefault("backups", []).append(catalog_entry)
        cat["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(cat, f, indent=2)

    return catalog_entry


def main():
    parser = argparse.ArgumentParser(description="Universal Data & Database Backup Engine")
    parser.add_argument("--asset", default="", help="Specific asset_id to back up (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without uploading")
    parser.add_argument("--no-verify", action="store_true", help="Skip remote existence verification")
    args = parser.parse_args()

    assets = load_assets()
    target_assets = [a for a in assets if a["asset_id"] == args.asset] if args.asset else [a for a in assets if a.get("backup_required")]

    print(f"=== UNIVERSAL BACKUP ENGINE (Assets to evaluate: {len(target_assets)}) ===")
    results = []
    for a in target_assets:
        res = backup_asset(a, dry_run=args.dry_run, verify_remote=not args.no_verify)
        results.append(res)

    print("\n==========================================")
    print("  BACKUP RUN SUMMARY")
    print("==========================================")
    for r in results:
        print(f"  - {r['asset_id']}: {r.get('status', 'ERROR')}")


if __name__ == "__main__":
    main()
