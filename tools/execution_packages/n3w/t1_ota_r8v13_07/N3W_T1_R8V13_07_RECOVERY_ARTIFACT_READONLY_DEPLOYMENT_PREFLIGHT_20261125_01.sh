#!/bin/bash
set -euo pipefail

HOST="${N3W_T1_SSH_TARGET:?N3W_T1_SSH_TARGET required}"
REPO="chrenguo-stack/HomeAssistant"
ARTIFACT_ID="14997816032"
ARTIFACT_SHA256="0ed412bfc923755d13b9cbe3ab744f173d4281f9730c4ca1baa490272e96a517"
MANIFEST_SHA256="e28e6197c867da322528fbf144a1aa06d56a43b1a9ad91b5ba0ff6af51f96080"
SOURCE_HEAD="29ce1eb341289d0275ab064996a035e5d55ae430"
OLD_LIVE_PYZ_SHA256="9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa"
NEW_PYZ_SHA256="807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2"
TX_ID="f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a"
USB_UUID="b72ac2fc-79a0-4fb8-888e-f35b0114f959"
HA_REF="local/n3w-homeassistant:2026.10.4-5881590f"
HA_ID="sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"
TARGET_REF="local/n3w-homeassistant:2026.10.0-0c73235a"
TARGET_ID="sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ZIP="$TMP/recovery.zip"

echo PHASE=LOCAL_EXACT_ARTIFACT_READONLY_BINDING
META_DIGEST="$(gh api "repos/$REPO/actions/artifacts/$ARTIFACT_ID" --jq '.digest')"
META_EXPIRED="$(gh api "repos/$REPO/actions/artifacts/$ARTIFACT_ID" --jq '.expired')"
test "$META_DIGEST" = "sha256:$ARTIFACT_SHA256"
test "$META_EXPIRED" = "false"
gh api "repos/$REPO/actions/artifacts/$ARTIFACT_ID/zip" > "$ZIP"
test "$(shasum -a 256 "$ZIP" | awk '{print $1}')" = "$ARTIFACT_SHA256"

python3 - "$ZIP" "$SOURCE_HEAD" "$MANIFEST_SHA256" "$NEW_PYZ_SHA256" <<'PY'
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import PurePosixPath

archive, source_head, manifest_sha, pyz_sha = sys.argv[1:5]
with zipfile.ZipFile(archive) as zf:
    infos = zf.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise SystemExit("ARTIFACT_DUPLICATE_MEMBER")
    for info in infos:
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts or info.is_dir():
            raise SystemExit(f"ARTIFACT_MEMBER_INVALID:{info.filename}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if mode and not stat.S_ISREG(mode):
            raise SystemExit(f"ARTIFACT_MEMBER_NOT_REGULAR:{info.filename}")
    if "manifest.json" not in names:
        raise SystemExit("MANIFEST_MISSING")
    manifest_raw = zf.read("manifest.json")
    if hashlib.sha256(manifest_raw).hexdigest() != manifest_sha:
        raise SystemExit("MANIFEST_SHA_DRIFT")
    manifest = json.loads(manifest_raw)
    if manifest.get("schema") != "gh.n3w-t1-ha-recovery-install/1":
        raise SystemExit("MANIFEST_SCHEMA_DRIFT")
    if manifest.get("source_head") != source_head:
        raise SystemExit("MANIFEST_SOURCE_DRIFT")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(names) != set(files) | {"manifest.json"}:
        raise SystemExit("ARTIFACT_FILE_SET_DRIFT")
    for name, expected in files.items():
        if not isinstance(expected, str):
            raise SystemExit(f"MANIFEST_FILE_DIGEST_INVALID:{name}")
        observed = hashlib.sha256(zf.read(name)).hexdigest()
        if observed != expected:
            raise SystemExit(f"ARTIFACT_FILE_DIGEST_DRIFT:{name}")
    if files.get("ha-recovery.pyz") != pyz_sha:
        raise SystemExit("MANIFEST_PYZ_DRIFT")
print("LOCAL_ARTIFACT_BINDING=PASS")
print("MANIFEST_SOURCE_HEAD=" + source_head)
print("MANIFEST_SHA256=" + manifest_sha)
print("NEW_RECOVERY_PYZ_SHA256=" + pyz_sha)
PY

echo PHASE=SPARE_T1_READONLY_DEPLOYMENT_PREFLIGHT
ssh "$HOST" 'bash -s' --   "$TX_ID" "$OLD_LIVE_PYZ_SHA256" "$NEW_PYZ_SHA256" "$USB_UUID"   "$HA_REF" "$HA_ID" "$TARGET_REF" "$TARGET_ID" "$SOURCE_HEAD"   "$ARTIFACT_ID" "$ARTIFACT_SHA256" "$MANIFEST_SHA256" <<'REMOTE_EOF'
set -euo pipefail
EXPECTED_TX_ID="$1"
EXPECTED_OLD_LIVE_PYZ_SHA256="$2"
EXPECTED_NEW_PYZ_SHA256="$3"
EXPECTED_USB_UUID="$4"
EXPECTED_HA_REF="$5"
EXPECTED_HA_ID="$6"
EXPECTED_TARGET_REF="$7"
EXPECTED_TARGET_ID="$8"
EXPECTED_SOURCE_HEAD="$9"
EXPECTED_ARTIFACT_ID="${10}"
EXPECTED_ARTIFACT_SHA256="${11}"
EXPECTED_MANIFEST_SHA256="${12}"

TX_FILE=/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json
LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
ENV=/etc/n3wfc4/docker-compose.env

test -f "$TX_FILE"
test -f "$LIVE"
test -f "$ENV"

LIVE_SHA="$(sha256sum "$LIVE" | awk '{print $1}')"
TX_SHA="$(sha256sum "$TX_FILE" | awk '{print $1}')"
ENV_SHA="$(sha256sum "$ENV" | awk '{print $1}')"
test "$LIVE_SHA" = "$EXPECTED_OLD_LIVE_PYZ_SHA256"
test "$LIVE_SHA" != "$EXPECTED_NEW_PYZ_SHA256"

/usr/bin/python3 - "$TX_FILE" "$EXPECTED_TX_ID" <<'PY'
import json
import sys

path, tx_id = sys.argv[1:3]
document = json.load(open(path, encoding="utf-8"))
expected = {
    "transaction_id_sha256": tx_id,
    "status": "ROLLED_BACK",
    "phase": "U13B_ROLLED_BACK",
    "failure_code": "ha_usb_target_acceptance_evidence_unavailable",
    "recovery_required": False,
    "authorization_claimed": True,
    "authorization_consumed": True,
    "authorization_id_sha256": "de25e2d5c8ea8f183a6dca35048f6896c54d3876bea70f6c35afc847819ed136",
    "predecessor_release_observed": True,
}
for key, value in expected.items():
    if document.get(key) != value:
        raise SystemExit(f"TERMINAL_TX_DRIFT:{key}:{document.get(key)!r}")
if document.get("current_image_ref") != "local/n3w-homeassistant:2026.10.4-5881590f":
    raise SystemExit("TERMINAL_CURRENT_IMAGE_DRIFT")
if document.get("target_image_ref") != "local/n3w-homeassistant:2026.10.0-0c73235a":
    raise SystemExit("TERMINAL_TARGET_IMAGE_DRIFT")
if document.get("target_release_step") not in (None, "RELEASED"):
    raise SystemExit(f"TERMINAL_TARGET_RELEASE_DRIFT:{document.get('target_release_step')!r}")
if "predecessor_start" not in document:
    raise SystemExit("PREDECESSOR_START_MISSING")
print("TERMINAL_TRANSACTION=PASS")
PY

/usr/bin/python3 - "$ENV" <<'PY'
import sys
values = {}
for raw in open(sys.argv[1], encoding="utf-8"):
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key] = value
if values.get("GH_HOMEASSISTANT_IMAGE") != "local/n3w-homeassistant:2026.10.4-5881590f":
    raise SystemExit("RECOVERED_HA_IMAGE_ENV_DRIFT")
if values.get("GH_N3W_T1_OTA_INSTALLED_VERSION") != "2026.10.4":
    raise SystemExit("RECOVERED_HA_VERSION_ENV_DRIFT")
print("RECOVERED_ENV=PASS")
PY

test "$(docker image inspect "$EXPECTED_HA_REF" --format '{{.Id}}')" = "$EXPECTED_HA_ID"
if docker image inspect "$EXPECTED_TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_IMAGE_UNEXPECTEDLY_PRESENT=true
  exit 31
fi
if docker image inspect "$EXPECTED_TARGET_ID" >/dev/null 2>&1; then
  echo TARGET_IMAGE_ID_UNEXPECTEDLY_PRESENT=true
  exit 32
fi

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" <<'PY'
import json
import sys
sys.path.insert(0, sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

document = json.load(open(sys.argv[2], encoding="utf-8"))
runtime = LocalHaPredecessorRuntime()
binding, _ = runtime._restart_binding()
if binding != document["predecessor_start"]:
    raise SystemExit("RECOVERED_BINDING_DRIFT")
runtime.verify_resident_predecessor_health(document)
print("RECOVERED_RUNTIME_HEALTH=PASS")
print("RECOVERED_LAUNCH_SHA256=" + binding["launch_sha256"])
for name in ("manager", "broker", "homeassistant"):
    image = binding["images"][name]
    print(f"RUNTIME_{name.upper()}_REF=" + image["reference"])
    print(f"RUNTIME_{name.upper()}_ID=" + image["runtime_id"])
PY

test "$(systemctl is-active n3wfc4-services-activation.service)" = active
test "$(systemctl is-active n3wfc4-broker-activation.service)" = active
test "$(systemctl is-active n3w-t1-ha-recovery-retry.timer)" = active
test "$(systemctl is-enabled n3w-t1-ha-recovery-retry.timer)" = enabled
test "$(systemctl is-active n3w-t1-ha-ota-ipc.socket)" = active
test "$(systemctl is-enabled n3w-t1-ha-ota-ipc.socket)" = enabled

RETRY_SERVICE_STATE="$(systemctl is-active n3w-t1-ha-recovery-retry.service || true)"
IPC_SERVICE_STATE="$(systemctl is-active n3w-t1-ha-ota-ipc.service || true)"
USB_MOUNT_TARGET="$(findmnt --list --noheadings --source "UUID=$EXPECTED_USB_UUID" --output TARGET | awk 'NF{print; exit}')"
test -n "$USB_MOUNT_TARGET"
USB_SOURCE="$(findmnt --noheadings --target "$USB_MOUNT_TARGET" --output SOURCE | awk 'NF{print; exit}')"
USB_FSTYPE="$(findmnt --noheadings --target "$USB_MOUNT_TARGET" --output FSTYPE | awk 'NF{print; exit}')"
USB_OPTIONS="$(findmnt --noheadings --target "$USB_MOUNT_TARGET" --output OPTIONS | awk 'NF{print; exit}')"
read -r USB_SIZE_BYTES USB_USED_BYTES USB_AVAILABLE_BYTES < <(
  df -B1 --output=size,used,avail "$USB_MOUNT_TARGET" | awk 'NR==2{print $1,$2,$3}'
)
read -r ROOT_SIZE_BYTES ROOT_USED_BYTES ROOT_AVAILABLE_BYTES < <(
  df -B1 --output=size,used,avail / | awk 'NR==2{print $1,$2,$3}'
)

test "$TX_SHA" = "4b1cc60e5557b9bc338d3d0469d30aa94c7974c34a0c26dffae5caf9fde4b105"
echo TX_FILE_SHA256="$TX_SHA"
echo COMPOSE_ENV_SHA256="$ENV_SHA"
echo LIVE_RECOVERY_PYZ_SHA256="$LIVE_SHA"
echo RETRY_SERVICE_STATE="$RETRY_SERVICE_STATE"
echo RETRY_TIMER_STATE=active
echo IPC_SERVICE_STATE="$IPC_SERVICE_STATE"
echo IPC_SOCKET_STATE=active
echo USB_UUID="$EXPECTED_USB_UUID"
echo USB_MOUNT_TARGET="$USB_MOUNT_TARGET"
echo USB_SOURCE="$USB_SOURCE"
echo USB_FSTYPE="$USB_FSTYPE"
echo USB_OPTIONS="$USB_OPTIONS"
echo USB_SIZE_BYTES="$USB_SIZE_BYTES"
echo USB_USED_BYTES="$USB_USED_BYTES"
echo USB_AVAILABLE_BYTES="$USB_AVAILABLE_BYTES"
echo ROOT_SIZE_BYTES="$ROOT_SIZE_BYTES"
echo ROOT_USED_BYTES="$ROOT_USED_BYTES"
echo ROOT_AVAILABLE_BYTES="$ROOT_AVAILABLE_BYTES"
echo EXPECTED_SOURCE_HEAD="$EXPECTED_SOURCE_HEAD"
echo EXPECTED_ARTIFACT_ID="$EXPECTED_ARTIFACT_ID"
echo EXPECTED_ARTIFACT_SHA256="$EXPECTED_ARTIFACT_SHA256"
echo EXPECTED_MANIFEST_SHA256="$EXPECTED_MANIFEST_SHA256"
echo EXPECTED_NEW_PYZ_SHA256="$EXPECTED_NEW_PYZ_SHA256"
echo ARTIFACT_DELTA_FROM_LIVE_PYZ_ONLY=true
echo DEPLOYMENT_ELIGIBLE=true
echo LOCAL_ARTIFACT_TEMP_ONLY=true
echo T1_MUTATION=false
echo INSTALL_REPLAY=false
echo SECOND_TRANSACTION=false
echo RESULT=R8V13_07_RECOVERY_ARTIFACT_READONLY_DEPLOYMENT_PREFLIGHT_PASS
REMOTE_EOF
