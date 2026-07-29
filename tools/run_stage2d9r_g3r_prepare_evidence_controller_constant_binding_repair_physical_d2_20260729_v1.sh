#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
WRAPPER="$SCRIPT_DIR/h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_physical_d2_wrapper_20260729_v1.py"

if [ "$#" -eq 0 ]; then
  exec python3 "$WRAPPER"
fi

MODE=$1
shift
case "$MODE" in
  contract-check|execute)
    exec python3 "$WRAPPER" "$MODE" "$@"
    ;;
  *)
    echo "first argument must be contract-check or execute" >&2
    exit 2
    ;;
esac
