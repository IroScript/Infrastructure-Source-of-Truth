#!/usr/bin/env bash
# clone_projects.sh — Clones all core projects into their exact physical directories.
set -euo pipefail

BASE_HOME="${HOME:-/home/azureuser}"
PROJECTS_ROOT="${PROJECTS_ROOT:-$BASE_HOME/IroScript_Projects}"

mkdir -p "$PROJECTS_ROOT"
mkdir -p "$PROJECTS_ROOT/Article_Publishing_Management"
mkdir -p "$PROJECTS_ROOT/Personal Life/Digital History management"
mkdir -p "$PROJECTS_ROOT/Social Media/youtube"
mkdir -p "$PROJECTS_ROOT/Whatsapp_Agy_Agents"

declare -A repos=(
  ["$PROJECTS_ROOT/Whatsapp master"]="https://github.com/IroScript/Antigravity-Global-Notifier.git"
  ["$PROJECTS_ROOT/Social Media/youtube/Youtube Automation"]="git@github.com:IroScript/Youtube-Pipeline.git"
  ["$PROJECTS_ROOT/Social Media/telegram-bot"]="https://github.com/IroScript/telegram-scraper-and-automation.git"
  ["$PROJECTS_ROOT/Personal Life/PERSONAL AI AGENT"]="https://github.com/IroScript/personal_ai_agent.git"
  ["$PROJECTS_ROOT/Personal Life/kids_tube_with_folder_seection"]="git@github.com:IroScript/kids_tube_with_folder_seection.git"
  ["$PROJECTS_ROOT/Personal Life/Rust_Task_With_Time_Keeping_And_Live_Note"]="git@github.com:IroScript/Rust_Task_With_Time_Keeping_And_Live_Note.git"
  ["$PROJECTS_ROOT/Article_Publishing_Management/3D-Game-Design-Studio"]="git@github.com:IroScript/3d-web-templates.git"
  ["$PROJECTS_ROOT/Article_Publishing_Management/Article-Publishing-Platform"]="git@github.com:IroScript/Article-Publishing-Platform.git"
)

export GIT_TERMINAL_PROMPT=0

for target_dir in "${!repos[@]}"; do
  repo_url="${repos[$target_dir]}"
  if [ ! -d "$target_dir/.git" ]; then
    echo "[*] Cloning $repo_url into $target_dir ..."
    git clone "$repo_url" "$target_dir"
  else
    echo "[+] Already cloned: $target_dir"
  fi
done
