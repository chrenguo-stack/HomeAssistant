# N3-W Current State

Updated: 2026-09-12  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/physical evidence takes precedence over older archives. The detailed local-chat/GitHub alignment for this state is:

`docs/development/N3W_KF089_LOCAL_CHAT_GITHUB_ALIGNMENT_20260912.md`

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
ACTIVE_PROGRESS_BRANCH=docs/n3w-kf089-board-b-physical-successor-preclaim-20260911
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
PR385_STATE=OPEN_UNMERGED
PR387_STATE=OPEN_UNMERGED
```

Documentation-only descendants do not redefine the frozen product or diagnostic source authorities.

## Current KF-089 product boundary

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

## Board B recovery boundary

The previous state claiming Board B remained in ROM download mode is superseded.

```text
ID03_OTADATA_MUTATION_PERSISTED=true
PERSISTENT_OTADATA_STATE=EXPECTED_POSTCHANGE_EXACT
TARGET_SLOT_SELECTION_STATE=POSTCHANGE_EXACT
SECOND_OTADATA_MUTATION_REQUIRED=false
APP0_REWRITE_REQUIRED=false
OTADATA_REWRITE_REQUIRED=false
FIRMWARE_FAILURE_PROVEN=false
```

ID06/ID07 were USB/RTS core-reset-only operations and did not re-sample the boot strap. ID09 captured ROM download mode. ID10 then executed one complete physical power cycle.

T1/Broker correlation after that power cycle recovered 194 fresh Board B Direct telemetry messages, sequence 0-193, all accepted. Therefore:

```text
PRODUCT_RUNTIME_AFTER_POWER_CYCLE=PASS
N3W_RUNTIME=PASS
SCHEMA_V5_RUNTIME_STATE=PASS
N3W_DIAG_DISCOVERY_SERIAL_LINE=NOT_DIRECTLY_OBSERVED
```

No further Board B boot-recovery mutation is currently justified.

## Current A/B / T1 readiness

```text
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
```

The qualified selective-RF geometry remains authoritative: Board A stays Direct while Board B is moved, powered off, to the known Wi-Fi-loss position. The Mac is not required at Board B's RF-loss position. Schema-v5 counters are read back after the RF window.

## T1 runtime boundary

```text
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
ACTIVE_DETOUR=NONE
AUTHORITATIVE_MANAGER_COUNT=1
LEGACY_MANAGER_COUNT=0
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_BROKER_COUNT=0
N3W_ACTIVE_COMPOSE_LINEAGE_COUNT=1
BROKER_HOST_PUBLICATION_RUNTIME=PASS
MANAGER_TO_BROKER_TLS_MQTT=PASS
HA_TO_BROKER_RUNTIME_CONTINUITY=PASS
T1_CONTROLLED_REBOOT_BOOT_RECOVERY=PASS
```

ID11 does not authorize T1 mutation.

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF089_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL_20260912_11
CURRENT_GATE_STATE=AUTHORIZED_NOT_YET_ADJUDICATED
ONE_RF_CAPTURE_ONLY=true
AUTO_RETRY=false
FLASH_WRITE=false
NVS_WRITE=false
OTADATA_WRITE=false
PAIRING_CHANGE=false
T1_MUTATION=false
```

ID11 must localize the first unproven boundary using Board B unicast-completion counters, Board A compact receive/decode/forward counters, and exact-window T1/Manager ingress evidence.

Pass route:

```text
B_UNICAST_TX_COMPLETION
-> A_COMPACT_RX
-> A_COMPACT_DECODE
-> A_LOCAL_FORWARD_SUBMIT
-> A_TO_T1_DOWNSTREAM_INGRESS
-> KF089_END_TO_END_RELAY_TELEMETRY
```

`esp_now_send(...) == ESP_OK` is submit evidence only and is never delivery proof.

## N3W OTA Guard boundary

PR #385 remains open and unmerged.

```text
GUARD_PREMUTATION_AND_MUTATION_DATA_PATH=PASS
GUARD_IDENTITY_CONTRACT_REPAIR=PASS
GUARD_POSTMUTATION_FLASH_FINISH_HANDLING=REPAIR_REQUIRED
GUARD_FAILURE_STATE_RECONNECT_PATH=REVIEW_REQUIRED
N3W_OTA_GUARD_FULLY_READY=false
```

Host/CI review proved the OTA-selection semantics, second-app0-flash guard, pre-mutation freshness checks, single-attempt mutation contract, and ESP32-C6 BASE MAC identity repair. Real Board B ID03 evidence then proved the flash block persisted even though `flash_finish(reboot=False)` failed and immediate failure-state reconnect could not confirm state. The post-mutation completion/verification path therefore remains a separate repair item.

ID11 is an N3-W relay data-path real-board test and does not exercise the OTA Guard mutation path.

## Required guards

- USB port is a locator only, never board identity authority.
- Fresh ROM identity is required before any board write.
- No automatic mutation retry or rollback after an uncertain write boundary.
- Lab diagnostic NVS writes are distinct from product NVS mutation.
- Strict read-only gates must not create temporary state on the target.
- Manager/Broker authority must not be selected by container name alone.
- Historical counters must be attributed to their boot session and exact test window.
- Public GitHub must not contain private board identities, credentials, raw private NVS, or private remote-host details.

## Route

```text
CURRENT=ID11_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL
NEXT=ADJUDICATE_FIRST_PASS_OR_FAIL_BOUNDARY
THEN=OTA_GUARD_POSTMUTATION_COMPLETION_REPAIR_WHEN_RELAY_GATE_STABLE
```

No PR merge is authorized by this current-state refresh.