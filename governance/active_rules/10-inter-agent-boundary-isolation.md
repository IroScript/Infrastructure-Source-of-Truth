# RULE-INTER-AGENT-BOUNDARY-ISOLATION: 5-LAYER INTER-AGENT PROJECT ISOLATION PROTOCOL
Version: 1.0.0
Authoritative Directive: SETTING_79_INTER_AGENT_PROJECT_WORKSPACE_BOUNDARY_ISOLATION

## CORE PRINCIPLE: ZERO CROSS-AGENT VISIBILITY & PRIVACY
No WhatsApp project agent may inspect, view, edit, execute, or receive work belonging to another WhatsApp project agent.
Cross-agent leakage across WhatsApp channels, filesystems, terminals, brains, or governance is strictly prohibited.

---

### LAYER 1: PRE-TOOL-USE HOOK POLICY ISOLATION (boundary-guard)
- Enforced by: `/home/azureuser/.agents/hooks/delete_guard.py` via `~/.gemini/config/hooks.json`.
- All tool calls (`view_file`, `write_to_file`, `replace_file_content`, `run_command`) are intercepted.
- If a project agent attempts to view or touch another project's files or directories, the call is blocked immediately with an explicit denial:
  `🛑 [BOUNDARY-GUARD HARD DENIAL: RULE_79] Cross-project command violation`
- Every violation logs a structured audit incident in `/home/azureuser/AGY-MASTER/INCIDENTS/`.

### LAYER 2: WHATSAPP BRIDGE CHANNEL & ROUTING ISOLATION
- Enforced by: `/home/azureuser/.webterminal/whatsapp_bridge.js` & `project_groups.json`.
- Strict 1:1 Inbound Routing: Prompts from Group A route ONLY to Window A.
- Strict 1:1 Outbound Delivery Silo: Turn responses, thinking, tool calls, and completion notifications for Window A route ONLY to Group A.
- Zero Fallback: Fallback to other windows' `lastUserMsg` is strictly forbidden, eliminating cross-group leakage.
- Direct Shell Sandboxing: Direct shell execution commands (`$` or `!`) are strictly confined to the caller's own project root.

### LAYER 3: OS & TMUX WORKSPACE JAILING
- Enforced by: `start_all_agents.sh` and persistent tmux panes.
- Each agent process (`agy:yt`, `agy:frappe`, `agy:tg`, `agy:history`, `agy:kids`, `agy:rust`, `agy:article`, `agy:game`, `agy:research`, `agy:report`, `agy:codex`) has its process working directory (CWD) locked inside its canonical project directory on disk.
- Pane processes cannot alter root directories of sibling projects.

### LAYER 4: AGENT MEMORY, BRAIN & SESSION TRANSLATION SILOING
- Enforced by: Unique conversation UUIDs and `delete_guard.py` Layer 4 brain guards.
- Each agent operates in its own dedicated session brain directory: `~/.gemini/antigravity-cli/brain/<uuid>/`.
- Agents are blocked from reading or viewing session transcripts, logs, or state files belonging to other conversation IDs.
- `conversation_summaries.db` is isolated from unauthorized project mutations.

### LAYER 5: GOVERNANCE & TEN-FOLD VERIFICATION PROTOCOL
- Enforced by: `/home/azureuser/.agents/verify_10_fold.py` and authoritative governance files.
- Deterministic negative tests verify cross-project isolation across all 10 vectors.
- Cryptographically signed machine state confirms 100% compliance before task completion.
