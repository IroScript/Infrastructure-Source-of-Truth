# BOOTSTRAP CREDENTIALS SPECIFICATION
**Secure GitHub Authentication & Deploy Key Bootstrap Protocol for Blank VM**

This document specifies how a newly provisioned blank VM safely acquires GitHub authentication credentials to clone the private `Infrastructure-Source-of-Truth` repository **BEFORE** AGY or any autonomous software is permitted to operate.

> [!CAUTION]
> **ZERO-PLAINTEXT MANDATE:** No private keys, passwords, or personal access tokens (PAT) may ever be committed to any Git repository or stored in plaintext on disk.

---

## 1. The Bootstrap Authentication Problem

To clone a **PRIVATE** GitHub repository (`git@github.com:IroScript/Infrastructure-Source-of-Truth.git`), a blank VM requires an authenticated SSH key or a Personal Access Token (PAT).
However:
- The SSH private key cannot be placed inside the repository it is needed to clone.
- AGY cannot be trusted to self-install or generate keys without verification.

Therefore, GitHub authentication must be injected into the blank VM at **Tier 3 (Secure Secret Restoration)** during the initial OS provisioning step.

---

## 2. Supported Ingestion Mechanisms

### Method A: Cloud Provider Secret Manager / Instance Metadata (Recommended)
1. Store the deploy private key (`id_ed25519_deploy`) in Google Cloud Secret Manager or Azure Key Vault.
2. During VM provisioning (cloud-init or startup-script), fetch the deploy key:
   ```bash
   # Example GCP Secret Manager retrieval
   gcloud secrets versions access latest --secret="INFRA_DEPLOY_SSH_KEY" > /home/azureuser/.ssh/id_ed25519
   ```

### Method B: Manual Secure SCP / Interactive Injection
1. From the operator's local workstation:
   ```bash
   scp -i ~/.ssh/admin_key ~/.ssh/iroscript_github_deploy_key azureuser@<VM_IP>:~/.ssh/id_ed25519
   ```

---

## 3. Strict Filesystem Permissions & Known Hosts Validation

Upon placing the SSH key on the target VM, execute:

```bash
# 1. Ensure .ssh directory exists with strict permissions
mkdir -p /home/azureuser/.ssh
chmod 0700 /home/azureuser/.ssh
chown azureuser:azureuser /home/azureuser/.ssh

# 2. Enforce strict private key permissions (POSIX 0600)
chmod 0600 /home/azureuser/.ssh/id_ed25519
chown azureuser:azureuser /home/azureuser/.ssh/id_ed25519

# 3. Pre-seed GitHub known_hosts to prevent interactive MITM prompts
ssh-keyscan -t ed25519,rsa github.com >> /home/azureuser/.ssh/known_hosts
chmod 0644 /home/azureuser/.ssh/known_hosts
```

---

## 4. Authentication Pre-Flight Verification

Before invoking `git clone`, execute the non-interactive SSH authentication probe:

```bash
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=accept-new git@github.com 2>&1 || true
```

**Assertion:**
Output MUST contain:
`Hi IroScript! You've successfully authenticated, but GitHub does not provide shell access.`
Exit code will be `1` (standard for GitHub shell refusal), but standard error must verify successful publickey acceptance.

---

## 5. Private Repository Clone Test

Once authenticated, verify private repository reachability without pulling working trees:

```bash
git ls-remote git@github.com:IroScript/Infrastructure-Source-of-Truth.git HEAD
```

**Assertion:**
Must return exit code `0` and the remote commit SHA matching `CURRENT_BASELINE.json`.

---

## 6. Deterministic Bootstrap Chain

```
[Blank VM Provisioned]
         │
         ▼
[Step 1: Install base OS packages: git, curl, ssh, python3, tmux]
         │
         ▼
[Step 2: Inject GitHub SSH Deploy Key & set chmod 0600]
         │
         ▼
[Step 3: Validate GitHub SSH Authentication (ssh -T git@github.com)]
         │
         ▼
[Step 4: Clone Infrastructure-Source-of-Truth repository]
         │
         ▼
[Step 5: Execute ./bootstrap/bootstrap_trust.sh]
         │
         ▼
[Step 6: Execute ./trust/verify_trust_baseline.sh]
         │
    ┌────┴───────────────────────────┐
    ▼                                ▼
[Baseline: VERIFIED]         [Baseline: FAIL]
    │                                │
    ▼                                ▼
[AGY Authorized to Operate]   [HALT & ALARM]
```
