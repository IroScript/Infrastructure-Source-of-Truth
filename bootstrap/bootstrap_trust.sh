#!/usr/bin/env bash
# bootstrap_trust.sh — Installs and activates the AGY trust baseline on a fresh VM.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec "${SCRIPT_DIR}/../trust/restore_trust_baseline.sh"
