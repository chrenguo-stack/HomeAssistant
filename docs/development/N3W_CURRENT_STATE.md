# N3-W Current State

Updated: 2026-09-12  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/physical evidence takes precedence over older archives. The detailed local-chat/GitHub alignment is recorded under `docs/development/` on the active progress branch.

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

No further Board B boot-recovery mutation is currently justified.

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

The RF capture is consumed and must not be repeated merely to recover missing host evidence. Zero T1 relay ingress in the 90-second RF window does not localize the product failure because Board B / Board A Schema-v5 counters remain unread.

## ID11 historical readback evidence gap

The original post-RF Board B identity attempt did not preserve enough raw identity evidence for fact-level replay.

```text
ID11_IDENTITY_COMMAND_RECOVERED=false
ID11_IDENTITY_STDOUT_RECOVERED=false
ID11_IDENTITY_STDERR_RECOVERED=false
IDENTITY_FAILURE_CLASS=EVIDENCE_INCOMPLETE
POST_RF_APPLICATION_BOOT_OBSERVED=false
SECOND_RF_CAPTURE_REQUIRED=false
```

## ID12 fresh read-only recovery STOP

Host-only preparation for a fresh identity + NVS readback successor passed, then the user explicitly authorized:

```text
AUTHORIZATION_ID=N3W_KF089_ID11_AB_SCHEMA_V5_READONLY_RECOVERY_20260912_12
```

ID12 stopped before any board access because the exact esptool wrapper file was not executable when invoked directly as a host command.

```text
ID12_CLAIMED=true
BOARD_B_IDENTITY_PASS=NOT_EXECUTED
BOARD_B_NVS_READ_PASS=NOT_EXECUTED
BOARD_A_IDENTITY_PASS=NOT_EXECUTED
BOARD_A_NVS_READ_PASS=NOT_EXECUTED
FIRST_UNPROVEN_OR_FAILED_STAGE=BOARD_B_IDENTITY_COMMAND_START
RAW_EVIDENCE_PERSISTED=false
APPLICATION_BOOT=false
FLASH_WRITE=false
NVS_WRITE=false
AUTO_RETRY=false
RESULT=STOP
STOP_REASON=ESPTOOL_WRAPPER_NOT_EXECUTABLE_BEFORE_READ_MAC
```

This is a host invocation defect only. It is not Board B failure and does not change the ID11 RF evidence. ID12 is retired because it was claimed; it must not be replayed.

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF089_ID12_ESPT0OL_PYTHON_INVOCATION_HOST_REPAIR
REAL_BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
SECOND_RF_CAPTURE=false
NEW_PHYSICAL_AUTHORIZATION=false
```

The next host-only task must repair the fresh read-only successor so the exact bound esptool Python wrapper is invoked through the exact bound Python interpreter instead of relying on the wrapper executable bit. The repair must cover both `read-mac` and `read-flash`, persist raw identity/read evidence, contain no write/erase primitive, and pass tests with a deliberately non-executable wrapper fixture. Only after that host repair is durably shared and tested may one new bounded read-only authorization be proposed for Board B and Board A.

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
- Fresh ROM identity is required before board-specific readback/write attribution.
- No automatic mutation retry or rollback after an uncertain write boundary.
- Strict read-only gates must not write target flash/NVS/otadata.
- Historical counters must be attributed to their boot session and exact RF window.
- Public GitHub must not contain private board identities, credentials, raw private NVS, or private remote-host details.
- `esp_now_send(...) == ESP_OK` is submit evidence only, never delivery proof.

No PR merge is authorized by this current-state refresh.
