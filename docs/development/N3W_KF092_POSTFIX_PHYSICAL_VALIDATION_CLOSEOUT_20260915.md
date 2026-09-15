# N3-W KF-092 Post-Fix Physical Validation Closeout — 2026-09-15

Status: `CLOSED_PASS`

> Public-safe closeout. Raw node IDs, board MACs, host addresses, credentials, private paths, raw NVS contents and raw runtime logs are intentionally omitted.

## Scope

This document closes KF-092 after the Relay MAC delivery-feedback source repair, the Relay-only connectivity-reboot harness repair, exact physical causation, Board A/B firmware alignment, and a final 30-minute aligned Relay continuity run.

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
KF092_SOURCE_REPAIR=PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
KF092_ALIGNED_AB_LONG_DURATION_CONTINUITY=PASS
```

KF-089 Relay end-to-end closeout and KF-091 Home Assistant/Broker TLS-DNS repair remain frozen PASS and are not reopened.

## Repository/source authority

```text
CURRENT_MAIN_AT_CLOSEOUT=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
CURRENT_MAIN_TREE_AT_CLOSEOUT=eed4ac1a95b64bc8c90c5784da8ffaeabb76ac7c
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

Exact physical successor artifact:

```text
SOURCE_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
SOURCE_TREE=448b10e4b11f7585d32e00c349cb39d2aaea200e
FIRMWARE_SIZE=1115968
FIRMWARE_SHA256=44584b34671123ba05d4b6f94643fb9bcdad0001c5e2797d93eefe6cb2cb81db
```

## Source defect and repair

Proven defect:

```text
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
SOURCE_DEFECT_PROVEN=true
```

The pre-repair runtime treated synchronous `esp_now_send(...) == ESP_OK` submit acceptance as Relay delivery success while actual asynchronous unicast MAC completion only fed diagnostics.

PR #411 repairs that contract:

```text
SYNC_SUBMIT_SUCCESS=NOT_DELIVERY_SUCCESS
IMMEDIATE_SYNC_SUBMIT_FAILURE=COUNTS_AS_FAILURE
ASYNC_UNICAST_COMPLETION=CALLBACK_SAFE_BOUNDED_ENQUEUE
NORMAL_LOOP=DRAINS_COMPLETIONS=true
CURRENT_ACTIVE_RELAY_DESTINATION_MATCH_REQUIRED=true
BROADCAST_COMPLETION_AFFECTS_CHILD_RELAY_PATH=false
STALE_RELAY_COMPLETION=IGNORE
ACTUAL_MAC_SUCCESS=FEEDS_RELAY_HYSTERESIS_SUCCESS
ACTUAL_MAC_FAILURE=FEEDS_RELAY_HYSTERESIS_FAILURE
RELAY_FAILURES_TO_DISCOVERY=2
```

## Relay-only reboot-policy repair

Before PR #412, intentional Relay-only operation repeatedly rebooted at approximately 15-minute intervals while Manager remained stable. This was a physical-harness policy conflict with default ESPHome connectivity reboot behavior, not evidence that PR #411 failed.

PR #412 changes only the physical harness:

```text
wifi.reboot_timeout=0s
mqtt.reboot_timeout=0s
PRODUCT_CPP_MUTATION=false
```

A durable Board B Relay-only snapshot exceeded 26 minutes in one boot and remained RelayActive.

```text
CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=PASS
PERIODIC_APPROX_15MIN_REBOOT_ELIMINATED=true
```

## Exact KF-092 physical causation

A controlled Relay reachability interruption from a freshly proven Relay baseline established the repaired causal chain without rebooting Board B:

```text
actual async unicast failure
-> Relay delivery hysteresis
-> RELAY_ACTIVE -> DISCOVERY
-> authenticated Relay reacquisition
-> RELAY_ACTIVE
-> same-boot recovery
```

Durable schema-v5 evidence included multiple unicast completion failures, a second RelayActive acquisition, repeated scan activity, successful peer reinstall and authenticated accept verification.

```text
PR411_ASYNC_MAC_DELIVERY_FEEDBACK=PHYSICAL_PASS
RELAY_FAILURE_TO_DISCOVERY=PHYSICAL_PASS
DISCOVERY_TO_RELAY_REACQUISITION=PHYSICAL_PASS
SAME_BOOT_RECOVERY=PHYSICAL_PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
```

The snapshot does not preserve the exact chronological grouping of every recorded completion failure, so no stronger claim is made about the ordering of all failures.

## Separate continuity investigation and Board A alignment

A later 20-minute Relay continuity run kept Board B in one boot but showed burst gaps in Manager-visible Relay traffic. Those gaps correlated with Board A Direct degradation. Broker evidence showed Board A MQTT timeout/reconnect events and later Board A reboots while Manager and Broker remained stable.

This made a pure Board-B-to-Board-A ESP-NOW incompatibility explanation unsupported and identified Board A local connectivity/reboot behavior or its shared upstream boundary as the primary continuity suspect.

Board A was then aligned to the same exact PR #412 successor artifact as Board B. The application-only inactive-slot-first deployment preserved the old application slot as rollback and kept NVS unchanged. A real cold boot proved the new application slot, preserved identity, MQTT/TLS Direct path and contiguous telemetry.

```text
BOARD_A_PR411_PR412_ALIGNMENT_REDEPLOY=PASS
BOARD_A_APP1_ACTIVATION=PASS
BOARD_A_IDENTITY_PRESERVED=PASS
BOARD_A_DIRECT_BASELINE_AFTER_ALIGNMENT=PASS
```

## Final aligned A/B 30-minute continuity — PASS

A clean aligned preclaim first proved Board A Direct and Board B Relay-through-A with one boot each and no sequence gaps. The subsequent 30-minute observation produced:

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

The six missing Board B positions were isolated single-frame losses. Five produced approximately 10-second accepted-frame intervals because one nominal 5-second frame was absent. There was no long multi-frame outage and no Board A Direct gap.

Therefore:

```text
N3W_KF092_ALIGNED_AB_RELAY_LONG_DURATION_CONTINUITY_20260915_01=PASS
BOARD_A_30MIN_DIRECT_CONTINUITY=PASS
BOARD_A_SINGLE_BOOT_30MIN=PASS
BOARD_B_30MIN_RELAY_CONTINUITY=PASS
BOARD_B_SINGLE_BOOT_30MIN=PASS
PREVIOUS_LARGE_BURST_GAPS_REPRODUCED=false
PREVIOUS_BOARD_A_REBOOT_PATTERN_REPRODUCED=false
ALIGNED_AB_LONG_DURATION_MAJOR_CONTINUITY_DEFECT=CLOSED_PASS
```

Boundary retained:

```text
ZERO_LOSS_RELAY_NOT_PROVEN=true
BOARD_B_ISOLATED_SINGLE_FRAME_LOSS_OBSERVED=true
BOARD_B_ISOLATED_MISSING_FRAME_COUNT=6
```

The final aligned run strongly supports Board A's old connectivity/reboot behavior as a major contributor to the earlier large burst gaps. A single controlled comparison does not prove it was the unique cause of every earlier missing frame.

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

## Next mainline boundary

KF-092 causal closure must not be relabelled as proof of a same-session Direct-to-Relay failover. The controlled KF-092 experiment started from an established Relay path and interrupted the active Relay gateway.

The next mainline acceptance remains a separate live failover gate:

```text
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_CLOSED
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
NEXT_ONE_GATE=N3W_LIVE_DIRECT_TO_RELAY_FAILOVER_ACCEPTANCE_PRECLAIM
```

Home Assistant Relay entity-update acceptance also remains separately open and is not claimed by this closeout.

## Guards retained

- `esp_now_send(...) == ESP_OK` is submit acceptance, not MAC delivery completion.
- Actual unicast completion must be destination-bound before affecting current Relay path state.
- Callback/Wi-Fi task code must not directly mutate normal-loop path state.
- Relay-only harnesses must not use connectivity reboot policies that invalidate Relay-only as a steady state.
- USB port is a locator only, not board identity authority.
- After ROM/stub flashing, a true normal application boot must be proven before runtime acceptance.
- Consumed one-shot physical authorizations are never replayable.
- Manager-visible continuity and device-side MAC delivery are distinct observability layers.
- A successful 30-minute continuity window does not establish zero packet loss.
