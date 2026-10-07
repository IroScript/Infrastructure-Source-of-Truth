# Worker and verifier workflow

Cheap builders may work concurrently on isolated tasks and project worktrees. Each task uses a unique `task_id`, immutable `project_uuid`, and project-level lock when changing shared project state. Global registry locks cover only short validated read/modify/write transactions.

Before independent review, the builder produces an evidence bundle containing the original task, project identity, changed-file list, diff, before/after hashes, commit SHA when committed, deterministic commands and outputs, exit codes, negative tests, lifecycle state, and unresolved items. It contains observable evidence only; hidden reasoning is excluded.

The deterministic verifier runs first and blocks completion on any failed required check. A provider adapter can then send the compact bundle to Codex, Claude, another CLI, or a manual reviewer. The adapter is optional and provider-neutral. All provider results validate against `independent_verifier.schema.json`; a plain `PASS` cannot satisfy the schema.

The verifier reviews task scope, changed files, evidence, required additional checks, and affected mappings. It does not become a source of truth or mandatory runtime dependency. GitHub remains the recoverable code, policy, and configuration source.
