#!/bin/sh
set -eu
: "${PR215_ARTIFACT_ZIP:?}" "${SOURCE_SHA:?}"
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
OUT=$(mktemp -d "${TMPDIR:-/tmp}/d2 17 full chain.XXXXXX")
trap 'rm -rf "$OUT"' EXIT HUP INT TERM
BUILDER="$ROOT/tools/h3_n2_stage2d9r_g3r_d2_17_canonical_builder_20260730_v1.py"
for lane in one two; do
  python3 -B "$BUILDER" --source-root "$ROOT" --pr215-artifact "$PR215_ARTIFACT_ZIP" \
    --source-sha "$SOURCE_SHA" --output "$OUT/review $lane"
done
diff -qr "$OUT/review one" "$OUT/review two"
(cd "$OUT/review one" && sha256sum -c SHA256SUMS)
PACKAGE="$OUT/review one/d2-17-execution-identity-frozen-physical-d2-execution-package"
REQUEST="$OUT/review one/PHYSICAL_D2_REQUEST_17.json"
RESULTS="$OUT/results with spaces"
TOOLS_DIR="$OUT/synthetic tools"
mkdir -p "$RESULTS" "$TOOLS_DIR"
for tool in python openssl esptool mosquitto; do
  printf '%s\n' '#!/bin/sh' 'exit 0' > "$TOOLS_DIR/$tool"
  chmod 700 "$TOOLS_DIR/$tool"
done
OUTER="$PACKAGE/run_d2_17_canonical_delivery_outer_20260730_v1.sh"
GH_D2_17_DELIVERY_PROFILE=public-ci "$OUTER" bind-install-idempotency-check \
  --result-output "$RESULTS/idempotency.json"
GH_D2_17_DELIVERY_PROFILE=public-ci "$OUTER" hardware-sentinel-self-check \
  --result-output "$RESULTS/hardware-sentinels.json"
run_profile() {
  profile=$1
  command_name=$2
  shift 2
  GH_D2_17_DELIVERY_PROFILE="$profile" "$OUTER" "$command_name" \
    --package-root "$PACKAGE" --physical-request "$REQUEST" \
    --python-executable "$TOOLS_DIR/python" --openssl-executable "$TOOLS_DIR/openssl" \
    --esptool-executable "$TOOLS_DIR/esptool" --mosquitto-executable "$TOOLS_DIR/mosquitto" "$@"
}
run_common() { run_profile public-ci "$@"; }
set +e
run_common create-authorization-from-frozen-identity \
  --execution-identity "$RESULTS/not-frozen.json" \
  --authorization-output "$RESULTS/forbidden-pre-freeze-authorization.json" \
  --issued-at 2026-07-30T07:00:00Z --expires-at 2026-07-30T08:00:00Z \
  --board-identity-sha256 "$(printf '1%.0s' $(seq 1 64))" \
  --serial-identity-sha256 "$(printf '2%.0s' $(seq 1 64))" \
  --baseline-state-sha256 "$(printf '3%.0s' $(seq 1 64))" >/dev/null 2>&1
PRE_FREEZE_RC=$?
set -e
[ "$PRE_FREEZE_RC" -ne 0 ]
[ ! -e "$RESULTS/forbidden-pre-freeze-authorization.json" ]
run_common freeze-execution-identity --identity-output "$RESULTS/execution-identity.json"
run_common create-authorization-from-frozen-identity \
  --execution-identity "$RESULTS/execution-identity.json" \
  --authorization-output "$RESULTS/synthetic-authorization.json" \
  --issued-at 2026-07-30T07:00:00Z --expires-at 2026-07-30T08:00:00Z \
  --board-identity-sha256 "$(printf '1%.0s' $(seq 1 64))" \
  --serial-identity-sha256 "$(printf '2%.0s' $(seq 1 64))" \
  --baseline-state-sha256 "$(printf '3%.0s' $(seq 1 64))"
for profile in public-ci private-package target-mac-static-check; do
  run_profile "$profile" static-check \
    --authorization-record "$RESULTS/synthetic-authorization.json" \
    --execution-identity "$RESULTS/execution-identity.json" \
    --result-output "$RESULTS/static-check-pass-$profile.json" --now 2026-07-30T07:30:00Z
done
cmp "$RESULTS/static-check-pass-public-ci.json" "$RESULTS/static-check-pass-private-package.json"
cmp "$RESULTS/static-check-pass-public-ci.json" "$RESULTS/static-check-pass-target-mac-static-check.json"
cp "$RESULTS/static-check-pass-public-ci.json" "$RESULTS/static-check-pass.json"
python3 -B - "$RESULTS/synthetic-authorization.json" "$RESULTS/tampered-authorization.json" <<'PY'
import hashlib,json,sys
source,target=sys.argv[1:]
value=json.load(open(source,encoding='utf-8'))
value['immutable_payload_tar_sha256']='0'*64
value.pop('authorization_record_sha256')
value['authorization_record_sha256']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
with open(target,'w',encoding='utf-8') as handle: json.dump(value,handle,sort_keys=True,indent=2); handle.write('\n')
import os; os.chmod(target,0o600)
PY
set +e
run_common static-check \
  --authorization-record "$RESULTS/tampered-authorization.json" \
  --execution-identity "$RESULTS/execution-identity.json" \
  --result-output "$RESULTS/static-check-tampered.json" --now 2026-07-30T07:30:00Z
RC=$?
set -e
[ "$RC" -eq 2 ]
ALIAS="$OUT/package alias"
ln -s "$PACKAGE" "$ALIAS"
PYTHONDONTWRITEBYTECODE=1 python3 -B - "$PACKAGE" "$ALIAS" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])))
import h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1 as contract
assert contract.normalized_delivery_path(Path(sys.argv[1])) == contract.normalized_delivery_path(Path(sys.argv[2]))
assert contract.delivery_equivalence_fingerprint(Path(sys.argv[1])) == contract.delivery_equivalence_fingerprint(Path(sys.argv[2]))
PY
D2_17_SHELL_RESULT_ROOT="$RESULTS" PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tests.h3_n2_stage2d9r_tls_candidate.test_h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_20260730_v1
[ -z "$(find "$OUT/review one" -type l -print -quit)" ]
[ -z "$(find "$OUT/review one" \( -type d -name __pycache__ -o -type f -name '*.pyc' \) -print -quit)" ]
[ -z "$(find "$OUT/review one" -type f -iname '*physical-authorization*.json' -print -quit)" ]
