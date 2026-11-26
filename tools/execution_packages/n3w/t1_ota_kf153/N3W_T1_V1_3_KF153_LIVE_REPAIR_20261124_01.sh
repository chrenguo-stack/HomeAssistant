#!/bin/bash
set -euo pipefail

HOST="${N3W_T1_SSH_TARGET:?N3W_T1_SSH_TARGET required}"
REPO="chrenguo-stack/HomeAssistant"
ARTIFACT_ID="14902399722"
ARTIFACT_SHA256="c19280ac1fcbca7ef0de10ba2a24c0e1993898b0de988693ae14cff2c8e63a66"
MANIFEST_SHA256="90e83d4c4ce2a25e6c9fbce0245344b8c3ba247a4b5ecc58d4e93c4ceb169877"
SOURCE_HEAD="90ce32ce4b6c329fd38c2771e352d129d6d00a86"
OLD_PYZ_SHA256="d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30"
NEW_PYZ_SHA256="5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a"
TX_SHA256="b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0"
REMOTE_STAGE="/tmp/n3w-kf153-live-repair-20261124-01"
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

ssh "$HOST" 'bash -s' -- "$TX_SHA256" "$OLD_PYZ_SHA256" "$NEW_PYZ_SHA256" "$REMOTE_STAGE" <<'REMOTE_EOF'
set -euo pipefail
EXPECTED_TX_SHA256="$1"
EXPECTED_OLD_PYZ_SHA256="$2"
EXPECTED_NEW_PYZ_SHA256="$3"
STAGE="$4"

LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
TX_FILE=/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json
NEW="$STAGE/new-ha-recovery.pyz"
OLD="$STAGE/old-ha-recovery.pyz"
TARGET_REF=local/n3w-homeassistant:2026.10.0-0c73235a
PRED_REF=local/n3w-homeassistant:2026.10.4-5881590f
PRED_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
MANAGER_REF=local/greenhouse-manager:fresh-1cae18039eee
MANAGER_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
BROKER_REF=local/n3w-mosquitto:2.1.2-3184566d
BROKER_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
EXPECTED_LAUNCH=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26

CONTROL_QUIESCED=false
PATCH_PUBLISHED=false
COMPLETED=false

atomic_publish() {
  src="$1"
  dst="$2"
  python3 - "$src" "$dst" <<'PY'
import os,stat,sys,tempfile
src,dst=sys.argv[1:3]
directory=os.path.dirname(dst)
fd,tmp=tempfile.mkstemp(prefix=".ha-recovery.pyz.kf153.",dir=directory)
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

runtime_check() {
  python3 - "$PRED_REF" "$PRED_ID" "$MANAGER_REF" "$MANAGER_ID" "$BROKER_REF" "$BROKER_ID" <<'PY'
import json,subprocess,sys
pairs=list(zip(sys.argv[1::2],sys.argv[2::2]))
for service,(ref,image_id) in zip(("homeassistant","manager","broker"),pairs):
    ids=subprocess.check_output([
        "docker","ps","-q","--no-trunc",
        "--filter","label=com.docker.compose.project=n3wfc4",
        "--filter",f"label=com.docker.compose.service={service}",
    ],text=True).split()
    if len(ids)!=1:
        raise SystemExit(f"RUNTIME_COUNT_DRIFT:{service}")
    doc=json.loads(subprocess.check_output(["docker","inspect",ids[0]],text=True))[0]
    if doc["Config"]["Image"]!=ref or doc["Image"]!=image_id or doc["State"]["Running"] is not True:
        raise SystemExit(f"RUNTIME_IDENTITY_DRIFT:{service}")
    if int(doc.get("RestartCount",0))!=0:
        raise SystemExit(f"RUNTIME_RESTART_DRIFT:{service}")
print("RUNTIME_IDENTITIES=PASS")
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
    if [ "$PATCH_PUBLISHED" = true ] && [ -f "$OLD" ]; then
      if [ "$CONTROL_QUIESCED" != true ]; then
        systemctl stop n3w-t1-ha-recovery-retry.timer
        systemctl stop n3w-t1-ha-recovery-retry.service
        systemctl stop n3w-t1-ha-ota-ipc.socket
        systemctl stop n3w-t1-ha-ota-ipc.service
        CONTROL_QUIESCED=true
      fi
      atomic_publish "$OLD" "$LIVE"
      if [ "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256" ]; then
        echo PATCH_ROLLBACK=PASS
      else
        echo PATCH_ROLLBACK=FAIL
      fi
    fi
    if [ "$CONTROL_QUIESCED" = true ]; then
      restore_control_plane
    fi
  fi
  echo RESULT=KF153_LIVE_REPAIR_STOP
  exit "$rc"
}
trap failure_recovery EXIT

echo PHASE=LIVE_PATCH_PRECHECK
test -f "$NEW"
test "$(sha256sum "$NEW" | awk '{print $1}')" = "$EXPECTED_NEW_PYZ_SHA256"
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256"
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"

python3 - "$TX_FILE" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
expected={
 "transaction_id_sha256":"afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3",
 "status":"ROLLED_BACK",
 "phase":"U8_RECOVERY_ADMISSION_COMPLETE",
 "failure_code":"ha_usb_release_predecessor_container_drift",
 "recovery_required":False,
 "authorization_claimed":False,
 "authorization_consumed":False,
 "authorization_id_sha256":None,
 "pre_cutover_predecessor_restored":True,
 "target_loaded_image_id":None,
 "target_activation":None,
}
for key,value in expected.items():
    if d.get(key)!=value:
        raise SystemExit(f"TX_DRIFT:{key}")
if "predecessor_release_intent" in d or "ha_data_restore" in d:
    raise SystemExit("TX_RECOVERY_DRIFT")
print("DURABLE_TERMINAL_TRANSACTION=PASS")
PY

test "$(systemctl is-active n3wfc4-services-activation.service)" = active
test "$(systemctl is-active n3wfc4-broker-activation.service)" = active
test "$(systemctl is-active n3w-t1-ha-recovery-retry.timer)" = active
test "$(systemctl is-enabled n3w-t1-ha-recovery-retry.timer)" = enabled
test "$(systemctl is-active n3w-t1-ha-ota-ipc.socket)" = active
test "$(systemctl is-enabled n3w-t1-ha-ota-ipc.socket)" = enabled
test "$(systemctl is-active n3w-t1-ha-recovery-retry.service)" = inactive
runtime_check
if docker image inspect "$TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_10_0_PRESENT=true
  exit 31
fi

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$EXPECTED_LAUNCH" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
d=json.load(open(sys.argv[2]))
binding=LocalHaPredecessorRuntime().capture_start_binding(d)
if binding["launch_sha256"]!=sys.argv[3]:
    raise SystemExit("LAUNCH_SHA_DRIFT")
print("PRE_PATCH_PREDECESSOR_BINDING=PASS")
PY

echo PHASE=QUIESCE_RECOVERY_CONTROL_PLANE
systemctl stop n3w-t1-ha-recovery-retry.timer
systemctl stop n3w-t1-ha-recovery-retry.service
systemctl stop n3w-t1-ha-ota-ipc.socket
systemctl stop n3w-t1-ha-ota-ipc.service
CONTROL_QUIESCED=true

test "$(systemctl is-active n3w-t1-ha-recovery-retry.timer)" = inactive
test "$(systemctl is-active n3w-t1-ha-recovery-retry.service)" = inactive
test "$(systemctl is-active n3w-t1-ha-ota-ipc.socket)" = inactive
test "$(systemctl is-active n3w-t1-ha-ota-ipc.service)" = inactive
test "$(systemctl is-active n3wfc4-services-activation.service)" = active
test "$(systemctl is-active n3wfc4-broker-activation.service)" = active
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"
runtime_check

echo PHASE=ATOMIC_PYZ_PATCH
install -m 0644 "$LIVE" "$OLD"
test "$(sha256sum "$OLD" | awk '{print $1}')" = "$EXPECTED_OLD_PYZ_SHA256"
atomic_publish "$NEW" "$LIVE"
PATCH_PUBLISHED=true
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_NEW_PYZ_SHA256"
/usr/bin/python3 -I "$LIVE" --help >/dev/null

echo PHASE=REARM_RECOVERY_CONTROL_PLANE
restore_control_plane
test "$(systemctl is-active n3w-t1-ha-ota-ipc.socket)" = active
test "$(systemctl is-active n3w-t1-ha-recovery-retry.timer)" = active
test "$(systemctl is-enabled n3w-t1-ha-ota-ipc.socket)" = enabled
test "$(systemctl is-enabled n3w-t1-ha-recovery-retry.timer)" = enabled
test "$(systemctl is-active n3w-t1-ha-recovery-retry.service)" = inactive
CONTROL_QUIESCED=false

echo PHASE=POST_PATCH_READONLY_CLOSURE
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"
test "$(systemctl is-active n3wfc4-services-activation.service)" = active
test "$(systemctl is-active n3wfc4-broker-activation.service)" = active
runtime_check
if docker image inspect "$TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_10_0_PRESENT=true
  exit 32
fi

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$EXPECTED_LAUNCH" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
d=json.load(open(sys.argv[2]))
binding=LocalHaPredecessorRuntime().capture_start_binding(d)
if binding["launch_sha256"]!=sys.argv[3]:
    raise SystemExit("POST_PATCH_LAUNCH_SHA_DRIFT")
print("POST_PATCH_PREDECESSOR_BINDING=PASS")
PY

rm -rf "$STAGE"
COMPLETED=true
trap - EXIT

echo LIVE_RECOVERY_PYZ_SHA256="$EXPECTED_NEW_PYZ_SHA256"
echo DURABLE_TRANSACTION_UNCHANGED=PASS
echo APPLICATION_RUNTIME_UNCHANGED=PASS
echo TARGET_10_0_PRESENT=false
echo RESULT=KF153_LIVE_REPAIR_PASS
REMOTE_EOF
