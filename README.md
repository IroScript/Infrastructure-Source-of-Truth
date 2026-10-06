# Infrastructure-Source-of-Truth
**Authoritative Infrastructure, AGY Trust Enforcement & System Reproducibility Repository**

- **Authoritative Remote:** `git@github.com:IroScript/Infrastructure-Source-of-Truth.git`
- **Source System:** Azure VM (`Debian GNU/Linux 13 (trixie)`)
- **Target System:** Google Cloud VM (`Debian 13` or compatible Linux)
- **Snapshot Date:** 2026-10-06T16:24:07.914362+00:00

---

## 1. Source of Truth Hierarchy

This architecture separates state into three orthogonal tiers to guarantee that VMs remain completely expendable:

### Tier 1 — GitHub (This Repository)
**Authoritative for:**
- All application source code repositories
- AGY Trust Policy, enforcement hooks, rules, and verifiers
- Infrastructure manifests (services, ports, tmux windows, system packages)
- Project directory mappings and symlink networks
- Bootstrap scripts and restoration playbooks

### Tier 2 — Persistent Data Backup (Google Drive via rclone)
**Authoritative for:**
- SQLite databases (OpenRecall `recall.db`, YouTube `youtube_pipeline.db`, Chrome history, Ask-Research DB)
- MariaDB production data dumps (`alco_mariadb_backup.sql`)
- WhatsApp Baileys multi-device pairing session tokens (`baileys_auth_info/`)
- User-generated assets, video renders, and media

### Tier 3 — Secret Restoration (Secure Re-Provisioning)
**Authoritative for:**
- API tokens, passwords, private SSH keys, OAuth client secrets
- Re-provisioned via secure vault or environment injection into `.env` files (never stored in GitHub plaintext)

---

## 2. Blank-VM Recovery Sequence (One-Command Bootstrap)

On any fresh Debian/Ubuntu-compatible VM:

```bash
# Step 1: Clone the Source of Truth
git clone git@github.com:IroScript/Infrastructure-Source-of-Truth.git
cd Infrastructure-Source-of-Truth

# Step 2: Establish and enforce the AGY Trust Baseline
./bootstrap/bootstrap_trust.sh

# Step 3: Self-verify the trust environment (Must output 'AGY TRUST BASELINE: VERIFIED')
./trust/verify_trust_baseline.sh

# Step 4: Install runtime toolchains
./bootstrap/bootstrap_runtime.sh

# Step 5: Clone all projects to canonical physical paths
./bootstrap/clone_projects.sh

# Step 6: Recreate symlink network
./bootstrap/recreate_symlinks.sh

# Step 7: Verify environment parity
./bootstrap/verify_environment.sh
```

---

## 3. Directory Layout

```
Infrastructure-Source-of-Truth/
├── README.md                           # Master architecture & bootstrap guide
├── CURRENT_BASELINE.json               # Point-in-time system state snapshot
├── trust/                              # First-class AGY trustworthiness specifications
│   ├── AGY_TRUST_POLICY.md             # 8 cardinal trust rules
│   ├── TRUST_BASELINE.json             # Exact SHA-256 integrity manifest
│   ├── TOOL_GUARDRAILS.json            # Prohibited commands & PreToolUse guards
│   ├── VERIFICATION_POLICY.md          # 10-vector verification mandate
│   ├── FAIL_CLOSED_POLICY.md           # Fail-closed specification
│   ├── verify_trust_baseline.sh        # Machine self-audit script
│   └── verification/                   # Packaged verifiers and hooks
├── projects/                           # Canonical project and repository registries
│   ├── PROJECTS.json                   # 11 project specifications
│   ├── GIT_REPOSITORIES.json           # Git roots, remotes, branches, and SHAs
│   ├── gitpush_folder_mapping.json     # Sanitized authoritative mapping
│   └── detect_mapping_drift.py         # Mapping drift validation script
├── infrastructure/                     # System runtime, service, and port manifests
├── configuration/                      # Sanitized configs and restore map
├── data/                               # Persistent and temporary data classifications
├── bootstrap/                          # Automated bootstrap scripts
├── restore/                            # Migration order, verification tests, checklist
└── checksums/                          # Cryptographic SHA-256 verification tree
```
