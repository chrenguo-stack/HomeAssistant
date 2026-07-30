#!/bin/sh
set -eu
: "${PR213_ARTIFACT_ZIP:?}"
: "${SOURCE_SHA:?}"
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/d2-15 install preflight.XXXXXX")
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
OUT="$TMP/review lane with spaces"
PYTHONPATH="$ROOT/tools${PYTHONPATH:+:$PYTHONPATH}" python3 -B \
  "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_15_contract_compatibility_install_preflight_repair_execution_binding_packager_20260730_v1.py" \
  --source-root "$ROOT" \
  --pr213-artifact "$PR213_ARTIFACT_ZIP" \
  --source-sha "$SOURCE_SHA" \
  --output "$OUT"
PKG="$OUT/d2-15-contract-compatibility-install-preflight-repaired-physical-d2-execution-package"
RESULT="$TMP/install-preflight-result.json"
PYTHONDONTWRITEBYTECODE=1 PYTHON_BIN=python3 /bin/sh \
  "$PKG/run_stage2d9r_g3r_d2_15_contract_compatibility_install_preflight_repaired_physical_d2_20260730_v1.sh" \
  install-preflight-check \
  --package-root "$PKG" \
  --result-output "$RESULT"
python3 -B - "$RESULT" <<'PY'
import json, sys
value=json.load(open(sys.argv[1],encoding='utf-8'))
assert value['status']=='PASS'
assert value['contract_compatibility_symbol_present'] is True
assert value['inherited_d2_11_install_completed'] is True
assert value['authorization_created'] is False
assert value['board_operation'] is False
assert value['usb_enumeration'] is False
assert value['serial_operation'] is False
assert value['flash_operation'] is False
PY
