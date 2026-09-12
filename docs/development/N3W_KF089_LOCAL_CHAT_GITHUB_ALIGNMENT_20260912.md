# N3-W KF-089 local-chat / GitHub alignment — 2026-09-12

Status: `CURRENT_PROGRESS_ALIGNMENT`

This document synchronizes the latest local-chat execution state with the durable GitHub team workspace. It does not merge PR #385 or PR #387 and does not authorize any new physical action beyond the already-recorded ID11 authorization.

## Repository and source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
PR385_STATE=OPEN_UNMERGED
PR387_STATE=OPEN_UNMERGED
```

Documentation-only repository descendants do not redefine the frozen product or diagnostic source authorities above.

## Board B recovery state — corrected and closed enough to return to relay testing

The stale public state that Board B remains in ROM download mode is no longer current.

Frozen recovery facts:

```text
ID03_OTADATA_MUTATION_PERSISTED=true
PERSISTENT_OTADATA_STATE=EXPECTED_POSTCHANGE_EXACT
TARGET_SLOT_SELECTION_STATE=POSTCHANGE_EXACT
SECOND_OTADATA_MUTATION_REQUIRED=false
APP0_REWRITE_REQUIRED=false
OTADATA_REWRITE_REQUIRED=false
FIRMWARE_FAILURE_PROVEN=false
```

ID06 and ID07 used USB/RTS core-reset-only mechanisms and did not re-sample the boot strap. ID09 later captured an ESP32-C6 ROM download-mode log. Host-only review showed the passive serial open was not the leading cause of entering download mode. The most consistent chain is that Board B was already in download mode and the earlier USB core resets did not exit it.

ID10 then performed one complete physical power cycle. The USB startup observer failed to rebind after the power transition, so startup serial evidence was not recovered. However, T1/Broker correlation after that power cycle recovered fresh Board B telemetry:

```text
BOARD_B_FRESH_TELEMETRY_FOUND=true
FIRST_TELEMETRY_TIME=2026-09-11T16:04:04.754Z
LAST_TELEMETRY_TIME=2026-09-11T16:20:09.888Z
TELEMETRY_COUNT=194
SEQ_RANGE=0-193
DIRECT_COUNT=194
RELAY_COUNT=0
ACCEPTED_COUNT=194
PRODUCT_RUNTIME_AFTER_POWER_CYCLE=PASS
```

The deployed Phase-4 generic source emits this synthetic telemetry only after `runtime_ready()` and binds the lab diagnostic boot session on the same runtime path. Therefore the current adjudication is:

```text
PRODUCT_RUNTIME_AFTER_POWER_CYCLE=PASS
N3W_RUNTIME=PASS
SCHEMA_V5_RUNTIME_STATE=PASS
N3W_DIAG_DISCOVERY_SERIAL_LINE=NOT_DIRECTLY_OBSERVED
```

No additional Board B boot-recovery mutation is justified by current evidence.

## Current A/B / T1 readiness

The final host-only preclaim for the relay data-path gate returned:

```text
SOURCE_AUTHORITY_PASS=true
T1_OBSERVER_READY=true
BOARD_A_DIRECT_CURRENT=true
BOARD_B_DIRECT_CURRENT=true
FRESH_BOOT_COUNTER_RESET_CONTRACT=PASS
A_FRESH_BOOT_BASELINE_SUFFICIENT=true
B_COLD_BOOT_BASELINE_SUFFICIENT=true
SELECTIVE_RF_ZONE_FROZEN=PASS
DEFAULT_STUB_READBACK_READY=true
BOARD_B_READBACK_COMMAND_READY=true
BOARD_A_READBACK_COMMAND_READY=true
FULL_OPERATOR_SEQUENCE_READY=true
SINGLE_AUTHORIZATION_CAN_COVER_ALL=true
READY_FOR_PHYSICAL_AUTHORIZATION=true
```

The selective RF geometry remains the qualified route: Board A remains Direct while Board B is moved, powered off, to the already-qualified Wi-Fi-loss position. The Mac does not need to be present at Board B's RF-loss position. Schema-v5 counters are persisted and are read back after the RF window.

## Current KF-089 acceptance boundary

Already proven:

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
```

Still not proven:

```text
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

The next physical gate is already explicitly authorized once:

```text
AUTHORIZATION_ID=N3W_KF089_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL_20260912_11
AUTHORIZATION_GRANTED=true
ONE_RF_CAPTURE_ONLY=true
AUTO_RETRY=false
FLASH_WRITE=false
NVS_WRITE=false
OTADATA_WRITE=false
PAIRING_CHANGE=false
T1_MUTATION=false
```

ID11 is authorized but no ID11 execution result has yet been recorded in the local chat at this alignment point. Do not mark the end-to-end Relay telemetry gate PASS until the RF window and A/B Schema-v5 readbacks produce evidence.

## ID11 evidence target

Board B counters:

```text
relay_telemetry_attempts
relay_telemetry_success
unicast_completion_count
unicast_completion_success
unicast_completion_failure
```

Board A counters:

```text
compact_rx_count
compact_state_reject_count
compact_child_binding_failure
compact_decode_success
compact_decode_failure
compact_wrap_failure
compact_forward_attempts
compact_forward_submit_success
compact_forward_submit_failure
```

Pass localization sequence:

```text
B_UNICAST_TX_COMPLETION
-> A_COMPACT_RX
-> A_COMPACT_DECODE
-> A_LOCAL_FORWARD_SUBMIT
-> A_TO_T1_DOWNSTREAM_INGRESS
-> KF089_END_TO_END_RELAY_TELEMETRY
```

`esp_now_send(...) == ESP_OK` remains synchronous submit evidence only and must never be treated as delivery success.

## T1 state

T1 convergence remains closed PASS:

```text
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
ACTIVE_DETOUR=NONE
AUTHORITATIVE_MANAGER_COUNT=1
LEGACY_MANAGER_COUNT=0
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_BROKER_COUNT=0
```

No T1 mutation is part of ID11.

## N3W OTA Guard — current disposition

PR #385 remains open and unmerged. Host/source review, safety contract, OTA selection semantics, single-attempt mutation design, second-app0-flash guard, and the ESP32-C6 BASE MAC identity-contract repair have passed their host/CI gates.

The real Board B ID03 execution nevertheless exposed a post-mutation closeout defect/ambiguity:

```text
FLASH_BLOCK_COMPLETED=true
FLASH_FINISH_COMPLETED=false
LATER_PERSISTENT_OTADATA_STATE=EXPECTED_POSTCHANGE_EXACT
```

Thus the write data ultimately persisted, while `flash_finish(reboot=False)` returned an error and the immediate failure-state reconnect/read could not establish the persistent result. The current Guard disposition is therefore:

```text
GUARD_PREMUTATION_AND_MUTATION_DATA_PATH=PASS
GUARD_IDENTITY_CONTRACT_REPAIR=PASS
GUARD_POSTMUTATION_FLASH_FINISH_HANDLING=REPAIR_REQUIRED
GUARD_FAILURE_STATE_RECONNECT_PATH=REVIEW_REQUIRED
N3W_OTA_GUARD_FULLY_READY=false
```

Do not describe PR #385 as fully production-ready until the post-mutation completion / verification path is repaired and regressed. ID11 is an N3-W Relay data-path real-board test; it does not exercise the OTA Guard mutation path.

## Current route

```text
CURRENT_ONE_GATE=N3W_KF089_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL_20260912_11
CURRENT_GATE_STATE=AUTHORIZED_NOT_YET_ADJUDICATED
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

After ID11, adjudicate the exact first failing or passing boundary. Separately, after the relay gate is stable, return to the OTA Guard post-mutation completion repair. No PR merge is authorized by this alignment document.
