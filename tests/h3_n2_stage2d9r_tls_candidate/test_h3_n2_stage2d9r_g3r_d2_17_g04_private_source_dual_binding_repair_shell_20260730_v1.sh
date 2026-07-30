#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat >"$TMP/terminal.json" <<'JSON'
{"private_source_sha":"0691b3c85cf3ee018cd07cf038138cbf4dcd1f34"}
JSON
python3 -B "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_17_private_source_dual_binding_contract_20260730_v1.py" \
  --terminal "$TMP/terminal.json" \
  --acceptance-source-sha "e58b934c7e00125bf7d7c5a75f6ee338dd5dbdd7" \
  --physical-decision-source-sha "2acda017ba287c36718fda1031d55acf4101697d" \
  >"$TMP/pass.json"
python3 - "$TMP/pass.json" <<'PY'
import json,sys
value=json.load(open(sys.argv[1]))
assert value["status"]=="PASS"
assert value["source_fields_are_distinct"] is True
PY
set +e
python3 -B "$ROOT/tools/h3_n2_stage2d9r_g3r_d2_17_private_source_dual_binding_contract_20260730_v1.py" \
  --terminal "$TMP/terminal.json" \
  --acceptance-source-sha "0691b3c85cf3ee018cd07cf038138cbf4dcd1f34" \
  --physical-decision-source-sha "2acda017ba287c36718fda1031d55acf4101697d" \
  >"$TMP/fail.json"
rc=$?
set -e
test "$rc" -eq 2
python3 - "$TMP/fail.json" <<'PY'
import json,sys
value=json.load(open(sys.argv[1]))
assert value=={"failure_code":"ACCEPTANCE_SOURCE_SHA_DRIFT","status":"FAIL"}
PY
