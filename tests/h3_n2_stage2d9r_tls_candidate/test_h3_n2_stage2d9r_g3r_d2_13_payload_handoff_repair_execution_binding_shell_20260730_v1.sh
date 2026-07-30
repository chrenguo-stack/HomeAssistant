#!/bin/sh
set -eu
umask 077
: "${PR210_ARTIFACT_ZIP:?}"
: "${SOURCE_SHA:?}"
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM
OUT="$TMP/review"

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_13_payload_handoff_repair_execution_binding_packager_20260730_v1.py" \
  --source-root "$ROOT" \
  --pr210-artifact "$PR210_ARTIFACT_ZIP" \
  --source-sha "$SOURCE_SHA" \
  --output "$OUT"

PACKAGE="$OUT/d2-13-payload-handoff-repaired-physical-d2-execution-package"
LAUNCHER="$PACKAGE/run_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_20260730_v1.sh"
REQUEST="$OUT/PHYSICAL_D2_REQUEST_13.json"
test -f "$LAUNCHER"
test -f "$REQUEST"

printf '{}\n' > "$TMP/fake-authorization.json"
set +e
sh "$LAUNCHER" contract-check \
  --package-root "$PACKAGE" \
  --physical-request "$REQUEST" \
  --authorization-record "$TMP/fake-authorization.json" \
  --result-output "$TMP/contract-result.json" \
  --now 2026-07-30T00:00:00Z > "$TMP/contract-stdout.json"
RC=$?
set -e
test "$RC" -eq 2
python3 -B - "$TMP/contract-result.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1],encoding='utf-8'))
assert v['status']=='FAIL'
assert v['failure_code']=='AUTHORIZATION_FIELD_SET_MISMATCH'
assert v['authorization_claimed'] is False
assert v['authorization_consumed'] is False
for key in ('board_operation','usb_enumeration','serial_operation','esptool_operation','flash_operation','network_operation'):
    assert v[key] is False
PY

# Real shell-to-Python handoff with a Finder-style symlink and spaces.
SPACE="$TMP/macOS Package With Spaces"
cp -R "$PACKAGE" "$SPACE"
ALIAS="$TMP/Finder Alias"
ln -s "$SPACE" "$ALIAS"
sh "$SPACE/run_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_20260730_v1.sh" handoff-check \
  --package-root "$ALIAS" \
  --result-output "$TMP/handoff-result.json" \
  > "$TMP/handoff-stdout.json"
python3 -B - "$TMP/handoff-result.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1],encoding='utf-8'))
assert v['status']=='PASS'
assert v['payload_arguments_injected'] is True
assert v['launcher_package_root_matches'] is True
assert v['immutable_payload_sha256_matches'] is True
assert v['recovery_payload_sha256_matches'] is True
for key in ('authorization_claimed','authorization_consumed','board_operation','usb_enumeration','serial_operation','esptool_operation','flash_operation','network_operation','prepare_executed','verify_executed'):
    assert v[key] is False
PY

# Authorization-created / claim-before failure must create stable evidence even
# when the inherited parser cannot run. Remove one payload from a disposable copy.
BROKEN="$TMP/Broken Package"
cp -R "$PACKAGE" "$BROKEN"
rm "$BROKEN/stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"
printf '{}\n' > "$TMP/execute-authorization.json"
mkdir "$TMP/state"
set +e
sh "$BROKEN/run_stage2d9r_g3r_d2_13_payload_handoff_repaired_physical_d2_20260730_v1.sh" execute \
  --package-root "$BROKEN" \
  --authorization-record "$TMP/execute-authorization.json" \
  --state-root "$TMP/state" \
  --result-output "$TMP/preclaim-result.json" \
  > "$TMP/preclaim-stdout.json"
RC=$?
set -e
test "$RC" -eq 2
test -f "$TMP/preclaim-result.json"
python3 -B - "$TMP/preclaim-result.json" "$TMP/state" <<'PY'
import json,sys
from pathlib import Path
v=json.load(open(sys.argv[1],encoding='utf-8'))
assert v['status']=='CONSUMED_FAILED'
assert v['failure_code']=='RECOVERY_PAYLOAD_TAR_MISSING'
assert v['failure_stage']=='OUTER_TO_INNER_PAYLOAD_HANDOFF'
assert v['authorization_created'] is True
assert v['authorization_claimed'] is False
assert v['authorization_consumed'] is True
for key in ('board_operation','usb_enumeration','serial_operation','esptool_operation','flash_operation','network_operation','prepare_executed','verify_executed'):
    assert v[key] is False
markers=list(Path(sys.argv[2]).glob('*.json'))
assert len(markers)==1
m=json.load(open(markers[0],encoding='utf-8'))
assert m['status']=='CONSUMED_FAILED'
assert m['authorization_claimed'] is False
assert m['authorization_consumed'] is True
PY

test -z "$(find "$OUT" "$SPACE" -type d -name __pycache__ -print -quit)"
test -z "$(find "$OUT" "$SPACE" -type f -name '*.pyc' -print -quit)"
echo '{"status":"PASS","payload_arguments_supplied_by_caller":false,"macos_path_normalization":true,"preclaim_result_present":true}'
