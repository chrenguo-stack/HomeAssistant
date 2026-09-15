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

Current KF-092 closeout authority:

`docs/development/N3W_KF092_POSTFIX_PHYSICAL_VALIDATION_CLOSEOUT_20260915.md`

Detailed physical-progress archive:

`docs/development/N3W_KF092_POSTFIX_PHYSICAL_VALIDATION_PROGRESS_ALIGNMENT_20260915.md`

## Product North Star

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

Broader acceptance state:

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
MAINLINE_ACCEPTANCE_ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=NOT_YET_CLOSED
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_CLOSED
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

The accepted KF-089 Relay end-to-end closeout and KF-091 Home Assistant/Broker TLS-DNS repair remain frozen PASS and are not reopened.

## KF-092 source defect and source repair — PASS

```text
KF092_DOMAIN=FIRMWARE_RUNTIME
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
SOURCE_DEFECT_PROVEN=true
```

PR #411 repairs the runtime so actual asynchronous unicast MAC completion, not synchronous submit acceptance, drives Relay delivery hysteresis.

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

## Relay-only reboot-policy repair — PASS

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

A durable Board B Relay-only schema-v5 snapshot exceeded 26 minutes in one boot and remained RelayActive.

```text
CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=PASS
PERIODIC_APPROX_15MIN_REBOOT_ELIMINATED=true
```

## KF-092 exact physical causation — PASS

A controlled Relay reachability interruption from a freshly proven Relay baseline established the repaired causal chain in one Board B boot:

```text
actual async unicast failure
-> Relay delivery hysteresis
-> RELAY_ACTIVE -> DISCOVERY
-> authenticated Relay reacquisition
-> RELAY_ACTIVE
-> same-boot recovery
```

```text
PR411_ASYNC_MAC_DELIVERY_FEEDBACK=PHYSICAL_PASS
RELAY_FAILURE_TO_DISCOVERY=PHYSICAL_PASS
DISCOVERY_TO_RELAY_REACQUISITION=PHYSICAL_PASS
SAME_BOOT_RECOVERY=PHYSICAL_PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
```

The durable snapshot does not preserve the exact chronological grouping of every recorded completion failure, so no stronger claim is made about the ordering of all failures.

## Separate Relay continuity investigation and Board A alignment

A later 20-minute Relay continuity run kept Board B in one boot but showed burst gaps in Manager-visible Relay traffic. The same intervals showed Board A Direct degradation. Exact Broker evidence showed Board A MQTT timeout/reconnect events and later Board A reboots while Manager and Broker remained stable.

This made a pure B→A ESP-NOW incompatibility explanation unsupported and identified Board A local connectivity/reboot behavior or its shared upstream boundary as the primary continuity suspect.

Board A was then aligned to the same exact PR #412 successor artifact as Board B. Deployment used inactive-slot-first application-only update with exact readback verification, old application slot retained as rollback and NVS unchanged. A real cold boot proved the new application slot, original identity, MQTT/TLS Direct path and contiguous telemetry.

```text
BOARD_A_PR411_PR412_ALIGNMENT_REDEPLOY=PASS
BOARD_A_APP1_ACTIVATION=PASS
BOARD_A_IDENTITY_PRESERVED=PASS
BOARD_A_DIRECT_BASELINE_AFTER_ALIGNMENT=PASS
```

## Fully aligned A/B Relay baseline — PASS

After both boards returned to the qualified physical layout, a clean preclaim established:

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

## Aligned A/B 30-minute Relay continuity — PASS

Final 30-minute observation with both boards on the exact same PR #412 successor artifact:

```text
BOARD_A_ACCEPTED_COUNT=360
BOARD_A_DIRECT_COUNT=360
BOARD_A_BOOT_COUNT=1
BOARD_A_SEQ_GAP_COUNT=0
BOARD_A_TIME_GAP_COUNT=0
BOARD_A_MQTT_TIMEOUT_OBSERVED=false

BOARD_B_ACCEPTED_COUNT=354
BOARD_B_DIRECT_COUNT=0
BOARD_B_RELAY_COUNT=354
BOARD_B_BOOT_COUNT=1
BOARD_B_GATEWAY_EXACT_A=true
BOARD_B_SEQUENCE_SPAN=360
BOARD_B_ISOLATED_MISSING_FRAME_COUNT=6
BOARD_B_MULTI_FRAME_BURST_LOSS_OBSERVED=false

MANAGER_RESTART_COUNT=0
BROKER_RESTART_COUNT=0
```

The six missing Board B sequence positions were isolated single-frame losses. No long multi-frame outage occurred and Board A had no Direct gap.

```text
N3W_KF092_ALIGNED_AB_RELAY_LONG_DURATION_CONTINUITY_20260915_01=PASS
BOARD_A_30MIN_DIRECT_CONTINUITY=PASS
BOARD_A_SINGLE_BOOT_30MIN=PASS
BOARD_B_30MIN_RELAY_CONTINUITY=PASS
BOARD_B_SINGLE_BOOT_30MIN=PASS
PREVIOUS_LARGE_BURST_GAPS_REPRODUCED=false
PREVIOUS_BOARD_A_REBOOT_PATTERN_REPRODUCED=false
ALIGNED_AB_LONG_DURATION_MAJOR_CONTINUITY_DEFECT=CLOSED_PASS
ZERO_LOSS_RELAY_NOT_PROVEN=true
```

The aligned comparison strongly supports Board A's old connectivity/reboot behavior as a major contributor to the earlier large burst gaps. It does not prove that behavior was the unique cause of every earlier missing frame.

## KF-092 closeout

```text
KF092_SOURCE_REPAIR=PASS
KF092_SOURCE_CI=PASS
KF092_REBOOT_POLICY_REPAIR=PASS
KF092_REBOOT_POLICY_PHYSICAL_FIX=PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
KF092_ALIGNED_AB_LONG_DURATION_CONTINUITY=PASS
KF092_STATUS=CLOSED_PASS
```

KF-092 is no longer the active physical gate.

## Current ONE gate

KF-092 causal closure must not be relabelled as proof of a same-session Direct→Relay failover. The accepted KF-092 controlled experiment started from an already established Relay path and interrupted the active Relay gateway.

```text
CURRENT_ONE_GATE=N3W_LIVE_DIRECT_TO_RELAY_FAILOVER_ACCEPTANCE_PRECLAIM
GATE_STATE=PENDING
```

The next mainline task is to establish a clean live Direct baseline and then separately prove automatic Direct→Relay failover without rebooting the child node. Relay→Direct recovery remains a subsequent independent gate.

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
- Wi-Fi/callback task code must not directly mutate normal-loop path state.
- Actual unicast completion must be destination-bound before affecting the current Relay path.
- Relay-only physical harnesses must not use connectivity reboot policies that invalidate Relay-only as a steady state.
- Manager-visible continuity and device-side MAC delivery are distinct observability layers.
- A successful long-duration Relay window does not prove zero packet loss.
- Application serial open is not a passive runtime oracle.
- After a ROM/stub flashing session, a true normal application boot must be proven before T1-only runtime acceptance.
- `otatool.py`/`parttool.py` invoked outside a fully exported ESP-IDF shell require explicit helper-path and `IDF_PATH` authority; host-tool failure must not be misclassified as board failure.
- Consumed one-shot physical authorizations are never replayable.
- USB port is a locator only, not board identity authority.
- No merge, additional board firmware write, Broker/Manager/Home Assistant/DynSec/credential/TLS mutation is authorized by this documentation synchronization.
