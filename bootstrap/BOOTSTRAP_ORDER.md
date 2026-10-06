# BOOTSTRAP ORDER & RECOVERY BLUEPRINT
**Deterministic Bootstrap Sequence for Blank VM Recovery**

When a new blank Debian/Ubuntu-compatible VM is provisioned, execute this exact linear sequence.

---

### Step 1: Clone Infrastructure Source of Truth
```bash
git clone git@github.com:IroScript/Infrastructure-Source-of-Truth.git /home/azureuser/IroScript_Projects/Infrastructure-Source-of-Truth
cd /home/azureuser/IroScript_Projects/Infrastructure-Source-of-Truth
```

### Step 2: Establish AGY Trust Baseline
```bash
./bootstrap/bootstrap_trust.sh
```
*Installs verification engine, delete guard hooks, completion gate hooks, rule files, and configurations into `/home/azureuser/.agents/` and `/home/azureuser/.gemini/`.*

### Step 3: Verify Trust Baseline Self-Test
```bash
./trust/verify_trust_baseline.sh
```
*Must output `AGY TRUST BASELINE: VERIFIED`. If any hash fails or file is missing, halt execution immediately.*

### Step 4: Install System Packages & Runtimes
```bash
./bootstrap/bootstrap_runtime.sh
```
*Installs apt packages, build-essential, tmux, git, curl, ffmpeg, uv, and Node.js.*

### Step 5: Clone All Project Code Repositories
```bash
./bootstrap/clone_projects.sh
```
*Clones all 8 core GitHub repositories to their exact canonical physical paths.*

### Step 6: Restore Persistent Data & Databases
Restore non-Git databases (OpenRecall `recall.db`, YouTube `youtube_pipeline.db`, Chrome history, MariaDB SQL dump) per `data/BACKUP_LOCATIONS.json`.

### Step 7: Re-Provision Secrets (.env files)
Populate environment variables matching `configuration/ENVIRONMENT_VARIABLE_NAMES.json` into respective project `.env` files.

### Step 8: Recreate Canonical Symlinks
```bash
./bootstrap/recreate_symlinks.sh
```
*Reconstructs all 8 operational symlinks across the workspace.*

### Step 9: Install Dependencies & Build
- WhatsApp Bridge: `cd /home/azureuser/.webterminal && npm install`
- Telegram Bot: `cd "/home/azureuser/IroScript_Projects/Social Media/telegram-bot" && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Frappe ERP Alco: Install bench via uv, restore MariaDB database.

### Step 10: Launch System & User Services
- `sudo systemctl daemon-reload && systemctl --user daemon-reload`
- `systemctl --user start frappe-mariadb.service`
- `systemctl --user start frappe-bench.service`
- `systemctl --user start ask-research-api.service`
- `sudo systemctl start agy-agents.service`
- `sudo systemctl start azure-file-explorer-tunnel.service`

### Step 11: Execute Final Parity Verification
```bash
./bootstrap/verify_environment.sh
```
*Validates that all symlinks and directories match expected state.*
