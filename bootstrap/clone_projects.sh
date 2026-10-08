#!/usr/bin/env bash
# clone_projects.sh — Generic project recovery entrypoint driven by canonical SOT metadata.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_HOME="${HOME:-/home/azureuser}"
PROJECTS_ROOT="${PROJECTS_ROOT:-$BASE_HOME/IroScript_Projects}"

python3 "$SCRIPT_DIR/project_recovery.py" \
  --sot-root "$SOT_ROOT" \
  --projects-root "$PROJECTS_ROOT" \
  --home "$BASE_HOME" \
  "$@"
