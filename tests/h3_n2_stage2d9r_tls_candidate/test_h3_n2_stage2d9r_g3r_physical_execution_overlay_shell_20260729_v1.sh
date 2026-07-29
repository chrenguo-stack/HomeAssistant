#!/bin/sh
set -eu
: "${STAGE2D9R_OVERLAY_PACKAGE_ROOT:?}"
: "${STAGE2D9R_OVERLAY_REQUEST:?}"
: "${STAGE2D9R_OVERLAY_VALID_AUTH:?}"
LAUNCHER="$STAGE2D9R_OVERLAY_PACKAGE_ROOT/run_stage2d9r_g3r_corrected_baseline_physical_d2_overlay_20260729_v1.sh"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/stage2d9r-overlay-shell-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
chmod 700 "$LAUNCHER"
"$LAUNCHER" contract-check "$STAGE2D9R_OVERLAY_REQUEST" "$STAGE2D9R_OVERLAY_VALID_AUTH" "$WORK/valid-result.json"
python3 - "$WORK/valid-result.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1]))
assert v['status']=='PASS'
assert v['board_operation'] is False
assert v['usb_enumeration'] is False
assert v['authorization_claimed'] is False
assert v['authorization_consumed'] is False
PY
for suffix in 04 05; do
  python3 - "$STAGE2D9R_OVERLAY_VALID_AUTH" "$WORK/invalid-$suffix.json" "$suffix" <<'PY'
import hashlib,json,sys
src,dst,suffix=sys.argv[1:]
v=json.load(open(src))
v['d2_request_id']='D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-'+suffix
v.pop('authorization_record_sha256',None)
v['authorization_record_sha256']=hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
json.dump(v,open(dst,'w'),sort_keys=True,indent=2)
PY
  if "$LAUNCHER" contract-check "$STAGE2D9R_OVERLAY_REQUEST" "$WORK/invalid-$suffix.json" "$WORK/invalid-$suffix-result.json"; then
    echo "old request $suffix unexpectedly accepted" >&2
    exit 1
  fi
  python3 - "$WORK/invalid-$suffix-result.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1]))
assert v['status']=='FAIL'
assert v['failure_code']=='AUTHORIZATION_D2_REQUEST_ID_MISMATCH'
assert v['board_operation'] is False
assert v['usb_enumeration'] is False
assert v['esptool_operation'] is False
assert v['flash_operation'] is False
PY
done
echo SHELL_INTEGRATION_PASS
