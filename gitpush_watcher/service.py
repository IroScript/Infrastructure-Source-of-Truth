"""Systemd Service management for GitPush Watcher (RULE 28)."""
from __future__ import annotations

import os
from pathlib import Path


SERVICE_TEMPLATE = """[Unit]
Description=Infrastructure Source of Truth GitPush Watcher Daemon
After=network.target

[Service]
Type=simple
WorkingDirectory={sot_root}
ExecStart={python_bin} {sot_root}/sot watcher run-daemon
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""


def generate_service_unit(sot_root: Path, python_bin: str = "/usr/bin/python3") -> str:
    """Generates a systemd unit content bound to the exact SOT root."""
    return SERVICE_TEMPLATE.format(
        sot_root=str(sot_root.resolve()),
        python_bin=python_bin
    )


def write_service_template(sot_root: Path, target_path: Path | None = None) -> Path:
    """Writes the systemd service template to gitpush_watcher/gitpush-watcher.service."""
    dest = target_path or (sot_root / "gitpush_watcher" / "gitpush-watcher.service")
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = generate_service_unit(sot_root)
    dest.write_text(content, encoding="utf-8")
    return dest
