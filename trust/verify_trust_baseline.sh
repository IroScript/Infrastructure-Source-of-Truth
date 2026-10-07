#!/usr/bin/env bash
set -euo pipefail
SOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
HOME_DIR="${HOME:?HOME must be set}"
python3 - "$SOT_ROOT" "$HOME_DIR" <<'PY'
import hashlib, json, stat, sys
from pathlib import Path
sot, home = Path(sys.argv[1]), Path(sys.argv[2])
manifest = json.loads((sot/'trust/TRUST_BASELINE.json').read_text())
errors=[]; count=0
for item in manifest.get('artifacts', []):
    source=sot/item['source']; target=home/item['destination']
    count += 1
    if not source.is_file() or not target.is_file() or target.is_symlink():
        if item.get('required', True): errors.append(f"{item['destination']}: missing or symlink")
        continue
    source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    target_sha=hashlib.sha256(target.read_bytes()).hexdigest()
    if source_sha != item['sha256'] or target_sha != item['sha256']:
        errors.append(f"{item['destination']}: SHA256 mismatch")
    if stat.S_IMODE(target.stat().st_mode) != int(item['mode'], 8):
        errors.append(f"{item['destination']}: permission mismatch")
cfg=home/'.gemini/config/hooks.json'
try:
    hooks=json.loads(cfg.read_text())
except Exception:
    hooks={}
if 'completion_gate_stop_hook.py' not in json.dumps(hooks):
    errors.append('completion gate is not activated in hook config')
root_file=home/'.agents/sot_root'
if not root_file.is_file() or root_file.read_text().strip() != str(sot):
    errors.append('SOT root binding missing or incorrect')
print(f'FILES CHECKED: {count}')
if errors:
    print('\n'.join('FAIL '+error for error in errors)); raise SystemExit(1)
print('TRUST BASELINE: PASS')
PY
SOT_PROFILE="${SOT_PROFILE:-portable-linux}"
"$SOT_ROOT/sot" artifacts verify --profile "$SOT_PROFILE" --home "$HOME_DIR"
