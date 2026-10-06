#!/usr/bin/env bash
# verify_trust_baseline.sh — Validates AGY trust baseline against disk files.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASELINE_FILE="${SCRIPT_DIR}/TRUST_BASELINE.json"

echo "=== AGY TRUST BASELINE AUDIT ==="
if [ ! -f "$BASELINE_FILE" ]; then
    echo "[-] ERROR: Baseline file $BASELINE_FILE does not exist!"
    echo "AGY TRUST BASELINE: FAIL"
    exit 1
fi

python3 -c "
import json, sys, os, hashlib

with open('$BASELINE_FILE') as f:
    items = json.load(f)

failures = 0
total = len(items)

for item in items:
    f_name = item['file']
    dest = item['destination']
    exp_sha = item['sha256']
    req = item['required']

    if not os.path.exists(dest):
        if req:
            print(f'[-] CRITICAL MISSING: {dest}')
            failures += 1
        else:
            print(f'[*] OPTIONAL MISSING: {dest}')
        continue

    actual_sha = hashlib.sha256(open(dest, 'rb').read()).hexdigest()
    if actual_sha != exp_sha:
        print(f'[-] HASH MISMATCH on {dest}:')
        print(f'    Expected: {exp_sha}')
        print(f'    Actual:   {actual_sha}')
        failures += 1
    else:
        print(f'[+] VERIFIED: {f_name} (SHA256 OK)')

print('----------------------------------------')
print(f'Total Files Evaluated: {total}')
print(f'Total Policy Failures: {failures}')
print('----------------------------------------')

if failures > 0:
    print('AGY TRUST BASELINE: FAIL')
    sys.exit(1)
else:
    print('AGY TRUST BASELINE: VERIFIED')
    sys.exit(0)
"
