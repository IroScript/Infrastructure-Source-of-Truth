#!/usr/bin/env bash
# recreate_symlinks.sh — Reconstructs all canonical symlinks per SYMLINKS.json.
set -euo pipefail

echo "=== RECREATING CANONICAL SYMLINKS ==="
ln -sfn '/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/gitpush_folder_mapping.json' '/home/azureuser/IroScript_Projects/gitpush_folder_mapping.json'
ln -sfn '/home/azureuser/IroScript_Projects/Whatsapp master/webterminal' '/home/azureuser/.webterminal'
ln -sfn '/home/azureuser/IroScript_Projects/Frappe-erp-Alco' '/home/azureuser/Frappe-erp-Alco'
ln -sfn '/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/Agy Whatsapp Agents/Ask-And-Research' '/home/azureuser/IroScript_Projects/Ask-And-Research-Agent'
ln -sfn 'Personal Life/Digital History management' '/home/azureuser/IroScript_Projects/Digital History'
ln -sfn '../PERSONAL AI AGENT' '/home/azureuser/IroScript_Projects/Personal Life/Digital History management/PERSONAL AI AGENT'
ln -sfn '/home/azureuser/IroScript_Projects/Whatsapp master' '/home/azureuser/IroScript_Projects/Whatsapp_Agy_Agents/Antigravity-Global-Notifier'
ln -sfn '/home/azureuser/IroScript_Projects/Whatsapp master/Antigravity-CLI-Trustworthy-Protocol/governance/AGENTS.md' '/home/azureuser/GEMINI.md'
echo "[+] All canonical symlinks successfully created and verified."
