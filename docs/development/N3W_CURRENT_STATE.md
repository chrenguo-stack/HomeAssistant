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
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=KF092_CAUSATION_PASS_CONTINUITY_FOLLOWUP_IN_PROGRESS
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

The accepted KF-089 Relay end-to-end closeout and the KF-091 Home Assistant/Broker TLS-DNS repair remain frozen PASS and are not reopened.

## KF-092 source defect and source repair

```text
KF092_DOMAIN=FIRMWARE_RUNTIME
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
SOURCE_DEFECT_PROVEN=true
```

PR #411 repairs the product runtime so actual asynchronous unicast MAC completion, not synchronous submit acceptance, drives Relay delivery hysteresis.

```text
SYNC_SUBMIT_SUCCESS=NOT_DELIVERY_SUCCESS
IMMEDIATE_SYNC_SUBMIT_FAILURE=COUNTS_AS_FAILURE
ASYNC_UNICAST_COMPLETION=CALLBACK_SAFE_BOUNDED_ENQUEUE
NORMAL_LOOP=DRAINS_COMPLETIONS=true
CURRENT_ACTIVE_RELAY_DESTINATION_MATCH_REQUIRED=true
BROADCAST_COMPLETION_AFFECTS_CHILD_RELAY_PATH=false
STALE_RELAY_COMPLETION=IGNORE
RELAY_FAILURES_TO_DISCOVERY=2
KF092_SOURCE_REPAIR=PASS
PR411_CI=PASS
```

## Relay-only reboot-policy repair

Before PR #412, repeated Board B Relay-only runs showed approximately 15-minute reboot intervals while Manager remained stable. This was classified as a physical-harness connectivity reboot policy conflict, not evidence that PR #411 failed.

PR #412 changes only the physical harness:

```text
wifi.reboot_timeout=0s
mqtt.reboot_timeout=0s
PRODUCT_CPP_MUTATION=false
HARNESS_REBOOT_TIMEOUT_SOURCE_REPAIR=PASS
PR412_CI=PASS
```

Exact successor artifact:

```text
SOURCE_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
SOURCE_TREE=448b10e4b11f7585d32e00c349cb39d2aaea200e
FIRMWARE_SIZE=1115968
FIRMWARE_SHA256=44584b34671123ba05d4b6f94643fb9bcdad0001c5e2797d93eefe6cb2cb81db
```

## Board B PR #412 physical validation — PASS

Board B exact PR #412 successor deployment passed inactive-slot-first write/readback verification with rollback slot preserved, NVS unchanged, bootloader untouched and partition table untouched.

A durable Relay-only schema-v5 snapshot exceeded 26 minutes in one boot and remained `RELAY_ACTIVE`, eliminating the prior approximately 15-minute reboot behavior.

```text
CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=PASS
PERIODIC_APPROX_15MIN_REBOOT_ELIMINATED=true
```

## KF-092 exact physical causation — PASS

A controlled Relay reachability interruption was executed from a freshly proven B→A→Manager Relay baseline. Board B remained in the same boot, recorded real asynchronous unicast delivery failures, returned from RelayActive to Discovery, authenticated the Relay again after Board A was restored, and re-entered RelayActive.

Durable same-boot snapshot evidence included:

```text
RELAY_ACTIVE_COUNT=2
PEER_INSTALL_ATTEMPTS=2
PEER_INSTALL_SUCCESS=2
ACCEPT_VERIFY=2
SCAN_ATTEMPTS=375
SCAN_SUCCESSES=342
SCAN_FAILURES=33
UNICAST_COMPLETION_COUNT=176
UNICAST_COMPLETION_SUCCESS=169
UNICAST_COMPLETION_FAILURE=7
PATH_STATE=RELAY_ACTIVE
```

Final KF-092 causation classification:

```text
PR411_ASYNC_MAC_DELIVERY_FEEDBACK=PHYSICAL_PASS
RELAY_FAILURE_TO_DISCOVERY=PHYSICAL_PASS
DISCOVERY_TO_RELAY_REACQUISITION=PHYSICAL_PASS
SAME_BOOT_RECOVERY=PHYSICAL_PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
```

The snapshot does not preserve the exact chronological grouping of every individual completion failure, so no stronger claim is made about all seven failures beyond the proven repaired causal path.

## Separate long-duration Relay continuity investigation

A later 20-minute run did not reproduce the earlier extreme single-frame result but did show burst gaps in Manager-visible Board B Relay traffic. Board B stayed in one boot. The same intervals also showed Board A Direct degradation.

Exact T1/Broker forensics proved Board A MQTT timeout/reconnect events and later two Board A reboots while Manager and Broker remained running with restart count zero. This moved the separate continuity investigation away from a pure B→A ESP-NOW incompatibility hypothesis and toward Board A local connectivity/reboot behavior or its shared upstream boundary.

```text
BOARD_B_SAME_BOOT_20MIN=true
BOARD_B_MANAGER_VISIBLE_RELAY_COUNT=206
BOARD_B_SEQUENCE_SPAN_POSITIONS=240
BOARD_B_MANAGER_VISIBLE_RATIO_APPROX=85.8_PERCENT
BOARD_A_DIRECT_AND_BOARD_B_RELAY_GAPS_CORRELATED=true
BOARD_A_MQTT_TIMEOUT_EVENTS_OBSERVED=true
BOARD_A_REBOOTS_OBSERVED=true
MANAGER_RESTART_COUNT=0
BROKER_RESTART_COUNT=0
```

The earlier Board B battery-depleted run is excluded from product adjudication.

## Board A alignment to exact PR #412 successor — PASS

Board A was then aligned to the same exact PR #412 successor artifact already proven on Board B. Deployment used inactive-slot-first application-only update with exact readback verification, old application slot retained as rollback, NVS unchanged, bootloader untouched and partition table untouched.

The host-side OTA tooling required explicit `PYTHONPATH` and `IDF_PATH` binding before the official ESP-IDF helper could perform the OTA metadata switch. Earlier failed host attempts stopped before the intended switch mutation.

A real cold power-cycle then proved the new Board A application boot and Direct path:

```text
BOARD_A_PR411_PR412_ALIGNMENT_REDEPLOY=PASS
BOARD_A_APP1_ACTIVATION=PASS
BOARD_A_IDENTITY_PRESERVED=PASS
BOARD_A_ACCEPTED_DIRECT_COUNT=22
BOARD_A_BOOT_COUNT=1
BOARD_A_SEQUENCE_CONTIGUOUS=true
BOARD_A_MQTT_TLS_SESSION_REESTABLISHED=true
BOARD_A_DIRECT_BASELINE_AFTER_ALIGNMENT=PASS
BOARD_A_ROLLBACK_SLOT=app0
```

## Fully aligned A/B Relay baseline — PASS

After both boards were returned to the qualified physical layout, a fresh two-minute preclaim established:

```text
BOARD_A_DIRECT_COUNT=24
BOARD_A_BOOT_COUNT=1
BOARD_A_SEQ_GAP_COUNT=0
BOARD_B_RELAY_COUNT=24
BOARD_B_DIRECT_COUNT=0
BOARD_B_BOOT_COUNT=1
BOARD_B_SEQ_GAP_COUNT=0
BOARD_B_RELAY_GATEWAY_EXACT_A=true
MANAGER_RESTART_COUNT=0
BROKER_RESTART_COUNT=0
ALIGNED_AB_RELAY_BASELINE=PASS
```

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF092_ALIGNED_AB_RELAY_LONG_DURATION_CONTINUITY_20260915_01
GATE_STATE=IN_PROGRESS
```

A 30-minute observation is currently running with both Board A and Board B on the same exact PR #412 successor artifact. Its purpose is to determine whether Board A remains one boot and avoids the prior MQTT timeout/reboot pattern, and whether Board B remains one-boot Relay-only through A without the prior long burst gaps.

No result from the running 30-minute gate is claimed until the observation completes.

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
- Relay-only physical acceptance must remain stable beyond the prior approximately 15-minute connectivity reboot window.
- Application serial open is not a passive runtime oracle.
- After a ROM/stub flashing session, a true normal application boot must be proven before T1-only runtime acceptance.
- `otatool.py`/`parttool.py` invoked outside a fully exported ESP-IDF shell require explicit helper-path and `IDF_PATH` authority; host-tool failure must not be misclassified as board failure.
- Consumed one-shot physical authorizations are never replayable.
- USB port is a locator only, not board identity authority.
- No merge, additional board firmware write, Broker/Manager/Home Assistant/DynSec/credential/TLS mutation is authorized by this documentation synchronization.
