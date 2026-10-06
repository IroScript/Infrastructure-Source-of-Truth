#!/usr/bin/env bash
# bootstrap_trust.sh — Installs and activates the AGY trust baseline on a fresh VM.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== BOOTSTRAPPING AGY TRUST BASELINE ==="

mkdir -p /home/azureuser/.agents/hooks
mkdir -p /home/azureuser/.agents/rules
mkdir -p /home/azureuser/.gemini/config

# 1. Install verification engine and hooks
cp -f "${REPO_ROOT}/trust/verification/verify_10_fold.py" /home/azureuser/.agents/verify_10_fold.py
chmod 0755 /home/azureuser/.agents/verify_10_fold.py

cp -f "${REPO_ROOT}/trust/verification/delete_guard.py" /home/azureuser/.agents/hooks/delete_guard.py
chmod 0755 /home/azureuser/.agents/hooks/delete_guard.py

cp -f "${REPO_ROOT}/trust/verification/completion_gate_stop_hook.py" /home/azureuser/.agents/hooks/completion_gate_stop_hook.py
chmod 0755 /home/azureuser/.agents/hooks/completion_gate_stop_hook.py

cp -f "${REPO_ROOT}/trust/verification/tool_audit_hook.py" /home/azureuser/.agents/hooks/tool_audit_hook.py
chmod 0755 /home/azureuser/.agents/hooks/tool_audit_hook.py

cp -f "${REPO_ROOT}/trust/verification/truth_pre_invocation.py" /home/azureuser/.agents/hooks/truth_pre_invocation.py
chmod 0755 /home/azureuser/.agents/hooks/truth_pre_invocation.py

# 2. Install rules
cp -f "${REPO_ROOT}"/trust/verification/rules/*.md /home/azureuser/.agents/rules/
chmod 0644 /home/azureuser/.agents/rules/*.md

# 3. Install configurations
cp -f "${REPO_ROOT}/configuration/hooks.json" /home/azureuser/.gemini/config/hooks.json
chmod 0644 /home/azureuser/.gemini/config/hooks.json

cp -f "${REPO_ROOT}/configuration/settings.json" /home/azureuser/.agents/settings.json
chmod 0644 /home/azureuser/.agents/settings.json

echo "[+] Trust baseline files installed successfully."
echo "[*] Executing verification self-test..."
"${REPO_ROOT}/trust/verify_trust_baseline.sh"
