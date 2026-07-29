#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
PYTHON_BIN=${PYTHON_BIN:-python3}
WRAPPER="$SCRIPT_DIR/h3_n2_stage2d9r_g3r_prepare_panic_timeline_reset_signature_physical_d2_wrapper_20260729_v1.py"

if [ "$#" -eq 0 ]; then
  exec "$PYTHON_BIN" "$WRAPPER"
fi

if [ "$1" != "contract-check" ] && [ "$1" != "execute" ]; then
  echo "first argument must be contract-check or execute" >&2
  exit 2
fi

exec "$PYTHON_BIN" "$WRAPPER" "$@"
