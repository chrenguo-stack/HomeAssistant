#!/bin/sh
set -eu
if [ "$#" -ne 0 ]; then echo "This one-shot G13 physical decision entry accepts no arguments." >&2; exit 2; fi
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
PYTHON_BIN=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
if [ ! -x "$PYTHON_BIN" ]; then echo "G13_FROZEN_PYTHON_MISSING" >&2; exit 2; fi
"$PYTHON_BIN" -B "$SCRIPT_DIR/h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.py" --decision-root "$SCRIPT_DIR"
RC=$?
"$PYTHON_BIN" -B "$SCRIPT_DIR/h3_n2_stage2d9r_g3r_d2_17_g13_physical_decision_marker_finalizer_20260731_v1.py"
exit "$RC"
