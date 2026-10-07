# Universal Agent Operating Standard

Version: 1.0.0. Normative terms **MUST**, **MUST NOT**, **SHOULD**, and **MAY** express mandatory, prohibited, recommended, and optional behavior.

## 1. Authority and roles

GitHub is authoritative for recoverable source, policy, rules, schemas, project identity, bootstrap logic, and configuration templates. A VM, agent memory, generated report, or chat statement MUST NOT override the GitHub commit. A dirty or unpushed SOT checkout is not current.

The task issuer assigns a role: `builder`, `deterministic_verifier`, `independent_verifier`, or `operator`. Vendor and model names do not grant authority. A builder changes code and records evidence but MUST NOT independently accept its own high or critical change. Deterministic checks are mandatory and MUST work without any AI provider. Independent verifiers are replaceable adapters that inspect evidence and challenge test logic. Operators perform only explicitly authorized operational actions.

If an agent receives only the repository URL and no task or role, it MUST read `AGENT_ENTRYPOINT.md`, discover capabilities, and ask the task issuer for the missing objective before making changes.

## 2. Canonical ownership

Each fact MUST have one manually maintained canonical owner:

- Project identity, remote, lifecycle and logical connections: `projects/PROJECT_REGISTRY.json`.
- Rule package behavior and version: `governance/rules/<rule_id>/<version>/rule.json` plus declared artifacts.
- External installed files: `external/EXTERNAL_ARTIFACTS.json`.
- Logical persistent assets and classification: `storage/DATA_ASSET_REGISTRY.json`.
- Secret metadata and encrypted-backup references: `secrets/SECRET_REGISTRY.json`; plaintext values MUST NOT be stored here.
- Backup/restore observations: append-only events in `storage/BACKUP_CATALOG.json`, derived from provider evidence.
- Machine-specific roots and runtime provider: a deployment profile.
- Task observations: one immutable task record per `task_id`.

`PROJECTS.json`, connection maps, runtime outputs, baseline snapshots, and evidence indexes MUST be generated derivatives. Manual edits to a derivative MUST be reported as drift. Project UUIDs are immutable; paths are deployment locations and MUST NOT be identities.

## 3. Entry, doctor and bootstrap

Agents MUST begin with `AGENT_ENTRYPOINT.md` and `agent-manifest.json`; they MUST NOT guess hidden files. `./sot doctor --format json` reports SOT parity, deployment profile, rule packages, installed artifacts, projects, orphans, Git parity, runtime mapping, backups, secrets metadata, Docker state, and verifier capability separately.

`./sot bootstrap --profile <profile>` MUST discover packages dynamically, validate schemas and hashes, resolve destination templates from the selected profile, install files atomically, activate supported adapters, run effective-state probes, scan for unmanaged artifacts, and then run doctor. Missing credentials, unsupported platform, missing/tampered required artifact, or failed probe MUST return nonzero and `RECOVERY_INCOMPLETE`.

Bootstrap MUST resolve its SOT root from its own location. Canonical files MUST NOT depend on a fixed username, home directory, Azure path, hostname, or mount. Roots such as `HOME`, `PROJECTS_ROOT`, `STATE_ROOT`, `RUNTIME_ROOT`, and `BACKUP_ROOT` MUST come from a validated deployment profile or environment contract. Paths MUST be normalized and destination containment MUST be checked before writes.

## 4. Rule packages

Rule packages are discovered by enumerating `governance/rules/*/*/rule.json`. The package directory is canonical; any rule index is generated and MUST be reproducible. The installer MUST NOT hard-code individual rule IDs or filenames.

Each package MUST declare a stable `rule_id`, semantic `version`, scope, severity, enabled state, supported agent classes, artifacts and SHA256 values, destination templates and permissions, load order, precedence, activation method, reload requirement, required proof level, positive and negative probes, expected effect, superseded version, rollback plan, and commit binding.

Before installation, the loader MUST validate the schema, unique identity, package path, source-file containment, artifact hashes, allowed destination roots, and supported activation type. Untrusted packages MUST NOT execute arbitrary shell commands. Probe execution MUST use an argv array without shell interpolation and a bounded timeout. Package installation MUST be atomic and preserve prior versions for rollback.

A new valid package MUST be discovered, parsed, installed, activated, verified, and added to a generated index without editing the core installer. Missing, disabled, malformed, conflicting, or tampered required rules MUST fail closed. Unsupported optional rules MUST be reported explicitly.

## 5. External artifacts and agent adapters

Every required file installed outside SOT MUST have a manifest record: artifact ID, canonical source, destination template, agent/runtime, owner, mode, SHA256, activation probe, reload requirement, verification probe, and required/optional status. Managed roots MUST be scanned for undeclared hooks, settings, rules, units, and runtime scripts. Unlisted policy artifacts MUST be reported as `UNMANAGED EXTERNAL ARTIFACT` and block readiness when the root is managed.

Canonical governance is vendor-neutral. An adapter declares supported agent/runtime versions, configuration discovery paths, actual precedence sources, destinations, activation method, reload requirement, effective-state probe, and unsupported-capability behavior. Codex, AGY, Claude, Qwen, and generic CLI files are generated/installed derivatives, never policy authorities. Precedence MUST be measured on the target runtime; unsupported precedence MUST NOT be invented.

## 6. Proof of Enforcement

Every rule declares `required_level` 1–7:

1. `DECLARED`: canonical package and expected behavior exist.
2. `DISCOVERED`: loader reports the exact package and source hash.
3. `PARSED`: schema/parser succeeds for the declared version.
4. `LOADED`: target agent/runtime confirms loading through a runtime probe.
5. `RESOLVED`: effective value is observed after profile, project, environment, and CLI precedence.
6. `ENFORCED`: controlled positive behavior demonstrates the rule's effect.
7. `ADVERSARIAL_VERIFIED`: bypass/negative tests show prohibited behavior remains blocked; the verifier inspects the test itself.

Each level requires machine evidence: command argv, exit code, output artifact references and SHA256, inputs and fixture hashes, inspected-file hashes, Git commit, runtime identity/version, timestamp, expected result, and observed result. Evidence references MUST resolve to immutable files. Nonempty strings and a program's printed `PASS` are not evidence. Missing level means `NOT VERIFIED`. A deterministic failure MUST prevent an approved verdict. High/critical enforcement rules SHOULD require L7.

## 7. Project lifecycle and concurrency

Project activation requires a valid local Git repo, known branch/upstream, real reachable remote, successful push and fetch, local/remote branch SHA equality, ahead=0 and behind=0, generated mappings verified, required data classified, backup policy satisfied, verification configured, and SOT registration pushed with remote SHA equality. Explicit `local_only=true` is the only policy exception.

Any failed stage MUST persist `ONBOARDING_INCOMPLETE`, current and last successful stage, failed stage, error class, retryability, timestamp, and operation ID. Retries MUST be idempotent. Registrations MUST use unique task/project IDs, schema validation, process locks, reread-after-lock, atomic temp+fsync+replace writes, post-write parse, and checksums. Locks SHOULD be per-project for work and short-lived for canonical registry transactions.

Discovery MUST recursively scan configured managed roots with no arbitrary depth cap. Known generated/dependency directories MAY be excluded only through narrow versioned rules. A registered parent MUST NOT hide an independent child. Missing scanner, unreadable root, malformed registry, orphan, or nonzero exit MUST block completion.

## 8. Builder and verifier workflows

The builder MUST bind work to a task ID and project UUID; capture base SHA and initial status; read applicable rules; make a scoped change; regenerate derivatives; run required deterministic and negative tests; scan secrets/databases/media before staging; and emit changed-file before/after hashes, diff hash, test commands/results, mapping/backup effects, and unresolved items.

The independent verifier MUST first identify task/request/project/revisions, validate evidence references and hashes, inspect changed files and relevant rules, inspect builder tests and exit-code behavior, determine additional checks, run independent deterministic/adversarial tests, and produce a structured verdict. It SHOULD expand review only when risk/evidence indicates cross-component impact. It MUST NOT reread unrelated application source by default.

Risk routing is capability-based: LOW generally needs deterministic checks; MEDIUM uses targeted independent review when warranted; HIGH requires a strong verifier; CRITICAL requires a high-capability independent verifier and L7 evidence. Provider unavailability leaves a required gate pending or inconclusive; it MUST NOT trigger self-approval.

## 9. Task evidence

Each task MUST have one immutable `verification/TASK_EVIDENCE/<task_id>/record.json`. It records task ID, project UUID, concise user request, builder/tool, start/end, base and after SHA, changed files and before/after hashes, diff reference/hash, tests and exact outcomes, deterministic result, mapping/backup effects, verifier status/identity, final verdict, and unresolved items. Attachments SHOULD be content-addressed. An index MUST be generated from records. Hidden chain-of-thought MUST NOT be stored.

Parallel workers MUST have unique task IDs and isolated worktrees or locks. Temporary names MUST be collision-resistant. Conflicts MUST be surfaced; updates MUST NOT overwrite one another silently.

## 10. Data, backups, and secrets

Storage classes are source code/config, database, media, durable runtime state, secret, and temporary/cache. Source code/config belongs in GitHub. Databases, videos, and durable state belong in configured external storage. Unknown durable data MUST fail closed rather than default to ordinary Git source.

Backup states are distinct: `DISCOVERED`, `BACKUP_REQUIRED`, `LOCAL_BACKUP_CREATED`, `REMOTE_UPLOAD_COMPLETE`, `REMOTE_OBJECT_VERIFIED`, `REMOTE_CHECKSUM_VERIFIED`, `REMOTE_RESTORE_VERIFIED`. Each transition requires separate evidence. Remote path existence is not a backup; upload exit zero is not object verification; remote size is not checksum proof; local restore is not remote restore. A restore is verified only after downloading the exact remote object to isolated storage and running domain integrity checks.

Provider adapters MUST support list, upload, metadata, checksum, download, retention, and restore evidence. Asset IDs MUST be provider independent. Live SQLite requires a consistent snapshot. SQL databases require documented logical/native backup methods. Restore tests MUST NOT overwrite production data.

Secrets MUST NOT be plaintext in GitHub or unencrypted external storage. SOT stores secret IDs, purpose, consumer, permissions, runtime destination, encrypted backup reference, key source reference, and recovery verification state only. Encryption and key recovery MUST be tested with isolated sample data. Secret values MUST NOT appear in logs or reports.

## 11. Docker and other runtimes

Docker profiles MUST pin images by immutable digest or controlled version and declare Dockerfiles/Compose, services, networks, ports, dependencies, health checks, resource limits, environment templates, secret references, and persistent volumes. Persistent volumes MUST map to registered external assets and MUST NOT be committed to Git.

`./sot bootstrap docker --profile <profile>` MUST validate the profile, restore approved data, start dependencies in order, and wait for health checks. Missing Docker, image, credentials, volume, or health checks means `DOCKER_RECOVERY: NOT VERIFIED`. Non-Docker runtimes use the same IDs and doctor contract through an adapter.

## 12. Verdict and acceptance

Allowed evidence verdicts are `VERIFIED`, `FAILED`, `NOT VERIFIED`, and `INCONCLUSIVE`. Summary states such as `READY`, `ZERO DRIFT`, `ACTIVE`, and `REMOTE_RESTORE_VERIFIED` MUST be derived from machine checks, never hand-entered. Any required failure returns nonzero and blocks readiness.

The architecture is ready only when a different-user/non-Azure blank machine can recover policy, rules, projects, runtime, and requested external data from GitHub plus secure credentials; a new rule requires no core installer edit; all required proof levels pass; and an alternate strong verifier can replace the current one through its adapter alone.
