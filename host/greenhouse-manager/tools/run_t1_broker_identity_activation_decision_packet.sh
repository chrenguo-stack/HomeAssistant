#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

usage() {
  cat <<'EOF'
Usage:
  run_t1_broker_identity_activation_decision_packet.sh \
    HANDOFF_DIRECTORY STAGE_DIRECTORY EXPECTED_RETAINED_TOPIC OUTPUT_DIRECTORY

Builds a fresh, read-only real-T1 activation decision packet. It does not create
an authorization, claim an authorization, restart services, or modify live files.
EOF
}

fail() {
  echo "T1 Broker activation decision packet failed: $*" >&2
  exit 2
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
fi

[[ $# -eq 4 ]] || {
  usage >&2
  exit 2
}

HANDOFF=$1
STAGE=$2
TOPIC=$3
OUTPUT=$4

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MANAGER_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
SOURCE="$MANAGER_ROOT/src"
TOOLS="$MANAGER_ROOT/tools"

[[ -d $HANDOFF && ! -L $HANDOFF ]] || fail "handoff directory is missing or unsafe"
[[ -d $STAGE && ! -L $STAGE ]] || fail "stage directory is missing or unsafe"
[[ $TOPIC == gh/* ]] || fail "expected retained topic must be in the gh namespace"
[[ $(basename -- "$OUTPUT") == greenhouse-m2-runtime-bindings-* ]] || \
  fail "output directory name is not allowed"
if [[ -e $OUTPUT && -L $OUTPUT ]]; then
  fail "output directory is a symbolic link"
fi
install -d -m 0700 "$OUTPUT"
OUTPUT=$(cd -- "$OUTPUT" && pwd)
[[ $(stat -c '%a' "$OUTPUT") == 700 ]] || fail "output directory must be mode 0700"

HA_GATE="$OUTPUT/homeassistant-target-gate.json"
EXECUTOR="$OUTPUT/production-executor-contract.json"
LIVE_GATE="$OUTPUT/live-mount-gate.json"
SKELETON="$OUTPUT/production-adapter-skeleton.json"
DRIVER="$OUTPUT/production-driver-contract.json"
CAPTURE="$OUTPUT/runtime-binding-capture.json"
PREFLIGHT="$OUTPUT/production-driver-preflight.json"
READINESS_SUMMARY="$OUTPUT/activation-readiness-summary.json"
AUTH_REQUEST="$OUTPUT/activation-authorization-request.json"
BEFORE="$OUTPUT/runtime-before.txt"
AFTER="$OUTPUT/runtime-after.txt"

for destination in \
  "$HA_GATE" "$EXECUTOR" "$LIVE_GATE" "$SKELETON" "$DRIVER" \
  "$CAPTURE" "$PREFLIGHT" "$READINESS_SUMMARY" "$AUTH_REQUEST" \
  "$BEFORE" "$AFTER"; do
  [[ ! -e $destination ]] || fail "output destination already exists: $(basename -- "$destination")"
done

command -v docker >/dev/null || fail "docker not found"
command -v python3 >/dev/null || fail "python3 not found"

runtime_inventory() {
  docker inspect \
    -f '{{.Name}}|{{.State.Status}}|{{.RestartCount}}|{{.State.StartedAt}}|{{.Image}}' \
    mosquitto greenhouse-manager homeassistant
}

runtime_inventory > "$BEFORE"
chmod 0600 "$BEFORE"

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_homeassistant_mqtt_target_gate.py" \
  "$STAGE" \
  --expected-retained-topic "$TOPIC" \
  > "$HA_GATE"
chmod 0600 "$HA_GATE"

read -r TARGET_KIND TARGET_FINGERPRINT ENTRY_FINGERPRINT STORAGE_SHA256 < <(
  python3 - "$HA_GATE" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    report = json.load(stream)

if report.get("schema") != "gh.m2.t1-homeassistant-mqtt-target-gate/1":
    raise SystemExit("Home Assistant target gate schema is invalid")
if report.get("read_only") is not True or report.get("target_model_ready") is not True:
    raise SystemExit("Home Assistant target gate is not ready")
official = report.get("homeassistant_official_reconfigure")
if not isinstance(official, dict):
    raise SystemExit("Home Assistant official reconfigure section is missing")
kind = report.get("selected_target_kind")
target = report.get("selected_target_fingerprint")
entry = official.get("pre_change_entry_fingerprint")
storage = official.get("pre_change_storage_sha256")
if kind not in {"loopback", "docker_service_alias", "host_address"}:
    raise SystemExit("Home Assistant target kind is invalid")
if not isinstance(target, str) or re.fullmatch(r"[0-9a-f]{16}", target) is None:
    raise SystemExit("Home Assistant target fingerprint is invalid")
if not isinstance(entry, str) or re.fullmatch(r"[0-9a-f]{16}", entry) is None:
    raise SystemExit("Home Assistant entry fingerprint is invalid")
if not isinstance(storage, str) or re.fullmatch(r"[0-9a-f]{64}", storage) is None:
    raise SystemExit("Home Assistant storage fingerprint is invalid")
print(kind, target, entry, storage)
PY
)

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_production_executor_contract.py" \
  "$HANDOFF" "$STAGE" > "$EXECUTOR"
chmod 0600 "$EXECUTOR"

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_live_mount_gate.py" \
  "$EXECUTOR" "$HANDOFF" "$STAGE" \
  --expected-retained-topic "$TOPIC" \
  > "$LIVE_GATE"
chmod 0600 "$LIVE_GATE"

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_production_adapter_skeleton.py" \
  "$EXECUTOR" "$LIVE_GATE" > "$SKELETON"
chmod 0600 "$SKELETON"

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_production_driver_contract.py" \
  "$EXECUTOR" "$SKELETON" "$LIVE_GATE" > "$DRIVER"
chmod 0600 "$DRIVER"

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_runtime_binding_manifest.py" \
  "$DRIVER" "$EXECUTOR" "$LIVE_GATE" "$OUTPUT" > "$CAPTURE"
chmod 0600 "$CAPTURE"

RUNTIME_MANIFEST=$(
  python3 - "$CAPTURE" "$OUTPUT" <<'PY'
import json
import pathlib
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    report = json.load(stream)
required = {
    "runtime_binding_captured": True,
    "read_only_capture": True,
    "production_driver_installed": False,
    "production_executor_available": False,
    "execution_enabled": False,
    "apply_enabled": False,
    "operator_action_authorized": False,
    "ready_for_live_activation": False,
    "current_services_modified": False,
    "preserve_anonymous": True,
    "anonymous_closure_enabled": False,
}
for field, expected in required.items():
    if report.get(field) is not expected:
        raise SystemExit(f"runtime capture failed: {field}")
name = report.get("runtime_binding_file")
if not isinstance(name, str) or "/" in name:
    raise SystemExit("runtime binding filename is invalid")
path = pathlib.Path(sys.argv[2]) / name
if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
    raise SystemExit("runtime binding file is missing or unsafe")
print(path)
PY
)

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_production_driver_preflight.py" \
  "$DRIVER" "$EXECUTOR" "$RUNTIME_MANIFEST" "$HANDOFF" "$STAGE" \
  --expected-retained-topic "$TOPIC" \
  --expected-target-kind "$TARGET_KIND" \
  --expected-target-fingerprint "$TARGET_FINGERPRINT" \
  --expected-entry-fingerprint "$ENTRY_FINGERPRINT" \
  --expected-storage-sha256 "$STORAGE_SHA256" \
  --max-manifest-age-seconds 1800 \
  > "$PREFLIGHT"
chmod 0600 "$PREFLIGHT"

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_activation_readiness_bundle.py" \
  "$DRIVER" "$EXECUTOR" "$RUNTIME_MANIFEST" "$PREFLIGHT" "$HA_GATE" "$OUTPUT" \
  --max-manifest-age-seconds 1800 \
  > "$READINESS_SUMMARY"
chmod 0600 "$READINESS_SUMMARY"

READINESS_BUNDLE=$(
  python3 - "$READINESS_SUMMARY" "$OUTPUT" <<'PY'
import json
import pathlib
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    report = json.load(stream)
required = {
    "readiness_bundle_complete": True,
    "operator_decision_required": True,
    "production_driver_installed": False,
    "production_executor_available": False,
    "execution_enabled": False,
    "apply_enabled": False,
    "operator_action_authorized": False,
    "ready_for_live_activation": False,
    "current_services_modified": False,
    "preserve_anonymous": True,
    "anonymous_closure_enabled": False,
}
for field, expected in required.items():
    if report.get(field) is not expected:
        raise SystemExit(f"readiness bundle failed: {field}")
name = report.get("activation_readiness_file")
if not isinstance(name, str) or "/" in name:
    raise SystemExit("readiness bundle filename is invalid")
path = pathlib.Path(sys.argv[2]) / name
if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
    raise SystemExit("readiness bundle is missing or unsafe")
print(path)
PY
)

PYTHONPATH="$SOURCE" \
python3 "$TOOLS/run_t1_broker_identity_activation_readiness_authorization.py" \
  request "$READINESS_BUNDLE" > "$AUTH_REQUEST"
chmod 0600 "$AUTH_REQUEST"

runtime_inventory > "$AFTER"
chmod 0600 "$AFTER"
cmp -s "$BEFORE" "$AFTER" || {
  diff -u "$BEFORE" "$AFTER" >&2 || true
  fail "service runtime identity changed during read-only decision-packet generation"
}

python3 - "$READINESS_SUMMARY" "$AUTH_REQUEST" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    readiness = json.load(stream)
with open(sys.argv[2], encoding="utf-8") as stream:
    request = json.load(stream)
required = {
    "authorization_created": False,
    "operator_action_authorized": False,
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
        raise SystemExit(f"authorization request failed: {field}")
confirmation = request.get("required_confirmation")
if not isinstance(confirmation, str) or re.fullmatch(
    r"AUTHORIZE-M2-BROKER-BUNDLE:[0-9a-f]{16}:[0-9a-f]{16}",
    confirmation,
) is None:
    raise SystemExit("authorization confirmation phrase is invalid")
print("ACTIVATION_READINESS=" + json.dumps(
    readiness,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
))
print("ACTIVATION_AUTHORIZATION_REQUEST=" + json.dumps(
    request,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
))
PY

echo "M2_4G_5R_ACTIVATION_DECISION_PACKET=PASS"
echo "OPERATOR_DECISION_REQUIRED=true"
echo "AUTHORIZATION_CREATED=false"
echo "CURRENT_SERVICES_MODIFIED=false"
echo "PRODUCTION_DRIVER_INSTALLED=false"
echo "EXECUTION_ENABLED=false"
echo "ARTIFACT_DIR=$OUTPUT"
