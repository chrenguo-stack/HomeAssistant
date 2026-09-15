# N3-W KF-092 Post-Fix Physical Validation Progress Alignment — 2026-09-15

Status: `CURRENT_PROGRESS_ALIGNMENT`

> Public-safe alignment only. Raw node IDs, board MACs, host addresses, credentials, private paths, raw NVS contents and raw runtime logs are intentionally omitted.

## 1. Scope

This document synchronizes the current local KF-092 physical-validation progress with GitHub after the Relay MAC delivery-feedback repair, the Relay-only connectivity-reboot harness repair, the exact causal validation, and the subsequent A/B firmware alignment.

```text
NORTH_STAR=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
CURRENT_DEFECT=KF-092
KF092_PHYSICAL_CAUSATION=PASS
LONG_DURATION_RELAY_CONTINUITY=IN_PROGRESS
```

The previously accepted KF-089 Relay end-to-end closeout and the KF-091 Home Assistant/Broker TLS-DNS repair remain frozen PASS and are not reopened.

## 2. Fresh repository authority

```text
CURRENT_MAIN=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
CURRENT_MAIN_TREE=eed4ac1a95b64bc8c90c5784da8ffaeabb76ac7c

PR410_STATE=OPEN_UNMERGED
PR410_ROLE=DOCUMENTATION_ALIGNMENT

PR411_STATE=OPEN_UNMERGED
PR411_HEAD=576bb79c422e469ef5505f9d2bd32bfc2ec825eb
PR411_BASE=56cc0b10726a25c380fe8aa6cd7ab488b5eac291
PR411_ROLE=KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR
PR411_CI=PASS

PR412_STATE=OPEN_UNMERGED
PR412_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
PR412_BASE=576bb79c422e469ef5505f9d2bd32bfc2ec825eb
PR412_ROLE=PHYSICAL_HARNESS_CONNECTIVITY_REBOOT_TIMEOUT_REPAIR
PR412_CI=PASS
```

PR #411 repairs the product runtime delivery-feedback contract. PR #412 is a stacked physical-harness-only successor that sets both Wi-Fi and MQTT reboot timeouts to `0s`; product C++ is unchanged by PR #412.

## 3. KF-092 source repair — PASS

Proven source defect:

```text
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
SOURCE_DEFECT_PROVEN=true
```

Accepted PR #411 semantics:

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

```text
KF092_SOURCE_REPAIR=PASS
PR411_CI=PASS
```

## 4. Relay-only reboot-policy blocker and PR #412 repair

The first post-PR #411 Relay-only runs repeatedly showed Board B boot sessions separated by approximately 15 minutes while Manager remained stable. This was classified as a physical-harness policy conflict: Relay-only is an intentional valid state, but default ESPHome connectivity reboot behavior can restart a node that intentionally has no Direct Wi-Fi/MQTT path.

```text
BOARD_B_PERIODIC_REBOOT_REPRODUCED=true
REBOOT_PERIOD_APPROX=15_MINUTES
HARNESS_REBOOT_POLICY_CONFLICT=PROVEN
REBOOT_IS_NOT_EVIDENCE_OF_KF092_SOURCE_REPAIR_FAILURE=true
```

PR #412 repair:

```text
wifi.reboot_timeout=0s
mqtt.reboot_timeout=0s
PRODUCT_CPP_MUTATION=false
HARNESS_REBOOT_TIMEOUT_SOURCE_REPAIR=PASS
PR412_CI=PASS
```

## 5. Exact PR #412 artifact and Board B deployment

```text
SOURCE_HEAD=f80d4a58bccb790029dbc85a9a9f48ad509e3a2d
SOURCE_TREE=448b10e4b11f7585d32e00c349cb39d2aaea200e
FIRMWARE_SIZE=1115968
FIRMWARE_SHA256=44584b34671123ba05d4b6f94643fb9bcdad0001c5e2797d93eefe6cb2cb81db
```

Board B was updated application-only using inactive-slot-first deployment with exact readback verification. The previous application slot remained the rollback slot; product NVS readback remained unchanged; bootloader and partition table were not written.

```text
BOARD_B_HARNESS_REDEPLOY=PASS
BOARD_B_DEPLOYED_SLOT_BOOT=PASS
BOARD_B_PROVISIONED_STATE_PRESERVED=PASS
BOARD_B_DIRECT_RUNTIME=PASS
BOARD_B_MQTT_RUNTIME=PASS
```

## 6. PR #412 physical reboot-timeout validation — PASS

A Relay-only same-boot durable schema-v5 snapshot was recovered after more than 26 minutes of runtime, exceeding the prior approximately 15-minute reboot period.

```text
SNAPSHOT_UPTIME_MS=1611054
PATH_STATE=RELAY_ACTIVE
RELAY_ACTIVE_COUNT=1
SCAN_ATTEMPTS=15
SCAN_SUCCESSES=15
UNICAST_COMPLETION_COUNT=304
UNICAST_COMPLETION_SUCCESS=298
UNICAST_COMPLETION_FAILURE=6
CONNECTIVITY_REBOOT_TIMEOUT_PHYSICAL_FIX=PASS
PERIODIC_APPROX_15MIN_REBOOT_ELIMINATED=true
```

`relay_telemetry_success` remains synchronous submit acceptance and is not the asynchronous delivery oracle. `unicast_completion_*` is the device-side delivery-completion evidence.

## 7. Controlled KF-092 failure causation — PASS

A fresh controlled run established a valid Relay path before stimulus. Board A was then intentionally made unreachable once and later restored. Board B recovered Relay service without rebooting.

The durable snapshot from the same Board B boot recorded:

```text
PATH_STATE=RELAY_ACTIVE
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
```

Together with the PR #411 source contract, this closes the repaired causal path:

```text
actual async unicast failure
-> Relay delivery hysteresis
-> RELAY_ACTIVE -> DISCOVERY
-> authenticated Relay reacquisition
-> RELAY_ACTIVE
-> same-boot recovery
```

Final classification:

```text
PR411_ASYNC_MAC_DELIVERY_FEEDBACK=PHYSICAL_PASS
RELAY_FAILURE_TO_DISCOVERY=PHYSICAL_PASS
DISCOVERY_TO_RELAY_REACQUISITION=PHYSICAL_PASS
SAME_BOOT_RECOVERY=PHYSICAL_PASS
KF092_PHYSICAL_CAUSATION_PROVEN=true
KF092_POSTFIX_PHYSICAL_VALIDATION=PASS
```

The snapshot does not persist the exact chronological grouping of every individual MAC completion failure; therefore no stronger claim is made about the ordering of all seven recorded failures.

## 8. Separate long-duration Relay continuity observation

After KF-092 causation closed, a separate 20-minute continuity run reproduced partial burst gaps but did not reproduce the earlier extreme single-frame behavior.

Board B remained one boot and Relay-only. Manager saw 206 Relay frames over sequence positions spanning 7 through 246, leaving 34 sequence positions absent from Manager visibility. Missing frames were bursty.

At the same times, Board A Direct visibility also degraded. Exact forensic correlation then proved Board A MQTT timeout/reconnect events and later two Board A reboots while Board B remained in the same boot.

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

This evidence shifts the separate continuity investigation away from a pure Board-B-to-Board-A ESP-NOW incompatibility hypothesis and toward Board A local connectivity/reboot behavior or its shared upstream boundary.

The earlier Board B battery-depleted run remains invalid for product adjudication and is not used as evidence of discovery or Relay failure.

## 9. Board A alignment to exact PR #412 successor — PASS

Board A was intentionally kept on its older firmware during KF-092 causal validation as a control. After the separate continuity investigation localized instability to Board A, the same exact PR #412 artifact already proven on Board B was deployed to Board A.

Deployment used inactive-slot-first application-only update. The new image was written to the inactive application slot, exact readback SHA matched the expected artifact, the original application slot was preserved as rollback, and NVS readback remained unchanged.

The initial OTA switch attempt stopped before mutation because the host Python environment could not resolve ESP-IDF helper modules. A later attempt also stopped before the switch because `IDF_PATH` was not exported and `parttool.py` therefore retained a literal `$IDF_PATH` in the esptool path. After explicitly binding both `PYTHONPATH` and `IDF_PATH`, the official OTA switch completed and post-switch metadata proved the new application slot active.

```text
BOARD_A_EXACT_ARTIFACT_BINDING=PASS
BOARD_A_TARGET_SLOT_READBACK_VERIFY=PASS
BOARD_A_OTA_SWITCH_RECOVERY=PASS
BOARD_A_NVS_READBACK_UNCHANGED=PASS
BOARD_A_NEW_SLOT=app1
BOARD_A_ROLLBACK_SLOT=app0
```

The first `hard-reset` validation did not prove an application boot because the device remained synchronizable as a ROM/stub bootloader target. A subsequent real power-cycle cold boot produced the required application-layer evidence.

Cold-boot Direct baseline:

```text
BOARD_A_ACCEPTED_DIRECT_COUNT=22
BOARD_A_BOOT_COUNT=1
BOARD_A_SEQUENCE_CONTIGUOUS=true
BOARD_A_MQTT_TLS_SESSION_REESTABLISHED=true
BOARD_A_APP1_COLD_BOOT_DIRECT_BASELINE=PASS
```

Therefore:

```text
BOARD_A_PR411_PR412_ALIGNMENT_REDEPLOY=PASS
BOARD_A_APP1_ACTIVATION=PASS
BOARD_A_IDENTITY_PRESERVED=PASS
BOARD_A_DIRECT_BASELINE_AFTER_ALIGNMENT=PASS
```

## 10. Fully aligned A/B Relay preclaim — PASS

After both boards were placed back into the qualified physical layout, the final narrow preclaim produced one clean two-minute window:

```text
BOARD_A_DIRECT_COUNT=24
BOARD_A_BOOT_COUNT=1
BOARD_A_SEQ_GAP_COUNT=0

BOARD_B_RELAY_COUNT=24
BOARD_B_DIRECT_COUNT=0
BOARD_B_BOOT_COUNT=1
BOARD_B_SEQ_GAP_COUNT=0
BOARD_B_RELAY_GATEWAY_EXACT_A=true

MANAGER_STATUS=running
MANAGER_RESTART_COUNT=0
BROKER_STATUS=running
BROKER_RESTART_COUNT=0
ALIGNED_AB_RELAY_BASELINE=PASS
```

This establishes a clean start point for the long-duration continuity revalidation with both Board A and Board B on the same exact PR #412 successor artifact.

## 11. Current ONE gate

A 30-minute observation is currently in progress:

```text
CURRENT_ONE_GATE=N3W_KF092_ALIGNED_AB_RELAY_LONG_DURATION_CONTINUITY_20260915_01
GATE_STATE=IN_PROGRESS
```

The gate is intended to determine whether, after A/B firmware alignment:

- Board A remains in one boot;
- Board A avoids the prior MQTT timeout/reconnect/reboot pattern;
- Board B remains one boot and Relay-only through Board A;
- Board B no longer exhibits the prior long burst gaps caused by the shared Board A/upstream instability.

No conclusion from this 30-minute gate is recorded until the observation completes.

## 12. Execution model

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
- No further board firmware write is authorized by this documentation synchronization.
- No Broker, Manager, Home Assistant, Dynamic Security, credential or TLS mutation is authorized by this documentation synchronization.
- Consumed one-shot physical authorizations remain non-replayable.
- Raw private evidence remains local/private.
