#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
export GH_D2_17_OUTER_PACKAGE_ROOT="$SCRIPT_DIR"
: "${GH_D2_17_DELIVERY_PROFILE:=public-ci}"
export GH_D2_17_DELIVERY_PROFILE
exec "$SCRIPT_DIR/run_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_20260730_v1.sh" "$@"
