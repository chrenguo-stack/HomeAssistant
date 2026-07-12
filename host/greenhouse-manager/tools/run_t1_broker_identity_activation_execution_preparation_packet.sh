#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

usage() {
  cat <<'EOF'
Usage:
  run_t1_broker_identity_activation_execution_preparation_packet.sh \
    RUNTIME_ARTIFACT_DIRECTORY AUTHORIZATION_CONFIRMATION OUTPUT_DIRECTORY

Creates a short-lived authorization, transaction plan, adapter contract and final
execution request from a fresh read-only decision packet. It does not claim or
consume the authorization, restart a service, or modify live Broker files.
EOF
}

fail() {
  echo "T1 Broker activation execution preparation failed: $*" >&2
  exit 2
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
fi

[[ $# -eq 3 ]] || {
  usage >&2
  exit 2
}

RUNTIME_DIR=$1
CONFIRMATION=$2
OUTPUT=$3

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MANAGER_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
SOURCE="$MANAGER_ROOT/src"
TOOLS="$MANAGER_ROOT/tools"

[[ -d $RUNTIME_DIR && ! -L $RUNTIME_DIR ]] || \
  fail "runtime artifact directory is missing or unsafe"
[[ $(basename -- "$RUNTIME_DIR") == greenhouse-m2-runtime-bindings-* ]] || \
  fail "runtime artifact directory name is not allowed"
[[ $(stat -c '%a' "$RUNTIME_DIR") == 700 ]] || \
  fail "runtime artifact directory must be mode 0700"
RUNTIME_DIR=$(cd -- "$RUNTIME_DIR" && pwd)

[[ $(basename -- "$OUTPUT") == greenhouse-m2-execution-preparation-* ]] || \
  fail "output directory name is not allowed"
if [[ -e $OUTPUT && -L $OUTPUT ]]; then
  fail "output directory is a symbolic link"
fi
install -d -m 0700 "$OUTPUT"
OUTPUT=$(cd -- "$OUTPUT" && pwd)
[[ $(stat -c '%a' "$OUTPUT") == 700 ]] || \
  fail "output directory must be mode 0700"
[[ $OUTPUT != "$RUNTIME_DIR" && $OUTPUT != "$RUNTIME_DIR"/* ]] || \
  fail "output directory must be separate from runtime artifacts"

command -v docker >/dev/null || fail "docker not found"
command -v python3 >/dev/null || fail "python3 not found"

EXECUTOR="$RUNTIME_DIR/production-executor-contract.json"
DRIVER="$RUNTIME_DIR/production-driver-contract.json"
CAPTURE="$RUNTIME_DIR/runtime-binding-capture.json"
PREFLIGHT="$RUNTIME_DIR/production-driver-preflight.json"
HA_GATE="$RUNTIME_DIR/homeassistant-target-gate.json"
READINESS_SUMMARY="$RUNTIME_DIR/activation-readiness-summary.json"

for source_file in \
  "$EXECUTOR" "$DRIVER" "$CAPTURE" "$PREFLIGHT" "$HA_GATE" \
  "$READINESS_SUMMARY"; do
  [[ -f $source_file && ! -L $source_file ]] || \
    fail "required runtime artifact is missing: $(basename -- "$source_file")"
  [[ $(stat -c '%a' "$source_file") == 600 ]] || \
    fail "runtime artifact must be mode 0600: $(basename -- "$source_file")"
done

read -r READINESS_BUNDLE RUNTIME_MANIFEST < <(
  python3 - "$READINESS_SUMMARY" "$CAPTURE" "$RUNTIME_DIR" <<'PY'
import json
import pathlib
import sys

readiness_summary = pathlib.Path(sys.argv[1])
capture_file = pathlib.Path(sys.argv[2])
root = pathlib.Path(sys.argv[3])

with readiness_summary.open(encoding="utf-8") as stream:
    readiness = json.load(stream)
with capture_file.open(encoding="utf-8") as stream:
    capture = json.load(stream)

readiness_name = readiness.get("activation_readiness_file")
manifest_name = capture.get("runtime_binding_file")
for label, name in (
    ("readiness bundle", readiness_name),
    ("runtime manifest", manifest_name),
):
    if not isinstance(name, str) or "/" in name:
        raise SystemExit(f"{label} filename is invalid")

readiness_path = root / readiness_name
manifest_path = root / manifest_name
for label, path in (
    ("readiness bundle", readiness_path),
    ("runtime manifest", manifest_path),
):
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise SystemExit(f"{label} is missing or unsafe")

print(readiness_path, manifest_path)
PY
)

AUTH_DIR="$OUTPUT/greenhouse-m2-activation-authorizations"
PLAN_DIR="$OUTPUT/greenhouse-m2-activation-plans"
install -d -m 0700 "$AUTH_DIR" "$PLAN_DIR"

AUTH_SUMMARY="$OUTPUT/authorization-summary.json"
PLAN_SUMMARY="$OUTPUT/transaction-plan-summary.json"
ADAPTER_CONTRACT="$OUTPUT/production-transaction-adapter-contract.json"
EXECUTION_REQUEST="$OUTPUT/production-activation-execution-request.json"
BEFORE="$OUTPUT/runtime-before.txt"
AFTER="$OUTPUT/runtime-after.txt"

for destination in \
  "$AUTH_SUMMARY" "$PLAN_SUMMARY" "$ADAPTER_CONTRACT" \
  "$EXECUTION_REQUEST" "$BEFORE" "$AFTER"; do
  [[ ! -e $destination ]] || \
    fail "output destination already exists: $(basename -- "$destination")"
done

runtime_inventory() {
  docker inspect \
    -f '{{.Name}}|{{.State.Status}}|{{.RestartCount}}|{{.State.StartedAt}}|{{.Image}}' \
    mosquitto greenhouse-manager homeassistant
}

runtime_inventory > "$BEFORE"
chmod 0600 "$BEFORE"

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_activation_readiness_authorization.py" \
  create "$READINESS_BUNDLE" "$AUTH_DIR" \
  --confirmation "$CONFIRMATION" \
  --ttl-seconds 1800 \
  > "$AUTH_SUMMARY"
chmod 0600 "$AUTH_SUMMARY"

AUTHORIZATION_FILE=$(
  python3 - "$AUTH_SUMMARY" "$AUTH_DIR" <<'PY'
import json
import pathlib
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    summary = json.load(stream)
required = {
    "single_use": True,
    "operator_action_authorized": True,
    "apply_enabled": False,
    "ready_for_live_activation": False,
    "current_services_modified": False,
    "preserve_anonymous": True,
    "anonymous_closure_enabled": False,
}
for field, expected in required.items():
    if summary.get(field) is not expected:
        raise SystemExit(f"authorization creation failed: {field}")
name = summary.get("authorization_file")
if not isinstance(name, str) or "/" in name:
    raise SystemExit("authorization filename is invalid")
path = pathlib.Path(sys.argv[2]) / name
if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
    raise SystemExit("authorization file is missing or unsafe")
print(path)
PY
)

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_activation_readiness_transaction_plan.py" \
  build "$AUTHORIZATION_FILE" "$READINESS_BUNDLE" "$PLAN_DIR" \
  > "$PLAN_SUMMARY"
chmod 0600 "$PLAN_SUMMARY"

TRANSACTION_PLAN=$(
  python3 - "$PLAN_SUMMARY" "$PLAN_DIR" <<'PY'
import json
import pathlib
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    summary = json.load(stream)
required = {
    "transaction_plan_ready": True,
    "authorization_valid": True,
    "authorization_claimed": False,
    "claim_enabled": False,
    "production_transaction_adapters_installed": False,
    "production_executor_available": False,
    "execution_enabled": False,
    "apply_enabled": False,
    "ready_for_live_activation": False,
    "current_services_modified": False,
    "preserve_anonymous": True,
    "anonymous_closure_enabled": False,
}
for field, expected in required.items():
    if summary.get(field) is not expected:
        raise SystemExit(f"transaction plan creation failed: {field}")
name = summary.get("transaction_plan_file")
if not isinstance(name, str) or "/" in name:
    raise SystemExit("transaction plan filename is invalid")
path = pathlib.Path(sys.argv[2]) / name
if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
    raise SystemExit("transaction plan is missing or unsafe")
print(path)
PY
)

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_production_transaction_adapter_contract.py" \
  "$TRANSACTION_PLAN" > "$ADAPTER_CONTRACT"
chmod 0600 "$ADAPTER_CONTRACT"

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_production_activation_orchestrator.py" \
  request \
  "$AUTHORIZATION_FILE" \
  "$READINESS_BUNDLE" \
  "$TRANSACTION_PLAN" \
  "$ADAPTER_CONTRACT" \
  "$EXECUTOR" \
  "$RUNTIME_MANIFEST" \
  > "$EXECUTION_REQUEST"
chmod 0600 "$EXECUTION_REQUEST"

runtime_inventory > "$AFTER"
chmod 0600 "$AFTER"
cmp -s "$BEFORE" "$AFTER" || {
  diff -u "$BEFORE" "$AFTER" >&2 || true
  fail "service runtime identity changed during execution preparation"
}

python3 - "$AUTH_SUMMARY" "$PLAN_SUMMARY" "$EXECUTION_REQUEST" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    authorization = json.load(stream)
with open(sys.argv[2], encoding="utf-8") as stream:
    plan = json.load(stream)
with open(sys.argv[3], encoding="utf-8") as stream:
    request = json.load(stream)

required = {
    "execution_request_ready": True,
    "authorization_valid": True,
    "authorization_claimed": False,
    "production_transaction_adapters_installed": False,
    "production_executor_available": False,
    "execution_enabled": False,
    "apply_enabled": False,
    "ready_for_live_activation": False,
    "current_services_modified": False,
    "preserve_anonymous": True,
    "anonymous_closure_enabled": False,
    "secret_values_included": False,
    "path_values_redacted": True,
}
for field, expected in required.items():
    if request.get(field) is not expected:
        raise SystemExit(f"execution request failed: {field}")
confirmation = request.get("required_confirmation")
if not isinstance(confirmation, str) or re.fullmatch(
    r"EXECUTE-M2-BROKER-ACTIVATION:[0-9a-f]{16}:[0-9a-f]{16}:[0-9a-f]{16}",
    confirmation,
) is None:
    raise SystemExit("execution confirmation phrase is invalid")
print("ACTIVATION_AUTHORIZATION=" + json.dumps(
    authorization,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
))
print("ACTIVATION_TRANSACTION_PLAN=" + json.dumps(
    plan,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
))
print("PRODUCTION_EXECUTION_REQUEST=" + json.dumps(
    request,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
))
PY

echo "M2_4G_5W_EXECUTION_PREPARATION_PACKET=PASS"
echo "AUTHORIZATION_CREATED=true"
echo "AUTHORIZATION_CLAIMED=false"
echo "EXECUTION_REQUEST_READY=true"
echo "LIVE_ACTIVATION_EXECUTED=false"
echo "CURRENT_SERVICES_MODIFIED=false"
echo "PRESERVE_ANONYMOUS=true"
echo "ARTIFACT_DIR=$OUTPUT"
