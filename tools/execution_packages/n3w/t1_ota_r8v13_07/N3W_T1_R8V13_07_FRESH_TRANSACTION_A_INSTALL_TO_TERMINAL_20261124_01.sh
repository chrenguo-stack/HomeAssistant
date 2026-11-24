#!/bin/bash
set -euo pipefail

LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
ROOT=/var/lib/n3w-t1-core-updater
TX_FILE="$ROOT/homeassistant-usb-upgrade.json"
INSTALL_AUTH="$ROOT/ha-install-authority.json"
PIN="$ROOT/ha-release-pin.json"
APPROVED=/run/n3w/t1-ota/approved-homeassistant.json

EXPECTED_TX="d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4"
EXPECTED_PYZ="5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a"
EXPECTED_MANIFEST="5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36"
EXPECTED_USB="b72ac2fc-79a0-4fb8-888e-f35b0114f959"
EXPECTED_TARGET_REF="local/n3w-homeassistant:2026.10.0-0c73235a"
EXPECTED_PREDECESSOR_REF="local/n3w-homeassistant:2026.10.4-5881590f"
EXPECTED_MANAGER_REF="local/greenhouse-manager:fresh-1cae18039eee"
EXPECTED_BROKER_REF="local/n3w-mosquitto:2.1.2-3184566d"
EXPECTED_TARGET_SHA="e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663"
EXPECTED_TARGET_SIZE="2448553472"
EXPECTED_PREDECESSOR_SHA="6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f"
EXPECTED_PREDECESSOR_SIZE="2447090176"
EXPECTED_OLD_INSTALL_BINDING="f012b3ed4fe47090e5dc23b23c48b558099ce6247dad716b4d6252ae8ef5cd83"
RELEASE="homeassistant-r8-predecessor-2026.10.0"
AUTH_ID="N3W_T1_CORE_UPDATER_R8V13_07_FRESH_TX_A_INSTALL_CUTOVER_20261124_01"
WORK=""

MUTATION_STARTED=false
INSTALL_INTENT_SUBMITTED=false
INSTALL_AUTHORITY_ISSUED=false

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
    "pre_cutover_predecessor_restored","predecessor_release_observed",
    "target_loaded_image_id","target_activation",
):
    print(f"{key.upper()}={json.dumps(d.get(key),separators=(',',':'))}")
print("PREDECESSOR_START_PRESENT="+str("predecessor_start" in d).lower())
print("TARGET_ACCEPTANCE_PRESENT="+str("target_acceptance" in d).lower())
PY
}

stop() {
  rc=$?
  echo FRESH_TX_A_INSTALL_RESULT=STOP
  echo EXIT_CODE="$rc"
  echo MUTATION_STARTED="$MUTATION_STARTED"
  echo INSTALL_INTENT_SUBMITTED="$INSTALL_INTENT_SUBMITTED"
  echo INSTALL_AUTHORITY_ISSUED="$INSTALL_AUTHORITY_ISSUED"
  summary || true
  if [ "$MUTATION_STARTED" = true ]; then
    echo DO_NOT_REPLAY_WITHOUT_DURABLE_CLASSIFICATION=true
  fi
  exit "$rc"
}
trap stop ERR

echo PHASE=PREINSTALL_EXACT_REBIND
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_PYZ"
test "$(sha256sum "$APPROVED" | awk '{print $1}')" = "$EXPECTED_MANIFEST"
WORK="$(mktemp -d /tmp/n3w-r8v13-07-fresh-tx-a-install-20261124-01.XXXXXX)"
chmod 700 "$WORK"

python3 - "$TX_FILE" "$EXPECTED_TX" "$EXPECTED_USB" "$EXPECTED_TARGET_REF" "$EXPECTED_PREDECESSOR_REF" "$EXPECTED_TARGET_SHA" "$EXPECTED_TARGET_SIZE" "$EXPECTED_PREDECESSOR_SHA" "$EXPECTED_PREDECESSOR_SIZE" <<'PY'
import json,sys
p,tx,uuid,target,pred,tsha,tsize,psha,psize=sys.argv[1:]
d=json.load(open(p))
expected={
    "transaction_id_sha256":tx,
    "status":"ACTIVE",
    "phase":"U4_READY_TO_INSTALL",
    "recovery_required":False,
    "authorization_claimed":False,
    "authorization_consumed":False,
    "usb_binding_mode":"existing_filesystem",
    "usb_filesystem_uuid":uuid,
    "current_image_ref":pred,
    "target_image_ref":target,
    "target_artifact_verified":True,
}
for key,value in expected.items():
    if d.get(key)!=value:
        raise SystemExit("U4_DRIFT:"+key)
if d.get("authorization_id_sha256") is not None or "predecessor_start" in d:
    raise SystemExit("U4_AUTHORIZATION_DRIFT")
materials=d.get("prepared_image_materials")
if not isinstance(materials,dict):
    raise SystemExit("U4_MATERIALS_MISSING")
tm=materials.get("target"); pm=materials.get("predecessor")
if not isinstance(tm,dict) or not isinstance(pm,dict):
    raise SystemExit("U4_MATERIALS_INVALID")
if (tm.get("image_ref"),tm.get("archive_sha256"),tm.get("archive_size_bytes"),tm.get("verified"),tm.get("fsynced")) != (target,tsha,int(tsize),True,True):
    raise SystemExit("U4_TARGET_MATERIAL_DRIFT")
if (pm.get("image_ref"),pm.get("archive_sha256"),pm.get("archive_size_bytes"),pm.get("verified"),pm.get("fsynced")) != (pred,psha,int(psize),True,True):
    raise SystemExit("U4_PREDECESSOR_MATERIAL_DRIFT")
print("FRESH_TX_A_U4_REBIND=PASS")
PY

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$EXPECTED_PREDECESSOR_REF" "$EXPECTED_TARGET_REF" "$EXPECTED_MANAGER_REF" "$EXPECTED_BROKER_REF" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
_,live,txp,pred,target,manager,broker=sys.argv
d=json.load(open(txp))
r=LocalHaPredecessorRuntime()
binding=r.capture_start_binding(d)
if binding["images"]["homeassistant"]["reference"]!=pred:
    raise SystemExit("PREINSTALL_HA_RUNTIME_DRIFT")
if binding["images"]["manager"]["reference"]!=manager:
    raise SystemExit("PREINSTALL_MANAGER_RUNTIME_DRIFT")
if binding["images"]["broker"]["reference"]!=broker:
    raise SystemExit("PREINSTALL_BROKER_RUNTIME_DRIFT")
if r._release_image(target) is not None:
    raise SystemExit("TARGET_ALREADY_PRESENT")
e=r.acceptance_observer().run_monitoring_self_test()
if e.verdict!="PASS":
    raise SystemExit("PREINSTALL_SELF_TEST_FAILED")
print("PREINSTALL_RUNTIME=PASS")
print("PREINSTALL_LAUNCH_SHA256="+binding["launch_sha256"])
print("PREINSTALL_SELF_TEST_SHA256="+e.sha256)
print("TARGET_10_0_PRESENT_BEFORE_INSTALL=false")
PY

echo PHASE=RELEASE_AUTHORITY_REVALIDATION
MUTATION_STARTED=true
/usr/bin/python3 -I - "$LIVE" "$PIN" "$APPROVED" "$EXPECTED_MANIFEST" "$RELEASE" <<'PY'
import hashlib,json,os,stat,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_ipc import (
    LocalApprovedHaRelease, RELEASE_PIN_SCHEMA, SIGNED_INDEX_STATE,
    read_local_release_input, read_signed_index, valid_signed_index,
)
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

_,live,pinp,manifestp,manifest_sha,release=sys.argv
pin_path=Path(pinp); manifest_path=Path(manifestp)
st=pin_path.lstat()
if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode)!=0o600 or st.st_uid!=0 or st.st_nlink!=1:
    raise SystemExit("RELEASE_PIN_METADATA_INVALID")
pin=json.loads(read_local_release_input(pin_path,limit=4096,private=True))
base={"schema","manifest_sha256","predecessor_image_id","expires_at_unix"}
signed={"signed_index","predecessor_binding_sha256"}
if set(pin) not in (base,base|signed):
    raise SystemExit("RELEASE_PIN_FIELDS_INVALID")
if pin.get("schema")!=RELEASE_PIN_SCHEMA or pin.get("manifest_sha256")!=manifest_sha:
    raise SystemExit("RELEASE_PIN_BINDING_INVALID")
if hashlib.sha256(manifest_path.read_bytes()).hexdigest()!=manifest_sha:
    raise SystemExit("APPROVED_MANIFEST_DRIFT")
runtime=LocalHaPredecessorRuntime()._runtime("homeassistant")
if pin.get("predecessor_image_id")!=runtime.get("image_id"):
    raise SystemExit("RELEASE_PIN_PREDECESSOR_DRIFT")
if "signed_index" in pin:
    if not valid_signed_index(pin["signed_index"]):
        raise SystemExit("RELEASE_PIN_SIGNED_INDEX_INVALID")
    if pin["signed_index"]!=read_signed_index(pin_path.with_name(SIGNED_INDEX_STATE)):
        raise SystemExit("RELEASE_PIN_SIGNED_INDEX_DRIFT")
    if not isinstance(pin.get("predecessor_binding_sha256"),str) or len(pin["predecessor_binding_sha256"])!=64:
        raise SystemExit("RELEASE_PIN_PREDECESSOR_BINDING_INVALID")
if type(pin.get("expires_at_unix")) is not int:
    raise SystemExit("RELEASE_PIN_EXPIRY_INVALID")
now=int(time.time())
if pin["expires_at_unix"]<=now:
    pin["expires_at_unix"]=now+21600
    fd,tmp=tempfile.mkstemp(prefix=".ha-release-pin.",dir=pin_path.parent)
    temp=Path(tmp)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w") as stream:
            json.dump(pin,stream,sort_keys=True,separators=(",",":"))
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp,pin_path)
        parent=os.open(pin_path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        temp.unlink(missing_ok=True)
    print("RELEASE_PIN_REFRESH=PASS")
else:
    print("RELEASE_PIN_REFRESH=NOT_REQUIRED")
resolver=LocalApprovedHaRelease(pin_path,manifest_path,lambda: LocalHaPredecessorRuntime()._runtime("homeassistant"))
admission=resolver.resolve_homeassistant_release(release)
if admission.release_identity!=release:
    raise SystemExit("RELEASE_ADMISSION_DRIFT")
print("RELEASE_PIN_SHA256="+hashlib.sha256(pin_path.read_bytes()).hexdigest())
print("RELEASE_PIN_EXPIRES_AT_UNIX="+str(json.loads(read_local_release_input(pin_path,limit=4096,private=True))["expires_at_unix"]))
print("RELEASE_ADMISSION=PASS")
PY

python3 - "$INSTALL_AUTH" "$EXPECTED_OLD_INSTALL_BINDING" <<'PY'
import json,sys
p,old_binding=sys.argv[1:]
try:
    d=json.load(open(p))
except FileNotFoundError:
    print("INSTALL_AUTHORITY_RESIDUE=ABSENT")
    raise SystemExit(0)
if d.get("schema")!="gh.n3w-t1-ha-install-authority/3":
    raise SystemExit("INSTALL_AUTHORITY_RESIDUE_SCHEMA_INVALID")
if d.get("binding_sha256")!=old_binding:
    raise SystemExit("INSTALL_AUTHORITY_RESIDUE_BINDING_UNEXPECTED")
print("INSTALL_AUTHORITY_RESIDUE=OLD_TERMINAL_SAFE_REPLACEABLE")
PY

echo PHASE=SUBMIT_INSTALL_INTENT
/usr/bin/python3 -I "$LIVE" --maintenance-submit-approved-release INSTALL --release-identity "$RELEASE" > "$WORK/install-intent.json"
INSTALL_INTENT_SUBMITTED=true

python3 - "$TX_FILE" "$EXPECTED_TX" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
if d.get("transaction_id_sha256")!=sys.argv[2] or d.get("status")!="ACTIVE" or d.get("phase")!="U5_INSTALL_REQUESTED_REVALIDATING":
    raise SystemExit("INSTALL_INTENT_U5_INVALID")
if d.get("authorization_claimed") is not False or d.get("authorization_consumed") is not False or d.get("authorization_id_sha256") is not None:
    raise SystemExit("INSTALL_INTENT_AUTHORIZATION_DRIFT")
if "predecessor_start" in d:
    raise SystemExit("INSTALL_INTENT_DESTRUCTIVE_DRIFT")
print("FRESH_TX_A_U5_INSTALL_INTENT=PASS")
PY

echo PHASE=ISSUE_INSTALL_AUTHORITY
REQ="$WORK/install-authority-request.json"
/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$REQ" "$AUTH_ID" <<'PY'
import json,os,sys,time
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import requested_install_binding_sha256
from n3w_t1_core_updater_v2_common import AUTHORIZATION_ID
_,live,txp,out,auth=sys.argv
if AUTHORIZATION_ID.fullmatch(auth) is None:
    raise SystemExit("AUTHORIZATION_ID_INVALID")
d=json.load(open(txp))
if d.get("status")!="ACTIVE" or d.get("phase")!="U5_INSTALL_REQUESTED_REVALIDATING":
    raise SystemExit("INSTALL_AUTHORITY_U5_NOT_READY")
req={
    "transaction_id_sha256":d["transaction_id_sha256"],
    "expires_at_unix":int(time.time())+21600,
    "binding_sha256":requested_install_binding_sha256(d),
    "authorization_id":auth,
}
fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"w") as f:
    json.dump(req,f,sort_keys=True,separators=(",",":"))
    f.write("\n"); f.flush(); os.fsync(f.fileno())
print("INSTALL_REQUEST_BINDING_SHA256="+req["binding_sha256"])
print("INSTALL_REQUEST_AUTHORIZATION_ID="+auth)
PY

/usr/bin/python3 -I "$LIVE" --issue-install-authority "$REQ"
INSTALL_AUTHORITY_ISSUED=true

python3 - "$INSTALL_AUTH" "$REQ" <<'PY'
import hashlib,json,sys,time
p,rq=sys.argv[1:]
d=json.load(open(p)); q=json.load(open(rq))
if d.get("schema")!="gh.n3w-t1-ha-install-authority/3" or d.get("binding_sha256")!=q.get("binding_sha256"):
    raise SystemExit("INSTALL_AUTHORITY_BINDING_INVALID")
if d.get("authorization_id")!=q.get("authorization_id") or d.get("expires_at_unix")!=q.get("expires_at_unix"):
    raise SystemExit("INSTALL_AUTHORITY_CONTENT_INVALID")
if d["expires_at_unix"]<=time.time():
    raise SystemExit("INSTALL_AUTHORITY_EXPIRED")
print("FRESH_INSTALL_AUTHORITY=PASS")
print("FRESH_INSTALL_AUTHORITY_SHA256="+hashlib.sha256(open(p,"rb").read()).hexdigest())
print("FRESH_INSTALL_LAUNCH_SHA256="+d["launch_sha256"])
PY

echo PHASE=PRODUCT_INSTALL_TO_TERMINAL
set +e
/usr/bin/python3 -I "$LIVE" --resume-pending
PRODUCT_RC=$?
set -e
echo PRODUCT_RESUME_RC="$PRODUCT_RC"
summary

echo PHASE=FINAL_DURABLE_CLASSIFICATION
FINAL=$(python3 - "$TX_FILE" "$EXPECTED_TX" "$AUTH_ID" <<'PY'
import hashlib,json,sys
p,tx,auth=sys.argv[1:]
d=json.load(open(p))
if d.get("transaction_id_sha256")!=tx:
    raise SystemExit("FINAL_TRANSACTION_DRIFT")
if d.get("status")=="COMMITTED" and d.get("phase")=="U13A_COMMITTED":
    if d.get("authorization_claimed") is not True or d.get("authorization_consumed") is not True:
        raise SystemExit("COMMIT_AUTHORIZATION_NOT_CONSUMED")
    if d.get("authorization_id_sha256")!=hashlib.sha256(auth.encode()).hexdigest():
        raise SystemExit("COMMIT_AUTHORIZATION_ID_DRIFT")
    if d.get("recovery_required") is not False or d.get("target_activation")!="WRITES_POSSIBLE":
        raise SystemExit("COMMIT_STATE_INVALID")
    receipt=d.get("target_acceptance",{}).get("receipt")
    if not isinstance(receipt,dict):
        raise SystemExit("COMMIT_ACCEPTANCE_MISSING")
    observations=receipt.get("observations")
    if not isinstance(observations,dict) or set(observations)!={"monitoring_path","protected_data"}:
        raise SystemExit("COMMIT_ACCEPTANCE_OBSERVATIONS_INVALID")
    if not all(isinstance(value,str) and len(value)==64 for value in observations.values()):
        raise SystemExit("COMMIT_ACCEPTANCE_OBSERVATION_HASH_INVALID")
    if receipt.get("images",{}).get("homeassistant",{}).get("reference")!=d.get("target_image_ref"):
        raise SystemExit("COMMIT_ACCEPTANCE_TARGET_REF_DRIFT")
    if receipt.get("images",{}).get("homeassistant",{}).get("runtime_id")!=d.get("target_loaded_image_id"):
        raise SystemExit("COMMIT_ACCEPTANCE_RUNTIME_ID_DRIFT")
    print("committed")
elif d.get("status")=="ROLLED_BACK" and d.get("phase")=="U13B_ROLLED_BACK":
    print("rolled_back")
else:
    print("stopped")
PY
)
echo FINAL_CLASS="$FINAL"

if [ "$FINAL" = committed ]; then
  /usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$EXPECTED_TARGET_REF" "$EXPECTED_MANAGER_REF" "$EXPECTED_BROKER_REF" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
_,live,txp,target,manager,broker=sys.argv
d=json.load(open(txp))
r=LocalHaPredecessorRuntime()
ha=r._runtime("homeassistant"); ma=r._runtime("manager"); br=r._runtime("broker")
if ha["image_ref"]!=target or ha["image_id"]!=d.get("target_loaded_image_id") or ha["restart_count"]!=0:
    raise SystemExit("POST_COMMIT_HA_RUNTIME_DRIFT")
if ma["image_ref"]!=manager or ma["restart_count"]!=0:
    raise SystemExit("POST_COMMIT_MANAGER_RUNTIME_DRIFT")
if br["image_ref"]!=broker or br["restart_count"]!=0:
    raise SystemExit("POST_COMMIT_BROKER_RUNTIME_DRIFT")
print("POST_COMMIT_RUNTIME=PASS")
print("TARGET_ACCEPTANCE_RECEIPT=PASS")
print("BUSINESS_HEALTH_FROM_ACCEPTANCE=PASS")
PY
  echo FINAL_TRANSACTION_SHA256="$(sha256sum "$TX_FILE" | awk '{print $1}')"
  echo FRESH_TX_A_INSTALL_RESULT=PASS
  echo R8V13_07_RESULT=PASS
  echo R8V13_07_TERMINAL=U13A_COMMITTED
  echo NEXT_BOUNDARY=STOP_BEFORE_R8V13_08
  trap - ERR
  exit 0
fi

if [ "$FINAL" = rolled_back ]; then
  /usr/bin/python3 -I - "$LIVE" "$EXPECTED_PREDECESSOR_REF" "$EXPECTED_MANAGER_REF" "$EXPECTED_BROKER_REF" <<'PY'
import sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
_,live,pred,manager,broker=sys.argv
r=LocalHaPredecessorRuntime()
ha=r._runtime("homeassistant"); ma=r._runtime("manager"); br=r._runtime("broker")
if ha["image_ref"]!=pred or ma["image_ref"]!=manager or br["image_ref"]!=broker:
    raise SystemExit("ROLLBACK_RUNTIME_DRIFT")
print("ROLLBACK_RUNTIME_HEALTH=PASS")
PY
  echo FRESH_TX_A_INSTALL_RESULT=ROLLED_BACK
  echo R8V13_07_RESULT=NOT_PASS
  echo R8V13_08_BLOCKED=true
  echo DO_NOT_REPLAY=true
  trap - ERR
  exit 2
fi

echo FRESH_TX_A_INSTALL_RESULT=STOPPED_NONTERMINAL
echo R8V13_07_RESULT=NOT_PASS
echo R8V13_08_BLOCKED=true
echo DO_NOT_REPLAY=true
trap - ERR
exit 3
