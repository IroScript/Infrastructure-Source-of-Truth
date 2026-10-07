"""Fail-closed file safety checks used before staging a managed project."""
from pathlib import Path
import os
import re
import subprocess
FORBIDDEN_NAMES = {'.env', '.env.prod', '.env.production', 'cookies.txt', 'cookies.sqlite', 'rclone.conf', 'id_rsa', 'id_ed25519', 'credentials.json', 'token.json'}
FORBIDDEN_SUFFIXES = {'.pem', '.p12', '.pfx', '.key', '.db', '.sqlite', '.sqlite3', '.rdb', '.sql', '.dump', '.bak', '.mp4', '.mov', '.mkv', '.avi', '.webm', '.mp3', '.wav', '.flac', '.apk'}
SKIP_SCAN_DIRS = {'.git', 'node_modules', '.venv', 'venv', 'target', 'build', 'dist', 'vendor', '.cache', '__pycache__'}
SENSITIVE_DIRS = {'wa_auth', '.ssh'}
MAX_BINARY_BYTES = 50 * 1024 * 1024
SECRET_PATTERNS = [re.compile(b'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'), re.compile(b'(?i)(?:api[_-]?key|password|secret|token)\\s*[:=]\\s*[\'\\"][^\'\\"\\s]{12,}'), re.compile(b'gh[pousr]_[A-Za-z0-9]{30,}')]
CLASSIFIER_LITERALS = {b'CLASS_D_SECRET', b'CLASS_A_GIT', b'CLASS_B_DATABASE', b'CLASS_C_LARGE_ASSET', b'CLASS_E_EPHEMERAL'}

def _has_secret_pattern(data: bytes) -> bool:
    for pattern in SECRET_PATTERNS:
        for m in pattern.finditer(data):
            matched = m.group(0)
            quote_split = re.split(b"['\"]", matched)
            if len(quote_split) >= 2:
                assigned_val = quote_split[-1].rstrip(b"'\";, \t\r\n")
                if assigned_val in CLASSIFIER_LITERALS:
                    open_quote_idx = len(matched) - len(assigned_val) - 1
                    if open_quote_idx >= 0:
                        open_quote = matched[open_quote_idx:open_quote_idx + 1]
                        if m.end() < len(data) and data[m.end():m.end() + 1] == open_quote:
                            continue
            return True
    return False

def unsafe_paths(root: str | Path):
    root = Path(root).resolve()
    bad = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        sensitive = [d for d in dirnames if d in SENSITIVE_DIRS]
        for dirname in sensitive:
            sensitive_path = current / dirname
            bad.append(str(sensitive_path.relative_to(root)))
            for child_dir, child_dirs, child_files in os.walk(sensitive_path):
                for child_dirname in child_dirs:
                    bad.append(str((Path(child_dir) / child_dirname).relative_to(root)))
                for child_file in child_files:
                    bad.append(str((Path(child_dir) / child_file).relative_to(root)))
        dirnames[:] = [d for d in dirnames if d not in SKIP_SCAN_DIRS | SENSITIVE_DIRS]
        for filename in filenames:
            path = current / filename
            rel = path.relative_to(root)
            name = path.name.lower()
            if name.startswith('.env') and name not in {'.env.example', '.env.template', '.env.sample'} or name in FORBIDDEN_NAMES or name.startswith('cookies') or name.endswith(('.sql.gz', '.dump.gz', '.bak.gz')) or (path.suffix.lower() in FORBIDDEN_SUFFIXES):
                bad.append(str(rel))
                continue
            try:
                size = path.stat().st_size
                if size > MAX_BINARY_BYTES:
                    bad.append(str(rel))
                    continue
                data = path.read_bytes()
                if b'\x00' in data and size > 1024 * 1024:
                    bad.append(str(rel))
                    continue
                if _has_secret_pattern(data):
                    bad.append(str(rel))
            except (OSError, UnicodeError):
                bad.append(str(rel))
    return sorted(set(bad))

def safe_stage(root: str | Path):
    root = str(Path(root).resolve())
    bad = unsafe_paths(root)
    if bad:
        raise ValueError('Fail-closed staging check: ' + ', '.join(bad[:20]))
    subprocess.run(['git', '-C', root, 'add', '--all'], check=True, timeout=15)