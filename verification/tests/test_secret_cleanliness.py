"""Verification of zero secrets in tracked git repository files."""
import re
import subprocess
from pathlib import Path

REAL_SECRET_PATTERNS = [
    re.compile(b"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"),
    re.compile(b'"type"\\s*:\\s*"service_account"'),
    re.compile(b'"client_secret"\\s*:\\s*"[^"]{16,}"'),
    re.compile(b"AKIA[0-9A-Z]{16}"),
    re.compile(b"gh[pousr]_[A-Za-z0-9]{36}"),
]

SKIP_PARTS = {"node_modules", ".git", ".venv", "vendor", "__pycache__", "archive", ".gemini"}

def test_no_tracked_secrets_in_sot():
    sot_root = Path(__file__).resolve().parent.parent.parent
    files = subprocess.check_output(["git", "-C", str(sot_root), "ls-files"], text=True).splitlines()
    for f in files:
        if f.endswith("precommit_safety.py") or f.endswith("test_universal_architecture.py") or f.endswith("test_secret_cleanliness.py"):
            continue
        if any(part in f.split("/") for part in SKIP_PARTS):
            continue
        p = sot_root / f
        if p.is_file():
            data = p.read_bytes()
            for pat in REAL_SECRET_PATTERNS:
                assert not pat.search(data), f"Secret detected in SOT tracked file: {f} matching {pat.pattern}"

def test_no_tracked_secrets_in_whatsapp_master():
    wm_root = Path("/home/azureuser/IroScript_Projects/Whatsapp master")
    if not wm_root.is_dir():
        return
    files = subprocess.check_output(["git", "-C", str(wm_root), "ls-files"], text=True).splitlines()
    for f in files:
        if any(part in f.split("/") for part in SKIP_PARTS):
            continue
        p = wm_root / f
        if p.is_file():
            data = p.read_bytes()
            for pat in REAL_SECRET_PATTERNS:
                assert not pat.search(data), f"Secret detected in WhatsApp Master tracked file: {f} matching {pat.pattern}"
