#!/bin/sh
set -eu
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
GH_D2_13_LAUNCHER_PACKAGE_ROOT=$SCRIPT_DIR
export GH_D2_13_LAUNCHER_PACKAGE_ROOT
PYTHON_BIN=${PYTHON_BIN:-python3}
WRAPPER="$SCRIPT_DIR/h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_wrapper_20260730_v1.py"

if [ "$#" -eq 0 ]; then
  exec "$PYTHON_BIN" "$WRAPPER"
fi
if [ "$1" != "contract-check" ] && [ "$1" != "handoff-check" ] && [ "$1" != "execute" ]; then
  echo "first argument must be contract-check, handoff-check or execute" >&2
  exit 2
fi
exec "$PYTHON_BIN" "$WRAPPER" "$@"
