# N3-W KF-089 Board B P0 Effective Pass and Physical Authorization Proposal — 2026-09-11

Status: `P0_EFFECTIVE_PASS_FROZEN_PHYSICAL_AUTHORIZATION_NOT_GRANTED`

This document combines the original local-host P0 closure with the single-point P0R1 remediation closure. It records the adjudication result and the exact proposed scope for a later one-time Board B physical authorization. It does not itself authorize physical access.

## 1. Fresh public authority rebind

```text
FRESH_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
OTA_GUARD_PR_385_STATE=OPEN
OTA_GUARD_PR_385_HEAD=7072a69939c9bef29e576d7e5f90800a3af7b867
REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
TEST_GIT_BLOB=5b4405b178384e2f3326c6ad0a3a963508d723e4
TOOL_VERSION=0.2.2-review
TOOL_MODE=BOARD_B_RECOVERY_ONLY
```

## 2. Original P0 result

Original local-host P0 stopped only at `LOCAL_GUARD_CHECK_TOOLCHAIN` because the Guard process was started by one Python interpreter while `--python` named a different interpreter. All other required host-only bindings reported PASS.

```text
REVIEWED_SOURCE_BLOB_BINDING=PASS
LOCAL_PYTHON_VERSION=3.11.9
LOCAL_PYTHON_BINDING=PASS
LOCAL_ESPTOOL_VERSION=5.2.0
LOCAL_ESPTOOL_RUNTIME_BINDING=PASS
LOCAL_ESP_IDF_WRAPPER_BINDING=PASS
LOCAL_GUARD_CHECK_TOOLCHAIN=FAIL

LOCAL_FIRMWARE_ARTIFACT_EXISTS=true
LOCAL_FIRMWARE_BIN_SIZE=1115648
LOCAL_FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
LOCAL_FIRMWARE_ARTIFACT_BINDING=PASS

PRIVATE_EVIDENCE_ROOT=PASS
EXPECTED_BOARD_B_IDENTITY_BOUND=true
EXPECTED_BOARD_B_IDENTITY_SOURCE=EXISTING_PRIVATE_TRUSTED_EVIDENCE

USB_ACCESS=false
SERIAL_OPEN=false
BOARD_ACCESS=false
FLASH_READ=false
FLASH_WRITE=false
OTADATA_WRITE=false
RF_EXECUTION=false
```

## 3. P0R1 bounded remediation result

The remediation changed no source, installed no package, rebuilt no firmware, and accessed no device. It used the exact already-proven interpreter both to launch Guard and as the explicit `--python` argument.

```text
GATE=HOST_ONLY_REMEDIATION
PHASE=P0R1_EXACT_PYTHON_INTERPRETER_BINDING

REVIEWED_SOURCE_BLOB_BINDING=PASS
LOCAL_PYTHON_VERSION=3.11.9
EXACT_PYTHON_SELF_BINDING=PASS
LOCAL_ESPTOOL_VERSION=5.2.0
LOCAL_ESPTOOL_RUNTIME_BINDING=PASS
LOCAL_ESP_IDF_WRAPPER_BINDING=PASS
LOCAL_GUARD_CHECK_TOOLCHAIN=PASS

FLASH_SECTOR_SIZE=4096
FLASH_WRITE_SIZE=1024
WRITE_BLOCK_ATTEMPTS=1

USB_ACCESS=false
SERIAL_OPEN=false
BOARD_ACCESS=false
FLASH_READ=false
FLASH_WRITE=false
OTADATA_WRITE=false
RF_EXECUTION=false

REMEDIATION_RESULT=PASS
FIRST_FAILED_STAGE=NONE
STOP_REASON=NONE
PHYSICAL_AUTHORIZATION_GRANTED=false
PHYSICAL_AUTHORIZATION_CONSUMED=false
```

## 4. Effective adjudication

The original P0 had exactly one failed stage. P0R1 directly remediated and re-proved that same stage without changing any previously frozen authority and without touching the physical target. No other P0 PASS criterion regressed.

Therefore:

```text
P0_EFFECTIVE_RESULT=PASS
P0_EFFECTIVE_PASS_BASIS=ORIGINAL_P0_PASS_FIELDS_PLUS_P0R1_EXACT_PYTHON_BINDING_PASS
SOURCE_AUTHORITY_DRIFT=false
TOOLCHAIN_AUTHORITY_DRIFT=false
FIRMWARE_AUTHORITY_DRIFT=false
EXPECTED_BOARD_B_IDENTITY_BOUND=true
PHYSICAL_DEVICE_ACCESS_DURING_P0_OR_P0R1=false

PHYSICAL_AUTHORIZATION_ELIGIBLE=true
PHYSICAL_AUTHORIZATION_GRANTED=false
PHYSICAL_AUTHORIZATION_CONSUMED=false
```

## 5. Proposed one-time Board B physical authorization

The following is a proposal only. It becomes active only after the operator explicitly grants this exact authorization in a later turn.

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01
AUTHORIZATION_STATUS=PROPOSED_NOT_GRANTED
REPLAY_PERMITTED=false
TARGET_ROLE=BOARD_B
TARGET_IDENTITY_AUTHORITY=PRIVATE_EXPECTED_IDENTITY_FROM_P0
USB_PORT_IS_LOCATOR_ONLY=true
FRESH_ROM_IDENTITY_REQUIRED=true
IDENTITY_MISMATCH_ACTION=STOP_BEFORE_ANY_FLASH_READ_OR_MUTATION

TOOL_MODE=BOARD_B_RECOVERY_ONLY
REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
ESPTOOL_VERSION=5.2.0
ESP_IDF_COMMIT=735507283d5b2f9fb363a1901172dbd9e847945d

FIRMWARE_BIN_SIZE=1115648
FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b

APP0_OFFSET=0x10000
APP0_READ_SIZE=1115648
APP0_WRITE_ALLOWED=false
SECOND_APP0_FLASH_ALLOWED=false

OTADATA_OFFSET=0x9000
OTADATA_READ_SIZE=0x2000
OTADATA_MUTATION_ALLOWED=ONLY_AFTER_IDENTITY_APP0_AND_PREIMAGE_GATES_PASS
OTADATA_MUTATION_COUNT_MAX=1
OTADATA_ENTRY_WRITE_SIZE=32
STOCK_ESPTOOL_WRITE_FLASH_FOR_MUTATION=false
MUTATION_RETRY=false
AUTO_ROLLBACK=false
AUTO_SECOND_ATTEMPT=false
```

### Authorized physical sequence after explicit grant

Only this sequence is eligible:

```text
P1_FRESH_ROM_IDENTITY
  -> compare fresh ROM BASE_MAC against private expected Board B identity
  -> mismatch: STOP

P2_EXISTING_APP0_EXACT_READBACK
  -> read 0x10000 + 1115648 bytes
  -> verify exact frozen SHA256
  -> mismatch/read failure: STOP; app0 write forbidden

P3_FULL_OTADATA_PRE_READ
  -> read 0x9000 + 0x2000
  -> parse/plan with Guard
  -> unsafe/ambiguous state: STOP

P4_SAME_CONNECTION_PREMUTATION_GATES
  -> recheck Board B ROM identity
  -> recheck app0 freshness
  -> recheck exact otadata preimage freshness
  -> any mismatch: STOP before flash_begin

P5_SINGLE_OTADATA_MUTATION
  -> exactly one project-owned direct ROM mutation
  -> one 32-byte OTA-select entry only
  -> no mutation retry

P6_FULL_OTADATA_POST_READ_AND_VERIFY
  -> read full 0x2000
  -> require non-target sector byte-identical
  -> require target sector exact erase + 32-byte planned entry semantics
  -> require selected slot=app0

P7_NORMAL_BOOT_AND_BOUNDED_SCHEMA_V5_OBSERVATION
  -> only after P6 PASS
```

If an error occurs after the mutation boundary may have been entered, the only allowed follow-up is the Guard's one bounded read-only failure-state capture. No automatic retry, rollback, second mutation, or normal boot is authorized.

## 6. Explicitly not authorized

```text
BOARD_A_ACCESS=false
BOARD_A_FLASH=false
BOARD_B_APP0_WRITE=false
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
NVS_WRITE=false
FULL_FLASH_WRITE=false
ERASE_FLASH=false
ERASE_REGION=false
T1_MUTATION=false
PAIRING_OR_KEY_CHANGE=false
RELAY_PROTOCOL_CHANGE=false
RETRY_POLICY_CHANGE=false
PR_MERGE=false
```

## 7. Next gate

```text
NEXT_ONE_GATE=OPERATOR_EXPLICIT_PHYSICAL_AUTHORIZATION
```

Until the operator explicitly grants `N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01`, physical authorization remains false and no Board B serial/Flash operation may begin.
