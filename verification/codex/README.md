# Manual AGY review

Tell Codex: “Review the Frappe AGY task against official standards.” The reviewer
uses the commands below to identify the project, conversation and user task. It
must resolve task ambiguity before making an audit claim. No automatic trigger,
WhatsApp command handler or terminal delivery is installed by this tool.

## Architecture

Manual request → exact workspace → conversation UUID → USER_INPUT step → task
transcript + selected code snapshots → independent review → report + AGY guideline.

Ten simultaneous CLIs do not share a “latest response” pointer. Each review has
its own UUID and task key (`conversation_id:user_step`). Workspace matching
resolves symlinks and URL-encoded paths. Task evidence ends at the next USER_INPUT.
Tool outputs remain attached to that task. Code files are explicitly selected;
mtime does not prove authorship. A changing task or file aborts collection.
Snapshots are per-file consistent, not an atomic filesystem-wide snapshot.

## Commands

Run from this directory:

```bash
python3 manual_review.py sessions --workspace /home/azureuser/Frappe-erp-Alco
python3 manual_review.py tasks --workspace /home/azureuser/Frappe-erp-Alco --session CONVERSATION_UUID
python3 manual_review.py collect --workspace /home/azureuser/Frappe-erp-Alco --session CONVERSATION_UUID --task-step USER_STEP --scope 'Official Frappe standards for this task' --file relative/path/to/code.py
python3 manual_review.py run --bundle /absolute/path/printed/by/collect
```

Repeat `--file` for each relevant code/config/test file. Select paths from actual
task logs; do not sweep unrelated new files from other projects. Include version
evidence and appropriate project instructions in the selection. Avoid credentials
and private data; common credential filenames are rejected, but this is not a
complete secret scanner. Collection stays local. `run` sends selected evidence to
Codex and enables live web search to check primary official documentation.

Artifacts are private, ignored by Git, and retained in `reviews/<review_uuid>/`:
task evidence, selected file snapshots, prompt, runner log, exit status, structured
result, report and AGY guideline. Inspect `evidence.json` before running. Runner
failure, timeout, malformed output or a wrong task ID produces no clearance.
Missing evidence must produce an inconclusive report. Read-only review cannot
establish runtime correctness merely from reported test logs.

`agy-guideline.md` is the manual handoff. It includes the original task identity
and project. Direct handoff should only be added with an authoritative binding
between conversation UUID, tmux pane and active task, plus stale-revision checks
and an idle queue. Current bridge routing guesses and an idle-looking prompt do
not provide that binding. Existing bridge automatic audits are unchanged.

Future task attribution requires a task ID recorded at dispatch, session binding,
and before/after code revisions (preferably an isolated worktree per concurrent
writer). Historical logs cannot retroactively prove authorship of current files.

## Validation

```bash
python3 -m unittest -v test_manual_review.py
```

These tests use temporary synthetic transcripts/files and a synthetic SQLite DB;
they test isolation and rejection behavior, not a live WhatsApp or AGY workflow.
