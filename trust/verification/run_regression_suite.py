"""SOT-owned deterministic regression entry point."""
import subprocess
import sys
from pathlib import Path

def _find_sot():
    p2 = Path(__file__).resolve().parents[2]
    if (p2 / 'verification/tests').is_dir():
        return p2
    sot_file = Path(__file__).resolve().parent / 'sot_root'
    if sot_file.is_file():
        p = Path(sot_file.read_text().strip())
        if (p / 'verification/tests').is_dir():
            return p
    def_p = Path.home() / 'IroScript_Projects' / 'Infrastructure-Source-of-Truth'
    if (def_p / 'verification/tests').is_dir():
        return def_p
    return p2

SOT = _find_sot()
checks = [[sys.executable, '-m', 'unittest', 'discover', '-s', str(SOT / 'verification/tests'), '-v']]
for command in checks:
    result = subprocess.run(command, cwd=SOT, timeout=120)
    if result.returncode:
        raise SystemExit(result.returncode)
print('DETERMINISTIC REGRESSION: PASS')
