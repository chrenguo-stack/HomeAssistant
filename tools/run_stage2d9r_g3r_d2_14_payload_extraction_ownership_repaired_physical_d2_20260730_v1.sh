#!/bin/sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
export GH_D2_14_LAUNCHER_PACKAGE_ROOT="$SCRIPT_DIR"
export GH_D2_13_LAUNCHER_PACKAGE_ROOT="$SCRIPT_DIR"
PYTHON_BIN=${PYTHON_BIN:-python3}
exec "$PYTHON_BIN" -B "$SCRIPT_DIR/h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repaired_physical_d2_wrapper_20260730_v1.py" "$@"
