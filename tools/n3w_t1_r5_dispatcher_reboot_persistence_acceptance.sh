#!/bin/bash
set -Eeuo pipefail

MODE="${1:-}"
LIVE_GUARD=/usr/local/sbin/n3w-broker-ingress-guard
GUARD_UNIT=/etc/systemd/system/n3wfc4-broker-ingress-guard.service
ACTIVATION_UNIT=/etc/systemd/system/n3wfc4-broker-activation.service
DISPATCHER=/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
ACTIVATION_ENV=/etc/n3wfc4/broker-activation.env
GUARD=n3wfc4-broker-ingress-guard.service
ACTIVATION=n3wfc4-broker-activation.service
PRE=/root/n3wfc4-r5-reboot-persistence-acceptance-20260927-01.pre
RESULT=/root/n3wfc4-r5-reboot-persistence-acceptance-20260927-01.result

EXPECTED_GUARD_BLOB=795903b06c7ee93a0602649e478bc070723ab8c0
EXPECTED_GUARD_UNIT_BLOB=b68d7d71ee43b26cb0481f0b278cf5739f3a2911
EXPECTED_ACTIVATION_UNIT_BLOB=c170c87d035b5c0d28c440514d40b5df360328d2
EXPECTED_DISPATCHER_BLOB=f733f5a1cfc936f77d1fabc383ccf262264e33d2

blob_sha() {
python3 - "$1" <<'PY'
import hashlib
import pathlib
import sys

data=pathlib.Path(sys.argv[1]).read_bytes()
payload=b"blob "+str(len(data)).encode()+b"\0"+data
print(hashlib.sha1(payload).hexdigest())
PY
}

get_pre() {
local key="$1"
awk -v key="$key" 'index($0,key "=")==1 {sub(/^[^=]*=/,""); print; exit}' "$PRE"
}

broker_id() {
docker ps -q --filter label=com.docker.compose.project=n3wfc4 --filter label=com.docker.compose.service=broker
}

manager_id() {
docker inspect greenhouse-manager --format '{{.Id}}'
}

manager_restart() {
docker inspect greenhouse-manager --format '{{.RestartCount}}'
}

guard_snapshot() {
python3 - "$LIVE_GUARD" <<'PY'
import runpy
import subprocess
import sys

tool=runpy.run_path(sys.argv[1])
payload=subprocess.run(
    ["iptables-save","-t","filter"],
    check=True,
    capture_output=True,
    text=True,
).stdout
inventory=tool["parse_firewall_inventory"](payload)
decision=tool["read_network_decision"]()

if decision.trusted_subnet is None:
    raise SystemExit("trusted subnet unavailable")

tool["_validate_prestate"](inventory)
tool["validate_applied_state"](inventory, decision.trusted_subnet)

if inventory.anchor_positions != (1,):
    raise SystemExit("DOCKER-USER anchor invalid")
if inventory.input_anchor_positions != (1,):
    raise SystemExit("INPUT anchor invalid")
if inventory.ambiguous_owned_rules:
    raise SystemExit("ambiguous DOCKER-USER owned rule")
if inventory.ambiguous_owned_input_rules:
    raise SystemExit("ambiguous INPUT owned rule")
if inventory.foreign_custom_chain_refs:
    raise SystemExit("foreign custom-chain reference")

print("NETWORK_DECISION_REASON="+decision.reason)
print("TRUSTED_NETWORK_SHA256="+str(tool["_network_sha256"](decision.trusted_subnet)))
print("DOCKER_USER_ANCHOR_POSITION=1")
print("INPUT_ANCHOR_POSITION=1")
print("R5_POLICY_EXACT=true")
PY
}

common_exact_check() {
[ "$(blob_sha "$LIVE_GUARD")" = "$EXPECTED_GUARD_BLOB" ]
[ "$(blob_sha "$GUARD_UNIT")" = "$EXPECTED_GUARD_UNIT_BLOB" ]
[ "$(blob_sha "$ACTIVATION_UNIT")" = "$EXPECTED_ACTIVATION_UNIT_BLOB" ]
[ "$(blob_sha "$DISPATCHER")" = "$EXPECTED_DISPATCHER_BLOB" ]
[ "$(stat -c '%a' "$LIVE_GUARD")" = "755" ]
[ "$(stat -c '%U:%G' "$LIVE_GUARD")" = "root:root" ]
[ "$(stat -c '%a' "$GUARD_UNIT")" = "644" ]
[ "$(stat -c '%U:%G' "$GUARD_UNIT")" = "root:root" ]
[ "$(stat -c '%a' "$ACTIVATION_UNIT")" = "644" ]
[ "$(stat -c '%U:%G' "$ACTIVATION_UNIT")" = "root:root" ]
[ "$(stat -c '%a' "$DISPATCHER")" = "755" ]
[ "$(stat -c '%U:%G' "$DISPATCHER")" = "root:root" ]
[ "$(stat -c '%a' "$ACTIVATION_ENV")" = "600" ]
[ "$(stat -c '%U:%G' "$ACTIVATION_ENV")" = "root:root" ]
}

prepare() {
umask 077
test ! -e "$PRE"
test ! -e "$RESULT"

common_exact_check

[ "$(systemctl is-active NetworkManager)" = "active" ]
[ "$(systemctl is-active docker)" = "active" ]
[ "$(systemctl is-active "$GUARD")" = "active" ]
[ "$(systemctl is-active "$ACTIVATION")" = "active" ]
[ "$(systemctl is-enabled NetworkManager)" = "enabled" ]
[ "$(systemctl is-enabled docker)" = "enabled" ]
[ "$(systemctl is-enabled "$GUARD")" = "enabled" ]
[ "$(systemctl is-enabled "$ACTIVATION")" = "enabled" ]

CONN_NAME="$(nmcli -g GENERAL.CONNECTION device show eth0 | head -n1)"
CONN_UUID="$(nmcli -g connection.uuid connection show "$CONN_NAME" | head -n1)"
IPV4_METHOD="$(nmcli -g ipv4.method connection show "$CONN_UUID" | head -n1)"
AUTOCONNECT="$(nmcli -g connection.autoconnect connection show "$CONN_UUID" | head -n1)"
ETH0_IPV4="$(nmcli -g IP4.ADDRESS device show eth0)"
ETH0_GATEWAY="$(nmcli -g IP4.GATEWAY device show eth0 | head -n1)"
BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"
BROKER_ID="$(broker_id)"
MANAGER_ID="$(manager_id)"
MANAGER_RESTART="$(manager_restart)"

[ -n "$CONN_NAME" ]
[ -n "$CONN_UUID" ]
[ "$IPV4_METHOD" = "auto" ]
[ "$AUTOCONNECT" = "yes" ]
[ -n "$ETH0_IPV4" ]
[ -n "$ETH0_GATEWAY" ]
[ -n "$BOOT_ID" ]
[ -n "$BROKER_ID" ]
[ -n "$MANAGER_ID" ]
[ "$(docker inspect "$BROKER_ID" --format '{{.State.Status}}')" = "running" ]
[ "$(docker inspect "$BROKER_ID" --format '{{.HostConfig.RestartPolicy.Name}}')" = "no" ]
[ "$(docker inspect "$BROKER_ID" --format '{{index .Config.Labels "com.docker.compose.project"}}')" = "n3wfc4" ]
[ "$(docker inspect greenhouse-manager --format '{{.State.Status}}')" = "running" ]

SNAPSHOT="$(guard_snapshot)"
printf '%s\n' "$SNAPSHOT"

TRUSTED_SHA="$(printf '%s\n' "$SNAPSHOT" | awk -F= '/^TRUSTED_NETWORK_SHA256=/{print $2}')"

cat > "$PRE" <<EOF
PREBOOT_BOOT_ID=$BOOT_ID
PREBOOT_UTC=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
PREBOOT_CONNECTION_NAME=$CONN_NAME
PREBOOT_CONNECTION_UUID=$CONN_UUID
PREBOOT_IPV4_METHOD=$IPV4_METHOD
PREBOOT_AUTOCONNECT=$AUTOCONNECT
PREBOOT_ETH0_IPV4=$ETH0_IPV4
PREBOOT_ETH0_GATEWAY=$ETH0_GATEWAY
PREBOOT_TRUSTED_NETWORK_SHA256=$TRUSTED_SHA
PREBOOT_BROKER_ID=$BROKER_ID
PREBOOT_MANAGER_ID=$MANAGER_ID
PREBOOT_MANAGER_RESTART_COUNT=$MANAGER_RESTART
EOF

chmod 0600 "$PRE"

echo "LIVE_GUARD_BLOB=$(blob_sha "$LIVE_GUARD")"
echo "LIVE_GUARD_UNIT_BLOB=$(blob_sha "$GUARD_UNIT")"
echo "LIVE_ACTIVATION_UNIT_BLOB=$(blob_sha "$ACTIVATION_UNIT")"
echo "LIVE_DISPATCHER_BLOB=$(blob_sha "$DISPATCHER")"
echo "NETWORKMANAGER_ENABLED=$(systemctl is-enabled NetworkManager)"
echo "DOCKER_ENABLED=$(systemctl is-enabled docker)"
echo "GUARD_ENABLED=$(systemctl is-enabled "$GUARD")"
echo "ACTIVATION_ENABLED=$(systemctl is-enabled "$ACTIVATION")"
echo "PREBOOT_BOOT_ID=$BOOT_ID"
echo "CONNECTION_NAME=$CONN_NAME"
echo "IPV4_METHOD=$IPV4_METHOD"
echo "AUTOCONNECT=$AUTOCONNECT"
echo "BROKER_ID_BEFORE=$BROKER_ID"
echo "BROKER_RESTART_POLICY=$(docker inspect "$BROKER_ID" --format '{{.HostConfig.RestartPolicy.Name}}')"
echo "MANAGER_ID_BEFORE=$MANAGER_ID"
echo "MANAGER_RESTART_COUNT_BEFORE=$MANAGER_RESTART"
echo "PRE_FILE_MODE=$(stat -c '%a' "$PRE")"
echo "PRE_FILE_OWNER=$(stat -c '%U:%G' "$PRE")"
echo "REBOOT_EXECUTED=false"
echo "PREPARATION_RESULT=PASS"
}

collect() {
umask 077
[ -f "$PRE" ]
test ! -e "$RESULT"
: > "$RESULT"
exec > >(tee -a "$RESULT") 2>&1

common_exact_check

PREBOOT_BOOT_ID="$(get_pre PREBOOT_BOOT_ID)"
PREBOOT_BROKER_ID="$(get_pre PREBOOT_BROKER_ID)"
PREBOOT_MANAGER_ID="$(get_pre PREBOOT_MANAGER_ID)"
PREBOOT_MANAGER_RESTART="$(get_pre PREBOOT_MANAGER_RESTART_COUNT)"
CURRENT_BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"

[ -n "$PREBOOT_BOOT_ID" ]
[ -n "$CURRENT_BOOT_ID" ]
[ "$CURRENT_BOOT_ID" != "$PREBOOT_BOOT_ID" ]

[ "$(systemctl is-active NetworkManager)" = "active" ]
[ "$(systemctl is-active docker)" = "active" ]
[ "$(systemctl is-active "$GUARD")" = "active" ]
[ "$(systemctl is-active "$ACTIVATION")" = "active" ]
[ "$(systemctl is-enabled NetworkManager)" = "enabled" ]
[ "$(systemctl is-enabled docker)" = "enabled" ]
[ "$(systemctl is-enabled "$GUARD")" = "enabled" ]
[ "$(systemctl is-enabled "$ACTIVATION")" = "enabled" ]

CONN_NAME="$(nmcli -g GENERAL.CONNECTION device show eth0 | head -n1)"
CONN_UUID="$(nmcli -g connection.uuid connection show "$CONN_NAME" | head -n1)"
IPV4_METHOD="$(nmcli -g ipv4.method connection show "$CONN_UUID" | head -n1)"
AUTOCONNECT="$(nmcli -g connection.autoconnect connection show "$CONN_UUID" | head -n1)"
CURRENT_IPV4="$(nmcli -g IP4.ADDRESS device show eth0)"
CURRENT_GATEWAY="$(nmcli -g IP4.GATEWAY device show eth0 | head -n1)"

[ -n "$CONN_NAME" ]
[ -n "$CONN_UUID" ]
[ "$IPV4_METHOD" = "auto" ]
[ "$AUTOCONNECT" = "yes" ]
[ -n "$CURRENT_IPV4" ]
[ -n "$CURRENT_GATEWAY" ]

SNAPSHOT="$(guard_snapshot)"
printf '%s\n' "$SNAPSHOT"

GUARD_LOG="$(journalctl -b -u "$GUARD" --no-pager -o cat)"
ACTIVATION_LOG="$(journalctl -b -u "$ACTIVATION" --no-pager -o cat)"
printf '%s\n' "$GUARD_LOG"
printf '%s\n' "$ACTIVATION_LOG"

GUARD_APPLY_COUNT="$(printf '%s\n' "$GUARD_LOG" | grep -c '"applied":true' || true)"
GUARD_PASS_COUNT="$(printf '%s\n' "$GUARD_LOG" | grep -c '"status":"PASS","applied":true' || true)"
GUARD_FAIL_CLOSED_COUNT="$(printf '%s\n' "$GUARD_LOG" | grep -c '"status":"FAIL_CLOSED","applied":true' || true)"
GUARD_ERROR_COUNT="$(printf '%s\n' "$GUARD_LOG" | grep -c '"status":"ERROR"' || true)"

[ "$GUARD_APPLY_COUNT" -ge 1 ]
[ "$GUARD_PASS_COUNT" -ge 1 ]
[ "$GUARD_ERROR_COUNT" = "0" ]

DOCKER_MONO="$(systemctl show docker.service -p ActiveEnterTimestampMonotonic --value)"
GUARD_MONO="$(systemctl show "$GUARD" -p ActiveEnterTimestampMonotonic --value)"
ACTIVATION_MONO="$(systemctl show "$ACTIVATION" -p ActiveEnterTimestampMonotonic --value)"

[ -n "$DOCKER_MONO" ]
[ -n "$GUARD_MONO" ]
[ -n "$ACTIVATION_MONO" ]
[ "$DOCKER_MONO" -gt 0 ]
[ "$GUARD_MONO" -gt 0 ]
[ "$ACTIVATION_MONO" -gt 0 ]
[ "$DOCKER_MONO" -le "$GUARD_MONO" ]
[ "$GUARD_MONO" -le "$ACTIVATION_MONO" ]

BROKER_ID="$(broker_id)"
MANAGER_ID="$(manager_id)"
MANAGER_RESTART="$(manager_restart)"

[ -n "$BROKER_ID" ]
[ -n "$MANAGER_ID" ]
[ "$(docker inspect "$BROKER_ID" --format '{{.State.Status}}')" = "running" ]
[ "$(docker inspect "$BROKER_ID" --format '{{.HostConfig.RestartPolicy.Name}}')" = "no" ]
[ "$(docker inspect "$BROKER_ID" --format '{{index .Config.Labels "com.docker.compose.project"}}')" = "n3wfc4" ]
[ "$(docker inspect greenhouse-manager --format '{{.State.Status}}')" = "running" ]
[ "$(ss -H -ltn 'sport = :8883' | wc -l | tr -d ' ')" = "1" ]

RECIPES_RUNNING="$(
docker ps -q --filter label=com.docker.compose.project=recipes --filter label=com.docker.compose.service=broker |
wc -l |
tr -d ' '
)"
[ "$RECIPES_RUNNING" = "0" ]

echo "PREBOOT_BOOT_ID=$PREBOOT_BOOT_ID"
echo "POSTBOOT_BOOT_ID=$CURRENT_BOOT_ID"
echo "BOOT_ID_CHANGED=true"
echo "NETWORKMANAGER_ACTIVE=$(systemctl is-active NetworkManager)"
echo "DOCKER_ACTIVE=$(systemctl is-active docker)"
echo "GUARD_ACTIVE=$(systemctl is-active "$GUARD")"
echo "ACTIVATION_ACTIVE=$(systemctl is-active "$ACTIVATION")"
echo "NETWORKMANAGER_ENABLED=$(systemctl is-enabled NetworkManager)"
echo "DOCKER_ENABLED=$(systemctl is-enabled docker)"
echo "GUARD_ENABLED=$(systemctl is-enabled "$GUARD")"
echo "ACTIVATION_ENABLED=$(systemctl is-enabled "$ACTIVATION")"
echo "GUARD_APPLIED_TRUE_COUNT=$GUARD_APPLY_COUNT"
echo "GUARD_PASS_APPLY_COUNT=$GUARD_PASS_COUNT"
echo "GUARD_FAIL_CLOSED_APPLY_COUNT=$GUARD_FAIL_CLOSED_COUNT"
echo "GUARD_ERROR_COUNT=$GUARD_ERROR_COUNT"
echo "DOCKER_ACTIVE_MONO=$DOCKER_MONO"
echo "GUARD_ACTIVE_MONO=$GUARD_MONO"
echo "ACTIVATION_ACTIVE_MONO=$ACTIVATION_MONO"
echo "BOOT_ORDER_DOCKER_GUARD_ACTIVATION=PASS"
echo "BROKER_ID_BEFORE=$PREBOOT_BROKER_ID"
echo "BROKER_ID_AFTER=$BROKER_ID"
echo "BROKER_STATE=$(docker inspect "$BROKER_ID" --format '{{.State.Status}}')"
echo "BROKER_RESTART_POLICY=$(docker inspect "$BROKER_ID" --format '{{.HostConfig.RestartPolicy.Name}}')"
echo "MANAGER_ID_BEFORE=$PREBOOT_MANAGER_ID"
echo "MANAGER_ID_AFTER=$MANAGER_ID"
echo "MANAGER_STATE=$(docker inspect greenhouse-manager --format '{{.State.Status}}')"
echo "MANAGER_RESTART_COUNT_BEFORE=$PREBOOT_MANAGER_RESTART"
echo "MANAGER_RESTART_COUNT_AFTER=$MANAGER_RESTART"
echo "TCP_8883_LISTEN_COUNT=$(ss -H -ltn 'sport = :8883' | wc -l | tr -d ' ')"
echo "RECIPES_BROKER_RUNNING_COUNT=$RECIPES_RUNNING"
echo "LIVE_GUARD_BLOB=$(blob_sha "$LIVE_GUARD")"
echo "LIVE_GUARD_UNIT_BLOB=$(blob_sha "$GUARD_UNIT")"
echo "LIVE_ACTIVATION_UNIT_BLOB=$(blob_sha "$ACTIVATION_UNIT")"
echo "LIVE_DISPATCHER_BLOB=$(blob_sha "$DISPATCHER")"
echo "POSTBOOT_REBOOT_PERSISTENCE=PASS"
echo "COLLECTION_RESULT=PASS"
}

case "$MODE" in
    prepare)
        prepare
        ;;
    collect)
        collect
        ;;
    *)
        echo "usage: $0 prepare|collect" >&2
        exit 2
        ;;
esac
