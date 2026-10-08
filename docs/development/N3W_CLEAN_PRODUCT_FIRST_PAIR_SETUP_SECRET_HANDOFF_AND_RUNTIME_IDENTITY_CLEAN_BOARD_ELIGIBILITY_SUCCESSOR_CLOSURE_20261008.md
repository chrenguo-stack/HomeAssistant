# N3-W Clean Product First-Pair / Runtime Identity
# P1 Current-Board Successor Clean-Board Eligibility Closure — 2026-10-08

```text
STATUS=CLOSED_PASS
EXECUTION_CLASS=ADJUDICATED_FROM_EXISTING_READONLY_EVIDENCE
NEW_BOARD_ACCESS=false
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
T1_MUTATION=false
MERGE=false
```

## 1. Why a successor P1 closure is required

The prior P1 R2 closure bound a different clean silicon:
`f9c00d136f84d1fdabb1e296608702539ed674271021b28cff2d4a23e4cd2bf7`.

During P3 preclaim the currently connected board produced:
`4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc`.

The mismatch proves only that the silicon is different. It does **not** prove
that the current board is used or dirty.

The operator explicitly states that the current board is brand new and unused.

## 2. Existing read-only evidence for the current board

No additional board command is needed for this adjudication. Existing P3
preclaim/classification evidence already established:

```text
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false

SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc

HISTORICAL_BOARD_A_MATCH=false
HISTORICAL_BOARD_B_MATCH=false
BLOCKED_P4_BOARD_MATCH=false
PRIOR_P1_R2_CANDIDATE_MATCH=false
SILICON_BINDING_UNIQUE=true

PARTITION_TABLE_STATE=BLANK
PARTITION_WINDOW_ALL_FF=true
PARTITION_COUNT=0
NVS_PARTITION_COUNT=0
OLD_N3W_STATE_ABSENT=true

PRODUCT_HARDWARE_ID_SHA256=DEFERRED
PRODUCT_IDENTITY_STATUS=DEFERRED_UNTIL_RUNTIME_QR_MANAGER_BINDING
```

The frozen P1 acceptance design explicitly defines an all-0xFF partition table
as BLANK. With no partition entries there is no defined NVS partition, and the
P1 oracle classifies old N3-W state as absent.

## 3. Artifact/source authority remains unchanged

```text
SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
ARTIFACT_ID=11469977052
BUILD_RUN_ID=37594598870
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
ARTIFACT_BINDING_PASS=true
```

The repository helper under
`clean_board_eligibility_readonly_preflight/executor.py` remains a stale
artifact-bound helper and is **not** the exact artifact authority. The formal P1
DSL plus replacement-artifact binding remains the authority.

## 4. Correction to the earlier P3 interpretation

```text
EARLIER_WRONG_BOARD_WORDING=SUPERSEDED
DIFFERENT_SILICON=true
CURRENT_BOARD_NEW_STATUS=OPERATOR_CONFIRMED_NEW
CURRENT_BOARD_CLEAN_ELIGIBILITY=PASS
```

P3 must bind to the latest successful P1 candidate authority, not permanently
to the first P1 R2 silicon digest.

## 5. Closure

```text
CLEAN_BOARD_ELIGIBILITY=PASS
CURRENT_CLEAN_CANDIDATE_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc

FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
PRODUCT_NORMAL_BOOT=false

READY_FOR_P2_REFREEZE=true
READY_FOR_P3=false
STOP=true
```

Because this successor P1 closure occurs after the earlier P2 snapshot, the P2
preboot runtime authority must be refreshed read-only before P3 mutation. No
Manager/Broker mutation is required or authorized by this closure.
