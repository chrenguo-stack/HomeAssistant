#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

usage() {
  cat <<'EOF'
Usage:
  run_t1_broker_identity_production_activation_packet.sh \
    PREPARATION_ARTIFACT_DIRECTORY RUNTIME_ARTIFACT_DIRECTORY \
    HANDOFF_DIRECTORY EXPECTED_RETAINED_TOPIC EXECUTION_CONFIRMATION \
    TRANSACTION_DIRECTORY

Executes one fully bound Broker identity activation. This is a live operation:
Mosquitto configuration and data may change and Mosquitto is restarted. Home
Assistant and greenhouse-manager are not restarted or reconfigured, node
credentials are not delivered, and anonymous compatibility remains enabled.
EOF
}

fail() {
  echo "T1 Broker production activation packet failed: $*" >&2
  exit 2
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
fi

[[ $# -eq 6 ]] || {
  usage >&2
  exit 2
}

PREPARATION_DIR=$1
RUNTIME_DIR=$2
HANDOFF=$3
TOPIC=$4
CONFIRMATION=$5
TRANSACTION_DIR=$6

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MANAGER_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
SOURCE="$MANAGER_ROOT/src"
TOOLS="$MANAGER_ROOT/tools"

[[ -d $PREPARATION_DIR && ! -L $PREPARATION_DIR ]] || \
  fail "preparation artifact directory is missing or unsafe"
[[ $(basename -- "$PREPARATION_DIR") == greenhouse-m2-execution-preparation-* ]] || \
  fail "preparation artifact directory name is not allowed"
[[ $(stat -c '%a' "$PREPARATION_DIR") == 700 ]] || \
  fail "preparation artifact directory must be mode 0700"
PREPARATION_DIR=$(cd -- "$PREPARATION_DIR" && pwd)

[[ -d $RUNTIME_DIR && ! -L $RUNTIME_DIR ]] || \
  fail "runtime artifact directory is missing or unsafe"
[[ $(basename -- "$RUNTIME_DIR") == greenhouse-m2-runtime-bindings-* ]] || \
  fail "runtime artifact directory name is not allowed"
[[ $(stat -c '%a' "$RUNTIME_DIR") == 700 ]] || \
  fail "runtime artifact directory must be mode 0700"
RUNTIME_DIR=$(cd -- "$RUNTIME_DIR" && pwd)

[[ -d $HANDOFF && ! -L $HANDOFF ]] || \
  fail "activation handoff directory is missing or unsafe"
HANDOFF=$(cd -- "$HANDOFF" && pwd)
[[ $TOPIC == gh/* ]] || fail "expected retained topic must be in the gh namespace"

[[ $(basename -- "$TRANSACTION_DIR") == greenhouse-m2-production-transactions-* ]] || \
  fail "transaction directory name is not allowed"
if [[ -e $TRANSACTION_DIR && -L $TRANSACTION_DIR ]]; then
  fail "transaction directory is a symbolic link"
fi
install -d -m 0700 "$TRANSACTION_DIR"
TRANSACTION_DIR=$(cd -- "$TRANSACTION_DIR" && pwd)
[[ $(stat -c '%a' "$TRANSACTION_DIR") == 700 ]] || \
  fail "transaction directory must be mode 0700"
[[ $TRANSACTION_DIR != "$PREPARATION_DIR" && \
   $TRANSACTION_DIR != "$PREPARATION_DIR"/* && \
   $TRANSACTION_DIR != "$RUNTIME_DIR" && \
   $TRANSACTION_DIR != "$RUNTIME_DIR"/* ]] || \
  fail "transaction directory must be separate from source artifacts"

command -v docker >/dev/null || fail "docker not found"
command -v python3 >/dev/null || fail "python3 not found"

AUTH_SUMMARY="$PREPARATION_DIR/authorization-summary.json"
PLAN_SUMMARY="$PREPARATION_DIR/transaction-plan-summary.json"
ADAPTER_CONTRACT="$PREPARATION_DIR/production-transaction-adapter-contract.json"
EXECUTION_REQUEST="$PREPARATION_DIR/production-activation-execution-request.json"
EXECUTOR="$RUNTIME_DIR/production-executor-contract.json"
CAPTURE="$RUNTIME_DIR/runtime-binding-capture.json"
READINESS_SUMMARY="$RUNTIME_DIR/activation-readiness-summary.json"

for source_file in \
  "$AUTH_SUMMARY" "$PLAN_SUMMARY" "$ADAPTER_CONTRACT" "$EXECUTION_REQUEST" \
  "$EXECUTOR" "$CAPTURE" "$READINESS_SUMMARY"; do
  [[ -f $source_file && ! -L $source_file ]] || \
    fail "required artifact is missing: $(basename -- "$source_file")"
  [[ $(stat -c '%a' "$source_file") == 600 ]] || \
    fail "artifact must be mode 0600: $(basename -- "$source_file")"
done

read -r AUTHORIZATION_FILE TRANSACTION_PLAN READINESS_BUNDLE RUNTIME_MANIFEST < <(
  python3 - \
    "$AUTH_SUMMARY" "$PLAN_SUMMARY" "$READINESS_SUMMARY" "$CAPTURE" \
    "$PREPARATION_DIR" "$RUNTIME_DIR" <<'PY'
import json
import pathlib
import sys

auth_summary_file = pathlib.Path(sys.argv[1])
plan_summary_file = pathlib.Path(sys.argv[2])
readiness_summary_file = pathlib.Path(sys.argv[3])
capture_file = pathlib.Path(sys.argv[4])
preparation_root = pathlib.Path(sys.argv[5])
runtime_root = pathlib.Path(sys.argv[6])

with auth_summary_file.open(encoding="utf-8") as stream:
    auth_summary = json.load(stream)
with plan_summary_file.open(encoding="utf-8") as stream:
    plan_summary = json.load(stream)
with readiness_summary_file.open(encoding="utf-8") as stream:
    readiness_summary = json.load(stream)
with capture_file.open(encoding="utf-8") as stream:
    capture = json.load(stream)

names = (
    (preparation_root / "greenhouse-m2-activation-authorizations", auth_summary.get("authorization_file"), "authorization"),
    (preparation_root / "greenhouse-m2-activation-plans", plan_summary.get("transaction_plan_file"), "transaction plan"),
    (runtime_root, readiness_summary.get("activation_readiness_file"), "readiness bundle"),
    (runtime_root, capture.get("runtime_binding_file"), "runtime manifest"),
)
paths = []
for parent, name, label in names:
    if not isinstance(name, str) or "/" in name:
        raise SystemExit(f"{label} filename is invalid")
    path = parent / name
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise SystemExit(f"{label} is missing or unsafe")
    paths.append(path)
print(*paths)
PY
)

python3 - "$EXECUTION_REQUEST" "$CONFIRMATION" <<'PY'
import hmac
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
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
}
for field, expected in required.items():
    if request.get(field) is not expected:
        raise SystemExit(f"execution request is unsafe: {field}")
expected = request.get("required_confirmation")
if not isinstance(expected, str) or not hmac.compare_digest(expected, sys.argv[2]):
    raise SystemExit("execution confirmation does not match the prepared request")
PY

BEFORE="$TRANSACTION_DIR/runtime-before.json"
AFTER="$TRANSACTION_DIR/runtime-after.json"
RESULT="$TRANSACTION_DIR/execution-result.json"
for destination in "$BEFORE" "$AFTER" "$RESULT"; do
  [[ ! -e $destination ]] || \
    fail "transaction destination already exists: $(basename -- "$destination")"
done

docker inspect mosquitto greenhouse-manager homeassistant > "$BEFORE"
chmod 0600 "$BEFORE"

set +e
PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_production_activation_execute.py" \
  "$AUTHORIZATION_FILE" \
  "$READINESS_BUNDLE" \
  "$TRANSACTION_PLAN" \
  "$ADAPTER_CONTRACT" \
  "$EXECUTOR" \
  "$RUNTIME_MANIFEST" \
  "$HANDOFF" \
  "$TRANSACTION_DIR" \
  --expected-retained-topic "$TOPIC" \
  --execution-confirmation "$CONFIRMATION" \
  --enable-production-execution \
  > "$RESULT"
EXECUTION_RC=$?
set -e
chmod 0600 "$RESULT"

docker inspect mosquitto greenhouse-manager homeassistant > "$AFTER"
chmod 0600 "$AFTER"

python3 - "$BEFORE" "$AFTER" "$EXECUTION_RC" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    before_list = json.load(stream)
with open(sys.argv[2], encoding="utf-8") as stream:
    after_list = json.load(stream)
execution_rc = int(sys.argv[3])

def indexed(values):
    result = {}
    for item in values:
        name = str(item.get("Name", "")).removeprefix("/")
        result[name] = item
    return result

before = indexed(before_list)
after = indexed(after_list)
for name in ("mosquitto", "greenhouse-manager", "homeassistant"):
    if name not in before or name not in after:
        raise SystemExit(f"runtime inventory is missing: {name}")
    if after[name].get("State", {}).get("Status") != "running":
        raise SystemExit(f"service is not running after transaction: {name}")
    if before[name].get("Id") != after[name].get("Id"):
        raise SystemExit(f"container identity changed: {name}")
    if before[name].get("Image") != after[name].get("Image"):
        raise SystemExit(f"container image changed: {name}")

for name in ("greenhouse-manager", "homeassistant"):
    before_identity = (
        before[name].get("State", {}).get("StartedAt"),
        before[name].get("RestartCount"),
    )
    after_identity = (
        after[name].get("State", {}).get("StartedAt"),
        after[name].get("RestartCount"),
    )
    if before_identity != after_identity:
        raise SystemExit(f"non-target service runtime changed: {name}")

if execution_rc == 0:
    before_started = before["mosquitto"].get("State", {}).get("StartedAt")
    after_started = after["mosquitto"].get("State", {}).get("StartedAt")
    if before_started == after_started:
        raise SystemExit("Mosquitto restart was not observed on successful activation")
PY

if [[ $EXECUTION_RC -ne 0 ]]; then
  echo "M2_4G_5X_PRODUCTION_ACTIVATION=FAILED" >&2
  echo "EXECUTION_RC=$EXECUTION_RC" >&2
  echo "TRANSACTION_DIR=$TRANSACTION_DIR" >&2
  exit "$EXECUTION_RC"
fi

python3 - "$RESULT" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    report = json.load(stream)
required = {
    "authorization_claimed": True,
    "authorization_consumed": True,
    "mutation_completed": True,
    "postactivation_verified": True,
    "rollback_completed": False,
    "broker_identity_activated": True,
    "ready_for_homeassistant_reconfigure_handoff": True,
    "homeassistant_reconfigured": False,
    "node_credentials_delivered": False,
    "production_executor_available": True,
    "execution_enabled": True,
    "apply_enabled": True,
    "current_services_modified": True,
    "preserve_anonymous": True,
    "anonymous_closure_enabled": False,
    "secret_values_included": False,
    "path_values_redacted": True,
}
for field, expected in required.items():
    if report.get(field) is not expected:
        raise SystemExit(f"production activation result failed: {field}")
print("PRODUCTION_ACTIVATION_RESULT=" + json.dumps(
    report,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
))
PY

echo "M2_4G_5X_PRODUCTION_ACTIVATION=PASS"
echo "BROKER_IDENTITY_ACTIVATED=true"
echo "AUTHORIZATION_CLAIMED=true"
echo "AUTHORIZATION_CONSUMED=true"
echo "HOMEASSISTANT_RECONFIGURED=false"
echo "NODE_CREDENTIALS_DELIVERED=false"
echo "PRESERVE_ANONYMOUS=true"
echo "ANONYMOUS_CLOSURE_ENABLED=false"
echo "TRANSACTION_DIR=$TRANSACTION_DIR"
