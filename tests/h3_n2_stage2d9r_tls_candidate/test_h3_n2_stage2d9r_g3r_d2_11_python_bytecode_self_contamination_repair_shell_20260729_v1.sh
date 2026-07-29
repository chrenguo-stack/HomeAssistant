#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
LAUNCHER="$ROOT/tools/run_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_20260729_v1.sh"
ARTIFACT=${PR208_ARTIFACT_ZIP:-}

if [ -z "$ARTIFACT" ] || [ ! -f "$ARTIFACT" ]; then
  echo "PR208_ARTIFACT_ZIP must name the exact downloaded Artifact" >&2
  exit 2
fi

TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/d2-11-bytecode-repair.XXXXXX")
trap 'rm -rf "$TMP_ROOT"' EXIT HUP INT TERM

OLD_ROOT="$TMP_ROOT/old"
FIXED_ROOT="$TMP_ROOT/fixed"
ENTRYPOINT="$TMP_ROOT/entrypoint"
mkdir -p "$OLD_ROOT" "$FIXED_ROOT" "$ENTRYPOINT"
unzip -q "$ARTIFACT" -d "$OLD_ROOT"
unzip -q "$ARTIFACT" -d "$FIXED_ROOT"

PACKAGE_NAME=d2-11-prepare-transport-pacing-physical-d2-execution-package
OLD_PACKAGE="$OLD_ROOT/$PACKAGE_NAME"
FIXED_PACKAGE="$FIXED_ROOT/$PACKAGE_NAME"
REQUEST_NAME=PHYSICAL_D2_REQUEST_11.json
OLD_WRAPPER=h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_physical_d2_wrapper_20260729_v1.py

printf '{}\n' >"$TMP_ROOT/non_authorizing-fixture.json"

(
  unset PYTHONDONTWRITEBYTECODE PYTHONPYCACHEPREFIX
  cd "$OLD_PACKAGE"
  if python3 "$OLD_WRAPPER" contract-check \
    --package-root "$OLD_PACKAGE" \
    --physical-request "$OLD_ROOT/$REQUEST_NAME" \
    --authorization-record "$TMP_ROOT/non_authorizing-fixture.json" \
    --result-output "$TMP_ROOT/old-result.json"
  then
    echo "unrepaired writable package unexpectedly passed" >&2
    exit 1
  fi
)
grep -q '"failure_code": "ContractError"' "$TMP_ROOT/old-result.json"
test -n "$(find "$OLD_PACKAGE" -type d -name __pycache__ -print -quit)"
test -n "$(find "$OLD_PACKAGE" -type f -name '*.pyc' -print -quit)"

cp "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_contract_20260729_v1.py" "$ENTRYPOINT/"
cp "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_repair_wrapper_20260729_v1.py" "$ENTRYPOINT/"
cp "$LAUNCHER" "$ENTRYPOINT/"
chmod 700 "$ENTRYPOINT/$(basename "$LAUNCHER")"

python3 - "$FIXED_PACKAGE" >"$TMP_ROOT/before.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
value = {
    str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(root.rglob("*"))
    if path.is_file()
}
print(json.dumps(value, sort_keys=True))
PY

PYTHONPATH="$FIXED_PACKAGE${PYTHONPATH:+:$PYTHONPATH}" \
  "$ENTRYPOINT/$(basename "$LAUNCHER")" contract-check \
  --package-root "$FIXED_PACKAGE" \
  --physical-request "$FIXED_ROOT/$REQUEST_NAME" \
  --authorization-record "$TMP_ROOT/non_authorizing-fixture.json" \
  --result-output "$TMP_ROOT/fixed-result.json" \
  >/dev/null 2>&1 && {
    echo "non-authorizing fixture unexpectedly passed" >&2
    exit 1
  }

grep -q '"failure_code": "AUTHORIZATION_SCHEMA_MISMATCH"' "$TMP_ROOT/fixed-result.json"
grep -q '"authorization_claimed": false' "$TMP_ROOT/fixed-result.json"
grep -q '"authorization_consumed": false' "$TMP_ROOT/fixed-result.json"
grep -q '"board_operation": false' "$TMP_ROOT/fixed-result.json"
grep -q '"serial_operation": false' "$TMP_ROOT/fixed-result.json"
grep -q '"flash_operation": false' "$TMP_ROOT/fixed-result.json"
grep -q '"network_operation": false' "$TMP_ROOT/fixed-result.json"

if find "$FIXED_PACKAGE" "$ENTRYPOINT" \
  \( -type d -name __pycache__ -o -type f -name '*.pyc' \) \
  -print -quit | grep -q .; then
  echo "repaired launcher created Python bytecode" >&2
  exit 1
fi

python3 - "$FIXED_PACKAGE" >"$TMP_ROOT/after.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
value = {
    str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(root.rglob("*"))
    if path.is_file()
}
print(json.dumps(value, sort_keys=True))
PY
cmp "$TMP_ROOT/before.json" "$TMP_ROOT/after.json"

STATUS=$("$LAUNCHER")
printf '%s\n' "$STATUS" | grep -q '"status": "SOURCE_ONLY_D2_12_REBIND_REQUIRED"'
printf '%s\n' "$STATUS" | grep -q '"d2_12_request_created": false'
printf '%s\n' "$STATUS" | grep -q '"board_operation": false'

echo "D2_11_PYTHON_BYTECODE_SELF_CONTAMINATION_REPAIR_SHELL=PASS"
