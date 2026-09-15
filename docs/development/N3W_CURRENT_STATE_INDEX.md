# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current KF-092 source-defect authority: `docs/development/N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_DEFECT_20260915.md`  
Formal KF-092 next-chat handoff: `docs/development/N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_NEW_CHAT_HANDOFF_V1.0_20260915.md`  
KF-091 repair record: `docs/development/N3W_KF091_HOME_ASSISTANT_BROKER_TLS_DNS_BINDING_20260915.md`  
Broader multi-node Relay / Home Assistant alignment archive: `docs/development/N3W_MULTI_NODE_RELAY_HOME_ASSISTANT_MQTT_PATH_PROGRESS_ALIGNMENT_20260915.md`  
KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
CURRENT_MAIN=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
CURRENT_DOC_ALIGNMENT_PR=410
CURRENT_DOC_ALIGNMENT_BRANCH=docs/n3w-multinode-relay-ha-mqtt-alignment-20260915
PR410_MERGED=false
```

The fixed main SHA above is the fresh main value at this alignment point. A new chat must query `main` fresh before source mutation.

## Accepted historical product boundary

```text
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
```

The simultaneous Relay proof remains frozen and is not reopened by later downstream/runtime findings.

## KF-091 — closed infrastructure repair

```text
KF091_STATUS=CLOSED_PASS
ROOT_CLASS=DOCKER_NETWORK_DNS_TO_TLS_IDENTITY_BINDING
ROOT_CAUSE_CLASS=BROKER_SHARED_NETWORK_MISSING_ALIAS_FOR_EXISTING_TLS_DNS_SAN
REPAIR_DESIGN=ADD_EXISTING_TLS_DNS_SAN_AS_BROKER_SHARED_NETWORK_ALIAS
BROKER_RECREATE_COUNT_EXACT=1
COMPOSE_SOURCE_POST_SHA256=d3a2bb681db523d4414e64fd26d49074d76c90ac5265493f18ec760494472f60
FC4_HA_TLS_SAN_DNS_RESOLVED=true
FC4_HA_TLS_HOSTNAME_VERIFIED=true
HA_MQTT_8883_SESSION_OBSERVED=true
```

No Home Assistant MQTT entry change, certificate/CA rotation, credential rotation, DynSec mutation, Manager configuration mutation, or board mutation was required.

## Current board/runtime evidence

```text
BOARD_A_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_A_LAST_RUNTIME_ROLE=DIRECT

BOARD_B_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_B_RELAY_ONLY_WINDOW_PROVEN=true
BOARD_B_RELAY_RUNTIME=INTERMITTENT

BOARD_C_PHYSICAL_STATE=POWERED_UNCHANGED
BOARD_C_AP_ASSOCIATED_OPERATOR_CONFIRMED=true
BOARD_C_DIRECT_PATH_REAL=true
BOARD_C_EXCLUDED_FROM_RELAY_ONLY_HA_ORACLE=true
```

Board B was observed as Relay-only in a fresh 130-second window (`Direct=0`, `Relay=27`), then had a later 180-second window with no Manager acceptance (`Direct=0`, `Relay=0`), and subsequently resumed Manager-accepted Relay traffic without operator intervention. The latest bounded capture observed 16 Relay accepts from `2026-09-15T03:06:35Z` through the capture boundary `2026-09-15T03:08:00Z`.

This disproves a permanent Board B runtime loss and does not prove a fixed Relay-session lifetime.

## KF-092 — current blocker

```text
KF092_STATUS=OPEN
KF092_DOMAIN=FIRMWARE_RUNTIME
SOURCE_DEFECT_PROVEN=true
FIELD_INCIDENT_CAUSATION=STRONGLY_INDICATED_NOT_YET_PHYSICALLY_PROVEN
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
```

Source review proves the current Relay path controller is updated using the synchronous `esp_now_send(...) == ESP_OK` submission result, while the actual asynchronous unicast MAC completion result is routed only into diagnostics. Therefore real MAC delivery failures do not currently drive `relay_failures_to_discovery` hysteresis.

Minimum repair direction:

```text
UNCAST_CALLBACK_TASK=ENQUEUE_DESTINATION_AND_COMPLETION_ONLY
NORMAL_LOOP=DRAIN_COMPLETIONS_AND_BIND_TO_CURRENT_ACTIVE_RELAY
ACTUAL_MAC_FAILURE=FEED_RELAY_FAILURE_HYSTERESIS
IMMEDIATE_SUBMIT_FAILURE=COUNT_AS_FAILURE
BROADCAST_COMPLETION=AFFECTS_RELAY_PATH_FALSE
STALE_RELAY_COMPLETION=IGNORE
```

Required tests must prove:

- delivery success keeps `RELAY_ACTIVE`;
- one delivery failure keeps `RELAY_ACTIVE` under current hysteresis;
- two actual delivery failures transition to `DISCOVERY`;
- immediate submit failure counts as failure;
- broadcast and stale old-peer completions do not alter current Relay path state;
- callback task does not directly mutate runtime/path state;
- success after one failure resets Relay failure hysteresis.

## Current broader acceptance boundary

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
MAINLINE_ACCEPTANCE_ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=NOT_YET_CLOSED
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=PENDING
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

Home Assistant/Broker TLS connectivity is no longer the blocker. Mainline item 2 remains open because the clean Relay-only Board B observation became intermittent before a final entity-update attribution gate closed.

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

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

The next chat may begin this authorized source repair directly after fresh repository authority rebind. It must not deploy firmware, access boards, mutate T1 live runtime, or continue into physical validation automatically after source/CI PASS.

Historical archives remain historical and are not rewritten to erase dated intermediate states.
