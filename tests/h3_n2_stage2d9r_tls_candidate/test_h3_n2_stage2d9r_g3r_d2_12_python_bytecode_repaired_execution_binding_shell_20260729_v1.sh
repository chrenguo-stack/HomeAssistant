#!/bin/sh
set -eu
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
PR208_ARTIFACT_ZIP=${PR208_ARTIFACT_ZIP:?PR208_ARTIFACT_ZIP required}
PR209_ARTIFACT_ZIP=${PR209_ARTIFACT_ZIP:?PR209_ARTIFACT_ZIP required}
SOURCE_SHA=${SOURCE_SHA:-1111111111111111111111111111111111111111}
PACKAGER="$ROOT/tools/h3_n2_stage2d9r_g3r_d2_12_python_bytecode_repaired_execution_binding_packager_20260729_v1.py"
LAUNCHER_NAME="run_stage2d9r_g3r_d2_12_python_bytecode_repaired_physical_d2_20260729_v1.sh"
EXECUTION_DIR="d2-12-python-bytecode-repaired-physical-d2-execution-package"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/d2-12-bytecode-shell.XXXXXX")
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

python3 -B "$PACKAGER" \
  --source-root "$ROOT" \
  --pr208-artifact "$PR208_ARTIFACT_ZIP" \
  --pr209-artifact "$PR209_ARTIFACT_ZIP" \
  --source-sha "$SOURCE_SHA" \
  --output "$WORK/lane-a"
python3 -B "$PACKAGER" \
  --source-root "$ROOT" \
  --pr208-artifact "$PR208_ARTIFACT_ZIP" \
  --pr209-artifact "$PR209_ARTIFACT_ZIP" \
  --source-sha "$SOURCE_SHA" \
  --output "$WORK/lane-b"

diff -qr "$WORK/lane-a" "$WORK/lane-b"
(cd "$WORK/lane-a" && sha256sum -c SHA256SUMS >/dev/null)

PACKAGE="$WORK/lane-a/$EXECUTION_DIR"
LAUNCHER="$PACKAGE/$LAUNCHER_NAME"
STATUS=$("$LAUNCHER")
printf '%s\n' "$STATUS" | grep -q '"status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_12_AUTHORIZATION"'
printf '%s\n' "$STATUS" | grep -q '"predecessor_status": "PRECLAIM_CONTRACT_FAILED"'
printf '%s\n' "$STATUS" | grep -q '"physical_baseline_locked_recovery_outcome": "UNKNOWN"'
printf '%s\n' "$STATUS" | grep -q '"bytecode_write_disabled_for_current_process": true'
printf '%s\n' "$STATUS" | grep -q '"board_operation": false'
printf '%s\n' "$STATUS" | grep -q '"network_operation": false'

test ! -e "$PACKAGE/run_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_20260729_v1.sh"
test -z "$(find "$PACKAGE" -type d -name __pycache__ -print -quit)"
test -z "$(find "$PACKAGE" -type f -name '*.pyc' -print -quit)"

find "$PACKAGE" -type f -exec sha256sum {} \; | sort >"$WORK/before.sha256"
printf '{}\n' >"$WORK/invalid-record.json"
if "$LAUNCHER" contract-check \
  --package-root "$PACKAGE" \
  --physical-request "$WORK/lane-a/PHYSICAL_D2_REQUEST_12.json" \
  --authorization-record "$WORK/invalid-record.json" \
  --result-output "$WORK/contract-result.json" \
  --now "2026-07-29T16:00:00Z" \
  >"$WORK/contract-stdout.txt"
then
  echo "invalid record unexpectedly passed" >&2
  exit 1
fi
grep -q '"failure_code": "AUTHORIZATION_FIELD_SET_MISMATCH"' "$WORK/contract-result.json"
grep -q '"authorization_claimed": false' "$WORK/contract-result.json"
grep -q '"authorization_consumed": false' "$WORK/contract-result.json"
grep -q '"board_operation": false' "$WORK/contract-result.json"
grep -q '"serial_operation": false' "$WORK/contract-result.json"
grep -q '"flash_operation": false' "$WORK/contract-result.json"
grep -q '"network_operation": false' "$WORK/contract-result.json"

find "$PACKAGE" -type f -exec sha256sum {} \; | sort >"$WORK/after.sha256"
cmp "$WORK/before.sha256" "$WORK/after.sha256"
test -z "$(find "$PACKAGE" -type d -name __pycache__ -print -quit)"
test -z "$(find "$PACKAGE" -type f -name '*.pyc' -print -quit)"

python3 -B - "$WORK/lane-a" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
request = json.loads((root / "PHYSICAL_D2_REQUEST_12.json").read_text())
review = json.loads(
    (root / "D2_12_PYTHON_BYTECODE_REPAIRED_EXECUTION_BINDING_REVIEW.json").read_text()
)
assert request["authorized"] is False
assert request["authorization_created"] is False
assert request["predecessor_status"] == "PRECLAIM_CONTRACT_FAILED"
assert request["predecessor_authorization_claimed"] is False
assert request["predecessor_authorization_consumed"] is False
assert request["physical_baseline_locked_recovery_outcome"] == "UNKNOWN"
assert request["bytecode_write_disabled_before_python"] is True
assert request["private_outer_runner_bytecode_guard_required"] is True
assert review["physical_request_created"] is True
assert review["physical_request_authorized"] is False
assert review["physical_authorization_created"] is False
assert review["board_operation"] is False
assert review["network_operation"] is False
PY

echo "D2_12_BYTECODE_REPAIRED_EXECUTION_BINDING_SHELL=PASS"
