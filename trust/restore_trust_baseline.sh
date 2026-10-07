#!/usr/bin/env bash
set -euo pipefail
SOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PROFILE="${SOT_PROFILE:-portable-linux}"
exec "$SOT_ROOT/sot" bootstrap --profile "$PROFILE"
