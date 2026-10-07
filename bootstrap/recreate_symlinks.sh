#!/usr/bin/env bash
# recreate_symlinks.sh — Reconstructs all canonical symlinks per SYMLINKS.json.
set -euo pipefail

BASE_HOME="${HOME:-/home/azureuser}"
PROJECTS_ROOT="${PROJECTS_ROOT:-$BASE_HOME/IroScript_Projects}"

echo "=== RECREATING CANONICAL SYMLINKS ==="
ln -sfn "$PROJECTS_ROOT/Whatsapp master/webterminal/gitpush_folder_mapping.json" "$PROJECTS_ROOT/gitpush_folder_mapping.json"
ln -sfn "$PROJECTS_ROOT/Whatsapp master/webterminal" "$BASE_HOME/.webterminal"
ln -sfn "$PROJECTS_ROOT/Frappe-erp-Alco" "$BASE_HOME/Frappe-erp-Alco"
ln -sfn "$PROJECTS_ROOT/Whatsapp master/webterminal/Agy Whatsapp Agents/Ask-And-Research" "$PROJECTS_ROOT/Ask-And-Research-Agent"
ln -sfn "Personal Life/Digital History management" "$PROJECTS_ROOT/Digital History"
ln -sfn "../PERSONAL AI AGENT" "$PROJECTS_ROOT/Personal Life/Digital History management/PERSONAL AI AGENT"
ln -sfn "$PROJECTS_ROOT/Whatsapp master" "$PROJECTS_ROOT/Whatsapp_Agy_Agents/Antigravity-Global-Notifier"
ln -sfn "$PROJECTS_ROOT/Whatsapp master/Antigravity-CLI-Trustworthy-Protocol/governance/AGENTS.md" "$BASE_HOME/GEMINI.md"
echo "[+] All canonical symlinks created."
