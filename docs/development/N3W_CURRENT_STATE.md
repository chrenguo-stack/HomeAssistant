# N3-W Current State

Updated: 2026-09-12  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/physical evidence takes precedence over older archives. The detailed local-chat/GitHub alignment is:

`docs/development/N3W_KF089_LOCAL_CHAT_GITHUB_ALIGNMENT_20260912.md`

The latest ID11 execution stop is:

`docs/development/N3W_KF089_ID11_RF_CAPTURE_STOP_HOST_IDENTITY_NORMALIZATION_20260912.md`

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

ID11 has not yet changed this product boundary because the decisive persisted Schema-v5 counters were not recovered.

## Board B recovery boundary

```text
ID03_OTADATA_MUTATION_PERSISTED=true
PERSISTENT_OTADATA_STATE=EXPECTED_POSTCHANGE_EXACT
TARGET_SLOT_SELECTION_STATE=POSTCHANGE_EXACT
SECOND_OTADATA_MUTATION_REQUIRED=false
APP0_REWRITE_REQUIRED=false
OTADATA_REWRITE_REQUIRED=false
FIRMWARE_FAILURE_PROVEN=false
PRODUCT_RUNTIME_AFTER_POWER_CYCLE=PASS
N3W_RUNTIME=PASS
SCHEMA_V5_RUNTIME_STATE=PASS
```

No further Board B boot-recovery mutation is currently justified.

## ID11 consumed RF capture

```text
AUTHORIZATION_ID=N3W_KF089_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL_20260912_11
ID11_CLAIMED=true
BOARD_A_DIRECT_BASELINE=true
BOARD_A_DIRECT_DURING_WINDOW=true
BOARD_B_COLD_BOOT_EXECUTED=true
SELECTIVE_RF_ZONE_USED=true
RF_WINDOW_START=2026-09-12T01:11:08.309724329Z
RF_WINDOW_END=2026-09-12T01:12:38.355480750Z
RF_WINDOW_SECONDS=90
BOARD_B_DIRECT_INGRESS_COUNT=0
BOARD_B_RELAY_INGRESS_COUNT=0
BOARD_B_ACCEPTED_RELAY_COUNT=0
SECOND_RF_CAPTURE=false
```

The zero relay-ingress count is not sufficient to declare an N3-W data-path failure. Board B / Board A Schema-v5 counter readback stopped before execution because the host-side Board B identity validation/normalization failed.

```text
FIRST_EXECUTION_BLOCKER=BOARD_B_IDENTITY_VALIDATION_HOST_NORMALIZATION
BOARD_B_SCHEMA_READBACK=NOT_EXECUTED
BOARD_A_SCHEMA_READBACK=NOT_EXECUTED
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
```

The consumed RF capture must be preserved. Do not repeat the RF test merely to recover missing readback evidence.

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

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF089_ID11_BOARD_B_IDENTITY_HOST_NORMALIZATION_FORENSIC
BOARD_ACCESS=false
USB_ACCESS=false
SECOND_RF_CAPTURE=false
AUTO_RETRY=false
```

The host-only forensic must recover the exact Board B identity command stdout/stderr and exact parser/normalizer path used in ID11, determine why validation failed, and compare it with the already-reviewed ESP32-C6 `BASE MAC:` identity-contract repair without assuming the same root cause.

If host normalization alone is proven and the diagnostic snapshots remain preserved, the next successor may be a separately authorized **read-only** A/B diagnostic readback of the already-consumed ID11 session. It must not rerun the RF window or boot the applications before readback.

## N3W OTA Guard boundary

PR #385 remains open and unmerged.

```text
GUARD_PREMUTATION_AND_MUTATION_DATA_PATH=PASS
GUARD_IDENTITY_CONTRACT_REPAIR=PASS
GUARD_POSTMUTATION_FLASH_FINISH_HANDLING=REPAIR_REQUIRED
GUARD_FAILURE_STATE_RECONNECT_PATH=REVIEW_REQUIRED
N3W_OTA_GUARD_FULLY_READY=false
```

ID11 is a relay data-path real-board test and does not exercise the OTA Guard mutation path.

## Required guards

- USB port is a locator only, never board identity authority.
- Fresh ROM identity is required before any board write.
- No automatic mutation retry or rollback after an uncertain write boundary.
- Lab diagnostic NVS writes are distinct from product NVS mutation.
- Strict read-only gates must not create target-side state.
- Historical counters must be attributed to their boot session and captured test window.
- Public GitHub must not contain private board identities, credentials, raw private NVS, or private remote-host details.

## Route

```text
CURRENT=ID11_HOST_IDENTITY_NORMALIZATION_FORENSIC
NEXT=RECOVER_EXISTING_ID11_SCHEMA_V5_READBACK_IF_SAFE
THEN=ADJUDICATE_B_TO_A_TO_T1_DATA_PATH
SECOND_RF_CAPTURE=FORBIDDEN
```

No PR merge is authorized by this current-state refresh.