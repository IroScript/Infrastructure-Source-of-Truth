# MIGRATION ORDER
**Dependency-Aware 14-Step Sequence for Azure VM -> Google VM Migration**

This execution order guarantees that lower-level primitives (toolchains, users, system libraries) exist before application repositories and daemons are brought online.

---

### Step 1: Base Operating System & Users
1. Provision Google Cloud VM with **Debian 13 (trixie)** x86_64.
2. Create default user `azureuser` (matching UID/GID 1000:1000) with sudo privileges.
3. Configure SSH access with user keys.

### Step 2: System Packages & Toolchains
1. Update apt repositories: `sudo apt update && sudo apt upgrade -y`.
2. Install base utilities: `sudo apt install -y tmux git curl wget build-essential jq sqlite3 ffmpeg libmariadb-dev redis-tools`.
3. Restore package selection list using `SYSTEM_PACKAGES.txt` (`sudo dpkg --set-selections < SYSTEM_PACKAGES.txt && sudo apt-get dselect-upgrade -y`).
4. Install Node.js v20 LTS via official NodeSource or apt (`/usr/bin/node`, `npm`).
5. Install NVM (Node Version Manager) and install Node `v24.21.0` (required by Frappe socketio).
6. Install UV (Python package & environment manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`.
7. Install Cloudflared: download official Debian deb package and install.
8. Install Antigravity CLI (`agy`) into `~/.local/bin/agy`.
9. Install OpenAI Codex CLI (`codex`) via npm global install.

### Step 3: Base Directory Hierarchy Creation
Create core filesystem structure:
```bash
mkdir -p /home/azureuser/IroScript_Projects
mkdir -p "/home/azureuser/IroScript_Projects/Article_Publishing_Management"
mkdir -p "/home/azureuser/IroScript_Projects/Personal Life/Digital History management"
mkdir -p "/home/azureuser/IroScript_Projects/Social Media/youtube"
mkdir -p "/home/azureuser/IroScript_Projects/Whatsapp_Agy_Agents"
mkdir -p "/home/azureuser/.config/systemd/user"
```

### Step 4: Clone Git Repositories (Code Restoration)
Clone all GitHub-backed projects to their canonical physical paths:
```bash
# 1. WhatsApp Master
git clone https://github.com/IroScript/Antigravity-Global-Notifier.git "/home/azureuser/IroScript_Projects/Whatsapp master"

# 2. YouTube Pipeline
git clone git@github.com:IroScript/Youtube-Pipeline.git "/home/azureuser/IroScript_Projects/Social Media/youtube/Youtube Automation"

# 3. Telegram Bot
git clone https://github.com/IroScript/telegram-scraper-and-automation.git "/home/azureuser/IroScript_Projects/Social Media/telegram-bot"

# 4. Personal AI Agent
git clone https://github.com/IroScript/personal_ai_agent.git "/home/azureuser/IroScript_Projects/Personal Life/PERSONAL AI AGENT"

# 5. Kids Tube
git clone git@github.com:IroScript/kids_tube_with_folder_seection.git "/home/azureuser/IroScript_Projects/Personal Life/kids_tube_with_folder_seection"

# 6. Rust Task
git clone git@github.com:IroScript/Rust_Task_With_Time_Keeping_And_Live_Note.git "/home/azureuser/IroScript_Projects/Personal Life/Rust_Task_With_Time_Keeping_And_Live_Note"

# 7. 3D Game Design Studio
git clone git@github.com:IroScript/3d-web-templates.git "/home/azureuser/IroScript_Projects/Article_Publishing_Management/3D-Game-Design-Studio"

# 8. Article Publishing Platform
git clone git@github.com:IroScript/Article-Publishing-Platform.git "/home/azureuser/IroScript_Projects/Article_Publishing_Management/Article-Publishing-Platform"
```

### Step 5: Restore Critical Non-Git Persistent Data (Category A)
Transfer and place critical databases from Azure VM to Google VM:
1. `Personal Life/PERSONAL AI AGENT/data/openrecall/recall.db`
2. `Personal Life/PERSONAL AI AGENT/data/chrome/chrome_history_master.db`
3. `Personal Life/openrecall_vault/vault_index.db`
4. `Social Media/youtube/Youtube Automation/PromptDatabase/database/youtube_pipeline.db`
5. `Whatsapp master/webterminal/Agy Whatsapp Agents/Ask-And-Research/ask_and_research.db`
6. `Whatsapp master/webterminal/baileys_auth_info/` (WhatsApp credentials)
7. `OpenAI_Codex/` directory files

### Step 6: Symlink Network Recreation
Execute symlink recreation commands as documented in `SYMLINKS.json`:
```bash
ln -sfn '/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/gitpush_folder_mapping.json' '/home/azureuser/IroScript_Projects/gitpush_folder_mapping.json'
ln -sfn '/home/azureuser/IroScript_Projects/Whatsapp master/webterminal' '/home/azureuser/.webterminal'
ln -sfn '/home/azureuser/IroScript_Projects/Frappe-erp-Alco' '/home/azureuser/Frappe-erp-Alco'
ln -sfn '/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/Agy Whatsapp Agents/Ask-And-Research' '/home/azureuser/IroScript_Projects/Ask-And-Research-Agent'
ln -sfn 'Personal Life/Digital History management' '/home/azureuser/IroScript_Projects/Digital History'
ln -sfn '../PERSONAL AI AGENT' '/home/azureuser/IroScript_Projects/Personal Life/Digital History management/PERSONAL AI AGENT'
ln -sfn '/home/azureuser/IroScript_Projects/Whatsapp master' '/home/azureuser/IroScript_Projects/Whatsapp_Agy_Agents/Antigravity-Global-Notifier'
ln -sfn '/home/azureuser/AGENTS.md' '/home/azureuser/GEMINI.md'
```

### Step 7: Secrets & Environment Variable Re-Provisioning
Restore `.env` configuration files matching `ENVIRONMENT_VARIABLE_NAMES.json`:
- `Article-Publishing-Platform/.env`
- `Social Media/telegram-bot/.env`
- `Social Media/telegram-bot/master_api_vault.env`
- `Rust_Task_With_Time_Keeping_And_Live_Note/backend/.env`

### Step 8: Dependencies & Runtime Environments Build
1. **WhatsApp Webterminal:** `cd /home/azureuser/.webterminal && npm install`
2. **Telegram Bot:** `cd "/home/azureuser/IroScript_Projects/Social Media/telegram-bot" && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. **Frappe ERP Alco:** Reinstall bench via `uv tool install frappe-bench` using Python 3.14. Restore portable MariaDB binary and database dump.
4. **Article Publishing Platform:** `cd "/home/azureuser/IroScript_Projects/Article_Publishing_Management/Article-Publishing-Platform" && npm install`

### Step 9: Systemd Service Installation
Copy unit files from `CONFIG_FILES.json`:
```bash
sudo cp /etc/systemd/system/agy-agents.service /etc/systemd/system/
sudo cp /etc/systemd/system/azure-file-explorer-tunnel.service /etc/systemd/system/
cp ~/.config/systemd/user/*.service ~/.config/systemd/user/

sudo systemctl daemon-reload
systemctl --user daemon-reload
```

### Step 10: Launch Database Daemons
1. Start Frappe MariaDB: `systemctl --user start frappe-mariadb.service`
2. Verify port 3306 listening: `ss -tulpn | grep :3306`

### Step 11: Launch Application Services & Tunnels
1. Start Ask-Research API: `systemctl --user start ask-research-api.service`
2. Start Frappe Bench: `systemctl --user start frappe-bench.service`
3. Start Cloudflare Tunnel: `sudo systemctl start azure-file-explorer-tunnel.service`

### Step 12: Launch Tmux WhatsApp Multi-Agent Supervisor
1. Start supervisor: `sudo systemctl start agy-agents.service`
2. Inspect tmux sessions: `tmux list-windows -t agy`

### Step 13: Port & Network Verification
Run `ss -tulpn` and verify all target ports:
- `8000` (Frappe ERP)
- `9000` (Frappe SocketIO)
- `8088` (Live Preview)
- `8095` (Ask-Research API)
- `3306` (MariaDB)
- `11000` / `13000` (Redis)

### Step 14: Automated Forensic Parity Audit
Execute verification tests detailed in `RESTORE_AND_VERIFY.md`.
