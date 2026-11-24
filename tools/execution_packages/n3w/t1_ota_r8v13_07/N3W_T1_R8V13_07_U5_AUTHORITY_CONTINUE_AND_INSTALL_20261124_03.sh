#!/bin/bash
set -euo pipefail
HOST="root@192.168.68.195"
ssh "$HOST" 'bash -s' <<'REMOTE_EOF'
set -euo pipefail
LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
ROOT=/var/lib/n3w-t1-core-updater
TX_FILE="$ROOT/homeassistant-usb-upgrade.json"
INSTALL_AUTH="$ROOT/ha-install-authority.json"
APPROVED=/run/n3w/t1-ota/approved-homeassistant.json
PIN="$ROOT/ha-release-pin.json"
COMPOSE=/etc/n3wfc4/docker-compose.yml
TX=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
RELEASE=homeassistant-r8-predecessor-2026.10.0
TARGET_REF=local/n3w-homeassistant:2026.10.0-0c73235a
PRED_REF=local/n3w-homeassistant:2026.10.4-5881590f
MANAGER_REF=local/greenhouse-manager:fresh-1cae18039eee
BROKER_REF=local/n3w-mosquitto:2.1.2-3184566d
USB_UUID=b72ac2fc-79a0-4fb8-888e-f35b0114f959
AUTH_ID=N3W_T1_CORE_UPDATER_R8V13_07_INSTALL_CUTOVER_20261124_03
REMOTE_STAGE=/tmp/n3w-r8v13-07-u5-install-continuation-20261124-03
EXPECTED_LIVE_SHA=d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
EXPECTED_COMPOSE_SHA=6cd522b55136beceb8661820896351238d2218c23c3b3e71e98a7521ac67f0f4
EXPECTED_MANIFEST_SHA=5fbae3dedc6af008fec90efc24e75349ce82fc3a538e935806bef6ab3cbc4a36

summary() {
python3 - "$TX_FILE" <<'PY'
import json,sys
try:
 d=json.load(open(sys.argv[1]))
except Exception as e:
 print('SUMMARY_READ_ERROR='+type(e).__name__)
 raise SystemExit(0)
for k in ('transaction_id_sha256','status','phase','failure_code','recovery_required','authorization_claimed','authorization_consumed','authorization_id_sha256','pre_cutover_predecessor_restored','predecessor_release_observed','target_loaded_image_id','target_activation'):
 print(f'{k.upper()}={json.dumps(d.get(k),separators=(",",":"))}')
print('PREDECESSOR_START_PRESENT='+str('predecessor_start' in d).lower())
print('PREDECESSOR_RELEASE_INTENT_PRESENT='+str('predecessor_release_intent' in d).lower())
print('HA_DATA_RESTORE_PRESENT='+str('ha_data_restore' in d).lower())
print('TARGET_ACCEPTANCE_PRESENT='+str('target_acceptance' in d).lower())
PY
}

stop() {
 rc=$?
 echo FRESH_INSTALL_CONTINUATION_RESULT=STOP
 echo EXIT_CODE="$rc"
 summary || true
 echo DO_NOT_REPLAY_INSTALL_INTENT=true
 exit "$rc"
}
trap stop ERR

echo PHASE=U5_CONTINUATION_PREFLIGHT
test ! -e "$REMOTE_STAGE"
mkdir -m 700 "$REMOTE_STAGE"
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$EXPECTED_LIVE_SHA"
test "$(sha256sum "$COMPOSE" | awk '{print $1}')" = "$EXPECTED_COMPOSE_SHA"
test "$(sha256sum "$APPROVED" | awk '{print $1}')" = "$EXPECTED_MANIFEST_SHA"
python3 - "$TX_FILE" "$TX" "$USB_UUID" "$TARGET_REF" "$PRED_REF" <<'PY'
import json,sys
p,tx,uuid,target,pred=sys.argv[1:]
d=json.load(open(p))
assert d['transaction_id_sha256']==tx
assert d['status']=='ACTIVE' and d['phase']=='U5_INSTALL_REQUESTED_REVALIDATING'
assert d['recovery_required'] is False
assert d['authorization_claimed'] is False and d['authorization_consumed'] is False
assert d.get('authorization_id_sha256') is None
assert 'predecessor_start' not in d
assert 'predecessor_release_intent' not in d
assert 'target_loaded_image_id' not in d
assert 'target_activation' not in d
assert d['usb_binding_mode']=='existing_filesystem'
assert d['usb_filesystem_uuid']==uuid
assert d['target_image_ref']==target and d['current_image_ref']==pred
assert d['target_artifact_verified'] is True
m=d['prepared_image_materials']
assert m['target']['image_ref']==target and m['predecessor']['image_ref']==pred
print('DURABLE_U5=PASS')
PY
python3 - "$PIN" "$EXPECTED_MANIFEST_SHA" <<'PY'
import json,sys,time
p,manifest=sys.argv[1:]
d=json.load(open(p))
assert d['schema']=='gh.n3w-t1-ha-release-pin/1'
assert d['manifest_sha256']==manifest
assert isinstance(d['expires_at_unix'],int) and d['expires_at_unix']>time.time()
print('CURRENT_RELEASE_PIN_VALID=PASS')
PY
/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$PRED_REF" "$MANAGER_REF" "$BROKER_REF" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
_,live,txp,pred,manager,broker=sys.argv
d=json.load(open(txp))
r=LocalHaPredecessorRuntime()
b=r.capture_start_binding(d)
assert b['images']['homeassistant']['reference']==pred
assert b['images']['manager']['reference']==manager
assert b['images']['broker']['reference']==broker
print('PREDECESSOR_RUNTIME_BEFORE_AUTHORITY=PASS')
print('CURRENT_LAUNCH_SHA256='+b['launch_sha256'])
PY
if docker image inspect "$TARGET_REF" >/dev/null 2>&1; then
  echo TARGET_10_0_PRESENT_BEFORE_AUTHORITY=true
  false
else
  echo TARGET_10_0_PRESENT_BEFORE_AUTHORITY=false
fi
python3 - "$INSTALL_AUTH" <<'PY'
import json,sys,time
p=sys.argv[1]
try:
 d=json.load(open(p))
except FileNotFoundError:
 print('EXISTING_INSTALL_AUTHORITY=ABSENT')
 raise SystemExit(0)
assert isinstance(d.get('expires_at_unix'),int) and d['expires_at_unix']<=time.time()
print('EXISTING_INSTALL_AUTHORITY=EXPIRED_NONREUSABLE')
print('EXISTING_INSTALL_AUTHORIZATION_ID='+repr(d.get('authorization_id')))
PY

echo PHASE=FRESH_VALID_INSTALL_AUTHORITY
REQ="$REMOTE_STAGE/install-authority-request.json"
/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$REQ" "$AUTH_ID" <<'PY'
import json,os,sys,time
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import requested_install_binding_sha256
from n3w_t1_core_updater_v2_common import AUTHORIZATION_ID
_,live,txp,out,auth=sys.argv
assert AUTHORIZATION_ID.fullmatch(auth) is not None
d=json.load(open(txp))
assert d['status']=='ACTIVE' and d['phase']=='U5_INSTALL_REQUESTED_REVALIDATING'
req={
 'transaction_id_sha256':d['transaction_id_sha256'],
 'expires_at_unix':int(time.time())+21600,
 'binding_sha256':requested_install_binding_sha256(d),
 'authorization_id':auth,
}
fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
 json.dump(req,f,sort_keys=True,separators=(',',':')); f.write('\n'); f.flush(); os.fsync(f.fileno())
print('INSTALL_REQUEST_BINDING_SHA256='+req['binding_sha256'])
print('INSTALL_REQUEST_AUTHORIZATION_ID='+auth)
print('INSTALL_REQUEST_EXPIRES_AT_UNIX='+str(req['expires_at_unix']))
PY
/usr/bin/python3 -I "$LIVE" --issue-install-authority "$REQ"
python3 - "$INSTALL_AUTH" "$REQ" "$AUTH_ID" <<'PY'
import hashlib,json,sys,time
p,rq,auth=sys.argv[1:]
d=json.load(open(p)); q=json.load(open(rq))
assert d['schema']=='gh.n3w-t1-ha-install-authority/3'
assert d['binding_sha256']==q['binding_sha256']
assert d['authorization_id']==auth
assert d['expires_at_unix']==q['expires_at_unix'] and d['expires_at_unix']>time.time()
assert isinstance(d.get('launch_sha256'),str) and len(d['launch_sha256'])==64
print('FRESH_VALID_INSTALL_AUTHORITY=PASS')
print('FRESH_INSTALL_AUTHORITY_SHA256='+hashlib.sha256(open(p,'rb').read()).hexdigest())
print('FRESH_INSTALL_LAUNCH_SHA256='+d['launch_sha256'])
PY
python3 - "$TX_FILE" "$TX" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d['transaction_id_sha256']==sys.argv[2]
assert d['status']=='ACTIVE' and d['phase']=='U5_INSTALL_REQUESTED_REVALIDATING'
assert d['authorization_claimed'] is False and d['authorization_consumed'] is False
assert d.get('authorization_id_sha256') is None
assert 'predecessor_start' not in d
print('POST_AUTHORITY_PREDESTRUCTIVE_STATE=PASS')
PY

echo PHASE=PRODUCT_INSTALL_U5_TO_TERMINAL
set +e
systemctl start n3w-t1-ha-recovery-retry.service
WORKER_RC=$?
set -e
echo INSTALL_WORKER_RC="$WORKER_RC"
summary

RECOVERY_ACTION=$(python3 - "$TX_FILE" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
active=d.get('status')=='ACTIVE'
phase=d.get('phase')
needs=active and (
 d.get('recovery_required') is True
 or 'predecessor_start' in d
 or phase in {'U9_LIVE_AUTHORIZATION_CLAIMED','U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED','U11_TARGET_INSTALLED_STARTED','U12_TARGET_ACCEPTANCE'}
)
print('resume' if needs else 'none')
PY
)
echo RECOVERY_CONTINUATION_ACTION="$RECOVERY_ACTION"
if [ "$RECOVERY_ACTION" = resume ]; then
  echo PHASE=AUTHORIZED_PRODUCT_RECOVERY_CONTINUATION
  set +e
  /usr/bin/python3 -I "$LIVE" --resume-pending
  RECOVERY_RC=$?
  set -e
  echo RECOVERY_CONTINUATION_RC="$RECOVERY_RC"
  summary
fi

echo PHASE=FINAL_DURABLE_CLASSIFICATION
FINAL_CLASS=$(python3 - "$TX_FILE" "$TX" "$AUTH_ID" <<'PY'
import hashlib,json,sys
p,tx,auth=sys.argv[1:]
d=json.load(open(p))
assert d['transaction_id_sha256']==tx
if d['status']=='COMMITTED' and d['phase']=='U13A_COMMITTED':
 assert d['authorization_claimed'] is True and d['authorization_consumed'] is True
 assert d['authorization_id_sha256']==hashlib.sha256(auth.encode()).hexdigest()
 assert d['recovery_required'] is False
 assert d.get('target_activation')=='WRITES_POSSIBLE'
 assert isinstance(d.get('target_loaded_image_id'),str) and d['target_loaded_image_id'].startswith('sha256:')
 ta=d.get('target_acceptance')
 assert isinstance(ta,dict) and isinstance(ta.get('receipt'),dict)
 receipt=ta['receipt']
 obs=receipt.get('observations')
 assert isinstance(obs,dict) and set(obs)=={'monitoring_path','protected_data'}
 assert all(isinstance(v,str) and len(v)==64 for v in obs.values())
 assert receipt['images']['homeassistant']['reference']==d['target_image_ref']
 assert receipt['images']['homeassistant']['runtime_id']==d['target_loaded_image_id']
 print('committed')
elif d['status']=='ROLLED_BACK' and d['phase']=='U13B_ROLLED_BACK':
 print('rolled_back')
else:
 print('stopped')
PY
)
echo FINAL_CLASS="$FINAL_CLASS"

if [ "$FINAL_CLASS" = committed ]; then
  /usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$TARGET_REF" "$MANAGER_REF" "$BROKER_REF" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
_,live,txp,target,manager,broker=sys.argv
d=json.load(open(txp)); r=LocalHaPredecessorRuntime()
ha=r._runtime('homeassistant'); ma=r._runtime('manager'); br=r._runtime('broker')
assert ha['image_ref']==target and ha['image_id']==d['target_loaded_image_id']
assert ma['image_ref']==manager and br['image_ref']==broker
assert ha['restart_count']==0 and ma['restart_count']==0 and br['restart_count']==0
print('POST_COMMIT_RUNTIME=PASS')
print('RUNTIME_HOMEASSISTANT='+json.dumps(ha,sort_keys=True,separators=(',',':')))
print('RUNTIME_MANAGER='+json.dumps(ma,sort_keys=True,separators=(',',':')))
print('RUNTIME_BROKER='+json.dumps(br,sort_keys=True,separators=(',',':')))
print('TARGET_ACCEPTANCE_RECEIPT=PASS')
print('BUSINESS_HEALTH_FROM_ACCEPTANCE=PASS')
PY
  test "$(systemctl is-active n3wfc4-services-activation.service)" = active
  test "$(systemctl is-active n3wfc4-broker-activation.service)" = active
  python3 - "$TX_FILE" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
print('FINAL_TRANSACTION_SHA256_PENDING_EXTERNAL_PRINT=true')
print('TARGET_ACCEPTANCE='+json.dumps(d['target_acceptance'],sort_keys=True,separators=(',',':')))
PY
  echo FINAL_TRANSACTION_SHA256="$(sha256sum "$TX_FILE" | awk '{print $1}')"
  echo FRESH_INSTALL_CONTINUATION_RESULT=PASS
  echo R8V13_07_RESULT=PASS
  echo R8V13_07_TERMINAL=U13A_COMMITTED
  echo BROKER_OTA_EXECUTED=false
  echo HOST_REBOOT_EXECUTED=false
  echo USB_FORMAT_EXECUTED=false
  echo USB_HISTORY_DELETE_EXECUTED=false
  echo NEXT_TASK=R8V13_08
  trap - ERR
  exit 0
fi

if [ "$FINAL_CLASS" = rolled_back ]; then
  /usr/bin/python3 -I - "$LIVE" "$PRED_REF" "$MANAGER_REF" "$BROKER_REF" <<'PY'
import sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
_,live,pred,manager,broker=sys.argv
r=LocalHaPredecessorRuntime()
ha=r._runtime('homeassistant'); ma=r._runtime('manager'); br=r._runtime('broker')
assert ha['image_ref']==pred and ma['image_ref']==manager and br['image_ref']==broker
print('ROLLBACK_RUNTIME_HEALTH=PASS')
PY
  echo FRESH_INSTALL_CONTINUATION_RESULT=ROLLED_BACK
  echo R8V13_07_RESULT=NOT_PASS
  echo R8V13_08_BLOCKED=true
  echo DO_NOT_REPLAY=true
  trap - ERR
  exit 2
fi

echo FRESH_INSTALL_CONTINUATION_RESULT=STOPPED_NONTERMINAL
summary
echo R8V13_07_RESULT=NOT_PASS
echo R8V13_08_BLOCKED=true
echo DO_NOT_REPLAY=true
trap - ERR
exit 3
REMOTE_EOF
