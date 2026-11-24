#!/bin/bash
set -euo pipefail

HOST="${N3W_T1_SSH_TARGET:?N3W_T1_SSH_TARGET required}"
REPO="chrenguo-stack/HomeAssistant"
ARTIFACT_ID="14939405227"
ARTIFACT_SHA256="9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5"
MANIFEST_SHA256="489aa375fda2b0fba76ee4e9bd30ab168ce9ee00feff05ee074af5b656d1eca8"
SOURCE_HEAD="a9b76d77c2a930a21089af7fe0cc814f4db60a9a"
OLD_PYZ_SHA256="5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a"
NEW_PYZ_SHA256="d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e"
TX_ID="d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4"
TX_SHA256="4c68793fb1909366aa9acee7c06b74f3bac12dfae8681b1c4a6407abd6d2bd44"
ENV_SHA256="8f4a73bfa8126f9e4ee993197cece40fddcdf140c994687a391014d627c0e8cc"
LIVE_LAUNCH_SHA256="955f0f69553f8f80639fab630dd23e23aec40d9e84a48f23536712701dbb1d05"
PREDECESSOR_LAUNCH_SHA256="67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26"
USB_MOUNT_TARGET="/mnt/n3w-ha-r8-predecessor"
REMOTE_STAGE="/tmp/n3w-r8v13-07-u10-live-repair-20261125-01"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ZIP="$TMP/recovery.zip"
PKG="$TMP/package"
mkdir -p "$PKG"

echo PHASE=LOCAL_ARTIFACT_BINDING
gh api "repos/$REPO/actions/artifacts/$ARTIFACT_ID/zip" > "$ZIP"
test "$(shasum -a 256 "$ZIP" | awk '{print $1}')" = "$ARTIFACT_SHA256"
unzip -q "$ZIP" -d "$PKG"
test "$(shasum -a 256 "$PKG/manifest.json" | awk '{print $1}')" = "$MANIFEST_SHA256"
test "$(shasum -a 256 "$PKG/ha-recovery.pyz" | awk '{print $1}')" = "$NEW_PYZ_SHA256"

python3 - "$PKG/manifest.json" "$SOURCE_HEAD" "$NEW_PYZ_SHA256" <<'PY'
import json,sys
manifest=json.load(open(sys.argv[1]))
if manifest.get("schema")!="gh.n3w-t1-ha-recovery-install/1":
    raise SystemExit("MANIFEST_SCHEMA_DRIFT")
if manifest.get("source_head")!=sys.argv[2]:
    raise SystemExit("MANIFEST_SOURCE_DRIFT")
if manifest.get("files",{}).get("ha-recovery.pyz")!=sys.argv[3]:
    raise SystemExit("MANIFEST_PYZ_DRIFT")
print("LOCAL_ARTIFACT_BINDING=PASS")
PY

echo PHASE=REMOTE_STAGE
ssh "$HOST" "set -euo pipefail; rm -rf '$REMOTE_STAGE'; install -d -m 700 '$REMOTE_STAGE'"
scp -q "$PKG/ha-recovery.pyz" "$HOST:$REMOTE_STAGE/new-ha-recovery.pyz"

ssh "$HOST" 'bash -s' --   "$TX_ID" "$TX_SHA256" "$ENV_SHA256" "$OLD_PYZ_SHA256" "$NEW_PYZ_SHA256"   "$LIVE_LAUNCH_SHA256" "$PREDECESSOR_LAUNCH_SHA256" "$USB_MOUNT_TARGET" "$REMOTE_STAGE" <<'REMOTE_EOF'
set -euo pipefail
EXPECTED_TX_ID="$1"
EXPECTED_TX_SHA256="$2"
EXPECTED_ENV_SHA256="$3"
EXPECTED_OLD_PYZ_SHA256="$4"
EXPECTED_NEW_PYZ_SHA256="$5"
EXPECTED_LIVE_LAUNCH_SHA256="$6"
EXPECTED_PREDECESSOR_LAUNCH_SHA256="$7"
EXPECTED_USB_MOUNT_TARGET="$8"
STAGE="$9"

LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
TX_FILE=/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json
ENV=/etc/n3wfc4/docker-compose.env
NEW="$STAGE/new-ha-recovery.pyz"
OLD="$STAGE/old-ha-recovery.pyz"
USB_UUID=b72ac2fc-79a0-4fb8-888e-f35b0114f959
TARGET_REF=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
PRED_REF=local/n3w-homeassistant:2026.10.4-5881590f
PRED_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
MANAGER_REF=local/greenhouse-manager:fresh-1cae18039eee
MANAGER_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
BROKER_REF=local/n3w-mosquitto:2.1.2-3184566d
BROKER_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563

CONTROL_QUIESCED=false
PATCH_PUBLISHED=false
RECOVERY_STARTED=false
COMPLETED=false

atomic_publish() {
  src="$1"
  dst="$2"
  python3 - "$src" "$dst" <<'PY'
import os,sys,tempfile
src,dst=sys.argv[1:3]
directory=os.path.dirname(dst)
fd,tmp=tempfile.mkstemp(prefix=".ha-recovery.pyz.r8v13-07.",dir=directory)
try:
    with os.fdopen(fd,"wb") as out, open(src,"rb") as inp:
        os.fchmod(out.fileno(),0o644)
        while True:
            block=inp.read(1024*1024)
            if not block:
                break
            out.write(block)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp,dst)
    dirfd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)
finally:
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
PY
}

restore_control_plane() {
  systemctl start n3w-t1-ha-ota-ipc.socket || true
  systemctl start n3w-t1-ha-recovery-retry.timer || true
}

failure_recovery() {
  rc=$?
  set +e
  if [ "$COMPLETED" != true ]; then
    if [ "$PATCH_PUBLISHED" = true ] && [ "$RECOVERY_STARTED" != true ] && [ -f "$OLD" ]; then
      systemctl stop n3w-t1-ha-recovery-retry.timer
      systemctl stop n3w-t1-ha-recovery-retry.service
      systemctl stop n3w-t1-ha-ota-ipc.socket
      systemctl stop n3w-t1-ha-ota-ipc.service
      CONTROL_QUIESCED=true
      atomic_publish "$OLD" "$LIVE"
      if [ "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256" ]; then
        echo PATCH_ROLLBACK=PASS
      else
        echo PATCH_ROLLBACK=FAIL
      fi
    fi
    restore_control_plane
  fi
  echo RECOVERY_STARTED="$RECOVERY_STARTED"
  echo RESULT=R8V13_07_U10_LIVE_REPAIR_AND_RECOVERY_STOP
  exit "$rc"
}
trap failure_recovery EXIT

candidate_recovery_check() {
  archive="$1"
  /usr/bin/python3 -I - "$archive" "$TX_FILE" "$EXPECTED_PREDECESSOR_LAUNCH_SHA256" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
d=json.load(open(sys.argv[2]))
r=LocalHaPredecessorRuntime()
if not r.rollback_writers_quiesced():
    raise SystemExit("ROLLBACK_WRITERS_NOT_QUIESCED")
if not r.observe_predecessor_released(d):
    raise SystemExit("PREDECESSOR_RELEASE_NOT_OBSERVED")
binding,_=r._verify_original_launch(d,allow_target_binding=True)
if binding != d["predecessor_start"]:
    raise SystemExit("PREDECESSOR_BINDING_DRIFT")
if binding["launch_sha256"] != sys.argv[3]:
    raise SystemExit("PREDECESSOR_LAUNCH_SHA_DRIFT")
print("CANDIDATE_RECOVERY_NORMALIZATION=PASS")
PY
}

echo PHASE=LIVE_REPAIR_PRECHECK
test -f "$TX_FILE"
test -f "$ENV"
test -f "$LIVE"
test -f "$NEW"
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"
test "$(sha256sum "$ENV" | awk '{print $1}')" = "$EXPECTED_ENV_SHA256"
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256"
test "$(sha256sum "$NEW" | awk '{print $1}')" = "$EXPECTED_NEW_PYZ_SHA256"

python3 - "$TX_FILE" "$EXPECTED_TX_ID" "$TARGET_ID" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
expected={
 "transaction_id_sha256":sys.argv[2],
 "status":"ACTIVE",
 "phase":"U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED",
 "failure_code":None,
 "recovery_required":True,
 "authorization_claimed":True,
 "authorization_consumed":True,
 "authorization_id_sha256":"6976d68fd1b6828b630fd05751c2855afd84efc65639753f1a318189fff62f50",
 "predecessor_release_observed":True,
 "target_loaded_image_id":sys.argv[3],
 "target_activation":"BINDING",
}
for key,value in expected.items():
    if d.get(key)!=value:
        raise SystemExit(f"TX_DRIFT:{key}:{d.get(key)!r}")
if d.get("current_image_ref")!="local/n3w-homeassistant:2026.10.4-5881590f":
    raise SystemExit("CURRENT_IMAGE_DRIFT")
if d.get("target_image_ref")!="local/n3w-homeassistant:2026.10.0-0c73235a":
    raise SystemExit("TARGET_IMAGE_DRIFT")
if "predecessor_start" not in d or "predecessor_release_intent" not in d:
    raise SystemExit("RECOVERY_JOURNAL_INCOMPLETE")
print("TRANSACTION_EXACT=PASS")
PY

python3 - "$ENV" <<'PY'
import sys
values={}
for raw in open(sys.argv[1],encoding="utf-8"):
    line=raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k,v=line.split("=",1)
    values[k]=v
if values.get("GH_HOMEASSISTANT_IMAGE")!="local/n3w-homeassistant:2026.10.0-0c73235a":
    raise SystemExit("HA_IMAGE_ENV_DRIFT")
if values.get("GH_N3W_T1_OTA_INSTALLED_VERSION")!="2026.10.0":
    raise SystemExit("HA_VERSION_ENV_DRIFT")
print("TARGET_ENV_EXACT=PASS")
PY

test "$(docker image inspect "$TARGET_REF" --format '{{.Id}}')" = "$TARGET_ID"
if docker image inspect "$PRED_REF" >/dev/null 2>&1; then
  echo PREDECESSOR_IMAGE_UNEXPECTEDLY_PRESENT=true
  exit 31
fi
if docker image inspect "$PRED_ID" >/dev/null 2>&1; then
  echo PREDECESSOR_IMAGE_ID_UNEXPECTEDLY_PRESENT=true
  exit 32
fi
test "$(docker image inspect "$MANAGER_REF" --format '{{.Id}}')" = "$MANAGER_ID"
test "$(docker image inspect "$BROKER_REF" --format '{{.Id}}')" = "$BROKER_ID"

RETRY_STATE="$(systemctl is-active n3w-t1-ha-recovery-retry.service || true)"
case "$RETRY_STATE" in
  inactive|failed) ;;
  *) echo "RETRY_SERVICE_NOT_QUIET=$RETRY_STATE"; exit 33 ;;
esac
test "$(systemctl is-active n3w-t1-ha-recovery-retry.timer)" = active
test "$(systemctl is-enabled n3w-t1-ha-recovery-retry.timer)" = enabled
test "$(systemctl is-active n3wfc4-broker-activation.service)" = active
MOUNT_TARGET="$(findmnt --list --noheadings --source "UUID=$USB_UUID" --output TARGET | awk 'NF{print; exit}')"
test "$MOUNT_TARGET" = "$EXPECTED_USB_MOUNT_TARGET"

OLD_LIVE_LAUNCH="$(/usr/bin/python3 -I - "$LIVE" <<'PY'
import sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
binding,_=LocalHaPredecessorRuntime()._restart_binding()
print(binding["launch_sha256"])
PY
)"
test "$OLD_LIVE_LAUNCH" = "$EXPECTED_LIVE_LAUNCH_SHA256"
candidate_recovery_check "$NEW"

echo PHASE=QUIESCE_RECOVERY_CONTROL_PLANE
systemctl stop n3w-t1-ha-recovery-retry.timer
systemctl stop n3w-t1-ha-recovery-retry.service
systemctl stop n3w-t1-ha-ota-ipc.socket
systemctl stop n3w-t1-ha-ota-ipc.service
CONTROL_QUIESCED=true
RETRY_TIMER_STATE="$(systemctl is-active n3w-t1-ha-recovery-retry.timer || true)"
RETRY_SERVICE_STATE="$(systemctl is-active n3w-t1-ha-recovery-retry.service || true)"
IPC_SOCKET_STATE="$(systemctl is-active n3w-t1-ha-ota-ipc.socket || true)"
IPC_SERVICE_STATE="$(systemctl is-active n3w-t1-ha-ota-ipc.service || true)"
echo QUIESCED_RETRY_TIMER_STATE="$RETRY_TIMER_STATE"
echo QUIESCED_RETRY_SERVICE_STATE="$RETRY_SERVICE_STATE"
echo QUIESCED_IPC_SOCKET_STATE="$IPC_SOCKET_STATE"
echo QUIESCED_IPC_SERVICE_STATE="$IPC_SERVICE_STATE"
test "$RETRY_TIMER_STATE" = inactive
case "$RETRY_SERVICE_STATE" in
  inactive|failed) ;;
  *) echo "RETRY_SERVICE_NOT_QUIET_AFTER_STOP=$RETRY_SERVICE_STATE"; exit 35 ;;
esac
case "$IPC_SOCKET_STATE" in
  inactive|failed) ;;
  *) echo "IPC_SOCKET_NOT_QUIET_AFTER_STOP=$IPC_SOCKET_STATE"; exit 36 ;;
esac
case "$IPC_SERVICE_STATE" in
  inactive|failed) ;;
  *) echo "IPC_SERVICE_NOT_QUIET_AFTER_STOP=$IPC_SERVICE_STATE"; exit 37 ;;
esac
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"
test "$(sha256sum "$ENV" | awk '{print $1}')" = "$EXPECTED_ENV_SHA256"
candidate_recovery_check "$NEW"

echo PHASE=ATOMIC_RECOVERY_PYZ_PATCH
install -m 0644 "$LIVE" "$OLD"
test "$(sha256sum "$OLD" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256"
atomic_publish "$NEW" "$LIVE"
PATCH_PUBLISHED=true
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_NEW_PYZ_SHA256"
/usr/bin/python3 -I "$LIVE" --help >/dev/null
candidate_recovery_check "$LIVE"

echo PHASE=EXECUTE_EXISTING_TRANSACTION_RECOVERY
systemctl start n3w-t1-ha-ota-ipc.socket
RECOVERY_STARTED=true
systemctl start n3w-t1-ha-recovery-retry.service
systemctl start n3w-t1-ha-recovery-retry.timer
CONTROL_QUIESCED=false

echo PHASE=VERIFY_TERMINAL_RECOVERY
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_NEW_PYZ_SHA256"
python3 - "$TX_FILE" "$EXPECTED_TX_ID" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
expected={
 "transaction_id_sha256":sys.argv[2],
 "status":"ROLLED_BACK",
 "phase":"U13B_ROLLED_BACK",
 "recovery_required":False,
 "authorization_claimed":True,
 "authorization_consumed":True,
 "authorization_id_sha256":"6976d68fd1b6828b630fd05751c2855afd84efc65639753f1a318189fff62f50",
 "predecessor_release_observed":True,
}
for key,value in expected.items():
    if d.get(key)!=value:
        raise SystemExit(f"TERMINAL_TX_DRIFT:{key}:{d.get(key)!r}")
print("TERMINAL_TRANSACTION=PASS")
PY

python3 - "$ENV" <<'PY'
import sys
values={}
for raw in open(sys.argv[1],encoding="utf-8"):
    line=raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k,v=line.split("=",1)
    values[k]=v
if values.get("GH_HOMEASSISTANT_IMAGE")!="local/n3w-homeassistant:2026.10.4-5881590f":
    raise SystemExit("RECOVERED_HA_IMAGE_ENV_DRIFT")
if values.get("GH_N3W_T1_OTA_INSTALLED_VERSION")!="2026.10.4":
    raise SystemExit("RECOVERED_HA_VERSION_ENV_DRIFT")
print("RECOVERED_ENV=PASS")
PY

test "$(docker image inspect "$PRED_REF" --format '{{.Id}}')" = "$PRED_ID"
if docker image inspect "$TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_IMAGE_STILL_PRESENT=true
  exit 34
fi

test "$(systemctl is-active n3wfc4-services-activation.service)" = active
test "$(systemctl is-active n3wfc4-broker-activation.service)" = active
test "$(systemctl is-active n3w-t1-ha-recovery-retry.timer)" = active
test "$(systemctl is-enabled n3w-t1-ha-recovery-retry.timer)" = enabled
test "$(systemctl is-active n3w-t1-ha-ota-ipc.socket)" = active

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$PREDECESSOR_LAUNCH_SHA256" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
d=json.load(open(sys.argv[2]))
r=LocalHaPredecessorRuntime()
binding,_=r._restart_binding()
if binding != d["predecessor_start"]:
    raise SystemExit("RECOVERED_BINDING_DRIFT")
if binding["launch_sha256"] != sys.argv[3]:
    raise SystemExit("RECOVERED_LAUNCH_SHA_DRIFT")
r.verify_resident_predecessor_health(d)
print("RECOVERED_RUNTIME_HEALTH=PASS")
PY

POST_TX_SHA="$(sha256sum "$TX_FILE" | awk '{print $1}')"
POST_ENV_SHA="$(sha256sum "$ENV" | awk '{print $1}')"
rm -rf "$STAGE"
COMPLETED=true
trap - EXIT

echo LIVE_RECOVERY_PYZ_SHA256="$EXPECTED_NEW_PYZ_SHA256"
echo POST_RECOVERY_TX_FILE_SHA256="$POST_TX_SHA"
echo POST_RECOVERY_COMPOSE_ENV_SHA256="$POST_ENV_SHA"
echo INSTALL_REPLAY=false
echo SECOND_TRANSACTION=false
echo RESULT=R8V13_07_U10_LIVE_REPAIR_AND_RECOVERY_PASS
REMOTE_EOF
