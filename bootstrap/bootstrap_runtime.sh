#!/usr/bin/env bash
# bootstrap_runtime.sh — Installs necessary toolchains and system runtimes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== INSTALLING SYSTEM PACKAGES & RUNTIMES ==="
sudo apt update
sudo apt install -y tmux git curl wget build-essential jq sqlite3 ffmpeg libmariadb-dev redis-tools

# Install UV
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Install Node LTS if not installed
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi

# Deploy systemd user services
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"
if [ -f "$REPO_ROOT/gitpush_watcher/gitpush-watcher.service" ]; then
    cp "$REPO_ROOT/gitpush_watcher/gitpush-watcher.service" "$SYSTEMD_USER_DIR/gitpush-watcher.service"
fi

echo "[+] Base runtimes installed."
