# N3-W Current State

Updated: 2026-09-12  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/physical evidence takes precedence over older archives.

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
PR388_STATE=OPEN_UNMERGED_PROCESS_CANDIDATE
```

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

No further Board B boot-recovery mutation is justified by current evidence.

## ID11 consumed RF capture

```text
AUTHORIZATION_ID=N3W_KF089_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL_20260912_11
ID11_CLAIMED=true
RF_WINDOW_COMPLETED=true
SECOND_RF_CAPTURE=false
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
```

The RF capture is consumed and must not be repeated merely to recover missing host evidence. Zero T1 relay ingress does not localize the product failure because Board B / Board A Schema-v5 counters remain unread.

## ID11 historical evidence gap

```text
ID11_IDENTITY_COMMAND_RECOVERED=false
ID11_IDENTITY_STDOUT_RECOVERED=false
ID11_IDENTITY_STDERR_RECOVERED=false
ID11_VALIDATION_SOURCE_RECOVERED=false
IDENTITY_FAILURE_CLASS=EVIDENCE_INCOMPLETE
POST_RF_APPLICATION_BOOT_OBSERVED=false
SECOND_RF_CAPTURE_REQUIRED=false
```

The historical identity-normalization root cause is not proven and must not be reconstructed from summary text alone.

## ID12 read-only recovery STOP

User authorized:

```text
AUTHORIZATION_ID=N3W_KF089_ID11_AB_SCHEMA_V5_READONLY_RECOVERY_20260912_12
ID12_CLAIMED=true
REPLAY_PERMITTED=false
```

Observed closure:

```text
BOARD_B_IDENTITY_PASS=NOT_EXECUTED
BOARD_B_NVS_READ_PASS=NOT_EXECUTED
BOARD_A_IDENTITY_PASS=NOT_EXECUTED
BOARD_A_NVS_READ_PASS=NOT_EXECUTED
FIRST_UNPROVEN_OR_FAILED_STAGE=BOARD_B_IDENTITY_COMMAND_START
RAW_EVIDENCE_PERSISTED=false
SECOND_RF_CAPTURE=false
APPLICATION_BOOT=false
FLASH_WRITE=false
NVS_WRITE=false
AUTO_RETRY=false
RESULT=STOP
STOP_REASON=esptool wrapper had no executable permission; command failed before read-mac; Board B was not accessed
```

Evidence classification:

```text
OBSERVED_BOARD_ACCESS=false
OBSERVED_READ_MAC_EXECUTED=false
OBSERVED_RAW_EVIDENCE_PERSISTED=false
OBSERVED_WRAPPER_EXECUTION_PERMISSION_ERROR=true

WRAPPER_IS_PYTHON_SCRIPT=NOT_PROVEN
DIRECT_WRAPPER_EXECUTION_USED=NOT_PROVEN
MISSING_EXECUTABLE_BIT_IS_ROOT_CAUSE=NOT_PROVEN
CORRECT_FIX_IS_PYTHON_PLUS_WRAPPER=NOT_PROVEN
```

Therefore ID12 proves a host-side pre-board execution failure, not a product or board failure. ID12 is consumed and must not be replayed.

## Execution-model transition

PR #388 is an open, unmerged process candidate that replaces ad-hoc DSL command compilation with versioned Execution Packages.

```text
HANDOFF_STANDARD_CANDIDATE_VERSION=1.1
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODEX_ROLE=EXACT_EXECUTOR
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
```

User direction at the end of this conversation is stricter than the current PR #388 candidate wording: future code should be authored by the high-level model and committed to GitHub; Codex should only execute exact committed code and return evidence/results. The next chat must formalize this stricter role split and the repository storage layout before the next physical gate.

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF089_EXECUTION_PACKAGE_ROLE_AND_STORAGE_FREEZE
REAL_BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
RF_EXECUTION=false
NEW_PHYSICAL_AUTHORIZATION=false
```

The next gate is host-only. It must freeze the new collaboration rule and package storage convention, update the process candidate if needed, then materialize the next read-only recovery Execution Package before requesting any new physical authorization.

## N3W OTA Guard boundary

```text
PR385_STATE=OPEN_UNMERGED
GUARD_PREMUTATION_AND_MUTATION_DATA_PATH=PASS
GUARD_IDENTITY_CONTRACT_REPAIR=PASS
GUARD_POSTMUTATION_FLASH_FINISH_HANDLING=REPAIR_REQUIRED
GUARD_FAILURE_STATE_RECONNECT_PATH=REVIEW_REQUIRED
N3W_OTA_GUARD_FULLY_READY=false
```

ID11/ID12 are N3-W relay-data-path evidence-recovery work and do not exercise the OTA Guard mutation path.

## Required guards

- USB port is a locator only, never board identity authority.
- No automatic RF retry; ID11 RF capture is consumed.
- ID12 is consumed and cannot be replayed.
- Strict read-only gates must not write target Flash/NVS/otadata.
- Public GitHub must not contain private board identities, credentials, raw private NVS, or private remote-host details.
- `esp_now_send(...) == ESP_OK` is submit evidence only, never delivery proof.
- Do not convert a plausible host-tool explanation into a proven root cause without raw evidence or exact source.
- No PR merge is authorized by this current-state refresh.
