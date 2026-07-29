#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
TOOLS="$ROOT/tools"
OUTPUT=$(PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TOOLS" python3 \
  "$TOOLS/h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_20260729_v1.py")
printf '%s\n' "$OUTPUT" | grep -q '"status": "SOURCE_ONLY_NO_CLOSURE_AUTHORIZATION"'
printf '%s\n' "$OUTPUT" | grep -q '"closure_applied": false'
printf '%s\n' "$OUTPUT" | grep -q '"board_operation": false'
printf '%s\n' "$OUTPUT" | grep -q '"replay_permitted": false'

if rg -n '(^|[[:space:]])(import|from)[[:space:]]+(serial|esptool|mosquitto)' \
  "$TOOLS/h3_n2_stage2d9r_g3r_d2_10_forensic_terminal_closure_20260729_v1.py"
then
  echo "forensic closure tool contains a prohibited physical dependency" >&2
  exit 1
fi
