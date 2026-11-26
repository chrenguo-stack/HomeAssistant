#!/bin/bash
set -euo pipefail

test "${N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_APPROVED:-}" = "YES"

HOST="${N3W_T1_SSH_TARGET:?N3W_T1_SSH_TARGET required}"
EXPECTED_OLD_TX_FILE_SHA256="795c89ce2a7b10246da381ed205e7bf3f77c2561197d1d6a6e4ac2fb9e332eed"
EXPECTED_OLD_TX_ID="d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4"
EXPECTED_PYZ_SHA256="9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa"
EXPECTED_USB_UUID="b72ac2fc-79a0-4fb8-888e-f35b0114f959"
EXPECTED_MANIFEST_SHA256="5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36"
EXPECTED_TARGET_SHA256="e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663"
EXPECTED_TARGET_SIZE="2448553472"
EXPECTED_LAUNCH_SHA256="67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26"
EXPECTED_PREPARE_AUTH_SHA256="9eb8f178020cbba23a0436c1b914bf82f9ccb7a499e8845c64fa2492955cdf79"
EXPECTED_INSTALL_AUTH_SHA256="304683dee3ff75785215710c5a4a8ffbb12ae0b0912101474b969a46e035c83b"
EXPECTED_RELEASE_PIN_SHA256="2df25242a476d28758b5de4c78f6d6c11bd85a71b49aa27d5c845345513c1cc6"

ssh "$HOST" 'bash -s' -- "$EXPECTED_OLD_TX_FILE_SHA256" "$EXPECTED_OLD_TX_ID" "$EXPECTED_PYZ_SHA256" "$EXPECTED_USB_UUID" "$EXPECTED_MANIFEST_SHA256" "$EXPECTED_TARGET_SHA256" "$EXPECTED_TARGET_SIZE" "$EXPECTED_LAUNCH_SHA256" "$EXPECTED_PREPARE_AUTH_SHA256" "$EXPECTED_INSTALL_AUTH_SHA256" "$EXPECTED_RELEASE_PIN_SHA256" <<'REMOTE_EOF'
set -euo pipefail

EXPECTED_OLD_TX_FILE_SHA256="$1"
EXPECTED_OLD_TX_ID="$2"
EXPECTED_PYZ_SHA256="$3"
EXPECTED_USB_UUID="$4"
EXPECTED_MANIFEST_SHA256="$5"
EXPECTED_TARGET_SHA256="$6"
EXPECTED_TARGET_SIZE="$7"
EXPECTED_LAUNCH_SHA256="$8"
EXPECTED_PREPARE_AUTH_SHA256="$9"
EXPECTED_INSTALL_AUTH_SHA256="${10}"
EXPECTED_RELEASE_PIN_SHA256="${11}"

ROOT=/var/lib/n3w-t1-core-updater
TX_FILE="$ROOT/homeassistant-usb-upgrade.json"
LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
APPROVED=/run/n3w/t1-ota/approved-homeassistant.json
PREPARE_AUTH="$ROOT/ha-prepare-authority.json"
INSTALL_AUTH="$ROOT/ha-install-authority.json"
TARGET_REF=local/n3w-homeassistant:2026.10.0-0c73235a
PRED_REF=local/n3w-homeassistant:2026.10.4-5881590f
MANAGER_REF=local/greenhouse-manager:fresh-1cae18039eee
BROKER_REF=local/n3w-mosquitto:2.1.2-3184566d
RELEASE=homeassistant-r8-predecessor-2026.10.0
REMOTE_STAGE=/tmp/n3w-r8v13-07-new-fresh-tx-a-prepare-20261125-02
MUTATION_STARTED=false

summary() {
python3 - "$TX_FILE" <<'PY'
import json,sys
try:
    d=json.load(open(sys.argv[1]))
except Exception as exc:
    print("SUMMARY_READ_ERROR="+type(exc).__name__)
    raise SystemExit(0)
for key in (
    "transaction_id_sha256","status","phase","failure_code","recovery_required",
    "authorization_claimed","authorization_consumed","authorization_id_sha256",
    "usb_filesystem_uuid","current_image_ref","target_image_ref",
):
    print(f"{key.upper()}={json.dumps(d.get(key),separators=(',',':'))}")
print("PREDECESSOR_START_PRESENT="+str("predecessor_start" in d).lower())
PY
}

stop() {
  rc=$?
  echo NEW_FRESH_TRANSACTION_A_PREPARE_RESULT=STOP
  echo EXIT_CODE="$rc"
  echo MUTATION_STARTED="$MUTATION_STARTED"
  summary || true
  if [ "$MUTATION_STARTED" = true ]; then
    echo DO_NOT_REPLAY_WITHOUT_DURABLE_CLASSIFICATION=true
  fi
  exit "$rc"
}
trap stop ERR

echo PHASE=PREMUTATION_REBIND

test -f "$TX_FILE"
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_OLD_TX_FILE_SHA256"
test -f "$LIVE"
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_PYZ_SHA256"
test -f "$APPROVED"
test "$(sha256sum "$APPROVED" | awk '{print $1}')" = "$EXPECTED_MANIFEST_SHA256"
test -f "$PREPARE_AUTH"
test "$(sha256sum "$PREPARE_AUTH" | awk '{print $1}')" = "$EXPECTED_PREPARE_AUTH_SHA256"
test -f "$INSTALL_AUTH"
test "$(sha256sum "$INSTALL_AUTH" | awk '{print $1}')" = "$EXPECTED_INSTALL_AUTH_SHA256"
test -f "$ROOT/ha-release-pin.json"
test "$(sha256sum "$ROOT/ha-release-pin.json" | awk '{print $1}')" = "$EXPECTED_RELEASE_PIN_SHA256"
python3 - "$PREPARE_AUTH" "$INSTALL_AUTH" "$ROOT/ha-release-pin.json" <<'PY'
import json,sys,time
for path in sys.argv[1:]:
    d=json.load(open(path))
    expiry=d.get("expires_at_unix")
    if type(expiry) is not int or expiry>time.time():
        raise SystemExit("EXPECTED_OLD_AUTHORITY_NOT_EXPIRED:"+path)
print("OLD_AUTHORITIES_AND_RELEASE_PIN_EXPIRED=PASS")
PY
test ! -e "$REMOTE_STAGE"
mkdir -m 700 "$REMOTE_STAGE"

python3 - "$TX_FILE" "$EXPECTED_OLD_TX_ID" "$EXPECTED_USB_UUID" "$PRED_REF" "$TARGET_REF" <<'PY'
import json,sys
path,old_id,uuid,pred,target=sys.argv[1:]
d=json.load(open(path))
expected={
    "transaction_id_sha256": old_id,
    "status": "ROLLED_BACK",
    "phase": "U13B_ROLLED_BACK",
    "failure_code": None,
    "recovery_required": False,
    "authorization_claimed": True,
    "authorization_consumed": True,
    "authorization_id_sha256": "6976d68fd1b6828b630fd05751c2855afd84efc65639753f1a318189fff62f50",
    "predecessor_release_observed": True,
    "usb_filesystem_uuid": uuid,
    "current_image_ref": pred,
    "target_image_ref": target,
}
for key,value in expected.items():
    if d.get(key)!=value:
        raise SystemExit(f"OLD_TERMINAL_DRIFT:{key}:{d.get(key)!r}")
if "predecessor_start" not in d:
    raise SystemExit("OLD_TERMINAL_PREDECESSOR_START_MISSING")
if d.get("target_release_step") not in (None,"RELEASED"):
    raise SystemExit("OLD_TERMINAL_TARGET_RELEASE_DRIFT")
print("OLD_TRANSACTION_TERMINAL_NO_REPLAY=PASS")
PY

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$PRED_REF" "$MANAGER_REF" "$BROKER_REF" "$EXPECTED_LAUNCH_SHA256" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
_,live,txp,pred,manager,broker,expected_launch=sys.argv
d=json.load(open(txp))
runtime=LocalHaPredecessorRuntime()
binding=runtime.capture_start_binding(d)
if binding["images"]["homeassistant"]["reference"]!=pred:
    raise SystemExit("HOMEASSISTANT_RUNTIME_DRIFT")
if binding["images"]["manager"]["reference"]!=manager:
    raise SystemExit("MANAGER_RUNTIME_DRIFT")
if binding["images"]["broker"]["reference"]!=broker:
    raise SystemExit("BROKER_RUNTIME_DRIFT")
evidence=runtime.acceptance_observer().run_monitoring_self_test()
if evidence.verdict!="PASS":
    raise SystemExit("MANAGER_BROKER_HA_SELF_TEST_FAILED")
if binding["launch_sha256"]!=expected_launch:
    raise SystemExit("PREMUTATION_LAUNCH_SHA_DRIFT")
print("PREMUTATION_RUNTIME=PASS")
print("PREMUTATION_LAUNCH_SHA256="+binding["launch_sha256"])
print("PREMUTATION_SELF_TEST_SHA256="+evidence.sha256)
PY

if docker image inspect "$TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_10_0_PRESENT_BEFORE_PREPARE=true
  false
else
  echo TARGET_10_0_PRESENT_BEFORE_PREPARE=false
fi

SOURCE=$(/usr/bin/python3 -I - "$LIVE" "$EXPECTED_USB_UUID" "$EXPECTED_OLD_TX_ID" "$EXPECTED_TARGET_SIZE" <<'PY'
import os,stat,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
_,live,uuid,txid,size=sys.argv
mount=LocalHaPredecessorRuntime()._original_mountpoint(uuid)
source=mount/"N3W-OTA"/txid/"target.tar"
info=source.lstat()
if (
    not stat.S_ISREG(info.st_mode)
    or stat.S_IMODE(info.st_mode)!=0o600
    or info.st_uid!=0
    or info.st_nlink!=1
    or info.st_size!=int(size)
):
    raise SystemExit("OLD_USB_TARGET_SOURCE_METADATA_DRIFT")
print(source)
PY
)
test "$(sha256sum "$SOURCE" | awk '{print $1}')" = "$EXPECTED_TARGET_SHA256"
echo OLD_USB_TARGET_SOURCE=PASS
echo OLD_USB_TARGET_SOURCE_PATH="$SOURCE"

python3 - "$ROOT" "$EXPECTED_TARGET_SHA256" "$EXPECTED_TARGET_SIZE" <<'PY'
import hashlib,os,stat,sys
from pathlib import Path
root,digest,size_raw=sys.argv[1:]
size=int(size_raw)
candidate=Path(root)/f"ha-target-{digest}.tar"
v=os.statvfs("/")
block=v.f_frsize
available=v.f_bavail*block
if candidate.exists():
    info=candidate.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600 or info.st_uid!=0 or info.st_size!=size:
        raise SystemExit("INTERNAL_CANDIDATE_EXISTING_METADATA_DRIFT")
    h=hashlib.sha256()
    with candidate.open("rb") as stream:
        while True:
            part=stream.read(1024*1024)
            if not part:
                break
            h.update(part)
    if h.hexdigest()!=digest:
        raise SystemExit("INTERNAL_CANDIDATE_EXISTING_SHA_DRIFT")
    required=block
    print("INTERNAL_CANDIDATE_PREEXISTING_EXACT=true")
else:
    required=((size+block-1)//block)*block+block
    print("INTERNAL_CANDIDATE_PREEXISTING_EXACT=false")
print("ROOT_AVAILABLE_BYTES="+str(available))
print("INTERNAL_CANDIDATE_REQUIRED_BYTES="+str(required))
if available<required:
    raise SystemExit("INTERNAL_CANDIDATE_SPACE_INSUFFICIENT")
print("INTERNAL_CANDIDATE_CAPACITY=PASS")
PY

echo PHASE=MATERIALIZE_FRESH_CANDIDATE
MUTATION_STARTED=true
EXPIRES_AT_UNIX="$(($(date +%s)+21600))"
/usr/bin/python3 -I "$LIVE" materialize-candidate   --approved-manifest "$APPROVED"   --approved-manifest-sha256 "$EXPECTED_MANIFEST_SHA256"   --target-archive "$SOURCE"   --expires-at-unix "$EXPIRES_AT_UNIX" > "$REMOTE_STAGE/materialize.json"

TARGET_SOURCE=$(python3 - "$REMOTE_STAGE/materialize.json" "$RELEASE" <<'PY'
import json,sys
path,release=sys.argv[1:]
d=json.load(open(path))
if d.get("status")!="CANDIDATE_MATERIALIZED" or d.get("release_identity")!=release:
    raise SystemExit("CANDIDATE_MATERIALIZATION_RESULT_INVALID")
target=d.get("target_source")
if not isinstance(target,str) or not target.startswith("/"):
    raise SystemExit("CANDIDATE_TARGET_SOURCE_INVALID")
print(target)
PY
)
echo CANDIDATE_MATERIALIZATION=PASS
echo CANDIDATE_TARGET_SOURCE="$TARGET_SOURCE"
test "$(sha256sum "$TARGET_SOURCE" | awk '{print $1}')" = "$EXPECTED_TARGET_SHA256"
/usr/bin/python3 -I - "$LIVE" "$ROOT/ha-release-pin.json" "$APPROVED" "$RELEASE" "$EXPECTED_MANIFEST_SHA256" <<'PY'
import hashlib,json,sys,time
from pathlib import Path
live,pin_path,manifest_path,release,manifest_sha=sys.argv[1:]
sys.path.insert(0,live)
from n3w_t1_core_updater_ha_ipc import LocalApprovedHaRelease
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
pin=json.load(open(pin_path))
if pin.get("schema")!="gh.n3w-t1-ha-release-pin/1":
    raise SystemExit("REFRESHED_RELEASE_PIN_SCHEMA_DRIFT")
if pin.get("manifest_sha256")!=manifest_sha:
    raise SystemExit("REFRESHED_RELEASE_PIN_MANIFEST_DRIFT")
if type(pin.get("expires_at_unix")) is not int or pin["expires_at_unix"]<=time.time():
    raise SystemExit("REFRESHED_RELEASE_PIN_EXPIRED")
if hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()!=manifest_sha:
    raise SystemExit("REFRESHED_APPROVED_MANIFEST_DRIFT")
resolver=LocalApprovedHaRelease(
    Path(pin_path),Path(manifest_path),
    lambda: LocalHaPredecessorRuntime()._runtime("homeassistant"),
)
admission=resolver.resolve_homeassistant_release(release)
if admission.release_identity!=release:
    raise SystemExit("REFRESHED_RELEASE_ADMISSION_DRIFT")
print("RELEASE_AUTHORITY_REFRESH=PASS")
print("REFRESHED_RELEASE_PIN_EXPIRES_AT_UNIX="+str(pin["expires_at_unix"]))
PY

echo PHASE=CREATE_NEW_FRESH_TRANSACTION_A
/usr/bin/python3 -I "$LIVE"   --maintenance-submit-approved-release PREPARE   --release-identity "$RELEASE" > "$REMOTE_STAGE/prepare-submit.json"

NEW_TX=$(python3 - "$TX_FILE" "$EXPECTED_OLD_TX_ID" "$PRED_REF" "$TARGET_REF" <<'PY'
import json,sys
path,old_id,pred,target=sys.argv[1:]
d=json.load(open(path))
if d["transaction_id_sha256"]==old_id:
    raise SystemExit("FRESH_TRANSACTION_ID_REUSED")
if d["status"]!="ACTIVE" or d["phase"]!="U1_PREPARE_REQUESTED":
    raise SystemExit("FRESH_TRANSACTION_U1_INVALID")
if d["current_image_ref"]!=pred or d["target_image_ref"]!=target:
    raise SystemExit("FRESH_TRANSACTION_DIRECTION_INVALID")
if d["recovery_required"] or d["authorization_claimed"] or d["authorization_consumed"]:
    raise SystemExit("FRESH_TRANSACTION_AUTHORIZATION_DRIFT")
if d.get("authorization_id_sha256") is not None:
    raise SystemExit("FRESH_TRANSACTION_AUTHORIZATION_ID_DRIFT")
print(d["transaction_id_sha256"])
PY
)
echo NEW_FRESH_TRANSACTION_ID="$NEW_TX"
echo NEW_FRESH_TRANSACTION_U1=PASS

echo PHASE=ISSUE_NEW_PREPARE_AUTHORITY
REQ="$REMOTE_STAGE/prepare-authority-request.json"
python3 - "$REQ" "$NEW_TX" "$EXPECTED_USB_UUID" "$TARGET_SOURCE" <<'PY'
import json,os,sys,time
out,tx,uuid,target=sys.argv[1:]
request={
    "transaction_id_sha256":tx,
    "expires_at_unix":int(time.time())+21600,
    "usb_filesystem_uuid":uuid,
    "target_source":target,
}
fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"w") as stream:
    json.dump(request,stream,sort_keys=True,separators=(",",":"))
    stream.write("\n")
    stream.flush()
    os.fsync(stream.fileno())
print("PREPARE_AUTHORITY_REQUEST_CREATED=PASS")
PY
/usr/bin/python3 -I "$LIVE" --issue-prepare-authority "$REQ"

python3 - "$PREPARE_AUTH" "$NEW_TX" "$EXPECTED_USB_UUID" "$TARGET_SOURCE" <<'PY'
import json,sys,time
path,tx,uuid,target=sys.argv[1:]
d=json.load(open(path))
if d.get("schema")!="gh.n3w-t1-ha-prepare-authority/2":
    raise SystemExit("PREPARE_AUTHORITY_SCHEMA_INVALID")
if d.get("transaction_id_sha256")!=tx or d.get("usb_filesystem_uuid")!=uuid:
    raise SystemExit("PREPARE_AUTHORITY_BINDING_INVALID")
if d.get("target_source")!=target:
    raise SystemExit("PREPARE_AUTHORITY_SOURCE_INVALID")
if type(d.get("expires_at_unix")) is not int or d["expires_at_unix"]<=time.time():
    raise SystemExit("PREPARE_AUTHORITY_EXPIRY_INVALID")
print("NEW_PREPARE_AUTHORITY=PASS")
PY

echo PHASE=PREPARE_TO_FRESH_U4
/usr/bin/python3 -I "$LIVE" --resume-pending > "$REMOTE_STAGE/resume.json"

echo PHASE=FINAL_U4_CLASSIFICATION
/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$NEW_TX" "$EXPECTED_USB_UUID" "$PRED_REF" "$TARGET_REF" "$EXPECTED_TARGET_SHA256" "$EXPECTED_TARGET_SIZE" "$INSTALL_AUTH" <<'PY'
import json,os,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime, requested_install_binding_sha256
_,live,txp,tx,uuid,pred,target,target_sha,target_size,install_auth=sys.argv
d=json.load(open(txp))
if d["transaction_id_sha256"]!=tx:
    raise SystemExit("FINAL_TRANSACTION_ID_DRIFT")
if d["status"]!="ACTIVE" or d["phase"]!="U4_READY_TO_INSTALL":
    raise SystemExit("FINAL_U4_NOT_REACHED")
if d["current_image_ref"]!=pred or d["target_image_ref"]!=target:
    raise SystemExit("FINAL_DIRECTION_DRIFT")
if d.get("usb_binding_mode")!="existing_filesystem" or d.get("usb_filesystem_uuid")!=uuid:
    raise SystemExit("FINAL_USB_BINDING_DRIFT")
if d.get("target_artifact_verified") is not True:
    raise SystemExit("FINAL_TARGET_NOT_VERIFIED")
if d["authorization_claimed"] or d["authorization_consumed"] or d.get("authorization_id_sha256") is not None:
    raise SystemExit("FINAL_AUTHORIZATION_DRIFT")
if "predecessor_start" in d:
    raise SystemExit("FINAL_PREDECESSOR_START_UNEXPECTED")
materials=d.get("prepared_image_materials")
if not isinstance(materials,dict):
    raise SystemExit("FINAL_PREPARED_MATERIALS_MISSING")
tm=materials.get("target"); pm=materials.get("predecessor")
if not isinstance(tm,dict) or not isinstance(pm,dict):
    raise SystemExit("FINAL_PREPARED_MATERIALS_INVALID")
if (
    tm.get("image_ref")!=target
    or tm.get("archive_sha256")!=target_sha
    or tm.get("archive_size_bytes")!=int(target_size)
    or tm.get("verified") is not True
    or tm.get("fsynced") is not True
):
    raise SystemExit("FINAL_TARGET_MATERIAL_DRIFT")
if pm.get("image_ref")!=pred or pm.get("verified") is not True or pm.get("fsynced") is not True:
    raise SystemExit("FINAL_PREDECESSOR_MATERIAL_DRIFT")
runtime=LocalHaPredecessorRuntime()
binding=runtime.capture_start_binding(d)
if binding["images"]["homeassistant"]["reference"]!=pred:
    raise SystemExit("FINAL_RUNTIME_PREDECESSOR_DRIFT")
evidence=runtime.acceptance_observer().run_monitoring_self_test()
if evidence.verdict!="PASS":
    raise SystemExit("FINAL_SELF_TEST_FAILED")
print("NEW_FRESH_TRANSACTION_A_U4=PASS")
print("NEW_FRESH_TRANSACTION_ID="+tx)
print("FINAL_LAUNCH_SHA256="+binding["launch_sha256"])
print("FINAL_SELF_TEST_SHA256="+evidence.sha256)
print("PREPARED_TARGET_SHA256="+tm["archive_sha256"])
print("PREPARED_TARGET_SIZE="+str(tm["archive_size_bytes"]))
print("PREPARED_PREDECESSOR_SHA256="+pm["archive_sha256"])
print("PREPARED_PREDECESSOR_SIZE="+str(pm["archive_size_bytes"]))
if os.path.exists(install_auth):
    old=json.load(open(install_auth))
    current_binding=requested_install_binding_sha256(d)
    if old.get("binding_sha256")==current_binding:
        raise SystemExit("STALE_INSTALL_AUTHORITY_COLLIDES_WITH_NEW_TRANSACTION")
    print("INSTALL_AUTHORITY_RESIDUE=OLD_TERMINAL_SAFE_REPLACEABLE")
else:
    print("INSTALL_AUTHORITY_RESIDUE=ABSENT")
PY

test ! -e "$TARGET_SOURCE"
if docker image inspect "$TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_10_0_PRESENT_AFTER_PREPARE=true
  false
else
  echo TARGET_10_0_PRESENT_AFTER_PREPARE=false
fi
test -f "$SOURCE"

echo NEW_FRESH_TRANSACTION_A_PREPARE_RESULT=PASS
echo R8V13_07_SUBSTATE=NEW_FRESH_U4_READY_TO_INSTALL
echo INSTALL_INTENT=false
echo INSTALL_AUTHORITY_ISSUED_FOR_NEW_TRANSACTION=false
echo HA_INSTALL_OR_CUTOVER=false
echo BROKER_OTA=false
echo HOST_REBOOT=false
echo OLD_TRANSACTION_REPLAY=false
echo RELEASE_AUTHORITY_REFRESHED=true
echo NEW_TRANSACTION_CREATED=true
echo NEXT_BOUNDARY=STOP_BEFORE_NEW_INSTALL_AUTHORIZATION
trap - ERR
REMOTE_EOF
