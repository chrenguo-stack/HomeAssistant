#!/bin/bash
set -euo pipefail

HOST="${N3W_T1_SSH_TARGET:?N3W_T1_SSH_TARGET required}"
EXPECTED_TX_SHA256="4b1cc60e5557b9bc338d3d0469d30aa94c7974c34a0c26dffae5caf9fde4b105"
EXPECTED_OLD_TX_ID="f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a"
EXPECTED_PYZ_SHA256="807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2"
EXPECTED_USB_UUID="b72ac2fc-79a0-4fb8-888e-f35b0114f959"
EXPECTED_LAUNCH="67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26"

ssh "$HOST" 'bash -s' -- "$EXPECTED_TX_SHA256" "$EXPECTED_OLD_TX_ID" "$EXPECTED_PYZ_SHA256" "$EXPECTED_USB_UUID" "$EXPECTED_LAUNCH" <<'REMOTE_EOF'
set -euo pipefail
EXPECTED_TX_SHA256="$1"
EXPECTED_OLD_TX_ID="$2"
EXPECTED_PYZ_SHA256="$3"
EXPECTED_USB_UUID="$4"
EXPECTED_LAUNCH="$5"

ROOT=/var/lib/n3w-t1-core-updater
TX_FILE="$ROOT/homeassistant-usb-upgrade.json"
LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
TARGET_REF=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
PRED_REF=local/n3w-homeassistant:2026.10.4-5881590f
PRED_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
MANAGER_REF=local/greenhouse-manager:fresh-1cae18039eee
MANAGER_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
BROKER_REF=local/n3w-mosquitto:2.1.2-3184566d
BROKER_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563

echo PHASE=R8V13_07_POST_PYZ_FRESH_REACCEPTANCE_READONLY_REBIND

test -f "$TX_FILE"
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"
test -f "$LIVE"
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_PYZ_SHA256"

python3 - "$TX_FILE" "$EXPECTED_OLD_TX_ID" "$EXPECTED_USB_UUID" <<'PY'
import json,sys
path,expected_id,expected_uuid=sys.argv[1:4]
d=json.load(open(path))
expected={
    "transaction_id_sha256": expected_id,
    "status": "ROLLED_BACK",
    "phase": "U13B_ROLLED_BACK",
    "failure_code": "ha_usb_target_acceptance_evidence_unavailable",
    "recovery_required": False,
    "authorization_claimed": True,
    "authorization_consumed": True,
    "authorization_id_sha256": "de25e2d5c8ea8f183a6dca35048f6896c54d3876bea70f6c35afc847819ed136",
    "predecessor_release_observed": True,
    "usb_filesystem_uuid": expected_uuid,
}
for key,value in expected.items():
    if d.get(key)!=value:
        raise SystemExit(f"OLD_TX_DRIFT:{key}:{d.get(key)!r}")
if d.get("current_image_ref")!="local/n3w-homeassistant:2026.10.4-5881590f":
    raise SystemExit("OLD_TX_CURRENT_IMAGE_DRIFT")
if d.get("target_image_ref")!="local/n3w-homeassistant:2026.10.0-0c73235a":
    raise SystemExit("OLD_TX_TARGET_IMAGE_DRIFT")
if "predecessor_start" not in d:
    raise SystemExit("OLD_TX_PREDECESSOR_START_MISSING")
print("OLD_TRANSACTION_TERMINAL_NO_REPLAY=PASS")
print("OLD_TRANSACTION_ID="+d["transaction_id_sha256"])
print("USB_FILESYSTEM_UUID="+d["usb_filesystem_uuid"])
PY

for spec in   "n3wfc4-services-activation.service:active"   "n3wfc4-broker-activation.service:active"   "n3w-t1-ha-recovery-retry.service:inactive"   "n3w-t1-ha-recovery-retry.timer:active"   "n3w-t1-ha-ota-ipc.socket:active"; do
  unit="${spec%%:*}"
  expected="${spec##*:}"
  test "$(systemctl is-active "$unit")" = "$expected"
done
for unit in n3w-t1-ha-recovery-startup.service n3w-t1-ha-recovery-retry.timer n3w-t1-ha-ota-ipc.socket; do
  test "$(systemctl is-enabled "$unit")" = enabled
done

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

if docker image inspect "$TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_10_0_PRESENT=true
  exit 31
fi
if docker image inspect "$TARGET_ID" >/dev/null 2>&1; then
  echo TARGET_10_0_ID_PRESENT=true
  exit 32
fi
test "$(docker image inspect "$PRED_REF" --format '{{.Id}}')" = "$PRED_ID"

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$EXPECTED_LAUNCH" <<'PY'
import json,re,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
from n3w_t1_core_updater_ha_usb_state import validate_transaction_document

d=validate_transaction_document(json.load(open(sys.argv[2],encoding="utf-8")))
expected=d["predecessor_start"]
journal=d.get("ha_data_restore")
if not isinstance(journal,dict) or journal.get("step")!="PUBLISHED":
    raise SystemExit("PUBLISHED_DATA_JOURNAL_MISSING")
runtime=LocalHaPredecessorRuntime()
raw_binding,_=runtime._restart_binding()
normalized_binding,_=runtime._restart_binding(published=journal)
if raw_binding["images"]!=expected["images"]:
    raise SystemExit("PREDECESSOR_IMAGE_BINDING_DRIFT")
if normalized_binding!=expected:
    raise SystemExit("PREDECESSOR_NORMALIZED_BINDING_DRIFT")
if normalized_binding["launch_sha256"]!=sys.argv[3]:
    raise SystemExit("NORMALIZED_LAUNCH_SHA_DRIFT")
runtime.verify_published_predecessor_health(d)
if runtime.candidate_manager_monitoring_self_test_available() is not True:
    raise SystemExit("MANAGER_SELF_TEST_CAPABILITY_UNAVAILABLE")
evidence=runtime.acceptance_observer().run_monitoring_self_test()
if evidence.verdict!="PASS" or not isinstance(evidence.sha256,str) or re.fullmatch(r"[0-9a-f]{64}",evidence.sha256) is None:
    raise SystemExit("MANAGER_BROKER_HA_SELF_TEST_FAILED")
print("CURRENT_PREDECESSOR_BINDING=PASS")
print("CURRENT_BINDING_MODE=PUBLISHED_DATA_NORMALIZED")
print("CURRENT_RAW_LAUNCH_SHA256="+raw_binding["launch_sha256"])
print("CURRENT_NORMALIZED_LAUNCH_SHA256="+normalized_binding["launch_sha256"])
print("MANAGER_BROKER_HA_SELF_TEST=PASS")
print("MANAGER_BROKER_HA_SELF_TEST_SHA256="+evidence.sha256)
PY

/usr/bin/python3 -I - "$LIVE" "$ROOT" "$TX_FILE" "$EXPECTED_OLD_TX_ID" "$PRED_ID" "$TARGET_REF" <<'PY'
import hashlib,json,stat,sys,time
from pathlib import Path

live,root_raw,tx_path,old_tx_id,pred_id,target_ref=sys.argv[1:7]
sys.path.insert(0,live)
from n3w_t1_core_updater_ha_recovery_startup import (
    INSTALL_AUTHORITY_SCHEMA,
    PREPARE_AUTHORITY_SCHEMA,
    LocalHaPredecessorRuntime,
    requested_install_binding_sha256,
)
from n3w_t1_core_updater_ha_ipc import (
    APPROVED_MANIFEST,
    IPC_SOCKET,
    RELEASE_PIN,
    RELEASE_PIN_SCHEMA,
    LocalApprovedHaRelease,
)

root=Path(root_raw)
transaction=json.load(open(tx_path))
now=int(time.time())

def read_private(name):
    path=root/name
    if not path.exists():
        return None,None,None
    info=path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode)!=0o600
        or info.st_uid!=0
        or info.st_nlink!=1
        or info.st_size>4096
    ):
        raise SystemExit(f"{name}:METADATA_DRIFT")
    raw=path.read_bytes()
    try:
        doc=json.loads(raw)
    except Exception as exc:
        raise SystemExit(f"{name}:JSON_INVALID") from exc
    if not isinstance(doc,dict):
        raise SystemExit(f"{name}:DOCUMENT_INVALID")
    return path,raw,doc

def print_common(label,raw,doc):
    expiry=doc.get("expires_at_unix")
    if type(expiry) is not int:
        raise SystemExit(f"{label}_EXPIRY_INVALID")
    expired=now>=expiry
    print(f"{label}_PRESENT=true")
    print(f"{label}_SHA256="+hashlib.sha256(raw).hexdigest())
    print(f"{label}_EXPIRES_AT_UNIX={expiry}")
    print(f"{label}_EXPIRED={str(expired).lower()}")
    return expired

path,raw,doc=read_private("ha-prepare-authority.json")
if path is None:
    print("HA_PREPARE_AUTHORITY_PRESENT=false")
else:
    expired=print_common("HA_PREPARE_AUTHORITY",raw,doc)
    if (
        set(doc)!={"schema","transaction_id_sha256","usb_filesystem_uuid","target_source","launch_sha256","expires_at_unix"}
        or doc.get("schema")!=PREPARE_AUTHORITY_SCHEMA
        or doc.get("transaction_id_sha256")!=old_tx_id
        or doc.get("usb_filesystem_uuid")!=transaction.get("usb_filesystem_uuid")
    ):
        raise SystemExit("HA_PREPARE_AUTHORITY_FOREIGN_OR_DRIFT")
    print("HA_PREPARE_AUTHORITY_TRANSACTION_ID_SHA256="+doc["transaction_id_sha256"])
    print(
        "HA_PREPARE_AUTHORITY_STATE="
        + ("EXPIRED_OLD_TERMINAL" if expired else "ACTIVE_OLD_TERMINAL_SAFE_REPLACEABLE")
    )

path,raw,doc=read_private("ha-install-authority.json")
if path is None:
    print("HA_INSTALL_AUTHORITY_PRESENT=false")
else:
    expired=print_common("HA_INSTALL_AUTHORITY",raw,doc)
    if (
        set(doc)!={"schema","binding_sha256","authorization_id","launch_sha256","expires_at_unix"}
        or doc.get("schema")!=INSTALL_AUTHORITY_SCHEMA
        or doc.get("binding_sha256")!=requested_install_binding_sha256(transaction)
    ):
        raise SystemExit("HA_INSTALL_AUTHORITY_FOREIGN_OR_DRIFT")
    print("HA_INSTALL_AUTHORITY_BINDING_SHA256="+doc["binding_sha256"])
    print(
        "HA_INSTALL_AUTHORITY_STATE="
        + ("EXPIRED_OLD_TERMINAL" if expired else "ACTIVE_OLD_TERMINAL_SAFE_REPLACEABLE")
    )

pin_path,pin_raw,pin=read_private(RELEASE_PIN)
manifest=IPC_SOCKET.with_name(APPROVED_MANIFEST)
if pin_path is None:
    print("HA_RELEASE_PIN_PRESENT=false")
    if manifest.exists():
        print("APPROVED_MANIFEST_PRESENT=true")
        print("APPROVED_MANIFEST_SHA256="+hashlib.sha256(manifest.read_bytes()).hexdigest())
    else:
        print("APPROVED_MANIFEST_PRESENT=false")
    print("HA_RELEASE_AUTHORITY_STATE=REFRESH_REQUIRED")
else:
    expired=print_common("HA_RELEASE_PIN",pin_raw,pin)
    if pin.get("schema")!=RELEASE_PIN_SCHEMA:
        raise SystemExit("HA_RELEASE_PIN_SCHEMA_DRIFT")
    if manifest.exists():
        manifest_raw=manifest.read_bytes()
        print("APPROVED_MANIFEST_PRESENT=true")
        print("APPROVED_MANIFEST_SHA256="+hashlib.sha256(manifest_raw).hexdigest())
    else:
        print("APPROVED_MANIFEST_PRESENT=false")
    if expired:
        print("HA_RELEASE_AUTHORITY_STATE=REFRESH_REQUIRED")
    else:
        runtime=LocalHaPredecessorRuntime()
        resolver=LocalApprovedHaRelease(
            pin_path,
            manifest,
            lambda: runtime._runtime("homeassistant"),
        )
        release_identity=transaction["target_manifest_identity"]["release_identity"]
        admission=resolver.resolve_homeassistant_release(release_identity)
        if (
            admission.current_image_ref!="local/n3w-homeassistant:2026.10.4-5881590f"
            or admission.current_image_identity.get("runtime_image_id")!=pred_id
            or admission.target_image_ref!=target_ref
        ):
            raise SystemExit("HA_RELEASE_AUTHORITY_ADMISSION_DRIFT")
        print("HA_RELEASE_AUTHORITY_RELEASE_IDENTITY="+release_identity)
        print("HA_RELEASE_AUTHORITY_STATE=ACTIVE_VALID_FOR_FRESH_PREPARE")
PY

python3 - "$EXPECTED_USB_UUID" "$EXPECTED_OLD_TX_ID" "$TX_FILE" <<'PY'
import json,os,stat,subprocess,sys,hashlib
from pathlib import Path

uuid,old_tx_id,tx_path=sys.argv[1:4]
transaction=json.load(open(tx_path,encoding="utf-8"))
expected_sha=transaction.get("target_archive_sha256")
expected_size=transaction.get("target_archive_size")
if not isinstance(expected_sha,str) or len(expected_sha)!=64 or type(expected_size) is not int or expected_size<=0:
    raise SystemExit("OLD_TX_TARGET_ARCHIVE_IDENTITY_INVALID")

doc=json.loads(subprocess.check_output([
    "lsblk","--json","--bytes","-o","PATH,TYPE,FSTYPE,UUID,SIZE,TRAN,MOUNTPOINTS"
],text=True))
rows=[]
def walk(items):
    for item in items or []:
        if str(item.get("uuid") or "").lower()==uuid.lower():
            rows.append(item)
        walk(item.get("children"))
walk(doc.get("blockdevices"))
if len(rows)!=1:
    raise SystemExit("BOUND_USB_DEVICE_COUNT_DRIFT")
row=rows[0]
if row.get("fstype")!="ext4":
    raise SystemExit("BOUND_USB_FILESYSTEM_DRIFT")
mounts=[x for x in (row.get("mountpoints") or []) if isinstance(x,str) and x]
if len(mounts)!=1:
    raise SystemExit("BOUND_USB_MOUNT_COUNT_DRIFT")
mount=Path(mounts[0])
source=mount/"N3W-OTA"/old_tx_id/"target.tar"
info=source.lstat()
if (
    not stat.S_ISREG(info.st_mode)
    or stat.S_IMODE(info.st_mode)!=0o600
    or info.st_uid!=0
    or info.st_nlink!=1
    or info.st_size!=expected_size
):
    raise SystemExit("OLD_USB_TARGET_SOURCE_METADATA_DRIFT")
hasher=hashlib.sha256()
with source.open("rb") as stream:
    while True:
        block=stream.read(1024*1024)
        if not block:
            break
        hasher.update(block)
digest=hasher.hexdigest()
if digest!=expected_sha:
    raise SystemExit("OLD_USB_TARGET_SOURCE_SHA_DRIFT")
print("BOUND_USB_PRESENT=PASS")
print("BOUND_USB_DEVICE="+str(row.get("path")))
print("BOUND_USB_TYPE="+str(row.get("type")))
print("BOUND_USB_TRANSPORT="+str(row.get("tran")))
print("BOUND_USB_SIZE_BYTES="+str(row.get("size")))
print("BOUND_USB_MOUNT="+str(mount))
v=os.statvfs(mount)
print("BOUND_USB_AVAILABLE_BYTES="+str(v.f_bavail*v.f_frsize))
print("OLD_USB_TARGET_SOURCE=PASS")
print("OLD_USB_TARGET_SOURCE_PATH="+str(source))
print("OLD_USB_TARGET_SOURCE_SHA256="+digest)
print("OLD_USB_TARGET_SOURCE_SIZE="+str(info.st_size))
v=os.statvfs("/")
print("ROOT_AVAILABLE_BYTES="+str(v.f_bavail*v.f_frsize))
PY

echo LIVE_RECOVERY_PYZ_SHA256="$EXPECTED_PYZ_SHA256"
echo TARGET_10_0_PRESENT=false
echo PERSISTENT_CONFIGURATION_MUTATION=false
echo OLD_TRANSACTION_REPLAY=false
echo NEW_TRANSACTION=false
echo RESULT=R8V13_07_POST_PYZ_FRESH_REACCEPTANCE_READONLY_REBIND_V3_PASS
REMOTE_EOF
