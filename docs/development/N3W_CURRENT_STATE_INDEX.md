# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current KF-092 physical-progress authority: `docs/development/N3W_KF092_POSTFIX_PHYSICAL_VALIDATION_PROGRESS_ALIGNMENT_20260915.md`  
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

Repository `main` must be queried fresh before source mutation or merge. The fixed SHA above is the current alignment-time authority only.

## Frozen accepted boundaries

```text
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF091_HOME_ASSISTANT_BROKER_TLS_DNS_BINDING_REPAIR=PASS
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
```

These results are not reopened by KF-092 continuation.

## KF-092 source and physical causation

```text
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
SOURCE_DEFECT_PROVEN=true
KF092_SOURCE_REPAIR=PASS
PR411_CI=PASS

PR411_ASYNC_MAC_DELIVERY_FEEDBACK=PHYSICAL_PASS
RELAY_FAILURE_TO_DISCOVERY=PHYSICAL_PASS
DISCOVERY_TO_RELAY_REACQUISITION=PHYSICAL_PASS
SAME_BOOT_RECOVERY=PHYSICAL_PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
```

The repaired path is now physically proven: real async unicast delivery failures feed Relay hysteresis, drive `RELAY_ACTIVE -> DISCOVERY`, and permit authenticated same-boot Relay reacquisition.

## Relay-only reboot-policy repair

```text
BOARD_B_PERIODIC_REBOOT_REPRODUCED=true
REBOOT_PERIOD_APPROX=15_MINUTES
HARNESS_REBOOT_POLICY_CONFLICT=PROVEN

wifi.reboot_timeout=0s
mqtt.reboot_timeout=0s
PRODUCT_CPP_MUTATION=false
HARNESS_REBOOT_TIMEOUT_SOURCE_REPAIR=PASS
PR412_CI=PASS
```

Exact PR #412 successor artifact:

```text
SOURCE_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
SOURCE_TREE=448b10e4b11f7585d32e00c349cb39d2aaea200e
FIRMWARE_SHA256=44584b34671123ba05d4b6f94643fb9bcdad0001c5e2797d93eefe6cb2cb81db
```

A durable Board B Relay-only snapshot exceeded 26 minutes in one boot, so the prior approximately 15-minute reboot behavior is physically eliminated for the repaired harness.

```text
CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=PASS
PERIODIC_APPROX_15MIN_REBOOT_ELIMINATED=true
```

## Separate Relay continuity investigation

A later 20-minute run kept Board B in one boot but showed burst gaps in Manager-visible Relay traffic. Exact T1/Broker correlation showed simultaneous Board A Direct degradation, Board A MQTT timeout/reconnect events, and later two Board A reboots while Manager and Broker stayed up.

```text
BOARD_B_SAME_BOOT_20MIN=true
BOARD_B_MANAGER_VISIBLE_RELAY_COUNT=206
BOARD_B_SEQUENCE_SPAN_POSITIONS=240
BOARD_A_DIRECT_AND_BOARD_B_RELAY_GAPS_CORRELATED=true
BOARD_A_MQTT_TIMEOUT_EVENTS_OBSERVED=true
BOARD_A_REBOOTS_OBSERVED=true
MANAGER_RESTART_COUNT=0
BROKER_RESTART_COUNT=0
```

This continuity issue is tracked separately from the already closed KF-092 causal proof.

## Board A / Board B aligned successor state

Board A was subsequently updated to the same exact PR #412 successor artifact as Board B, with inactive-slot-first application-only deployment, exact readback verification, rollback slot retained and NVS unchanged.

A true cold boot then proved Board A Direct runtime and identity continuity.

```text
BOARD_A_PR411_PR412_ALIGNMENT_REDEPLOY=PASS
BOARD_A_APP1_ACTIVATION=PASS
BOARD_A_IDENTITY_PRESERVED=PASS
BOARD_A_DIRECT_BASELINE_AFTER_ALIGNMENT=PASS
```

The fully aligned A/B physical-layout preclaim then passed:

```text
BOARD_A_DIRECT_COUNT=24
BOARD_A_BOOT_COUNT=1
BOARD_A_SEQ_GAP_COUNT=0
BOARD_B_RELAY_COUNT=24
BOARD_B_DIRECT_COUNT=0
BOARD_B_BOOT_COUNT=1
BOARD_B_SEQ_GAP_COUNT=0
BOARD_B_RELAY_GATEWAY_EXACT_A=true
ALIGNED_AB_RELAY_BASELINE=PASS
```

## Current broader acceptance boundary

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
MAINLINE_ACCEPTANCE_ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=NOT_YET_CLOSED
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=KF092_CAUSATION_PASS_CONTINUITY_FOLLOWUP_IN_PROGRESS
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF092_ALIGNED_AB_RELAY_LONG_DURATION_CONTINUITY_20260915_01
GATE_STATE=IN_PROGRESS
```

A 30-minute observation is currently running with both A and B on the same exact successor artifact. Its result is intentionally not pre-judged in this index.

## Execution model

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_MAC_TERMINAL_EXECUTION
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
CODEX_ENABLED=false
EXECUTOR=USER_MAC_TERMINAL
```

Historical handoff and archive files remain historical and are not rewritten merely to erase dated intermediate states.
