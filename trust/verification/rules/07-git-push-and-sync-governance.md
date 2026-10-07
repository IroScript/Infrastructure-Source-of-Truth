# GIT PUSH, REMOTE REPOSITORY SYNC & COMMIT HISTORY GOVERNANCE

This document establishes the mandatory operational rules for remote Git synchronization, commit messaging standards, branch targeting, repository pre-validation, ambiguity prevention, tree integrity verification, and immutable commit history preservation across all managed environments under the zero-interaction autonomous architecture.

---

### SECTION 1: AUTOMATIC UNATTENDED GIT PUSH & COMMIT MESSAGE SPECIFICATION
1. **Mandatory Automated Remote Push**:
   Following any code creation, modification, or configuration edit in tracked repositories, the GitPush Watcher subsystem continuously stabilizes snapshots, commits, and pushes changes to the remote Git repository without requiring user interaction.
2. **Strict Binary Commit Message Prefixes**:
   - If change directly originates from an explicit user task:
     `User Requested : <concise actual change summary>`
   - If change is autonomous, inferred, maintenance-generated, watcher-generated, architecture-generated, or origin cannot be proven:
     `Unverified : <concise actual change summary>`
   - Ambiguity strictly defaults to `Unverified : `. Never falsely classify autonomous work as User Requested.
   - Previous commit messages must not be rewritten after verification; verification evidence resides in the task ledger.

---

### SECTION 2: REPOSITORY PRE-VALIDATION & MULTI-REPO DISAMBIGUATION
3. **Repository Pre-Inspection**:
   Prior to staging and pushing, verify:
   - Physical existence of a valid `.git` directory in the target project root (`git rev-parse --is-inside-work-tree`).
   - Configured and reachable remote URL (`git remote -v`).
4. **Deterministic Registry-Driven Disambiguation**:
   Because multiple projects may be interlinked or nested across workspaces:
   - SOT `PROJECT_REGISTRY.json` binds the immutable `project_uuid` to its canonical path and Git remote.
   - If a repository remote is missing and cannot be created automatically, mark state as `ONBOARDING_INCOMPLETE` and continue local protection without blocking the agent. Zero user prompt or interactive wait is permitted.
5. **Standard `main` Branch Target**:
   All pushes must target the registered default branch (typically **`main`**).

---

### SECTION 3: POST-PUSH SHA ALIGNMENT & TRACKED TREE INTEGRITY
6. **Two-Point SHA Alignment Verification**:
   Immediately after every push execution, verify SHA alignment:
   - Local HEAD SHA: `git rev-parse HEAD`
   - Remote Branch SHA: `git ls-remote origin <branch>`
7. **Strict SHA Equality Assertion**:
   Remote GitHub SHA must strictly equal local HEAD SHA (`remote_SHA == local_SHA`). Discrepancies persist as `PUSH_PENDING` with automated backoff retry.
8. **Push Failure Resilience**:
   Push failure must never cause local changes to disappear. Never force-push or reset working tree.

---

### SECTION 4: COMMIT HISTORY IMMUTABILITY & VERIFICATION EVIDENCE
9. **Zero History Rewrite / Force-Push Ban**:
   Autonomous processes are strictly prohibited from:
   - Force-pushing (`git push --force`, `git push -f`, `git push --force-with-lease`).
   - History rewriting (`git commit --amend` on pushed commits, `git rebase -i`, `git filter-branch`).
   - Destructive branch reset (`git reset --hard`).
   - Commit or history deletion (`git push origin --delete`).
10. **Mandatory Empirical Evidence & Disclosure**:
    If any verification vector or remote parity check cannot be fully completed, the exact failure status and raw command output must be recorded in machine-readable task records without sanitization or concealment.
