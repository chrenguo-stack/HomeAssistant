# N3-W KF-092 Post-Fix Physical Validation Progress Alignment — 2026-09-15

Status: `CURRENT_PROGRESS_ALIGNMENT`

> Public-safe alignment only. Raw node IDs, board MACs, host addresses, credentials, private paths, raw NVS contents and raw runtime logs are intentionally omitted.

## 1. Scope

This document synchronizes the current local physical-validation progress with GitHub after the KF-092 source repair and the physical-harness connectivity-reboot repair.

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
CURRENT_DEFECT=KF-092
KF092_PHYSICAL_VALIDATION=IN_PROGRESS
```

The previously accepted KF-089 Relay end-to-end closeout and the KF-091 Home Assistant/Broker TLS-DNS repair remain frozen PASS and are not reopened.

## 2. Fresh repository authority

Fresh GitHub authority at this alignment point:

```text
CURRENT_MAIN=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
CURRENT_MAIN_TREE=eed4ac1a95b64bc8c90c5784da8ffaeabb76ac7c

PR410_STATE=OPEN_UNMERGED
PR410_ROLE=DOCUMENTATION_ALIGNMENT

PR411_STATE=OPEN_UNMERGED
PR411_HEAD=576bb79c422e469ef5505f9d2bd32bfc2ec825eb
PR411_BASE=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
PR411_ROLE=KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR

PR412_STATE=OPEN_UNMERGED
PR412_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
PR412_BASE=576bb79c422e469ef5505f9d2bd32bfc2ec825eb
PR412_ROLE=PHYSICAL_HARNESS_CONNECTIVITY_REBOOT_TIMEOUT_REPAIR
```

PR #411 source/host/compile CI passed before physical deployment. PR #412 completed all 11 observed pull-request workflows successfully before the second Board B deployment.

## 3. KF-092 source repair — PASS

The proven source defect was:

```text
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
```

PR #411 repairs the control flow so that synchronous `esp_now_send(...) == ESP_OK` submit acceptance is no longer treated as Relay delivery success.

Accepted semantics:

```text
ASYNC_UNICAST_COMPLETION=BOUNDED_CALLBACK_SAFE_ENQUEUE
NORMAL_LOOP=DRAIN_SEND_COMPLETIONS_BEFORE_RX
CURRENT_ACTIVE_RELAY_DESTINATION_MATCH_REQUIRED=true
ACTUAL_MAC_SUCCESS=FEEDS_RELAY_HYSTERESIS_SUCCESS
ACTUAL_MAC_FAILURE=FEEDS_RELAY_HYSTERESIS_FAILURE
IMMEDIATE_SYNC_SUBMIT_FAILURE=COUNTS_AS_FAILURE
SYNC_SUBMIT_SUCCESS=NOT_DELIVERY_SUCCESS
BROADCAST_COMPLETION_AFFECTS_CHILD_RELAY_PATH=false
STALE_RELAY_DESTINATION_COMPLETION=IGNORE
RELAY_FAILURES_TO_DISCOVERY=2
```

Host/source regression coverage includes successful completion, one failure, two failures to `DISCOVERY`, immediate submit failure, broadcast exclusion, stale-destination exclusion, callback-task ownership, failure reset on success, and preservation of Direct/Relay recovery behavior.

```text
KF092_SOURCE_REPAIR=PASS
PR411_CI=PASS
```

## 4. First post-fix Board B deployment and Relay evidence

The PR #411 repair firmware was deployed application-only using the safe inactive-slot-first procedure. Bootloader, partition table and product NVS were not erased or rewritten by the deployment operation.

The post-deployment Direct runtime was healthy, and a Relay-only baseline later produced continuous Manager-accepted Relay telemetry with no Direct acceptance, rejection or duplicate evidence.

A controlled Relay reachability interruption then produced:

```text
PRE_OFF_RELAY_TRAFFIC=PRESENT
POWER_OFF_WINDOW_RELAY_TRAFFIC=0
POST_POWER_ON_RELAY_RECOVERY=PASS
RECOVERY_WITHIN_SAME_INITIAL_BOOT=PASS
```

This demonstrated real Relay interruption/recovery behavior, but the board later rebooted and therefore the exact async-MAC-failure causal chain was not yet closed.

## 5. Repeated approximately 15-minute reboot pattern — harness defect proven

Subsequent Manager-side timeline recovery observed multiple successive Board B boot sessions while Relay telemetry itself remained healthy between restarts.

Two successive boot-to-boot intervals were approximately 15 minutes, while the Manager remained continuously running with restart count zero.

This pattern matched ESPHome connectivity reboot policy during intentional Relay-only operation where Direct Wi-Fi and MQTT are unavailable by design.

Classification:

```text
BOARD_B_PERIODIC_REBOOT_REPRODUCED=true
REBOOT_PERIOD_APPROX=15_MINUTES
REBOOT_IS_NOT_EVIDENCE_OF_KF092_SOURCE_REPAIR_FAILURE=true
HARNESS_REBOOT_POLICY_CONFLICT=PROVEN
KF092_EXACT_CAUSATION_CAPTURE=BLOCKED_BY_HARNESS_REBOOT_POLICY
```

The physical harness therefore required connectivity reboot timeouts to be disabled so Relay-only operation could be a legitimate long-lived steady state.

## 6. PR #412 physical-harness repair — source/CI PASS

PR #412 changes only the Phase 4 physical harness and source-contract coverage:

```text
wifi.reboot_timeout=0s
mqtt.reboot_timeout=0s
PRODUCT_CPP_MUTATION=false
```

Local validation passed through direct source-contract execution and ESPHome 2026.4.3 configuration validation. GitHub pull-request CI completed successfully across all 11 observed workflows.

```text
PR412_CI=PASS
HARNESS_REPAIR_SOURCE_GATE=PASS
```

## 7. Board B redeployment of exact PR #412 head — PASS

Exact source authority:

```text
SOURCE_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
SOURCE_TREE=448b10e4b11f7585d32e00c349cb39d2aaea200e
```

Fresh build artifact used for the physical deployment:

```text
FIRMWARE_SIZE=1115968
FIRMWARE_SHA256=44584b34671123ba05d4b6f94643fb9bcdad0001c5e2797d93eefe6cb2cb81db
```

The board was in ROM Download Mode for the application-only update. Fresh OTA metadata proved slot 1 active and slot 0 inactive before the write.

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

The one-shot Board B redeployment authorization was claimed and consumed and is not replayable.

## 8. Post-deployment application boot and Direct baseline — PASS

The first T1-only 90-second observation immediately after the ROM flashing session saw no Board B ingress. This did not establish a Direct product failure because a normal application boot had not yet been directly proven after the ROM session.

A controlled USB serial diagnostic then produced an explicit USB reset and proved:

```text
BOOT_PARTITION=app0
BOOT_OFFSET=0x10000
PROVISIONED_RUNTIME_STATE_LOADED=true
WIFI_CONNECTED=true
DIRECT_CHANNEL=11
RUNTIME_ACTIVE=true
RUNTIME_MODE=direct
MQTT_CONNECTED=true
DIAGNOSTIC_SCHEMA_VERSION=5
PHASE4_TELEMETRY_ACCEPTED=true
```

The build timestamp observed at runtime matched the exact redeployment build.

A subsequent T1-only correlation window observed:

```text
DIRECT_ACCEPTED_COUNT=12
RELAY_ACCEPTED_COUNT=0
BOOT_COUNT=1
DIRECT_SEQUENCE_CONTIGUOUS=true
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

The initial no-ingress window is currently classified as `APPLICATION_BOOT_NOT_PROVEN_AFTER_ROM_FLASH_SESSION`, not as a Direct/MQTT/Manager defect. Future ROM-flash procedures must explicitly perform a clean normal application boot before T1-only runtime acceptance.

## 9. Board C current evidence

A fresh 120-second observation found the third board continuously accepted by Manager through Direct telemetry with one stable boot and contiguous sequence progression.

Historical Board B Relay evidence from the same day also contained a bounded interval where the third board acted as the Relay gateway for Board B.

Therefore the current public-safe classification is:

```text
BOARD_C_DIRECT_RUNTIME=PASS
BOARD_C_RELAY_GATEWAY_FUNCTION=OBSERVED_PASS
```

This does not replace the earlier frozen simultaneous B+C Relay-through-A acceptance; it only records that the third board remains live and has also been observed performing the Relay gateway role.

## 10. Current KF-092 physical-validation boundary

Current closure status:

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

The 20-minute Relay-only same-boot validation has not yet been executed after the PR #412 redeployment. The prior approximately 15-minute reboot pattern therefore cannot yet be declared physically eliminated.

## 11. Current ONE gate

The next physical gate is intentionally narrow:

```text
CURRENT_ONE_GATE=KF092_BOARD_B_20MIN_RELAY_ONLY_SAME_BOOT_STABILITY
```

Acceptance requires a Relay-only observation longer than the previous approximately 15-minute reboot period:

```text
DIRECT_ACCEPTED_COUNT=0
RELAY_ACCEPTED_COUNT>0
BOOT_COUNT=1
SAME_BOOT_20MIN=PASS
RELAY_ONLY_20MIN=PASS
CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=PASS
```

Only after that passes should the exact KF-092 causal validation continue:

```text
Board A controlled Relay reachability interruption
-> actual async unicast failures
-> Relay failure hysteresis
-> RELAY_ACTIVE -> DISCOVERY
-> authenticated Relay reacquisition
-> same-boot recovery
-> durable schema-v5 diagnostic snapshot
```

The durable diagnostic snapshot remains the required device-side oracle for final async-MAC-failure causation. Application serial open is not a passive runtime oracle and should not be used during the causal window.

## 12. Execution model

Current execution model for this stage:

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_MAC_TERMINAL_EXECUTION
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_ENABLED=false
EXECUTOR=USER_MAC_TERMINAL
USER_ROLE=EXACT_COMMAND_EXECUTOR_AND_RAW_RESULT_REPORTER
```

## 13. Safety / authority boundary

- PR #410, PR #411 and PR #412 remain open and unmerged at this alignment point.
- No merge is authorized by this documentation synchronization.
- No new board firmware write is authorized by this documentation synchronization.
- No Broker, Manager, Home Assistant, Dynamic Security, credential or TLS mutation is authorized by this documentation synchronization.
- Consumed one-shot physical authorizations remain non-replayable.
- Raw private evidence remains local/private.
