# N3-W Current State

Updated: 2026-09-15  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/live evidence takes precedence if later evidence proves drift.

## Repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
CURRENT_MAIN=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
CURRENT_MAIN_TREE=eed4ac1a95b64bc8c90c5784da8ffaeabb76ac7c
CURRENT_DOC_ALIGNMENT_PR=410
PR410_STATE=OPEN_UNMERGED

PR411_STATE=OPEN_UNMERGED
PR411_HEAD=576bb79c422e469ef5505f9d2bd32bfc2ec825eb
PR411_ROLE=KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR
PR411_CI=PASS

PR412_STATE=OPEN_UNMERGED
PR412_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
PR412_BASE=576bb79c422e469ef5505f9d2bd32bfc2ec825eb
PR412_ROLE=PHYSICAL_HARNESS_CONNECTIVITY_REBOOT_TIMEOUT_REPAIR
PR412_CI=PASS
```

Detailed current KF-092 physical-progress authority:

`docs/development/N3W_KF092_POSTFIX_PHYSICAL_VALIDATION_PROGRESS_ALIGNMENT_20260915.md`

## Product North Star

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

Broader acceptance state:

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
MAINLINE_ACCEPTANCE_ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=NOT_YET_CLOSED
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=IN_PROGRESS_KF092
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

The accepted KF-089 Relay end-to-end closeout and the KF-091 Home Assistant/Broker TLS-DNS repair remain frozen PASS and are not reopened.

## KF-091 — closed infrastructure repair

```text
KF091_STATUS=CLOSED_PASS
ROOT_CLASS=DOCKER_NETWORK_DNS_TO_TLS_IDENTITY_BINDING
ROOT_CAUSE_CLASS=BROKER_SHARED_NETWORK_MISSING_ALIAS_FOR_EXISTING_TLS_DNS_SAN
REPAIR_DESIGN=ADD_EXISTING_TLS_DNS_SAN_AS_BROKER_SHARED_NETWORK_ALIAS
FC4_HA_TLS_SAN_DNS_RESOLVED=true
FC4_HA_TLS_HOSTNAME_VERIFIED=true
HA_MQTT_8883_SESSION_OBSERVED=true
```

No Home Assistant MQTT-entry change, certificate/CA rotation, credential rotation, Dynamic Security mutation, Manager configuration change or board mutation was required.

## KF-092 source defect and source repair

Proven defect:

```text
KF092_DOMAIN=FIRMWARE_RUNTIME
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
SOURCE_DEFECT_PROVEN=true
```

PR #411 repairs the source contract so that actual asynchronous unicast MAC completion, not synchronous submit acceptance, drives Relay delivery hysteresis.

Accepted repair semantics:

```text
SYNC_SUBMIT_SUCCESS=NOT_DELIVERY_SUCCESS
IMMEDIATE_SYNC_SUBMIT_FAILURE=COUNTS_AS_FAILURE
ASYNC_UNICAST_COMPLETION=CALLBACK_SAFE_BOUNDED_ENQUEUE
NORMAL_LOOP=DRAINS_COMPLETIONS=true
CURRENT_ACTIVE_RELAY_DESTINATION_MATCH_REQUIRED=true
BROADCAST_COMPLETION_AFFECTS_CHILD_RELAY_PATH=false
STALE_RELAY_COMPLETION=IGNORE
RELAY_FAILURES_TO_DISCOVERY=2
```

```text
KF092_SOURCE_REPAIR=PASS
PR411_CI=PASS
```

## Post-fix physical evidence before harness repair

Board B was successfully deployed with the PR #411 repair firmware using an application-only inactive-slot-first update with readback verification and no deployment-time product NVS erase.

Fresh Relay-only Manager observation proved continuous Relay telemetry with no Direct acceptance. A controlled Relay reachability interruption then proved Relay interruption and recovery, including same-boot recovery before a later unexpected Board B reboot.

Subsequent timeline recovery observed repeated Board B boot sessions at approximately 15-minute intervals while the Manager remained continuously running.

Classification:

```text
BOARD_B_PERIODIC_REBOOT_REPRODUCED=true
REBOOT_PERIOD_APPROX=15_MINUTES
REBOOT_IS_NOT_EVIDENCE_OF_KF092_SOURCE_REPAIR_FAILURE=true
HARNESS_REBOOT_POLICY_CONFLICT=PROVEN
```

The reboot pattern is consistent with ESPHome connectivity reboot policy conflicting with intentional Relay-only operation, where Direct Wi-Fi and MQTT are unavailable by design.

## Physical harness reboot-timeout repair

PR #412 changes only the Phase 4 physical harness and its source-contract test:

```text
wifi.reboot_timeout=0s
mqtt.reboot_timeout=0s
PRODUCT_CPP_MUTATION=false
```

Local source/config validation passed and all 11 observed PR #412 workflows completed successfully.

```text
HARNESS_REBOOT_TIMEOUT_SOURCE_REPAIR=PASS
PR412_CI=PASS
```

## Board B exact PR #412 redeployment

Exact deployed source authority:

```text
SOURCE_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
SOURCE_TREE=448b10e4b11f7585d32e00c349cb39d2aaea200e
FIRMWARE_SIZE=1115968
FIRMWARE_SHA256=44584b34671123ba05d4b6f94643fb9bcdad0001c5e2797d93eefe6cb2cb81db
```

Deployment closure:

```text
PRE_ACTIVE_SLOT=1
TARGET_SLOT=0
TARGET_SLOT_READBACK_VERIFY=PASS
POST_ACTIVE_SLOT=0
ROLLBACK_SLOT=1
NVS_READBACK_UNCHANGED=PASS
NVS_ERASE=false
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
BOARD_B_HARNESS_REDEPLOY=PASS
```

The one-shot redeployment authorization was consumed and is not replayable.

## Board B post-deploy runtime baseline

A controlled serial diagnostic explicitly proved the new application booted from app0 at offset `0x10000`, loaded the existing provisioned runtime state, connected Wi-Fi, activated Direct mode on channel 11, connected MQTT and produced schema-v5 accepted telemetry.

A subsequent T1-only correlation window proved:

```text
DIRECT_ACCEPTED_COUNT=12
RELAY_ACCEPTED_COUNT=0
BOOT_COUNT=1
BOARD_B_DIRECT_CORRELATION=PASS
MANAGER_RESTART_COUNT=0
```

Therefore:

```text
BOARD_B_DEPLOYED_SLOT_BOOT=PASS
BOARD_B_PROVISIONED_STATE_PRESERVED=PASS
BOARD_B_DIRECT_RUNTIME=PASS
BOARD_B_MQTT_RUNTIME=PASS
BOARD_B_NEW_HARNESS_FIRMWARE_ACTIVE=true
```

The earlier immediate post-flash no-ingress window is classified as `APPLICATION_BOOT_NOT_PROVEN_AFTER_ROM_FLASH_SESSION`, not as a Direct/MQTT/Manager defect. Future ROM-flash validation must explicitly establish a clean normal application boot before T1-only acceptance.

## Board C current evidence

Fresh observation proves the third board remains Direct-active with continuous Manager acceptance. A separate bounded Board B Relay interval also observed that board acting as a Relay gateway.

```text
BOARD_C_DIRECT_RUNTIME=PASS
BOARD_C_RELAY_GATEWAY_FUNCTION=OBSERVED_PASS
```

The earlier simultaneous Board B + Board C Relay-through-Board A acceptance remains frozen PASS.

## Current KF-092 physical-validation boundary

```text
KF092_SOURCE_REPAIR=PASS
KF092_RELAY_ONLY_BASELINE=PASS
KF092_RELAY_RECOVERY_BEHAVIOR=PASS
HARNESS_REBOOT_POLICY_CONFLICT=PROVEN
HARNESS_REBOOT_TIMEOUT_SOURCE_REPAIR=PASS
HARNESS_REDEPLOYMENT=PASS
POSTDEPLOY_DIRECT_BASELINE=PASS

CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=NOT_YET_PROVEN
KF092_RELAY_FAILURE_PATH_EXERCISED=NOT_YET_PROVEN
PHYSICAL_CAUSATION_PROVEN=false
KF092_POSTFIX_PHYSICAL_VALIDATION=NOT_YET_CLOSED
```

The post-PR #412 20-minute Relay-only same-boot gate has not yet been executed. Therefore the previous approximately 15-minute reboot behavior has not yet been physically proven eliminated.

## Current ONE gate

```text
CURRENT_ONE_GATE=KF092_BOARD_B_20MIN_RELAY_ONLY_SAME_BOOT_STABILITY
```

Required result:

```text
DIRECT_ACCEPTED_COUNT=0
RELAY_ACCEPTED_COUNT>0
BOOT_COUNT=1
SAME_BOOT_20MIN=PASS
RELAY_ONLY_20MIN=PASS
CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=PASS
```

Only after that passes should the exact KF-092 causal gate continue with controlled Relay reachability loss, actual asynchronous unicast failure evidence, `RELAY_ACTIVE -> DISCOVERY`, authenticated Relay reacquisition, same-boot recovery and a durable schema-v5 diagnostic snapshot.

## Execution model

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_MAC_TERMINAL_EXECUTION
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_ENABLED=false
EXECUTOR=USER_MAC_TERMINAL
USER_ROLE=EXACT_COMMAND_EXECUTOR_AND_RAW_RESULT_REPORTER
```

## Required guards

- `esp_now_send(...) == ESP_OK` is submit acceptance, not MAC delivery completion.
- Wi-Fi-task callback code must not directly mutate normal-loop path state.
- Actual unicast completion must be destination-bound before affecting the current Relay path.
- Relay-only physical acceptance must remain stable beyond the previous approximately 15-minute connectivity reboot window.
- Application serial open is not a passive runtime oracle.
- After a ROM-flash session, normal application boot must be proven explicitly before T1-only acceptance.
- Consumed one-shot physical authorizations are never replayable.
- USB port is a locator only, not board identity authority.
- No merge, additional board firmware write, Broker/Manager/Home Assistant/DynSec/credential/TLS mutation is authorized by this documentation synchronization.
