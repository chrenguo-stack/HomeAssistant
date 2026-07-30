#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
export GH_D2_16_LAUNCHER_PACKAGE_ROOT="$SCRIPT_DIR"
exec python3 -B "$SCRIPT_DIR/h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repaired_physical_d2_wrapper_20260730_v1.py" "$@"
