#!/bin/bash
set -Eeuo pipefail

LIVE_GUARD=/usr/local/sbin/n3w-broker-ingress-guard
DISPATCHER=/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
GUARD=n3wfc4-broker-ingress-guard.service
ACTIVATION=n3wfc4-broker-activation.service
RESULT=/root/n3wfc4-r5-link-cycle-acceptance-20260927-01.log
EXPECTED_GUARD_BLOB=795903b06c7ee93a0602649e478bc070723ab8c0
EXPECTED_DISPATCHER_BLOB=f733f5a1cfc936f77d1fabc383ccf262264e33d2
EXPECTED_MANAGER_ID=e6977f617caf9bcdb9aa2417a37a6edaff338f221638b668d4d0a0b991b77405
EXPECTED_MANAGER_RESTART=1846
SUCCESS=false
RECOVERY_EXECUTED=false
CONN_UUID=
CONN_NAME=
BROKER_ID_BEFORE=
MANAGER_ID_BEFORE=
MANAGER_RESTART_BEFORE=
FOREIGN_COUNT_BEFORE=
FOREIGN_SHA_BEFORE=

: > "$RESULT"
exec > >(tee -a "$RESULT") 2>&1

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

wait_disconnected() {
local deadline=$((SECONDS + 45))
while [ "$SECONDS" -lt "$deadline" ]; do
    local state
    local addresses
    state="$(nmcli -t -f GENERAL.STATE device show eth0 2>/dev/null || true)"
    addresses="$(nmcli -g IP4.ADDRESS device show eth0 2>/dev/null || true)"
    if ! printf '%s\n' "$state" | grep -q '^GENERAL.STATE:100' && [ -z "$addresses" ]; then
        return 0
    fi
    sleep 1
done
return 1
}

wait_connected() {
local deadline=$((SECONDS + 90))
while [ "$SECONDS" -lt "$deadline" ]; do
    local state
    local addresses
    state="$(nmcli -t -f GENERAL.STATE device show eth0 2>/dev/null || true)"
    addresses="$(nmcli -g IP4.ADDRESS device show eth0 2>/dev/null || true)"
    if printf '%s\n' "$state" | grep -q '^GENERAL.STATE:100' && [ -n "$addresses" ]; then
        return 0
    fi
    sleep 1
done
return 1
}

wait_guard_event_status() {
local since_epoch="$1"
local status="$2"
local deadline=$((SECONDS + 70))
while [ "$SECONDS" -lt "$deadline" ]; do
    if journalctl -u "$GUARD" --since "@$since_epoch" --no-pager -o cat 2>/dev/null |
        grep -q "\"status\":\"$status\",\"applied\":true"; then
        return 0
    fi
    sleep 1
done
return 1
}

firewall_snapshot() {
local expected_mode="$1"
python3 - "$LIVE_GUARD" "$expected_mode" <<'PY'
import hashlib
import runpy
import subprocess
import sys

tool=runpy.run_path(sys.argv[1])
mode=sys.argv[2]
payload=subprocess.run(
    ["iptables-save","-t","filter"],
    check=True,
    capture_output=True,
    text=True,
).stdout
inventory=tool["parse_firewall_inventory"](payload)
decision=tool["read_network_decision"]()
tool["_validate_prestate"](inventory)

if mode == "connected":
    if decision.trusted_subnet is None:
        raise SystemExit("trusted subnet unavailable")
else:
    if decision.trusted_subnet is not None:
        raise SystemExit("trusted subnet unexpectedly present")

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

foreign=[]
for raw in payload.splitlines():
    line=raw.strip()
    if not line.startswith("-A "):
        continue
    if line.startswith(f"-A {tool['CUSTOM_CHAIN']} "):
        continue
    if tool["_is_exact_anchor"](line):
        continue
    if tool["_is_exact_input_anchor"](line):
        continue
    foreign.append(line)

body="\n".join(foreign)+"\n"
print("NETWORK_DECISION_REASON="+decision.reason)
print("TRUSTED_NETWORK_SHA256="+str(tool["_network_sha256"](decision.trusted_subnet)))
print("FOREIGN_RULE_COUNT="+str(len(foreign)))
print("FOREIGN_RULES_SHA256="+hashlib.sha256(body.encode()).hexdigest())
print("DOCKER_USER_ANCHOR_POSITION=1")
print("INPUT_ANCHOR_POSITION=1")
print("R5_POLICY_EXACT=true")
PY
}

recover() {
set +e
if [ "$SUCCESS" = "true" ]; then
    return 0
fi
RECOVERY_EXECUTED=true
echo "=== RECOVERY START ==="
if [ -n "$CONN_UUID" ]; then
    for attempt in 1 2 3; do
        nmcli connection up uuid "$CONN_UUID" ifname eth0 >/dev/null 2>&1 || true
        if wait_connected; then
            echo "RECOVERY_LINK_ATTEMPT=$attempt"
            break
        fi
    done
fi
systemctl reload-or-restart "$GUARD" >/dev/null 2>&1 || true
systemctl start "$ACTIVATION" >/dev/null 2>&1 || true
echo "RECOVERY_ETH0_STATE=$(nmcli -t -f GENERAL.STATE device show eth0 2>/dev/null || true)"
echo "RECOVERY_ETH0_IPV4=$(nmcli -g IP4.ADDRESS device show eth0 2>/dev/null | tr '\n' ',' || true)"
echo "RECOVERY_GUARD_STATE=$(systemctl is-active "$GUARD" 2>/dev/null || true)"
echo "RECOVERY_ACTIVATION_STATE=$(systemctl is-active "$ACTIVATION" 2>/dev/null || true)"
echo "RECOVERY_BROKER_RUNNING_COUNT=$(docker ps -q --filter label=com.docker.compose.project=n3wfc4 --filter label=com.docker.compose.service=broker 2>/dev/null | wc -l | tr -d ' ')"
echo "RECOVERY_MANAGER_STATE=$(docker inspect greenhouse-manager --format '{{.State.Status}}' 2>/dev/null || true)"
echo "RECOVERY_MANAGER_RESTART_COUNT=$(docker inspect greenhouse-manager --format '{{.RestartCount}}' 2>/dev/null || true)"
echo "=== RECOVERY END ==="
}

on_error() {
local rc="$1"
trap - ERR EXIT
set +e
echo "PHASE_RESULT=FAIL"
echo "FAILURE_RC=$rc"
recover
echo "RECOVERY_EXECUTED=$RECOVERY_EXECUTED"
exit "$rc"
}

on_exit() {
local rc="$?"
if [ "$rc" -ne 0 ] && [ "$SUCCESS" != "true" ]; then
    trap - ERR EXIT
    recover
fi
}

trap 'on_error $?' ERR
trap on_exit EXIT

echo "=== PRECHECK ==="
[ "$(id -u)" = "0" ]
[ "$(blob_sha "$LIVE_GUARD")" = "$EXPECTED_GUARD_BLOB" ]
[ "$(blob_sha "$DISPATCHER")" = "$EXPECTED_DISPATCHER_BLOB" ]
[ "$(systemctl is-active NetworkManager)" = "active" ]
[ "$(systemctl is-active docker)" = "active" ]
[ "$(systemctl is-active "$GUARD")" = "active" ]
[ "$(systemctl is-active "$ACTIVATION")" = "active" ]

CONN_NAME="$(nmcli -g GENERAL.CONNECTION device show eth0 | head -n1)"
[ -n "$CONN_NAME" ]
CONN_UUID="$(nmcli -g connection.uuid connection show "$CONN_NAME" | head -n1)"
[ -n "$CONN_UUID" ]

IPV4_METHOD="$(nmcli -g ipv4.method connection show "$CONN_UUID" | head -n1)"
AUTOCONNECT="$(nmcli -g connection.autoconnect connection show "$CONN_UUID" | head -n1)"
ORIGINAL_IPV4="$(nmcli -g IP4.ADDRESS device show eth0)"
ORIGINAL_GATEWAY="$(nmcli -g IP4.GATEWAY device show eth0 | head -n1)"

BROKER_ID_BEFORE="$(docker ps -q --filter label=com.docker.compose.project=n3wfc4 --filter label=com.docker.compose.service=broker)"
[ -n "$BROKER_ID_BEFORE" ]
MANAGER_ID_BEFORE="$(docker inspect greenhouse-manager --format '{{.Id}}')"
MANAGER_RESTART_BEFORE="$(docker inspect greenhouse-manager --format '{{.RestartCount}}')"

[ "$MANAGER_ID_BEFORE" = "$EXPECTED_MANAGER_ID" ]
[ "$MANAGER_RESTART_BEFORE" = "$EXPECTED_MANAGER_RESTART" ]

BASELINE="$(firewall_snapshot connected)"
printf '%s\n' "$BASELINE"
FOREIGN_COUNT_BEFORE="$(printf '%s\n' "$BASELINE" | awk -F= '/^FOREIGN_RULE_COUNT=/{print $2}')"
FOREIGN_SHA_BEFORE="$(printf '%s\n' "$BASELINE" | awk -F= '/^FOREIGN_RULES_SHA256=/{print $2}')"

echo "CONNECTION_NAME=$CONN_NAME"
echo "CONNECTION_UUID=$CONN_UUID"
echo "IPV4_METHOD=$IPV4_METHOD"
echo "AUTOCONNECT=$AUTOCONNECT"
echo "ORIGINAL_IPV4=$ORIGINAL_IPV4"
echo "ORIGINAL_GATEWAY=$ORIGINAL_GATEWAY"
echo "BROKER_ID_BEFORE=$BROKER_ID_BEFORE"
echo "MANAGER_ID_BEFORE=$MANAGER_ID_BEFORE"
echo "MANAGER_RESTART_COUNT_BEFORE=$MANAGER_RESTART_BEFORE"
echo "PRECHECK=PASS"

EVENT_EPOCH="$(date +%s)"
echo "EVENT_START_UTC=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

echo "=== LINK DOWN ==="
nmcli connection down uuid "$CONN_UUID"
wait_disconnected
wait_guard_event_status "$EVENT_EPOCH" "FAIL_CLOSED"

echo "ETH0_STATE_DOWN=$(nmcli -t -f GENERAL.STATE device show eth0 || true)"
echo "ETH0_IPV4_DOWN=$(nmcli -g IP4.ADDRESS device show eth0 | tr '\n' ',' || true)"

DOWN_STATE="$(firewall_snapshot disconnected)"
printf '%s\n' "$DOWN_STATE"

DOWN_FOREIGN_COUNT="$(printf '%s\n' "$DOWN_STATE" | awk -F= '/^FOREIGN_RULE_COUNT=/{print $2}')"
DOWN_FOREIGN_SHA="$(printf '%s\n' "$DOWN_STATE" | awk -F= '/^FOREIGN_RULES_SHA256=/{print $2}')"

[ "$DOWN_FOREIGN_COUNT" = "$FOREIGN_COUNT_BEFORE" ]
[ "$DOWN_FOREIGN_SHA" = "$FOREIGN_SHA_BEFORE" ]

DOWN_GUARD_LOG="$(journalctl -u "$GUARD" --since "@$EVENT_EPOCH" --no-pager -o cat)"
printf '%s\n' "$DOWN_GUARD_LOG"

DOWN_FAIL_CLOSED_COUNT="$(printf '%s\n' "$DOWN_GUARD_LOG" | grep -c '"status":"FAIL_CLOSED","applied":true' || true)"
echo "DOWN_FAIL_CLOSED_APPLY_COUNT=$DOWN_FAIL_CLOSED_COUNT"
[ "$DOWN_FAIL_CLOSED_COUNT" -ge 1 ]

[ "$(systemctl is-active "$GUARD")" = "active" ]
[ "$(systemctl is-active "$ACTIVATION")" = "active" ]
[ "$(docker inspect "$BROKER_ID_BEFORE" --format '{{.State.Status}}')" = "running" ]
[ "$(docker inspect greenhouse-manager --format '{{.State.Status}}')" = "running" ]
[ "$(docker inspect greenhouse-manager --format '{{.RestartCount}}')" = "$MANAGER_RESTART_BEFORE" ]

echo "DOWN_FAIL_CLOSED=PASS"

echo "=== LINK UP ==="
UP_EPOCH="$(date +%s)"
nmcli connection up uuid "$CONN_UUID" ifname eth0
wait_connected
wait_guard_event_status "$UP_EPOCH" "PASS"

echo "ETH0_STATE_AFTER=$(nmcli -t -f GENERAL.STATE device show eth0)"
echo "ETH0_IPV4_AFTER=$(nmcli -g IP4.ADDRESS device show eth0)"
echo "ETH0_GATEWAY_AFTER=$(nmcli -g IP4.GATEWAY device show eth0 | head -n1)"

UP_STATE="$(firewall_snapshot connected)"
printf '%s\n' "$UP_STATE"

UP_FOREIGN_COUNT="$(printf '%s\n' "$UP_STATE" | awk -F= '/^FOREIGN_RULE_COUNT=/{print $2}')"
UP_FOREIGN_SHA="$(printf '%s\n' "$UP_STATE" | awk -F= '/^FOREIGN_RULES_SHA256=/{print $2}')"

[ "$UP_FOREIGN_COUNT" = "$FOREIGN_COUNT_BEFORE" ]
[ "$UP_FOREIGN_SHA" = "$FOREIGN_SHA_BEFORE" ]

UP_GUARD_LOG="$(journalctl -u "$GUARD" --since "@$UP_EPOCH" --no-pager -o cat)"
printf '%s\n' "$UP_GUARD_LOG"

UP_PASS_COUNT="$(printf '%s\n' "$UP_GUARD_LOG" | grep -c '"status":"PASS","applied":true' || true)"
UP_ERROR_COUNT="$(printf '%s\n' "$UP_GUARD_LOG" | grep -c '"status":"ERROR"' || true)"
echo "UP_PASS_APPLY_COUNT=$UP_PASS_COUNT"
echo "UP_GUARD_ERROR_COUNT=$UP_ERROR_COUNT"
[ "$UP_PASS_COUNT" -ge 1 ]
[ "$UP_ERROR_COUNT" = "0" ]

BROKER_ID_AFTER="$(docker ps -q --filter label=com.docker.compose.project=n3wfc4 --filter label=com.docker.compose.service=broker)"
MANAGER_ID_AFTER="$(docker inspect greenhouse-manager --format '{{.Id}}')"
MANAGER_RESTART_AFTER="$(docker inspect greenhouse-manager --format '{{.RestartCount}}')"

echo "BROKER_ID_AFTER=$BROKER_ID_AFTER"
echo "BROKER_STATE=$(docker inspect "$BROKER_ID_AFTER" --format '{{.State.Status}}')"
echo "MANAGER_ID_AFTER=$MANAGER_ID_AFTER"
echo "MANAGER_STATE=$(docker inspect greenhouse-manager --format '{{.State.Status}}')"
echo "MANAGER_RESTART_COUNT_AFTER=$MANAGER_RESTART_AFTER"
echo "GUARD_ACTIVE=$(systemctl is-active "$GUARD")"
echo "ACTIVATION_ACTIVE=$(systemctl is-active "$ACTIVATION")"
echo "TCP_8883_LISTEN_COUNT=$(ss -H -ltn 'sport = :8883' | wc -l | tr -d ' ')"

[ "$BROKER_ID_AFTER" = "$BROKER_ID_BEFORE" ]
[ "$MANAGER_ID_AFTER" = "$MANAGER_ID_BEFORE" ]
[ "$MANAGER_RESTART_AFTER" = "$MANAGER_RESTART_BEFORE" ]
[ "$(docker inspect "$BROKER_ID_AFTER" --format '{{.State.Status}}')" = "running" ]
[ "$(docker inspect greenhouse-manager --format '{{.State.Status}}')" = "running" ]
[ "$(systemctl is-active "$GUARD")" = "active" ]
[ "$(systemctl is-active "$ACTIVATION")" = "active" ]
[ "$(ss -H -ltn 'sport = :8883' | wc -l | tr -d ' ')" = "1" ]

SUCCESS=true
trap - ERR EXIT

echo "LINK_DOWN_FAIL_CLOSED=PASS"
echo "LINK_UP_TRUSTED_POLICY_RESTORED=PASS"
echo "FOREIGN_FIREWALL_STATE_PRESERVED=PASS"
echo "BROKER_RUNTIME_CONTINUITY=PASS"
echo "MANAGER_RUNTIME_CONTINUITY=PASS"
echo "RECOVERY_EXECUTED=false"
echo "PHASE_RESULT=PASS"
echo "=== COMPLETE ==="
