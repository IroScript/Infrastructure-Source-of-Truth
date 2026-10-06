# RESTORE AND VERIFY PLAYBOOK
**Forensic Verification Procedures & Parity Audit Matrix for Google VM**

This document specifies the exact post-migration validation commands and assertions to confirm 100% equivalence between the Azure source VM and the target Google VM.

---

## 1. Automated Parity Verification Matrix

| Component | Azure VM Source State | Target Google VM Assertion | Verification Command |
| :--- | :--- | :--- | :--- |
| **Project Directory Tree** | 11 canonical project folders | All 11 folders exist on disk | `python3 -c "import json, os; p=json.load(open('PROJECTS.json')); assert all(os.path.exists(x['canonical_physical_path']) for x in p)"` |
| **Git Repositories** | 11 Git roots verified | Git roots match toplevels | `git rev-parse --show-toplevel` in each folder |
| **Git Remotes** | Exact URLs in `GIT_REPOSITORIES.json` | Remotes match exactly | `git remote get-url origin` |
| **Symlink Health** | 8 active critical symlinks | All symlinks resolve without dangling | `python3 -c "import json, os; s=json.load(open('SYMLINKS.json')); assert all(os.path.exists(x['alias_path']) for x in s)"` |
| **MariaDB Daemon** | Port 3306 listening (user-space 11.8) | Port 3306 active and responsive | `ss -tulpn \| grep :3306` |
| **Frappe Web & SocketIO** | Port 8000 and 9000 listening | HTTP 200/302 on 8000, 9000 active | `curl -sI http://127.0.0.1:8000 \| head -n 1` |
| **Ask-Research API** | Port 8095 listening | REST endpoint responds | `curl -sI http://127.0.0.1:8095/health` |
| **Live Preview Server** | Port 8088 listening | HTTP 200 on 8088 | `curl -sI http://127.0.0.1:8088 \| head -n 1` |
| **Tmux Supervisor** | 14 active windows (`agy:0` to `agy:13`) | All 14 windows initialized | `tmux list-windows -t agy \| wc -l` (>= 14) |
| **Persistent Databases** | `recall.db` (>100MB), `youtube_pipeline.db` (>70MB) | File sizes > 0 and valid SQLite | `sqlite3 /path/to/db "PRAGMA integrity_check;"` |
| **Secrets & Keys** | All `.env` files populated | Zero placeholder tokens | Verify environment variable counts |

---

## 2. Per-Project Verification Playbook

### Project 1: WhatsApp Master (`whatsapp`)
```bash
test -d "/home/azureuser/IroScript_Projects/Whatsapp master/.git"
git -C "/home/azureuser/IroScript_Projects/Whatsapp master" remote get-url origin
# Output must be: https://github.com/IroScript/Antigravity-Global-Notifier.git
tmux has-session -t agy
tmux list-panes -t agy:1
```

### Project 2: YouTube Pipeline (`yt`)
```bash
test -d "/home/azureuser/IroScript_Projects/Social Media/youtube/Youtube Automation/.git"
git -C "/home/azureuser/IroScript_Projects/Social Media/youtube/Youtube Automation" remote get-url origin
# Output must be: git@github.com:IroScript/Youtube-Pipeline.git
sqlite3 "/home/azureuser/IroScript_Projects/Social Media/youtube/Youtube Automation/PromptDatabase/database/youtube_pipeline.db" "PRAGMA quick_check;"
```

### Project 3: Telegram Bot (`tg`)
```bash
test -d "/home/azureuser/IroScript_Projects/Social Media/telegram-bot/.git"
git -C "/home/azureuser/IroScript_Projects/Social Media/telegram-bot" remote get-url origin
# Output must be: https://github.com/IroScript/telegram-scraper-and-automation.git
test -f "/home/azureuser/IroScript_Projects/Social Media/telegram-bot/.env"
```

### Project 4: Personal AI Agent (`history`)
```bash
test -d "/home/azureuser/IroScript_Projects/Personal Life/PERSONAL AI AGENT/.git"
git -C "/home/azureuser/IroScript_Projects/Personal Life/PERSONAL AI AGENT" remote get-url origin
# Output must be: https://github.com/IroScript/personal_ai_agent.git
sqlite3 "/home/azureuser/IroScript_Projects/Personal Life/PERSONAL AI AGENT/data/openrecall/recall.db" "PRAGMA quick_check;"
```

### Project 5: Kids Tube (`kids`)
```bash
test -d "/home/azureuser/IroScript_Projects/Personal Life/kids_tube_with_folder_seection/.git"
git -C "/home/azureuser/IroScript_Projects/Personal Life/kids_tube_with_folder_seection" remote get-url origin
# Output must be: git@github.com:IroScript/kids_tube_with_folder_seection.git
```

### Project 6: Rust Task (`rust`)
```bash
test -d "/home/azureuser/IroScript_Projects/Personal Life/Rust_Task_With_Time_Keeping_And_Live_Note/.git"
git -C "/home/azureuser/IroScript_Projects/Personal Life/Rust_Task_With_Time_Keeping_And_Live_Note" remote get-url origin
# Output must be: git@github.com:IroScript/Rust_Task_With_Time_Keeping_And_Live_Note.git
```

### Project 7: 3D Game Design Studio (`game`)
```bash
test -d "/home/azureuser/IroScript_Projects/Article_Publishing_Management/3D-Game-Design-Studio/.git"
git -C "/home/azureuser/IroScript_Projects/Article_Publishing_Management/3D-Game-Design-Studio" remote get-url origin
# Output must be: git@github.com:IroScript/3d-web-templates.git
```

### Project 8: Article Publishing Platform (`article`)
```bash
test -d "/home/azureuser/IroScript_Projects/Article_Publishing_Management/Article-Publishing-Platform/.git"
git -C "/home/azureuser/IroScript_Projects/Article_Publishing_Management/Article-Publishing-Platform" remote get-url origin
# Output must be: git@github.com:IroScript/Article-Publishing-Platform.git
test -f "/home/azureuser/IroScript_Projects/Article_Publishing_Management/Article-Publishing-Platform/.env"
```

### Project 9: Frappe ERP Alco (`frappe`)
```bash
test -d "/home/azureuser/IroScript_Projects/Frappe-erp-Alco/frappe-bench/apps/alco_ecommerce/.git"
systemctl --user is-active frappe-mariadb.service
systemctl --user is-active frappe-bench.service
curl -sI http://127.0.0.1:8000 | head -n 1
```

### Project 10: Ask & Research Agent (`research`)
```bash
test -L "/home/azureuser/IroScript_Projects/Ask-And-Research-Agent"
readlink -f "/home/azureuser/IroScript_Projects/Ask-And-Research-Agent"
systemctl --user is-active ask-research-api.service
curl -s http://127.0.0.1:8095/health
```

### Project 11: OpenAI Codex (`codex`)
```bash
test -d "/home/azureuser/IroScript_Projects/OpenAI_Codex"
tmux capture-pane -p -t agy:13 | grep -E "Codex|OpenAI"
```
