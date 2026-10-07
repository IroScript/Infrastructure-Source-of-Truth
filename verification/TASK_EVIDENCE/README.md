# Task evidence ledger

Create one immutable JSON record per completed important task. Record task/project identity, request summary, builder/tool, start and end timestamps, changed files with before/after SHA256, commit SHA, test commands and exit codes, deterministic result, verifier identity/status, final verdict, and unresolved items. Do not store hidden chain-of-thought, credentials, or raw secret-bearing transcripts.

The directory is append-only by policy. The index is a convenience; each record is authoritative only after its content hash is included in a pushed Git commit.
