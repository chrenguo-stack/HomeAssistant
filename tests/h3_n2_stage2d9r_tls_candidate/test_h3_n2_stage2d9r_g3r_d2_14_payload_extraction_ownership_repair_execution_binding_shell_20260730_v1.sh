#!/bin/sh
set -eu
: "${PR212_ARTIFACT_ZIP:?PR212_ARTIFACT_ZIP is required}"
: "${SOURCE_SHA:?SOURCE_SHA is required}"
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/d2-14 shell ownership.XXXXXX")
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
OUTPUT="$WORK/review lane"
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repair_execution_binding_packager_20260730_v1.py" \
  --source-root "$ROOT" \
  --pr212-artifact "$PR212_ARTIFACT_ZIP" \
  --source-sha "$SOURCE_SHA" \
  --output "$OUTPUT"
PACKAGE="$OUTPUT/d2-14-payload-extraction-ownership-repaired-physical-d2-execution-package"
RESULT="$WORK/root ownership result.json"
/bin/sh "$PACKAGE/run_stage2d9r_g3r_d2_14_payload_extraction_ownership_repaired_physical_d2_20260730_v1.sh" \
  root-ownership-check \
  --package-root "$PACKAGE" \
  --result-output "$RESULT"
python3 -B - "$RESULT" <<'PY'
import json
import sys
value=json.load(open(sys.argv[1],encoding="utf-8"))
assert value["status"] == "PASS"
assert value["outer_payload_preextraction"] is False
assert value["inner_payload_extraction_count"] == 1
assert value["payload_roots_empty_before_inner_start"] is True
assert value["payload_tar_copy_inside_roots"] is False
assert value["immutable_payload_inventory_valid"] is True
assert value["recovery_payload_inventory_valid"] is True
assert value["authorization_claimed"] is False
assert value["authorization_consumed"] is False
assert value["board_operation"] is False
assert value["usb_enumeration"] is False
assert value["serial_operation"] is False
assert value["flash_operation"] is False
PY
if find "$OUTPUT" \( -type d -name __pycache__ -o -type f -name '*.pyc' -o -type l \) -print -quit | grep -q .; then
  echo "bytecode or symlink found" >&2
  exit 1
fi
