# KF-089 ID26 — Minimal End-to-End Relay Revalidation

Status: `HOST_ONLY_PACKAGE_PREPARATION`

ID24 repaired the active Manager Relay Dynamic Security ACL contract and ID25 forced one fresh Manager MQTT session, proving that both Direct and exact Relay subscriptions were requested successfully while the Broker and repaired Dynamic Security state remained stable.

ID26 is the smallest live gate that can now close the remaining KF-089 evidence gap. It does **not** repeat the earlier USB/ROM/NVS two-board forensic sequence. Instead it uses a bounded, single-source Relay power window and the authoritative Manager acceptance log as the end-to-end oracle.

## Goal

Prove one fresh product telemetry path after the ACL repair and subscription reactivation:

```text
Board B fresh power-on in the previously qualified Relay-only location
-> authenticated Relay acquisition / product Relay transmission
-> Board A gateway forwarding while remaining Direct
-> Broker-mediated Relay ingress
-> Manager accepted simplified N3-W telemetry source=relay
```

A PASS proves:

```text
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
```

Home Assistant entity/display propagation remains outside this gate.

## Proven predecessors

```text
ID21_BOARD_SIDE_RELAY_CHAIN=PROVEN
ID22_BOARD_SIDE_RELAY_CHAIN_PROVEN_IN_SESSION=true
ID22_MANAGER_RELAY_ACCEPTANCE=NOT_PROVEN
ID23_ROOT_CAUSE=MANAGER_RELAY_DYNSEC_RECEIVE_ACL_MISSING

ID24_REPAIR_RESULT=PASS
ID24_POSTSTATE_EXACT_RELAY_ACL_COUNT=3
ID24_POSTSTATE_EXACT_CONTRACT_PROVEN=true

ID25_REACTIVATION_RESULT=PASS
ID25_MANAGER_RESTART_COMMAND_COUNT=1
ID25_POSTRESTART_RELAY_SUBSCRIPTION_REQUEST_OBSERVED=true
ID25_POSTRESTART_DIRECT_SUBSCRIPTION_REQUEST_OBSERVED=true
ID25_POSTRESTART_FAILURE_LOG_ABSENT=true
ID25_DYNSEC_STATE_UNCHANGED=true
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

ID25 durable adjudication authority is PR #403 comment `5658298216`.

## Why this gate is intentionally minimal

The board-side Relay chain has already been proven independently. The remaining question after ID24/ID25 is whether a fresh real Relay frame now reaches the repaired and re-subscribed Manager.

Therefore ID26 deliberately avoids:

- USB attachment to Board A or Board B;
- serial opening;
- ROM Download mode;
- flash/NVS/otadata reads or writes;
- firmware reflash;
- Board A power cycling;
- Manager or Broker restart;
- MQTT test publishing;
- an extra MQTT subscriber.

The Mac may remain on the normal network and does not need to be co-located with Board B.

## Physical/environment contract for later live execution

Before the bounded window:

1. Board A remains powered in its normal AP-covered Direct position.
2. Board B is fully powered off at the previously qualified Relay-only location where normal AP/Wi-Fi is unavailable but A<->B ESP-NOW Relay is viable.
3. Other Relay-capable test senders are powered off.
4. T1, the authoritative Broker, and the authoritative Manager remain running.

The executor first performs a short T1-only quiescence baseline while Board B remains off. The baseline must contain zero accepted `source=relay` Manager records.

Then the operator performs exactly one fresh Board B power window:

1. power Board B on at the Relay-only location;
2. leave Board B powered for at least 180 seconds;
3. power Board B off;
4. confirm the completion token.

No Board A physical action is required.

## T1 oracle

The frozen Manager source emits:

```text
Accepted simplified N3-W telemetry source=relay node=<...> gateway=<...> key=<...>
```

only after the MQTT Relay topic has been received, parsed, accepted by the shared ingress router, and its canonical output handled.

ID26 records exact node/gateway identifiers only in private evidence. Public closure exposes counts and correlation shape, not raw identifiers.

To keep attribution fail-closed, PASS requires:

```text
PREWINDOW_ACCEPTED_RELAY_COUNT=0
WINDOW_ACCEPTED_RELAY_COUNT>=1
WINDOW_UNIQUE_ACCEPTED_RELAY_ROUTE_COUNT=1
```

The pre-window zero baseline plus the operator-bound single-source power window prevents a historical/background Relay acceptance from satisfying the gate.

## Live execution sequence after separate authorization

1. Exact-bind package HEAD and clean tracked worktree.
2. Bind the accepted ID25 executor/source authority.
3. Claim the fresh one-shot authorization before any T1 or physical operation.
4. Read-only inspect T1 containers and bind the authoritative Manager and Broker.
5. Read current Broker Dynamic Security state and prove the exact repaired ID24 contract still holds; save a private SHA256 snapshot.
6. Operator confirms Board A remains Direct, Board B is off at the Relay-only location, and all other Relay-capable test senders are off.
7. Capture a 10-second T1-only quiescence baseline; require zero accepted Relay records.
8. Capture the live-window start timestamp.
9. Operator powers Board B on, holds the Relay-only power window for at least 180 seconds, powers Board B off, then confirms the completion token.
10. Capture the live-window end timestamp and bounded Manager logs.
11. Require at least one accepted Relay record and exactly one unique accepted `(node,gateway)` route in the bounded window.
12. Re-read T1 runtime and prove Manager/Broker container runtime fingerprints did not change.
13. Re-read Dynamic Security and prove the exact repaired contract plus byte-for-byte SHA256 equality with pre-window state.
14. Emit sanitized closure and stop.

## PASS boundary

```text
SOURCE_END_TO_END_ORACLE_CONTRACT_PROVEN=true
LIVE_REPAIRED_DYNSEC_PRESTATE_PROVEN=true
PREWINDOW_ACCEPTED_RELAY_COUNT=0
BOARD_B_FRESH_RELAY_POWER_WINDOW_COMPLETED=true
WINDOW_ACCEPTED_RELAY_COUNT>=1
WINDOW_UNIQUE_ACCEPTED_RELAY_ROUTE_COUNT=1
MANAGER_RUNTIME_STABLE=true
BROKER_RUNTIME_STABLE=true
LIVE_REPAIRED_DYNSEC_POSTSTATE_PROVEN=true
DYNSEC_STATE_UNCHANGED=true
T1_BROKER_MEDIATED_RELAY_INGRESS=PROVEN
MANAGER_RELAY_ACCEPTANCE=PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
HOME_ASSISTANT_ENTITY_UPDATE=NOT_IN_SCOPE
REVALIDATION_RESULT=PASS
```

## Failure behavior

Any failure after authorization claim is final for that authorization. There is no automatic retry and no automatic rollback. In particular, a failed or incomplete Board B power window must not be repeated under the same authorization.

## Forbidden

```text
BOARD_A_PHYSICAL_MUTATION=false
BOARD_A_USB_ACCESS=false
BOARD_B_USB_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
FLASH_ERASE=false
HOST_NVS_WRITE=false
OTADATA_WRITE=false
APP_WRITE=false
PAIRING_CHANGE=false
CREDENTIAL_CHANGE=false
T1_FILE_WRITE=false
T1_DOCKER_MUTATION=false
MANAGER_RESTART=false
BROKER_RESTART=false
BROKER_CONFIG_MUTATION=false
DYNSEC_MUTATION=false
T1_NETWORK_MUTATION=false
MQTT_TEST_PUBLISH=false
MQTT_EXTRA_SUBSCRIBER=false
AUTO_RETRY=false
AUTO_ROLLBACK=false
PR_MERGE=false
```

Board B's one authorized product power-on/off window and the product firmware's normal runtime behavior are expected live-test actions, not host-side configuration mutation.

## Evidence boundary

Private evidence may contain the SSH target, Docker identifiers, raw Manager logs, raw Dynamic Security JSON, exact node/gateway route identifiers, dedup keys, timestamps and private filesystem paths.

Public GitHub may contain only package/source hashes, bounded counts, boolean contract results and sanitized adjudication summaries.
