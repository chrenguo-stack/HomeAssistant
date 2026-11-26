#!/bin/bash
set -euo pipefail

HOST="${N3W_T1_SSH_TARGET:?N3W_T1_SSH_TARGET required}"
EXPECTED_TX_ID="d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4"
EXPECTED_OLD_PYZ_SHA256="5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a"
EXPECTED_NEW_PYZ_SHA256="d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e"
EXPECTED_NEW_MANIFEST_SHA256="489aa375fda2b0fba76ee4e9bd30ab168ce9ee00feff05ee074af5b656d1eca8"
EXPECTED_SOURCE_HEAD="a9b76d77c2a930a21089af7fe0cc814f4db60a9a"
EXPECTED_ARTIFACT_ID="14939405227"
EXPECTED_ARTIFACT_SHA256="9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5"

ssh "$HOST" 'bash -s' -- "$EXPECTED_TX_ID" "$EXPECTED_OLD_PYZ_SHA256" "$EXPECTED_NEW_PYZ_SHA256" "$EXPECTED_NEW_MANIFEST_SHA256" "$EXPECTED_SOURCE_HEAD" "$EXPECTED_ARTIFACT_ID" "$EXPECTED_ARTIFACT_SHA256" <<'REMOTE_EOF'
set -euo pipefail
EXPECTED_TX_ID="$1"
EXPECTED_OLD_PYZ_SHA256="$2"
EXPECTED_NEW_PYZ_SHA256="$3"
EXPECTED_NEW_MANIFEST_SHA256="$4"
EXPECTED_SOURCE_HEAD="$5"
EXPECTED_ARTIFACT_ID="$6"
EXPECTED_ARTIFACT_SHA256="$7"

TX_FILE=/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json
LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
ENV=/etc/n3wfc4/docker-compose.env
USB_UUID=b72ac2fc-79a0-4fb8-888e-f35b0114f959
PRED_REF=local/n3w-homeassistant:2026.10.4-5881590f
PRED_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
TARGET_REF=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
MANAGER_REF=local/greenhouse-manager:fresh-1cae18039eee
MANAGER_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
BROKER_REF=local/n3w-mosquitto:2.1.2-3184566d
BROKER_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563

echo PHASE=R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT

test -f "$TX_FILE"
test -f "$LIVE"
LIVE_SHA="$(sha256sum "$LIVE" | awk '{print $1}')"
test "$LIVE_SHA" = "$EXPECTED_OLD_PYZ_SHA256"
test "$LIVE_SHA" != "$EXPECTED_NEW_PYZ_SHA256"
TX_SHA="$(sha256sum "$TX_FILE" | awk '{print $1}')"
ENV_SHA="$(sha256sum "$ENV" | awk '{print $1}')"

python3 - "$TX_FILE" "$EXPECTED_TX_ID" "$TARGET_ID" <<'PY'
import json,sys
p,txid,target_id=sys.argv[1:4]
d=json.load(open(p))
expected={
 "transaction_id_sha256":txid,
 "status":"ACTIVE",
 "phase":"U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED",
 "failure_code":None,
 "recovery_required":True,
 "authorization_claimed":True,
 "authorization_consumed":True,
 "authorization_id_sha256":"6976d68fd1b6828b630fd05751c2855afd84efc65639753f1a318189fff62f50",
 "predecessor_release_observed":True,
 "target_loaded_image_id":target_id,
 "target_activation":"BINDING",
}
for k,v in expected.items():
    if d.get(k)!=v:
        raise SystemExit(f"TX_DRIFT:{k}:{d.get(k)!r}")
if d.get("current_image_ref")!="local/n3w-homeassistant:2026.10.4-5881590f":
    raise SystemExit("CURRENT_IMAGE_DRIFT")
if d.get("target_image_ref")!="local/n3w-homeassistant:2026.10.0-0c73235a":
    raise SystemExit("TARGET_IMAGE_DRIFT")
if "predecessor_start" not in d:
    raise SystemExit("PREDECESSOR_START_MISSING")
if "predecessor_release_intent" not in d:
    raise SystemExit("PREDECESSOR_RELEASE_INTENT_MISSING")
if "target_acceptance" not in d:
    raise SystemExit("TARGET_ACCEPTANCE_MISSING")
print("TRANSACTION_BINDING=PASS")
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
    raise SystemExit("HA_OTA_VERSION_ENV_DRIFT")
print("TARGET_BINDING_ENV=PASS")
PY

test "$(docker image inspect "$TARGET_REF" --format '{{.Id}}')" = "$TARGET_ID"
if docker image inspect "$PRED_REF" >/dev/null 2>&1; then
  PRED_PRESENT=true
  PRED_OBSERVED_ID="$(docker image inspect "$PRED_REF" --format '{{.Id}}')"
  test "$PRED_OBSERVED_ID" = "$PRED_ID"
else
  PRED_PRESENT=false
  PRED_OBSERVED_ID=absent
fi

test "$(docker image inspect "$MANAGER_REF" --format '{{.Id}}')" = "$MANAGER_ID"
test "$(docker image inspect "$BROKER_REF" --format '{{.Id}}')" = "$BROKER_ID"

RETRY_STATE="$(systemctl is-active n3w-t1-ha-recovery-retry.service || true)"
case "$RETRY_STATE" in
  inactive|failed) ;;
  *) echo "RETRY_SERVICE_NOT_QUIET=$RETRY_STATE"; exit 31 ;;
esac
test "$(systemctl is-active n3w-t1-ha-recovery-retry.timer)" = active
test "$(systemctl is-enabled n3w-t1-ha-recovery-retry.timer)" = enabled

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
d=json.load(open(sys.argv[2]))
r=LocalHaPredecessorRuntime()
binding,origins=r._restart_binding()
print("LIVE_LAUNCH_SHA256="+binding["launch_sha256"])
print("LIVE_HA_REF="+binding["images"]["homeassistant"]["reference"])
print("LIVE_HA_ID="+binding["images"]["homeassistant"]["runtime_id"])
print("ROLLBACK_WRITERS_QUIESCED="+str(r.rollback_writers_quiesced()).lower())
print("LIVE_BINDING_JSON="+json.dumps(binding,sort_keys=True,separators=(",",":")))
print("PREDECESSOR_START_JSON="+json.dumps(d["predecessor_start"],sort_keys=True,separators=(",",":")))
PY

MOUNT_TARGET="$(findmnt --list --noheadings --source "UUID=$USB_UUID" --output TARGET | awk 'NF{print; exit}')"
test -n "$MOUNT_TARGET"

echo TX_FILE_SHA256="$TX_SHA"
echo LIVE_OLD_PYZ_SHA256="$LIVE_SHA"
echo COMPOSE_ENV_SHA256="$ENV_SHA"
echo PREDECESSOR_IMAGE_PRESENT="$PRED_PRESENT"
echo PREDECESSOR_IMAGE_ID="$PRED_OBSERVED_ID"
echo USB_MOUNT_TARGET="$MOUNT_TARGET"
echo EXPECTED_SOURCE_HEAD="$EXPECTED_SOURCE_HEAD"
echo EXPECTED_ARTIFACT_ID="$EXPECTED_ARTIFACT_ID"
echo EXPECTED_ARTIFACT_SHA256="$EXPECTED_ARTIFACT_SHA256"
echo EXPECTED_NEW_MANIFEST_SHA256="$EXPECTED_NEW_MANIFEST_SHA256"
echo EXPECTED_NEW_PYZ_SHA256="$EXPECTED_NEW_PYZ_SHA256"
echo LIVE_MUTATION=false
echo INSTALL_REPLAY=false
echo RESULT=R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT_PASS
REMOTE_EOF
