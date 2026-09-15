# N3-W Current State

Updated: 2026-09-15  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/live evidence takes precedence over this document if later evidence proves drift.

## Repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
CURRENT_MAIN=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
CURRENT_DOC_ALIGNMENT_PR=410
CURRENT_DOC_ALIGNMENT_BRANCH=docs/n3w-multinode-relay-ha-mqtt-alignment-20260915
PR410_MERGED=false
```

KF-089 code/package integration through PR #406→#408 remains closed and accepted. Current board firmware source authority remains:

```text
BOARD_FIRMWARE_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
DEPLOYED_MANAGER_SOURCE=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
```

## Product North Star

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

Broader acceptance state:

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
MAINLINE_ACCEPTANCE_ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=NOT_YET_CLOSED
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=PENDING
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

The accepted simultaneous two-child Relay proof remains frozen:

```text
WINDOW_ACCEPTED_RELAY_COUNT=82
WINDOW_REJECTED_RELAY_COUNT=0
WINDOW_DUPLICATE_RELAY_COUNT=0
WINDOW_UNIQUE_RELAY_ROUTE_COUNT=2
WINDOW_UNIQUE_RELAY_NODE_COUNT=2
WINDOW_UNIQUE_RELAY_GATEWAY_COUNT=1
BOARD_B_ACCEPTED_RELAY_COUNT=40
BOARD_C_ACCEPTED_RELAY_COUNT=42
BOARD_A_DIRECT_DURING_RELAY_COUNT=98
BOARD_B_DIRECT_DURING_RELAY_COUNT=0
BOARD_C_DIRECT_DURING_RELAY_COUNT=0
BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PROVEN
```

## KF-091 infrastructure repair — CLOSED PASS

KF-091 was localized to:

```text
ROOT_DOMAIN=INFRASTRUCTURE
ROOT_CLASS=DOCKER_NETWORK_DNS_TO_TLS_IDENTITY_BINDING
ROOT_CAUSE_CLASS=BROKER_SHARED_NETWORK_MISSING_ALIAS_FOR_EXISTING_TLS_DNS_SAN
```

The exact preclaim proved the TLS DNS SAN, Home Assistant MQTT target, and Manager target were identical by public-safe fingerprint and that the SAN was absent from the Broker shared-network DNS authority.

Authorized repair:

```text
AUTHORIZATION=FC4_HOME_ASSISTANT_BROKER_TLS_SAN_ALIAS_REPAIR_MUTATION_20260915_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

Repair closure:

```text
REPAIR_DESIGN=ADD_EXISTING_TLS_DNS_SAN_AS_BROKER_SHARED_NETWORK_ALIAS
BROKER_RECREATE_COUNT_EXACT=1
COMPOSE_SOURCE_PRE_SHA256=56f004d4b1741ea7e868de7aa5491faa213b56c87864cc19deeadd5f465429db
COMPOSE_SOURCE_POST_SHA256=d3a2bb681db523d4414e64fd26d49074d76c90ac5265493f18ec760494472f60
BROKER_IMAGE_UNCHANGED=true
BROKER_8883_PUBLICATION_UNCHANGED=true
BROKER_CA_UNCHANGED=true
BROKER_CERT_UNCHANGED=true
DYNSEC_SHA256_UNCHANGED=true
MANAGER_CONTAINER_ID_UNCHANGED=true
HOME_ASSISTANT_CONTAINER_ID_UNCHANGED=true
HOME_ASSISTANT_MQTT_ENTRY_CHANGE=false
HOME_ASSISTANT_CREDENTIAL_CHANGE=false
BOARD_MUTATION=false
FC4_HA_TLS_SAN_DNS_RESOLVED=true
FC4_HA_TCP_8883_CONNECTABLE=true
FC4_HA_TLS_CHAIN_VERIFIED=true
FC4_HA_TLS_HOSTNAME_VERIFIED=true
MANAGER_8883_SESSION_RECOVERED=true
```

Subsequent read-only validation observed:

```text
HA_MQTT_8883_SESSION_OBSERVED=true
```

Therefore the prior Home Assistant/Broker TLS DNS blocker is closed. Do not reconfigure Home Assistant, rotate certificates/credentials, weaken hostname verification, or reopen DynSec for this issue without new direct counter-evidence.

## Current board/runtime observations

Operator-confirmed physical state is intentionally unchanged for handoff.

```text
BOARD_A_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_A_LAST_RUNTIME_ROLE=DIRECT

BOARD_B_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_B_DIRECT_ACCEPTANCE_IN_FRESH_RELAY_WINDOWS=0
BOARD_B_RELAY_ONLY_WINDOW_PROVEN=true
BOARD_B_RELAY_RUNTIME=INTERMITTENT

BOARD_C_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_C_AP_ASSOCIATED_OPERATOR_CONFIRMED=true
BOARD_C_DIRECT_PATH_REAL=true
BOARD_C_EXCLUDED_FROM_RELAY_ONLY_HA_ORACLE=true
```

Board B evidence across bounded windows:

```text
FRESH_WINDOW_1_BOARD_B_DIRECT=0
FRESH_WINDOW_1_BOARD_B_RELAY=27
LATER_180S_BOARD_B_DIRECT=0
LATER_180S_BOARD_B_RELAY=0
LOOKBACK_BOARD_B_ACCEPTED_RELAY=56
LOOKBACK_BOARD_B_REJECTED=0
LATEST_OBSERVED_RELAY_RUN_START=2026-09-15T03:06:35Z
LATEST_OBSERVED_RELAY_RUN_END_AT_CAPTURE=2026-09-15T03:08:00Z
LATEST_OBSERVED_RELAY_RUN_COUNT=16
```

This proves Board B can lose Manager-visible Relay telemetry for a bounded period and later resume Relay without operator intervention. It does not prove a fixed Relay-session lifetime.

Board C remained Direct-capable and AP-associated. Historical mixed Direct/Relay observations for Board C must not be used as the Relay-only Home Assistant oracle.

## KF-092 source defect — current blocker

Fresh source review of the deployed board source authority and current repository code proved a Relay delivery-feedback defect:

```text
KF092_STATUS=OPEN
KF092_DOMAIN=FIRMWARE_RUNTIME
SOURCE_DEFECT_PROVEN=true
FIELD_INCIDENT_CAUSATION=STRONGLY_INDICATED_NOT_YET_PHYSICALLY_PROVEN
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
```

Current control flow:

```text
send_telemetry()
-> send_encrypted_peer()
-> EspNowDriver::send()
-> esp_now_send(...) == ESP_OK
-> synchronous submit result passed to LocalPathController::note_relay_result()
```

But actual MAC-layer ESP-NOW delivery success/failure arrives later through the asynchronous send callback. The callback currently forwards unicast completion only to diagnostics and does not feed the runtime/path controller.

Consequences:

```text
MAC_DELIVERY_FAIL_CAN_OCCUR=true
SYNC_SUBMIT_CAN_STILL_BE_ESP_OK=true
RELAY_FAILURE_HYSTERESIS_SEES_FALSE_SUCCESS=true
RELAY_ACTIVE_CAN_REMAIN_STUCK=true
REDISCOVERY_CAN_BE_DELAYED_OR_SKIPPED=true
```

This source defect matches the observed Board B symptom class but requires post-fix physical validation before field causation is upgraded to proven.

## KF-092 minimum repair direction

The repair must preserve callback/task safety. The Wi-Fi task must not mutate `LocalPathController` directly.

Required design:

```text
ESP-NOW unicast callback
-> enqueue bounded completion record {destination, success}
-> normal component loop drains records
-> accept only completion matching current active Relay destination
-> feed actual MAC result into Relay failure hysteresis
```

Additional rules:

- synchronous `esp_now_send()` immediate submission failure counts as a failure because no callback-successful delivery can follow;
- `ESP_OK` submission is not delivery success and must not reset Relay failure hysteresis by itself;
- broadcast completions never affect child Relay path state;
- stale completion from an old Relay peer is ignored;
- two actual Relay failures must still drive the existing default hysteresis from `RELAY_ACTIVE` to `DISCOVERY`;
- one actual success after a prior failure resets Relay failure hysteresis;
- callback code remains bounded and non-blocking.

Required host/source tests include success, one failure, two failures→DISCOVERY, immediate submit failure, broadcast exclusion, stale destination exclusion, callback-task non-mutation, and failure-reset-on-success.

## Current live-service boundary

Last exact evidence before handoff:

```text
AUTHORITATIVE_MANAGER_RUNNING=true
AUTHORITATIVE_BROKER_RUNNING=true
AUTHORITATIVE_HOMEASSISTANT=fc4-homeassistant
HA_MQTT_8883_SESSION_OBSERVED=true
DYNSEC_ACCEPTED_SHA256=af6ab6e7c43c9eeb4300d529a4f9acdd097c83f2f2e8c3b780af03926252aeff
```

No live runtime mutation, board access, USB/serial access, Flash write, NVS mutation, RF experiment, MQTT test publish, or extra subscriber is authorized for the next source-repair gate.

## Authorization carried to next chat

```text
AUTHORIZATION=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
GRANTED=true
CLAIMED=false
CONSUMED=false
RESULT=PENDING
REPLAY_PERMITTED=true
SCOPE=SOURCE_HOST_TEST_CI_DOCUMENTATION_ONLY
BOARD_ACCESS=false
T1_LIVE_MUTATION=false
```

The authorization is intentionally carried forward. The next chat does not need to ask for the same source-repair authorization again if fresh repository authority rebind succeeds and the repair stays inside the frozen scope.

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

The next chat starts directly with source repair after fresh repository rebind. It must not perform board deployment or physical validation automatically after source/CI PASS.

## Required guards

- `esp_now_send(...) == ESP_OK` is submit acceptance, not MAC delivery completion.
- Wi-Fi-task callback code must not directly mutate normal-loop path state.
- actual unicast completion must be destination-bound before affecting the current Relay path.
- consumed authorizations are not replayable.
- USB port is a locator only, not board identity authority.
- no board/serial/Flash/NVS/RF access without a later explicit physical authorization.
- no Home Assistant/Broker/DynSec repair is currently indicated.
- no TLS hostname-verification weakening is permitted.

Detailed KF-092 authority:

`docs/development/N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_DEFECT_20260915.md`

Formal next-chat handoff:

`docs/development/N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_NEW_CHAT_HANDOFF_V1.0_20260915.md`
