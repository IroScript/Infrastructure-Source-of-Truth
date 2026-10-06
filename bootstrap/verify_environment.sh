#!/usr/bin/env bash
# verify_environment.sh — Validates environment parity against manifests.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== EXECUTING ENVIRONMENT PARITY VERIFICATION ==="
python3 -c "
import json, os

with open('${REPO_ROOT}/infrastructure/SYMLINKS.json') as f:
    symlinks = json.load(f)
for s in symlinks:
    alias = s['alias_path']
    real = s['resolved_physical_target']
    assert os.path.realpath(alias) == real, f'Mismatch on {alias}'
print('[+] Symlinks verified.')

with open('${REPO_ROOT}/projects/PROJECTS.json') as f:
    projects = json.load(f)
for p in projects:
    assert os.path.exists(p['canonical_physical_path']), f'Missing folder: {p["canonical_physical_path"]}'
print('[+] Project directories verified.')
"
echo "PARITY VERIFICATION: PASS"
