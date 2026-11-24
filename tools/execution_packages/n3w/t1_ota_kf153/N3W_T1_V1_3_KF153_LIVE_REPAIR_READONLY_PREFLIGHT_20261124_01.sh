#!/bin/bash
set -euo pipefail
HOST="${N3W_T1_SSH_TARGET:?N3W_T1_SSH_TARGET required}"
EXPECTED_TX_SHA256="b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0"
EXPECTED_OLD_PYZ_SHA256="d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30"
EXPECTED_NEW_PYZ_SHA256="5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a"
EXPECTED_NEW_MANIFEST_SHA256="90e83d4c4ce2a25e6c9fbce0245344b8c3ba247a4b5ecc58d4e93c4ceb169877"
EXPECTED_SOURCE_HEAD="90ce32ce4b6c329fd38c2771e352d129d6d00a86"
ssh "$HOST" 'bash -s' -- "$EXPECTED_TX_SHA256" "$EXPECTED_OLD_PYZ_SHA256" "$EXPECTED_NEW_PYZ_SHA256" "$EXPECTED_NEW_MANIFEST_SHA256" "$EXPECTED_SOURCE_HEAD" <<'REMOTE_EOF'
set -euo pipefail
EXPECTED_TX_SHA256="$1"
EXPECTED_OLD_PYZ_SHA256="$2"
EXPECTED_NEW_PYZ_SHA256="$3"
EXPECTED_NEW_MANIFEST_SHA256="$4"
EXPECTED_SOURCE_HEAD="$5"
ROOT=/var/lib/n3w-t1-core-updater
TX_FILE="$ROOT/homeassistant-usb-upgrade.json"
LIVE=/opt/n3w-t1-core-updater/ha-recovery.pyz
COMPOSE=/etc/n3wfc4/docker-compose.yml
TARGET_REF=local/n3w-homeassistant:2026.10.0-0c73235a
PRED_REF=local/n3w-homeassistant:2026.10.4-5881590f
PRED_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
MANAGER_REF=local/greenhouse-manager:fresh-1cae18039eee
MANAGER_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
BROKER_REF=local/n3w-mosquitto:2.1.2-3184566d
BROKER_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
EXPECTED_LAUNCH=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
EXPECTED_COMPOSE=6cd522b55136beceb8661820896351238d2218c23c3b3e71e98a7521ac67f0f4

echo PHASE=KF153_LIVE_REPAIR_READONLY_PREFLIGHT

test -f "$TX_FILE"
test "$(sha256sum "$TX_FILE" | awk '{print $1}')" = "$EXPECTED_TX_SHA256"
test -f "$LIVE"
LIVE_SHA="$(sha256sum "$LIVE" | awk '{print $1}')"
test "$LIVE_SHA" = "$EXPECTED_OLD_PYZ_SHA256"
test "$LIVE_SHA" != "$EXPECTED_NEW_PYZ_SHA256"
test "$(sha256sum "$COMPOSE" | awk '{print $1}')" = "$EXPECTED_COMPOSE"

python3 - "$TX_FILE" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p))
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
for k,v in expected.items():
    if d.get(k)!=v:
        raise SystemExit(f"TX_DRIFT:{k}")
for key in ("predecessor_release_intent","ha_data_restore"):
    if key in d:
        raise SystemExit(f"TX_UNEXPECTED:{key}")
if d.get("current_image_ref")!="local/n3w-homeassistant:2026.10.4-5881590f":
    raise SystemExit("TX_CURRENT_IMAGE_DRIFT")
if d.get("target_image_ref")!="local/n3w-homeassistant:2026.10.0-0c73235a":
    raise SystemExit("TX_TARGET_IMAGE_DRIFT")
print("DURABLE_TERMINAL_TRANSACTION=PASS")
PY

for spec in   "n3wfc4-services-activation.service:active"   "n3wfc4-broker-activation.service:active"   "n3w-t1-ha-recovery-retry.service:inactive"   "n3w-t1-ha-recovery-retry.timer:active"   "n3w-t1-ha-ota-ipc.socket:active"; do
  unit="${spec%%:*}"
  expected="${spec##*:}"
  test "$(systemctl is-active "$unit")" = "$expected"
done
for unit in n3w-t1-ha-recovery-startup.service n3w-t1-ha-recovery-retry.timer n3w-t1-ha-ota-ipc.socket; do
  test "$(systemctl is-enabled "$unit")" = enabled
done

test "$(docker ps -q --filter label=com.docker.compose.project=n3wfc4 --filter label=com.docker.compose.service=homeassistant | wc -l)" -eq 1
test "$(docker ps -q --filter label=com.docker.compose.project=n3wfc4 --filter label=com.docker.compose.service=manager | wc -l)" -eq 1
test "$(docker ps -q --filter label=com.docker.compose.project=n3wfc4 --filter label=com.docker.compose.service=broker | wc -l)" -eq 1

python3 - "$PRED_REF" "$PRED_ID" "$MANAGER_REF" "$MANAGER_ID" "$BROKER_REF" "$BROKER_ID" <<'PY'
import json,subprocess,sys
pairs=list(zip(sys.argv[1::2],sys.argv[2::2]))
services=("homeassistant","manager","broker")
for service,(ref,image_id) in zip(services,pairs):
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
docker image inspect "$PRED_REF" >/dev/null

test "$(sha256sum /opt/n3w-t1-core-updater/ha-ota-candidate.compose.yml | awk '{print $1}')" = c6381d8cfa39ffb1fa82ef0bce7705cf7ff80f45ec2144a507cdfc5f69e2b9bd
test "$(sha256sum /opt/n3w-t1-core-updater/ha-ota-monitoring.configuration.yaml | awk '{print $1}')" = 97c26f3c46977fd0e3954dfbed3e87bdbedbe8c023bf897c2ebe3fa01460f003
test "$(sha256sum /opt/n3w-t1-core-updater/n3w_ota_monitoring/manifest.json | awk '{print $1}')" = dabda554722edbc46fe98535e24591c3d0cd92f6a30a2800fff4a03a14b7d424
test "$(sha256sum /opt/n3w-t1-core-updater/n3w_ota_monitoring/__init__.py | awk '{print $1}')" = 94347a2d183fa5ba2a0c3570f48f812f2cd686fecc4d966cc2f904df004b2d1a
test "$(sha256sum /etc/systemd/system/n3w-t1-ha-ota-ipc.service | awk '{print $1}')" = 101ae89088bf5749e3ec97e853e5c994f2622ac3b72826aba65d89c52a3c4538
test "$(sha256sum /etc/systemd/system/n3w-t1-ha-ota-ipc.socket | awk '{print $1}')" = 3fe49568640fcd84b53e0b20b1c225b678855fbd28993adabab0fb9048cd5c49
test "$(sha256sum /etc/systemd/system/n3w-t1-ha-recovery-retry.service | awk '{print $1}')" = 581ed80caa6a503e3a0c328963c15ea6a6e89594feac2ce9f2fa4c9e153a200a
test "$(sha256sum /etc/systemd/system/n3w-t1-ha-recovery-retry.timer | awk '{print $1}')" = 98aa71efe365c5ca87cbe52a587a2e156bb53d41ae9bc9162744028149650b41
test "$(sha256sum /etc/systemd/system/n3w-t1-ha-recovery-startup.service | awk '{print $1}')" = ad0f033d9c9df54e82b95053c222aa01e42daffcaf4ef103a12f65773ca25058
test "$(sha256sum /etc/systemd/system/n3wfc4-services-activation.service.d/ota-ha-recovery.conf | awk '{print $1}')" = 56122da602fb46af0b3fba6b839dab9cd7ac54905b163a6ed18e124fc14910e2

test "$(systemctl show --property=NeedDaemonReload --value n3wfc4-services-activation.service)" = no

/usr/bin/python3 -I - "$LIVE" "$TX_FILE" "$EXPECTED_LAUNCH" <<'PY'
import json,sys
sys.path.insert(0,sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime
transaction=json.load(open(sys.argv[2]))
runtime=LocalHaPredecessorRuntime()
binding=runtime.capture_start_binding(transaction)
if binding["launch_sha256"]!=sys.argv[3]:
    raise SystemExit("LAUNCH_SHA_DRIFT")
print("CURRENT_PREDECESSOR_BINDING=PASS")
print("CURRENT_LAUNCH_SHA256="+binding["launch_sha256"])
PY

echo EXPECTED_SOURCE_HEAD="$EXPECTED_SOURCE_HEAD"
echo EXPECTED_NEW_MANIFEST_SHA256="$EXPECTED_NEW_MANIFEST_SHA256"
echo EXPECTED_NEW_PYZ_SHA256="$EXPECTED_NEW_PYZ_SHA256"
echo LIVE_OLD_PYZ_SHA256="$LIVE_SHA"
echo NON_PYZ_SUCCESSOR_PARITY=PASS
echo TARGET_10_0_PRESENT=false
echo LIVE_MUTATION=false
echo RESULT=KF153_LIVE_REPAIR_READONLY_PREFLIGHT_PASS
REMOTE_EOF
