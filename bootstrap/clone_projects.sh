#!/usr/bin/env bash
# clone_projects.sh — Clones all core projects into their exact physical directories.
set -euo pipefail

mkdir -p "/home/azureuser/IroScript_Projects"
mkdir -p "/home/azureuser/IroScript_Projects/Article_Publishing_Management"
mkdir -p "/home/azureuser/IroScript_Projects/Personal Life/Digital History management"
mkdir -p "/home/azureuser/IroScript_Projects/Social Media/youtube"
mkdir -p "/home/azureuser/IroScript_Projects/Whatsapp_Agy_Agents"

declare -A repos=(
  ["/home/azureuser/IroScript_Projects/Whatsapp master"]="https://github.com/IroScript/Antigravity-Global-Notifier.git"
  ["/home/azureuser/IroScript_Projects/Social Media/youtube/Youtube Automation"]="git@github.com:IroScript/Youtube-Pipeline.git"
  ["/home/azureuser/IroScript_Projects/Social Media/telegram-bot"]="https://github.com/IroScript/telegram-scraper-and-automation.git"
  ["/home/azureuser/IroScript_Projects/Personal Life/PERSONAL AI AGENT"]="https://github.com/IroScript/personal_ai_agent.git"
  ["/home/azureuser/IroScript_Projects/Personal Life/kids_tube_with_folder_seection"]="git@github.com:IroScript/kids_tube_with_folder_seection.git"
  ["/home/azureuser/IroScript_Projects/Personal Life/Rust_Task_With_Time_Keeping_And_Live_Note"]="git@github.com:IroScript/Rust_Task_With_Time_Keeping_And_Live_Note.git"
  ["/home/azureuser/IroScript_Projects/Article_Publishing_Management/3D-Game-Design-Studio"]="git@github.com:IroScript/3d-web-templates.git"
  ["/home/azureuser/IroScript_Projects/Article_Publishing_Management/Article-Publishing-Platform"]="git@github.com:IroScript/Article-Publishing-Platform.git"
)

for target_dir in "${!repos[@]}"; do
  repo_url="${repos[$target_dir]}"
  if [ ! -d "$target_dir/.git" ]; then
    echo "[*] Cloning $repo_url into $target_dir ..."
    git clone "$repo_url" "$target_dir"
  else
    echo "[+] Already cloned: $target_dir"
  fi
done
