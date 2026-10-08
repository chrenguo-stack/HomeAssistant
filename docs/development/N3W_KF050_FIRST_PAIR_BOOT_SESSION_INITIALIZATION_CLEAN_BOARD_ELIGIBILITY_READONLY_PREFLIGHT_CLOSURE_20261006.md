# N3-W KF-050 First-Pair Boot-Session Initialization — Clean-Board Eligibility Read-Only Preflight Closure — 2026-10-06

```text
TASK=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261005_01
STATUS=CLOSED_PASS
CLEAN_BOARD_ELIGIBILITY=PASS
BOARD_ACCESS=true
BOARD_WRITE=false
FLASH_ERASE=false
FLASH_WRITE=false
NVS_WRITE=false
T1_MUTATION=false
MANAGER_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MERGE=false
```

## 1. Bound product artifact

```text
SOURCE_HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
SOURCE_TREE=f45ca257de0b6e41f0458346711bb4e105ba1fcc
WORKFLOW_RUN_ID=37249933019
ARTIFACT_ID=11320812037
ARTIFACT_NAME=n3w-kf050-first-pair-f1rc2-157448b-exact-source
RELEASE_ZIP_SHA256=44610382a0e7d9c04e4445e873b9d99fd9a781d18fd497f39cb382d3fce3b3ff
FIRMWARE_BIN_SHA256=4595edea29c93b3618435035bd87e3740f3c8afd0b663dc0b21ef65de343cd6b
```

## 2. Candidate-board read-only evidence

The candidate board was inspected before any erase or write. Public-safe evidence:

```text
CLEAN_BOARD_ELIGIBILITY_LOCAL=PASS
HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
HARDWARE_ID_UNIQUE_VS_BOARD_A_B=true
PARTITION_TABLE_STATE=BLANK
NVS_PARTITION_COUNT=0
OLD_N3W_STATE_ABSENT=true
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
```

The raw ROM MAC and private board evidence remain outside the public repository. The blank partition table is accepted by the frozen preexecution contract: a factory-new board is not required to already contain the production partition table.

## 3. Manager/T1 read-only history evidence

The running `greenhouse-manager` container was inspected without restart or mutation. The registration, credential lifecycle, and replay authorities were opened read-only. Lookup was performed by the public-safe hardware-id SHA-256 rather than publishing the raw hardware ID.

```text
MANAGER_HISTORY_READONLY=PASS
MANAGER_CONTAINER_RUNNING=true
REGISTRATION_HISTORY_TOTAL=0
PAIRING_SESSIONS_FOR_TARGET=0
REGISTRATION_EVENTS_FOR_TARGET=0
REGISTRATION_NODE_HISTORY_FOR_TARGET=0
NODE_ID_LEASES_FOR_TARGET=0
RETIREMENT_OUTBOX_FOR_TARGET=0
CREDENTIAL_HISTORY_COUNT=0
HISTORICAL_NODE_ID_COUNT=0
REPLAY_REGISTRY_TOTAL_ROWS=4
REPLAY_ROWS_FOR_HISTORICAL_TARGET_NODES=0
MANAGER_OLD_REGISTRATION_FOR_HARDWARE_ABSENT=true
MANAGER_OLD_CREDENTIAL_HISTORY_FOR_HARDWARE_ABSENT=true
MANAGER_OLD_REPLAY_BINDING_FOR_TARGET_ABSENT=true
MANAGER_MUTATION=false
MANAGER_REPLAY_MUTATION=false
```

The existing four replay rows belong to other historical nodes; none can be linked to this candidate because the candidate has no registration/credential history and therefore no historical node identity.

## 4. Executor verification

The clean-board read-only executor and Manager-history checker were source-tested before use.

```text
READONLY_PREFLIGHT_CI_RUN=37473577548
READONLY_PREFLIGHT_CI=PASS
ESPTOOL_MUTATION_SUBCOMMANDS_ABSENT=true
SQL_MUTATION_STATEMENTS_ABSENT=true
SQLITE_QUERY_ONLY=true
```

## 5. Closure decision

All Stage P1 predicates from the clean-board physical acceptance preexecution are satisfied.

```text
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
HARDWARE_ID_UNIQUE=true
HARDWARE_ID_NOT_BOARD_A=true
HARDWARE_ID_NOT_BOARD_B=true
OLD_N3W_PEER_STATE_ABSENT=true
OLD_N3W_BROKER_STATE_ABSENT=true
OLD_N3W_PENDING_PAIRING_STATE_ABSENT=true
OLD_N3W_BOOT_STATE_ABSENT=true
OLD_N3W_SETUP_OR_PAIRING_RESIDUE_ABSENT=true
MANAGER_OLD_REGISTRATION_FOR_HARDWARE_ABSENT=true
MANAGER_OLD_CREDENTIAL_HISTORY_FOR_HARDWARE_ABSENT=true
MANAGER_OLD_REPLAY_BINDING_FOR_TARGET_ABSENT=true
CLEAN_BOARD_ELIGIBILITY=PASS
```

No erase or write was used to manufacture a clean state. This board is therefore qualified as the clean-product physical acceptance candidate.

## 6. Next gate

No board write is authorized by this closure. The next gate prepares T1 as a healthy initial Broker address A before first pairing.

```text
NEXT_ONE_GATE=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_T1_HEALTHY_BROKER_A_PREPARATION_20261006_01
BOARD_WRITE=false
T1_MUTATION_REQUIRES_SEPARATE_AUTHORIZATION=true
MERGE=false
```
