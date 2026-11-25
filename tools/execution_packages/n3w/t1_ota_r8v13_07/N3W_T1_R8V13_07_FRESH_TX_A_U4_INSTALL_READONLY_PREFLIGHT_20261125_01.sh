#!/bin/bash
set -euo pipefail

HOST="${N3W_T1_SSH_TARGET:?N3W_T1_SSH_TARGET required}"
EXPECTED_TX="f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a"
EXPECTED_PYZ="9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa"
EXPECTED_MANIFEST="5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36"
EXPECTED_USB="b72ac2fc-79a0-4fb8-888e-f35b0114f959"
EXPECTED_LAUNCH="67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26"
EXPECTED_TARGET_SHA="e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663"
EXPECTED_TARGET_SIZE="2448553472"
EXPECTED_PREDECESSOR_SHA="6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f"
EXPECTED_PREDECESSOR_SIZE="2447090176"

ssh "$HOST" 'bash -s' --   "$EXPECTED_TX" "$EXPECTED_PYZ" "$EXPECTED_MANIFEST" "$EXPECTED_USB" "$EXPECTED_LAUNCH"   "$EXPECTED_TARGET_SHA" "$EXPECTED_TARGET_SIZE" "$EXPECTED_PREDECESSOR_SHA" "$EXPECTED_PREDECESSOR_SIZE" <<'REMOTE_EOF'
set -euo pipefail

EXPECTED_TX="$1"
EXPECTED_PYZ="$2"
EXPECTED_MANIFEST="$3"
EXPECTED_USB="$4"
EXPECTED_LAUNCH="$5"
EXPECTED_TARGET_SHA="$6"
EXPECTED_TARGET_SIZE="$7"
EXPECTED_PREDECESSOR_SHA="$8"
EXPECTED_PREDECESSOR_SIZE="$9"

ROOT=/var/lib/n3w-t1-core-updater
TX_FILE="$ROOT/homeassistant-usb-upgrade.json"
LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
PIN="$ROOT/ha-release-pin.json"
APPROVED=/run/n3w/t1-ota/approved-homeassistant.json
PREPARE_AUTH="$ROOT/ha-prepare-authority.json"
INSTALL_AUTH="$ROOT/ha-install-authority.json"
TARGET_REF=local/n3w-homeassistant:2026.10.0-0c73235a
PRED_REF=local/n3w-homeassistant:2026.10.4-5881590f
MANAGER_REF=local/greenhouse-manager:fresh-1cae18039eee
BROKER_REF=local/n3w-mosquitto:2.1.2-3184566d
RELEASE=homeassistant-r8-predecessor-2026.10.0

echo PHASE=R8V13_07_FRESH_TX_A_U4_INSTALL_READONLY_PREFLIGHT

test -f "$TX_FILE"
test -f "$LIVE"
test -f "$PIN"
test -f "$APPROVED"
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_PYZ"
test "$(sha256sum "$APPROVED" | awk '{print $1}')" = "$EXPECTED_MANIFEST"

TX_FILE_SHA256="$(sha256sum "$TX_FILE" | awk '{print $1}')"
PIN_SHA256="$(sha256sum "$PIN" | awk '{print $1}')"
echo TX_FILE_SHA256="$TX_FILE_SHA256"
echo RELEASE_PIN_SHA256="$PIN_SHA256"

/usr/bin/python3 -I -   "$LIVE" "$TX_FILE" "$PIN" "$APPROVED" "$PREPARE_AUTH" "$INSTALL_AUTH"   "$EXPECTED_TX" "$EXPECTED_USB" "$EXPECTED_LAUNCH"   "$EXPECTED_TARGET_SHA" "$EXPECTED_TARGET_SIZE" "$EXPECTED_PREDECESSOR_SHA" "$EXPECTED_PREDECESSOR_SIZE"   "$PRED_REF" "$TARGET_REF" "$MANAGER_REF" "$BROKER_REF" "$RELEASE" <<'PY'
import hashlib,json,os,stat,sys,time
from pathlib import Path

(
    _,live,tx_path,pin_path,approved_path,prepare_auth_path,install_auth_path,
    expected_tx,expected_usb,expected_launch,target_sha,target_size_raw,pred_sha,pred_size_raw,
    pred_ref,target_ref,manager_ref,broker_ref,release
)=sys.argv
sys.path.insert(0,live)

from n3w_t1_core_updater_ha_ipc import LocalApprovedHaRelease
from n3w_t1_core_updater_ha_recovery_startup import (
    LocalHaPredecessorRuntime,
    requested_install_binding_sha256,
)

target_size=int(target_size_raw)
pred_size=int(pred_size_raw)
tx=json.load(open(tx_path))
expected={
    "transaction_id_sha256": expected_tx,
    "status": "ACTIVE",
    "phase": "U4_READY_TO_INSTALL",
    "failure_code": None,
    "recovery_required": False,
    "authorization_claimed": False,
    "authorization_consumed": False,
    "authorization_id_sha256": None,
    "usb_binding_mode": "existing_filesystem",
    "usb_filesystem_uuid": expected_usb,
    "current_image_ref": pred_ref,
    "target_image_ref": target_ref,
    "target_artifact_verified": True,
}
for key,value in expected.items():
    if tx.get(key)!=value:
        raise SystemExit(f"U4_TRANSACTION_DRIFT:{key}:{tx.get(key)!r}")
if "predecessor_start" in tx:
    raise SystemExit("U4_PREDECESSOR_START_UNEXPECTED")

materials=tx.get("prepared_image_materials")
if not isinstance(materials,dict):
    raise SystemExit("PREPARED_IMAGE_MATERIALS_MISSING")
target=materials.get("target")
pred=materials.get("predecessor")
if not isinstance(target,dict) or not isinstance(pred,dict):
    raise SystemExit("PREPARED_IMAGE_MATERIALS_INVALID")
if (
    target.get("image_ref")!=target_ref
    or target.get("archive_sha256")!=target_sha
    or target.get("archive_size_bytes")!=target_size
    or target.get("verified") is not True
    or target.get("fsynced") is not True
):
    raise SystemExit("TARGET_MATERIAL_DRIFT")
if (
    pred.get("image_ref")!=pred_ref
    or pred.get("archive_sha256")!=pred_sha
    or pred.get("archive_size_bytes")!=pred_size
    or pred.get("verified") is not True
    or pred.get("fsynced") is not True
):
    raise SystemExit("PREDECESSOR_MATERIAL_DRIFT")

runtime=LocalHaPredecessorRuntime()
binding=runtime.capture_start_binding(tx)
if binding.get("launch_sha256")!=expected_launch:
    raise SystemExit("LAUNCH_SHA_DRIFT")
for name,ref in (
    ("homeassistant",pred_ref),
    ("manager",manager_ref),
    ("broker",broker_ref),
):
    if binding["images"][name]["reference"]!=ref:
        raise SystemExit(f"RUNTIME_REF_DRIFT:{name}")
evidence=runtime.acceptance_observer().run_monitoring_self_test()
if evidence.verdict!="PASS":
    raise SystemExit("MONITORING_SELF_TEST_FAILED")
print("U4_TRANSACTION=PASS")
print("CURRENT_LAUNCH_SHA256="+binding["launch_sha256"])
print("MANAGER_BROKER_HA_SELF_TEST=PASS")
print("MANAGER_BROKER_HA_SELF_TEST_SHA256="+evidence.sha256)
print("INSTALL_BINDING_SHA256="+requested_install_binding_sha256(tx))

pin=json.load(open(pin_path))
expiry=pin.get("expires_at_unix")
if type(expiry) is not int:
    raise SystemExit("RELEASE_PIN_EXPIRY_INVALID")
print("RELEASE_PIN_EXPIRES_AT_UNIX="+str(expiry))
print("RELEASE_PIN_EXPIRED="+str(expiry<=time.time()).lower())
try:
    admission=LocalApprovedHaRelease(
        Path(pin_path),Path(approved_path),
        lambda: runtime._runtime("homeassistant"),
    ).resolve_homeassistant_release(release)
except Exception as exc:
    print("RELEASE_AUTHORITY_STATE=REFRESH_REQUIRED")
    print("RELEASE_AUTHORITY_REASON="+str(exc))
else:
    if admission.release_identity!=release:
        raise SystemExit("RELEASE_ADMISSION_DRIFT")
    print("RELEASE_AUTHORITY_STATE=ACTIVE_VALID_FOR_INSTALL")

def classify_authority(path_raw, kind):
    path=Path(path_raw)
    if not path.exists():
        print(f"{kind}_AUTHORITY_PRESENT=false")
        print(f"{kind}_AUTHORITY_STATE=ABSENT")
        return
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600 or info.st_uid!=0:
        raise SystemExit(f"{kind}_AUTHORITY_METADATA_INVALID")
    raw=path.read_bytes()
    doc=json.loads(raw)
    print(f"{kind}_AUTHORITY_PRESENT=true")
    print(f"{kind}_AUTHORITY_SHA256="+hashlib.sha256(raw).hexdigest())
    exp=doc.get("expires_at_unix")
    print(f"{kind}_AUTHORITY_EXPIRES_AT_UNIX="+str(exp))
    print(f"{kind}_AUTHORITY_EXPIRED="+str(type(exp) is int and exp<=time.time()).lower())
    if kind=="PREPARE":
        if doc.get("transaction_id_sha256")==expected_tx:
            print("PREPARE_AUTHORITY_STATE=CURRENT_TX_RESIDUE")
        else:
            print("PREPARE_AUTHORITY_STATE=OTHER_TX_RESIDUE")
    else:
        current_binding=requested_install_binding_sha256(tx)
        if doc.get("binding_sha256")==current_binding:
            print("INSTALL_AUTHORITY_STATE=CURRENT_BINDING")
        else:
            print("INSTALL_AUTHORITY_STATE=OLD_TERMINAL_SAFE_REPLACEABLE")

classify_authority(prepare_auth_path,"PREPARE")
classify_authority(install_auth_path,"INSTALL")
PY

if docker image inspect "$TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_10_0_PRESENT=true
  exit 91
else
  echo TARGET_10_0_PRESENT=false
fi

USB_MOUNT="$(findmnt -rn -S UUID="$EXPECTED_USB" -o TARGET)"
test -n "$USB_MOUNT"
USB_AVAILABLE_BYTES="$(df -B1 --output=avail "$USB_MOUNT" | tail -1 | tr -d ' ')"
ROOT_AVAILABLE_BYTES="$(df -B1 --output=avail / | tail -1 | tr -d ' ')"
echo USB_MOUNT="$USB_MOUNT"
echo USB_AVAILABLE_BYTES="$USB_AVAILABLE_BYTES"
echo ROOT_AVAILABLE_BYTES="$ROOT_AVAILABLE_BYTES"

echo PERSISTENT_CONFIGURATION_MUTATION=false
echo INSTALL_INTENT=false
echo INSTALL_AUTHORITY_ISSUED=false
echo PRODUCT_WORKER_DISPATCH=false
echo HA_INSTALL_OR_CUTOVER=false
echo R8V13_08_AUTO_ADVANCE=false
echo RESULT=R8V13_07_FRESH_TX_A_U4_INSTALL_READONLY_PREFLIGHT_PASS
REMOTE_EOF
