# Azure WhatsApp–Codex Bridge: Preservation and Recovery Guide

This guide records how to preserve and restore the existing WhatsApp bridge connecting the Azure VM's `agy:codex` tmux window to the Codex group. It supplements the general VM bootstrap and does not authorize changes to AGY, Research, or other project routes.

## Source of truth and protected data

- Keep bridge source and sanitized operational manifests in `IroScript/Infrastructure-Source-of-Truth`. Track the bridge project's source separately in its own Git repository; record its canonical path, remote, branch, and commit in infrastructure manifests.
- Treat `/home/azureuser/.webterminal/project_groups.json` as the routing manifest. Preserve the Codex group ID, `window: agy:codex`, and its project working directory. Keep WhatsApp pairing/authentication, OAuth tokens, API keys, and private keys out of Git. Back up restorable auth data only through the private backup process in `storage/`.
- Preserve Codex sessions and configuration under `/home/azureuser/.codex` as user data. Never commit credentials, session transcripts, databases, or raw auth folders here.
- Before each bridge change, make a timestamped copy of `whatsapp_bridge.js`, record its source commit and SHA-256, and note whether the diff touches Codex-only or shared routing/delivery logic. Keep rollback copies outside Git unless explicitly sanitized.

## Change and restore procedure

1. Verify the host (`hostname`, `uname -a`), tmux session (`tmux list-windows -t agy`), bridge service, and Git status before acting. Work on the Azure VM; a local computer may only carry SSH traffic.
2. Fetch or clone the WhatsApp bridge project at its recorded canonical path and revision. Restore runtime packages and service definitions using repository bootstrap manifests. Do not recreate behavior from memory or start a parallel bridge process.
3. Restore secrets and WhatsApp pairing only from the approved private backup or vault. Set correct ownership and restrictive permissions. Never place secret values in manifests, logs, shell history, or Git.
4. Restore the Codex group mapping and existing `agy:codex` tmux window. Keep AGY (`agy:0`), Research (`agy:research`), and other project mappings intact. Never replace the entire routing manifest with a Codex-only file.
5. Compare restored source against the recorded commit and checksum. Review the diff, syntax-check the bridge, then verify service health, WhatsApp connection, group-to-window mapping, and read-only Codex status before enabling traffic.
6. For rollback, stop only the affected bridge service using its documented service manager, restore the timestamped source and matching manifest backup, verify checksum and mappings, then start the existing service once. Never reset or delete Codex history, WhatsApp auth, databases, tmux windows, or other agent state as a shortcut.

## Runtime controls and verification

Record the installed Codex CLI version, model-picker options, reasoning values, model helper path, bridge command syntax, rollout/event source, WhatsApp chunk limit, and service name in sanitized manifests. Do not assume a model alias is valid: verify the TUI selection and a completed turn's rollout `turn_context` before marking it supported. Track configured default separately from the running session and latest turn.

For Codex WhatsApp delivery, keep the formatted final response as the last message in a turn. If the persisted `task_complete` event follows the final-answer event, hold the final response until the completion notice is delivered, then send the formatted response. If the completion event arrives first, send it before the final response. Never send bridge-generated turn-completion metadata after the formatted final response. Preserve the existing response framing and session footer.

After restore or update, verify without prompting AGY that the WhatsApp bridge is connected; the Codex group maps to `agy:codex`; Codex and Research panes are alive; model status agrees between TUI, helper, config, and latest rollout; and the Codex event watcher is active. Record date, CLI/source revision, checksum, results, backup location, and limitations in a dated verification record. Do not claim parity or successful model switching without runtime evidence.

## Updating this record

When bridge behavior, routing, service setup, Codex controls, or recovery steps change, update this guide and relevant sanitized manifests in the same reviewed change. Preserve known-good commits and backups. Do not copy AGY rules or private Gemini settings into Codex configuration, or vice versa.
