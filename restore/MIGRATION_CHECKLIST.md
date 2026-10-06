# MIGRATION CHECKLIST
**Execution Day Runbook for Target Google VM**

### Phase 1: Pre-Migration Prep (On Azure VM)
- [ ] Export MariaDB database dump: `mysqldump --defaults-file=/home/azureuser/IroScript_Projects/Frappe-erp-Alco/runtime/mariadb-conf/my.cnf alco > /home/azureuser/IroScript_Projects/alco_mariadb_backup.sql`
- [ ] Archive critical databases: `tar -czvf /home/azureuser/IroScript_Projects/databases_critical.tar.gz` (OpenRecall, YouTube Pipeline, Chrome history, Ask-Research)
- [ ] Archive WhatsApp session credentials: `tar -czvf /home/azureuser/IroScript_Projects/baileys_auth.tar.gz "/home/azureuser/IroScript_Projects/Whatsapp master/webterminal/baileys_auth_info"`
- [ ] Collect all `.env` files into an encrypted vault bundle
- [ ] Copy `MIGRATION_CONTROL_CENTER` directory to secure backup store

### Phase 2: Google VM Provisioning & Setup
- [ ] Launch Google Cloud VM with Debian 13 (trixie) x86_64
- [ ] Create user `azureuser` and set up SSH authorized_keys
- [ ] Install base packages from `SYSTEM_PACKAGES.txt`
- [ ] Install Node.js v20 LTS and NVM (Node v24.21.0)
- [ ] Install UV and Python 3.14
- [ ] Install Cloudflared deb package
- [ ] Install Antigravity CLI and Codex CLI

### Phase 3: Filesystem & Git Repositories
- [ ] Create directory structure per `MIGRATION_ORDER.md`
- [ ] Clone all 8 core GitHub repositories to exact canonical paths
- [ ] Extract `databases_critical.tar.gz` into respective project folders
- [ ] Extract `baileys_auth.tar.gz` into `Whatsapp master/webterminal/baileys_auth_info`
- [ ] Recreate all 8 critical symlinks using commands from `SYMLINKS.json`

### Phase 4: Configurations & Secrets
- [ ] Decrypt and place `.env` files per `ENVIRONMENT_VARIABLE_NAMES.json`
- [ ] Copy systemd unit files to `/etc/systemd/system/` and `~/.config/systemd/user/`
- [ ] Run `sudo systemctl daemon-reload` and `systemctl --user daemon-reload`

### Phase 5: Runtimes & Dependencies
- [ ] Rebuild virtualenv in `Social Media/telegram-bot`
- [ ] Run `npm install` in `Whatsapp master/webterminal`
- [ ] Run `npm install` in `Article-Publishing-Platform`
- [ ] Run `cargo build` in `Rust_Task_With_Time_Keeping_And_Live_Note`
- [ ] Set up user-space MariaDB 11.8 and import `alco_mariadb_backup.sql`

### Phase 6: Service Activation & Daemons
- [ ] Start user services: `frappe-mariadb.service`, `frappe-bench.service`, `ask-research-api.service`
- [ ] Start system services: `agy-agents.service`, `azure-file-explorer-tunnel.service`
- [ ] Enable all services on boot

### Phase 7: Post-Migration Forensic Verification
- [ ] Execute `RESTORE_AND_VERIFY.md` automated assertions
- [ ] Check ports: 8000, 9000, 8088, 8095, 3306, 11000, 13000
- [ ] Verify tmux windows: `agy:0` through `agy:13` active
- [ ] Verify WhatsApp connectivity: check WhatsApp group notification
- [ ] Confirm Cloudflare Live Preview reachable from browser
