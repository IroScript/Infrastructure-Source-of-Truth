# Agent entrypoint

This repository is the canonical source for managed project policy, bootstrap, registry schemas, and verification contracts. Read this file first whenever an agent receives this repository URL.

## Roles

The task issuer assigns one role: `builder`, `deterministic_verifier`, `independent_verifier`, or `operator`. A model or vendor name never grants authority. If the task does not specify a role or requested outcome, inspect and report; do not invent a task.

- A **builder** changes code and produces machine evidence. It cannot independently accept its own high-risk change.
- A **deterministic verifier** runs reproducible shell, Python, Git, checksum, database, and runtime checks. It is mandatory and provider independent.
- An **independent verifier** challenges a builder's evidence and tests. Codex is one replaceable adapter.
- An **operator** performs explicitly authorized deployment, restore, or other operational actions.

## First commands

From the repository root:

```sh
./sot doctor --format json
./sot rules list
./sot verify --help
```

Before changing anything, read [`UNIVERSAL_AGENT_OPERATING_STANDARD.md`](UNIVERSAL_AGENT_OPERATING_STANDARD.md), `agent-manifest.json`, and the applicable project and rule package manifests. `./sot bootstrap --profile <profile>` installs the declared baseline; use `--dry-run` to inspect the plan. Bootstrap may change the target machine's configured destinations.

## Authority and completion

`projects/PROJECT_REGISTRY.json` owns project identity; immutable `project_uuid` is the machine identity and paths are locations. `governance/rules/**/rule.json` owns rule package definitions. `external/EXTERNAL_ARTIFACTS.json` owns declared files installed outside this repository. `storage/DATA_ASSET_REGISTRY.json` owns logical persistent assets; backup catalog entries are observations, not proof by themselves.

GitHub is authoritative for recoverable code, policy, schemas, and templates. A dirty or unpushed Source-of-Truth checkout is not current. A project is not `ACTIVE` based on a remote URL: required remote objects, successful push/fetch, exact SHA parity, mappings, data classification, backup policy, and Source-of-Truth registration must all be verified.

## Failure behavior

Missing credentials, missing or tampered required artifacts, unregistered external rules, orphan projects, failed tests, unavailable required remotes, checksum mismatch, or insufficient proof MUST leave the operation incomplete. Report `NOT VERIFIED` when the required evidence is unavailable. Never turn a command's printed `PASS` into proof without inspecting its inputs, outputs, exit code, and test behavior.
