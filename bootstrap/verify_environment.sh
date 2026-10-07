#!/usr/bin/env bash
# verify_environment.sh — Validates environment parity against manifests.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== EXECUTING ENVIRONMENT PARITY VERIFICATION ==="
python3 - "$REPO_ROOT" <<'PY'
import json, os, sys
from pathlib import Path

repo_root = Path(sys.argv[1])
with open(repo_root / 'infrastructure/SYMLINKS.json') as f:
    symlinks = json.load(f)
home = os.environ.get('HOME', '/home/azureuser')
projects_root = os.environ.get('PROJECTS_ROOT', os.path.join(home, 'IroScript_Projects'))
def exp(p): return p.replace('${HOME}', home).replace('${PROJECTS_ROOT}', projects_root)
for s in symlinks:
    alias = exp(s['alias_path'])
    real = exp(s['resolved_physical_target'])
    assert os.path.realpath(alias) == os.path.realpath(real), f'Mismatch on {alias}'
print('[+] Symlinks verified.')

with open(repo_root / 'projects/PROJECTS.json') as f:
    projects = json.load(f)
for p in projects:
    assert os.path.exists(p['canonical_physical_path']), f'Missing folder: {p["canonical_physical_path"]}'
print('[+] Project directories verified.')
PY
echo "PARITY VERIFICATION: PASS"
