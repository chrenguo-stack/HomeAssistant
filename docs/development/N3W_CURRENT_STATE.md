# N3-W Current State

Updated: 2026-09-14
Status: `CURRENT_STATE_AUTHORITY`

This is the concise public-safe authority for the current N3-W state. Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## Repository / source authority

Fresh repository main observed during KF-089 closeout:

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
REPOSITORY_MAIN_TREE=91d2e4767887dad86525cf521e476d4a1234551a
```

The accepted KF-089 repair/validation stack is not yet integrated into `main`:

```text
PR400_STATE=OPEN_DRAFT_UNMERGED
PR400_HEAD=b973934b760db975ada601819191c62fe0513a9e
PR403_STATE=OPEN_DRAFT_UNMERGED
PR403_HEAD=1f4cb36a2d1180753556eb08d2b46fa180d423e0
PR404_STATE=OPEN_DRAFT_UNMERGED
PR404_HEAD=83006bc87904843d6ca784355556032852c3813d
```

Repository main must always be queried fresh. Live acceptance and repository integration are separate authorities: the T1 runtime repair and physical Relay acceptance are proven, while the corresponding source/guard stack still requires normal PR integration.

Active architecture authority remains:

`docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

Current product direction remains:

- provisioned runtime startup does not require an existing Wi-Fi association;
- Direct remains preferred;
- when Direct is unavailable, node-local bounded autonomous Relay discovery is allowed;
- full custom radio-ownership architecture remains deferred unless later evidence requires it.

## Deployed product authorities

Board Schema-v5 authority used by the accepted two-board Relay chain:

```text
BOARD_FIRMWARE_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
BOARD_FIRMWARE_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
DIAGNOSTIC_SCHEMA_VERSION=5
```

Current deployed Manager authority remains distinct from the unmerged source repair:

```text
DEPLOYED_MANAGER_SOURCE=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
LIVE_MANAGER_DYNSEC_REPAIR=PASS
MANAGER_RELAY_SOURCE_CONTRACT_INTEGRATION=PENDING_PR400_MERGE_PATH
```

ID24 repaired the active live Dynamic Security role in place. ID25 then performed exactly one Manager restart to establish a fresh MQTT subscription cycle. ID26 proved fresh Relay telemetry delivery without further Manager/Broker/DynSec mutation.

## KF-089 final Relay acceptance

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
BOARD_SIDE_RELAY_CHAIN=PROVEN
T1_BROKER_MEDIATED_RELAY_INGRESS=PROVEN
MANAGER_RELAY_ACCEPTANCE=PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
```

The final ID26 fresh window was isolated by a Board-B-off baseline:

```text
PREWINDOW_ACCEPTED_RELAY_COUNT=0
PREWINDOW_QUIESCENCE_SECONDS_OBSERVED=10.003290081047453
RELAY_WINDOW_SECONDS_OBSERVED=384.16830721497536
WINDOW_ACCEPTED_RELAY_COUNT=38
WINDOW_REJECTED_RELAY_COUNT=0
WINDOW_DUPLICATE_RELAY_COUNT=0
WINDOW_UNIQUE_ACCEPTED_RELAY_ROUTE_COUNT=1
```

This proves the product chain through Manager acceptance:

```text
BOARD_B
-> ESP_NOW
-> BOARD_A_GATEWAY_FORWARD
-> MQTT_BROKER
-> MANAGER_RELAY_INGRESS
-> MANAGER_ACCEPTED_TELEMETRY
```

Detailed public-safe closeout authority:

`docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`

## Dynamic Security / subscription repair boundary

The downstream Relay failure was localized to the active Manager Dynamic Security role. Default subscribe and client-receive behavior remained deny, while the Manager role lacked the exact Relay ingress receive contract.

Accepted least-privilege topic:

```text
gh/v1/<sid>/ingress/gateway/+/+/frame
```

Accepted ACL trio:

```text
subscribePattern
publishClientReceive
unsubscribePattern
```

Final repair/runtime state:

```text
ID24_REPAIR_RESULT=PASS
POSTSTATE_EXACT_RELAY_ACL_COUNT=3
POSTSTATE_EXACT_CONTRACT_PROVEN=true

ID25_REACTIVATION_RESULT=PASS
POSTRESTART_RELAY_SUBSCRIPTION_REQUEST_OBSERVED=true
POSTRESTART_DIRECT_SUBSCRIPTION_REQUEST_OBSERVED=true
POSTRESTART_FAILURE_LOG_ABSENT=true

ID26_REVALIDATION_RESULT=PASS
LIVE_REPAIRED_DYNSEC_POSTSTATE_PROVEN=true
DYNSEC_STATE_UNCHANGED=true
MANAGER_RUNTIME_STABLE=true
BROKER_RUNTIME_STABLE=true
```

No broad `ingress/gateway/#` grant is part of the accepted repair.

## Last-proven physical boundary

```text
BOARD_A_LAST_PROVEN_STATE=POWERED_DIRECT_DURING_ID26_UNTOUCHED
BOARD_A_USB_ACCESS_DURING_ID26=false
BOARD_A_PHYSICAL_MUTATION_DURING_ID26=false

BOARD_B_ID26_INITIAL_STATE=POWERED_OFF_AT_QUALIFIED_RELAY_ONLY_LOCATION
BOARD_B_ID26_POWER_WINDOW_COMPLETED=true
BOARD_B_ID26_FINAL_STATE=POWERED_OFF
BOARD_B_USB_ACCESS_DURING_ID26=false

CONTROLLED_RF_EXPERIMENT=PASS
```

These are last-proven experiment boundary facts, not a claim about the boards' real-time state after the operator later leaves the experiment.

## T1 runtime boundary

The previously accepted T1 runtime-convergence closure remains in force. ID24-ID26 additionally prove the current Relay receive path without reopening the infrastructure detour.

```text
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
AUTHORITATIVE_MANAGER_COUNT=1
AUTHORITATIVE_BROKER_COUNT=1
BROKER_HOST_PUBLICATION_RUNTIME=PASS
MANAGER_TO_BROKER_TLS_MQTT=PASS

ID26_MANAGER_RUNTIME_STABLE=true
ID26_BROKER_RUNTIME_STABLE=true
ID26_DYNSEC_STATE_UNCHANGED=true
```

Detailed historical T1 convergence archive:

`docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`

## Acceptance boundaries not claimed by KF-089 closeout

```text
HOME_ASSISTANT_ENTITY_UPDATE=NOT_IN_SCOPE
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

The accepted fresh/cold Relay path must not be re-labelled as proof of a same-session Direct→Relay transition or Relay→Direct recovery.

## Required guards

- USB port is a locator only and is not board identity authority.
- Board-targeted mutation requires explicit operator target/connection confirmation before board access and fresh ROM silicon identity before write.
- Application serial open is not a passive runtime oracle.
- Lab diagnostic NVS writes are distinct from product NVS mutation.
- Discovery RX means decoded handler RX, not accepted advertisement.
- Historical discovery counts are boot-session cumulative, not exact final RF-window counts.
- Schema-v4 `esp_now_send(...) == ESP_OK` is submit acceptance, not asynchronous delivery completion; Schema-v5 completion counters are the correct device-side completion oracle.
- Manager/Broker authority must not be selected by container name alone.
- Strict read-only gates must not create temporary files on the target.
- Current DynSec authority must be derived from the running Broker effective configuration; broad Relay grants remain forbidden.
- The Manager Relay role must retain exactly the required least-privilege receive contract while default deny remains active.
- A live in-place ACL repair does not reactivate an existing MQTT subscription by itself; reactivation evidence must be established separately.
- End-to-end Relay proof requires a bounded fresh traffic window with a clean pre-window baseline or another equally strong attribution oracle.
- Consumed one-shot authorizations are never replayable.

## Current ONE gate

KF-089 no longer requires another physical/T1 gate for its Relay end-to-end acceptance.

```text
NEXT_ONE_GATE=KF089_PR_STACK_INTEGRATION_REVIEW
PHYSICAL_AUTHORIZATION_REQUIRED=false
T1_AUTHORIZATION_REQUIRED=false
```

Safe integration order is documented in the closeout archive:

```text
PR400
-> PR403
-> PR404
-> KF089_CLOSEOUT_DOCS_PR
```

Each stacked PR must be freshly reviewed against the then-current `main` before integration. No merge authority is implied by this state document.

## Frozen broader acceptance

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
```

Public GitHub stores source, tests, hashes, sanitized closures, architecture decisions, and sanitized runtime alignment. Raw NVS, credentials, private board identities, remote-host details, private paths/addresses, raw Manager logs, and raw Dynamic Security snapshots remain private/local.
