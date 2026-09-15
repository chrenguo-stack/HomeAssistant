# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current KF-092 post-fix physical-progress authority: `docs/development/N3W_KF092_POSTFIX_PHYSICAL_VALIDATION_PROGRESS_ALIGNMENT_20260915.md`  
KF-092 original source-defect authority: `docs/development/N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_DEFECT_20260915.md`  
KF-091 repair record: `docs/development/N3W_KF091_HOME_ASSISTANT_BROKER_TLS_DNS_BINDING_20260915.md`  
Broader multi-node Relay / Home Assistant alignment archive: `docs/development/N3W_MULTI_NODE_RELAY_HOME_ASSISTANT_MQTT_PATH_PROGRESS_ALIGNMENT_20260915.md`  
KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
CURRENT_MAIN=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
CURRENT_MAIN_TREE=eed4ac1a95b64bc8c90c5784da8ffaeabb76ac7c
CURRENT_DOC_ALIGNMENT_PR=410
PR410_STATE=OPEN_UNMERGED

PR411_STATE=OPEN_UNMERGED
PR411_HEAD=576bb79c422e469ef5505f9d2bd32bfc2ec825eb
PR411_CI=PASS

PR412_STATE=OPEN_UNMERGED
PR412_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
PR412_BASE=576bb79c422e469ef5505f9d2bd32bfc2ec825eb
PR412_CI=PASS
```

Repository `main` must be queried fresh before source mutation or merge. The fixed SHA above is the alignment-time authority only.

## Frozen accepted boundaries

```text
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF091_HOME_ASSISTANT_BROKER_TLS_DNS_BINDING_REPAIR=PASS
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
```

These accepted results are not reopened by the KF-092 continuation.

## KF-092 source repair

```text
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
SOURCE_DEFECT_PROVEN=true
KF092_SOURCE_REPAIR=PASS
PR411_CI=PASS
```

PR #411 changes the Relay delivery-feedback contract so actual asynchronous unicast MAC completion drives Relay failure hysteresis. Synchronous submit success is no longer delivery success; immediate submit failure counts; broadcast/stale completion is excluded; callback task ownership remains bounded.

## Relay-only reboot-policy blocker and harness repair

Repeated Board B boot sessions were observed at approximately 15-minute intervals while Relay traffic was healthy between restarts and Manager remained continuously running.

```text
BOARD_B_PERIODIC_REBOOT_REPRODUCED=true
REBOOT_PERIOD_APPROX=15_MINUTES
HARNESS_REBOOT_POLICY_CONFLICT=PROVEN
```

PR #412 repairs only the physical harness:

```text
wifi.reboot_timeout=0s
mqtt.reboot_timeout=0s
PRODUCT_CPP_MUTATION=false
HARNESS_REBOOT_TIMEOUT_SOURCE_REPAIR=PASS
PR412_CI=PASS
```

## Board B redeployment and Direct baseline

Exact deployed successor authority:

```text
SOURCE_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
SOURCE_TREE=448b10e4b11f7585d32e00c349cb39d2aaea200e
FIRMWARE_SHA256=44584b34671123ba05d4b6f94643fb9bcdad0001c5e2797d93eefe6cb2cb81db
```

Deployment and runtime status:

```text
PRE_ACTIVE_SLOT=1
TARGET_SLOT=0
TARGET_SLOT_READBACK_VERIFY=PASS
POST_ACTIVE_SLOT=0
ROLLBACK_SLOT=1
NVS_READBACK_UNCHANGED=PASS
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
BOARD_B_HARNESS_REDEPLOY=PASS

BOARD_B_DEPLOYED_SLOT_BOOT=PASS
BOARD_B_PROVISIONED_STATE_PRESERVED=PASS
BOARD_B_DIRECT_RUNTIME=PASS
BOARD_B_MQTT_RUNTIME=PASS
BOARD_B_DIRECT_CORRELATION=PASS
```

The initial T1-only no-ingress window immediately after the ROM flashing session is classified as `APPLICATION_BOOT_NOT_PROVEN_AFTER_ROM_FLASH_SESSION`, not as a Direct/MQTT/Manager defect.

## Board C current evidence

```text
BOARD_C_DIRECT_RUNTIME=PASS
BOARD_C_RELAY_GATEWAY_FUNCTION=OBSERVED_PASS
```

The earlier frozen simultaneous B+C Relay-through-A result remains the main multi-node Relay acceptance authority.

## Current broader acceptance boundary

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
MAINLINE_ACCEPTANCE_ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=NOT_YET_CLOSED
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=IN_PROGRESS_KF092
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

## Current KF-092 physical boundary

```text
KF092_RELAY_ONLY_BASELINE=PASS
KF092_RELAY_RECOVERY_BEHAVIOR=PASS
HARNESS_REDEPLOYMENT=PASS
POSTDEPLOY_DIRECT_BASELINE=PASS

CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=NOT_YET_PROVEN
KF092_RELAY_FAILURE_PATH_EXERCISED=NOT_YET_PROVEN
PHYSICAL_CAUSATION_PROVEN=false
KF092_POSTFIX_PHYSICAL_VALIDATION=NOT_YET_CLOSED
```

## Current ONE gate

```text
CURRENT_ONE_GATE=KF092_BOARD_B_20MIN_RELAY_ONLY_SAME_BOOT_STABILITY
```

Required acceptance:

```text
DIRECT_ACCEPTED_COUNT=0
RELAY_ACCEPTED_COUNT>0
BOOT_COUNT=1
SAME_BOOT_20MIN=PASS
RELAY_ONLY_20MIN=PASS
CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=PASS
```

After this gate passes, continue to the exact async-MAC causal proof: controlled Relay reachability interruption, actual unicast failures, `RELAY_ACTIVE -> DISCOVERY`, authenticated Relay reacquisition, same-boot recovery and durable schema-v5 diagnostic snapshot.

## Execution model

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_MAC_TERMINAL_EXECUTION
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_ENABLED=false
EXECUTOR=USER_MAC_TERMINAL
```

Historical handoff files remain historical and are not rewritten merely to erase their dated authorization/state snapshots.
