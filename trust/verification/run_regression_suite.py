"""SOT-owned deterministic regression entry point."""
import subprocess
import sys
from pathlib import Path
SOT = Path(__file__).resolve().parents[2]
checks = [[sys.executable, '-m', 'unittest', 'discover', '-s', str(SOT / 'verification/tests'), '-v']]
for command in checks:
    result = subprocess.run(command, cwd=SOT, timeout=15)
    if result.returncode:
        raise SystemExit(result.returncode)
print('DETERMINISTIC REGRESSION: PASS')