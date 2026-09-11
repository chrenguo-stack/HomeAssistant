# N3-W KF-089 Board B Physical Successor Preclaim Design — 2026-09-11

Status: `DESIGN_FROZEN_HOST_GITHUB_ONLY`  
Scope: Board B physical successor preclaim design for the current KF-089 Schema-v5 recovery route.  
This document authorizes **no** board access, USB/serial open, Flash read/write, reset, RF execution, T1 mutation, Broker/Manager mutation, or PR merge.

## 1. Gate identity

```text
NORTH_STAR=N3W_KF089_END_TO_END_RELAY_TELEMETRY
CURRENT_ROUTE_NODE=BOARD_B_PHYSICAL_SUCCESSOR_PRECLAIM_DESIGN
NEXT_PHYSICAL_GATE=N3W_KF089_BOARD_B_PHYSICAL_SUCCESSOR_RECOVERY

DESIGN_STATUS=FROZEN
PRECLAIM_EXECUTION=NOT_STARTED
PHYSICAL_AUTHORIZATION_REQUIRED=true
PHYSICAL_AUTHORIZATION_GRANTED=false
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_READ=false
FLASH_WRITE=false
OTADATA_WRITE=false
RF_EXECUTION=false
```

The purpose of this gate is to freeze the exact authority, safety contract, stop conditions, private/public evidence boundary, and future physical execution order before any physical action occurs.

## 2. Fresh repository authority at design time

```text
REPOSITORY=chrenguo-stack/HomeAssistant
DESIGN_BASE_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
DESIGN_BASE_TREE=91d2e4767887dad86525cf521e476d4a1234551a
```

The reviewed recovery implementation currently lives in PR #385 and is not yet present on `main`.

```text
OTA_GUARD_PR=385
OTA_GUARD_PR_STATE_AT_DESIGN=OPEN
OTA_GUARD_PR_HEAD_AT_R2_FREEZE=7072a69939c9bef29e576d7e5f90800a3af7b867
REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
TOOL_PATH=tools/n3w_ota_guard.py
TEST_PATH=tests/tools/test_n3w_ota_guard.py
TOOL_VERSION=0.2.2-review
TOOL_MODE=BOARD_B_RECOVERY_ONLY
TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
TEST_GIT_BLOB=5b4405b178384e2f3326c6ad0a3a963508d723e4
R2_FINAL_RESULT=PASS
R2_TARGETED_TEST_COUNT=45
R2_TARGETED_TEST_RESULT=PASS
```

### Physical source-authority rule

Physical execution must not begin from an ambiguous worktree or an unbound copy of the helper.

Preferred authority before the physical gate:

```text
PREFERRED_TOOL_AUTHORITY=MERGED_MAIN_EXACT_BLOB
```

The physical preclaim must freshly prove that the execution source is either:

1. a `main` descendant containing the exact reviewed tool blob and test blob above; or
2. the exact reviewed implementation commit `b8eb0aec...` / PR #385 source, explicitly pinned by commit and blob hashes.

Any source delta to `tools/n3w_ota_guard.py` after the reviewed blob requires a new host/source review before physical use.

```text
UNREVIEWED_TOOL_SOURCE_ALLOWED=false
SILENT_TOOL_SOURCE_DRIFT_ALLOWED=false
```

PR #385 merge is **not** authorized by this document.

## 3. Frozen product and firmware authority

The product/diagnostic authority remains:

```text
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
```

The Schema-v5 app image authority is:

```text
APP0_OFFSET=0x10000
APP0_PARTITION_SIZE=0x3C0000
APP0_READBACK_LENGTH=1115648
EXPECTED_APP0_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
CURRENT_EXPECTED_ACTIVE_SLOT=app1
TARGET_SLOT=app0
ROLLBACK_SLOT=app1
```

The recovery-only successor requires no local firmware binary for writing because **no app0 write path exists**. The existing device app0 must itself read back to the exact frozen size and SHA-256 above.

```text
APP0_WRITE_ALLOWED=false
SECOND_APP0_FLASH_ALLOWED=false
FRESH_DEPLOYMENT_ALLOWED=false
```

Mismatch is a hard STOP and does not authorize repair/reflash.

## 4. Frozen flash layout and mutation scope

```text
OTADATA_OFFSET=0x9000
OTADATA_SIZE=0x2000
OTADATA_COPY0_OFFSET=0x9000
OTADATA_COPY1_OFFSET=0xA000
OTADATA_SECTOR_SIZE=0x1000
OTA_ENTRY_SIZE=32

APP1_OFFSET=0x3D0000
APP1_SIZE=0x3C0000
NVS_OFFSET=0x790000
NVS_SIZE=0x70000
```

The future physical successor may mutate only one OTA-select entry at `0x9000` or `0xA000`, as planned from the fresh prechange otadata snapshot.

```text
BOOTLOADER_MUTATION=false
PARTITION_TABLE_MUTATION=false
APP0_MUTATION=false
APP1_MUTATION=false
NVS_MUTATION=false
FULL_OTADATA_ERASE=false
FULL_OTADATA_REPLACEMENT=false
GENERIC_WRITE_FLASH=false
MUTATION_PAYLOAD_SIZE=32
```

The already-frozen physical partition layout is reused only after fresh Board B identity binding. Any evidence of a different board/layout is a STOP condition; this design does not generalize the helper to arbitrary devices.

## 5. Private Board B identity authority

USB device path is a locator only and is never identity authority.

```text
USB_PORT_IS_LOCATOR_ONLY=true
FRESH_ROM_SILICON_IDENTITY_REQUIRED=true
PRIVATE_EXPECTED_BOARD_B_IDENTITY_REQUIRED=true
IDENTITY_MISMATCH_ACTION=STOP_BEFORE_MUTATION
```

The exact expected Board B BASE_MAC or other private silicon identity must be supplied from the private execution authority at run time. It must **not** be committed to the public repository.

Public GitHub authority records only the rule and PASS/FAIL result, never the raw private identity value.

## 6. Host-only preclaim requirements before physical authorization

Before requesting/claiming the physical successor authorization, a host-only preclaim must freshly establish:

```text
FRESH_MAIN_REBIND=PASS
PR385_REBIND=PASS
TOOL_SOURCE_BINDING=PASS
TOOL_BLOB_BINDING=PASS
TEST_BLOB_BINDING=PASS
R2_FREEZE_BINDING=PASS

PYTHON_INTERPRETER_BINDING=PASS
ESP_IDF_VERSION=5.5.4
ESPTOOL_VERSION=5.2.0
ESPTOOL_WRAPPER_SHA256=a8461ddc0852eb1d00cf9d13bfc7698a3cad92871e51f2c4d1ff7ee2561150be
OTA_GUARD_CHECK_TOOLCHAIN=PASS

BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_READ=false
FLASH_WRITE=false
```

`check-toolchain` evidence must use a new empty private directory outside every Git worktree. No package install, upgrade, repair, or alternate esptool version is permitted during this preclaim.

If exact toolchain binding cannot be proven, STOP. Do not install/upgrade packages as an implicit repair.

## 7. Proposed one-time physical authorization

This document defines a proposed identifier but does not grant it:

```text
PROPOSED_AUTHORIZATION_ID=N3W_KF089_BOARD_B_PHYSICAL_SUCCESSOR_RECOVERY_20260911_01
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
```

A future user message must explicitly authorize the physical gate. Authorization must be claimed/consumed only immediately before the first physical access covered by that authorization.

The authorization scope should be limited to:

```text
TARGET=BOARD_B_ONLY
FRESH_ROM_IDENTITY_READ=true
APP0_EXACT_READBACK=true
OTADATA_PRE_READ=true
ONE_OTA_SELECT_MUTATION=true
OTADATA_POST_READBACK=true
ONE_NORMAL_BOOT_AFTER_VERIFIED_PASS=true
BOUNDED_SCHEMA_V5_RUNTIME_OBSERVATION=true

APP0_WRITE=false
APP1_WRITE=false
NVS_WRITE=false
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
MUTATION_RETRY=false
SECOND_FLASH=false
BOARD_A_ACCESS=false
T1_MUTATION=false
```

## 8. Future physical execution order

The execution order is intentionally linear and fail-closed.

### P0 — operator physical-state declaration

The operator identifies the intended physical Board B and presents it for the authorized operation. Historical USB port names are not accepted as identity.

```text
OPERATOR_TARGET_CONFIRMATION_REQUIRED=true
```

### P1 — fresh ROM silicon identity

Perform the Guard's exact read-only identity operation and compare against the private expected Board B identity.

```text
IDENTITY_MATCH=PASS -> continue
IDENTITY_MATCH=FAIL -> STOP
IDENTITY_MATCH=UNKNOWN -> STOP
```

No mutation may occur before this passes.

### P2 — existing app0 exact readback

Read exactly:

```text
OFFSET=0x10000
LENGTH=1115648
```

Then verify:

```text
SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
```

Decision:

```text
MATCH -> accept the original app0 write and continue
MISMATCH -> STOP; NO SECOND FLASH
READ_FAILURE -> STOP; NO SECOND FLASH
```

This is the mandatory recovery of the previously unproven app0 content state.

### P3 — full prechange otadata read and plan

Read exactly `0x9000 + 0x2000`, parse both copies, and require the Guard's bounded recovery contract to pass.

Expected normal precondition:

```text
SELECTED_SLOT=app1
TARGET_SLOT=app0
```

Fail closed on:

```text
APP0_ALREADY_SELECTED
NO_VALID_OTA_COPY
EQUAL_VALID_OTA_SEQ
UNSUPPORTED_OR_UNKNOWN_OTA_STATE
UNSAFE_ACTIVE_OTA_STATE
UNSAFE_TARGET_PRESERVE_STATE
SEQUENCE_OVERFLOW_OR_ERASE_MARKER
```

If app0 is already selected, STOP and adjudicate the fresh state; do not rewrite otadata merely to reproduce the expected route.

### P4 — same-connection pre-mutation freshness gate

Immediately before `flash_begin`, the same direct ROM connection must re-prove:

```text
BASE_MAC_MATCH=true
APP0_HOST_SHA256_AUTHORITY=true
APP0_DEVICE_MD5_EQUALS_SHA_BOUND_READBACK_MD5=true
OTADATA_DEVICE_MD5_EQUALS_EXACT_PREIMAGE_MD5=true
AUTHORIZATION_ID_BOUND=true
```

Any mismatch => STOP before `flash_begin`.

### P5 — exactly one controlled otadata mutation

Allowed persistent mutation:

```text
DIRECT_ROM_MUTATION=true
STOCK_ESPTOOL_WRITE_FLASH_USED=false
CONNECT_ATTEMPTS=1
WRITE_BLOCK_ATTEMPTS=1
WORKFLOW_MUTATION_RETRY=false
TARGET_OFFSET=planned 0x9000 or 0xA000 only
ENTRY_SIZE=32
HOST_RESET_REQUESTED=false
```

The Guard records the mutation boundary before entering `flash_begin` because erase may begin inside that call.

### P6 — failure handling after mutation boundary

If an exception occurs after the mutation boundary:

```text
MUTATION_RETRY=false
AUTO_ROLLBACK=false
AUTO_BOOT=false
```

Attempt one bounded read-only full-otadata failure-state capture. Classification is limited to:

```text
PRECHANGE_EXACT
EXPECTED_POSTCHANGE_EXACT
PARTIAL_OR_OTHER_STATE
UNKNOWN
```

None of these states authorizes an automatic second mutation.

### P7 — mandatory full postwrite verification

On apparent mutation success, read full `0x2000` otadata and require:

```text
NON_TARGET_SECTOR_BYTE_IDENTICAL=true
TARGET_SECTOR_EQUALS_PLANNED_ENTRY_PLUS_FF_REMAINDER=true
SELECTED_SLOT=app0
ACTIVE_COPY=planned_target_copy
OTA_SEQ=planned_new_seq
CRC_VALID=true
OTA_STATE_PRESERVED=true
SEQ_LABEL_PRESERVED=true
```

Any failure => STOP; no retry and no automatic boot.

### P8 — one normal boot only after verified PASS

Only after P7 passes may one explicitly authorized normal boot/reset/power-cycle be performed.

```text
NORMAL_BOOT_ALLOWED_AFTER_P7_PASS=true
NORMAL_BOOT_ALLOWED_BEFORE_P7_PASS=false
ROLLBACK_SLOT_APP1_UNTOUCHED=true
```

The boot step is not performed by `N3W OTA Guard`; it is an operator/executor step covered only by the future physical authorization.

### P9 — bounded Schema-v5 runtime observation

After normal boot, collect only enough evidence to answer the existing KF-089 localization question. The next diagnostic objective remains:

```text
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

Priority evidence from Board B is the Schema-v5 unicast completion counters. Do not broaden this gate into protocol redesign, retry-policy change, key/pairing redesign, or T1 mutation.

## 9. Stop conditions

Any of the following is a hard STOP:

```text
SOURCE_AUTHORITY_MISMATCH
TOOL_BLOB_MISMATCH
UNREVIEWED_TOOL_DELTA
TOOLCHAIN_BINDING_FAILURE
UNEXPECTED_ESPTOOL_VERSION
BOARD_IDENTITY_MISMATCH
APP0_SIZE_MISMATCH
APP0_SHA256_MISMATCH
OTADATA_PREIMAGE_FRESHNESS_MISMATCH
OTADATA_PARSE_OR_STATE_UNSUPPORTED
APP0_ALREADY_SELECTED_WITHOUT_ADJUDICATION
MUTATION_EXCEPTION
POSTWRITE_VERIFY_FAILURE
UNEXPECTED_RESET
UNEXPECTED_SECOND_CONNECTION_OR_RETRY
```

STOP means no implicit repair, no second Flash, no retry, no alternate tool, and no expansion to Board A or T1.

## 10. Evidence and privacy boundary

Private execution evidence may contain USB locator, full BASE_MAC, raw app0 readback, raw otadata images, local paths, exact toolchain paths, and raw serial/tool output. It must remain outside the Git worktree.

Public GitHub closure may record only sanitized facts such as:

```text
AUTHORIZATION_ID
SOURCE/TOOL/TEST COMMIT OR BLOB HASHES
TOOLCHAIN PASS/FAIL
BOARD_IDENTITY_BINDING=PASS/FAIL
APP0_READBACK_SIZE
APP0_READBACK_SHA256
PRECHANGE_SELECTED_SLOT
OTADATA_PLAN SUMMARY
MUTATION RESULT
POSTWRITE_SELECTED_SLOT
SCHEMA_V5 COUNTERS / SANITIZED DIAGNOSTIC COUNTS
STOP_REASON
```

Do not commit raw MACs, raw node IDs, Setup Secrets, application/system keys, MQTT credentials, private T1 addresses, raw NVS, local absolute user paths, or private raw logs.

## 11. Physical successor closure schema

A future executor must return at least:

```text
=== N3W KF089 BOARD B PHYSICAL SUCCESSOR RECOVERY CLOSURE ===

GATE=N3W_KF089_BOARD_B_PHYSICAL_SUCCESSOR_RECOVERY
AUTHORIZATION_ID=
AUTHORIZATION_GRANTED=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=
REPLAY_PERMITTED=false

FRESH_MAIN=
EXECUTION_SOURCE_COMMIT=
TOOL_GIT_BLOB=
TEST_GIT_BLOB=
TOOL_SOURCE_BINDING=
TOOLCHAIN_BINDING=

BOARD_TARGET=BOARD_B
FRESH_ROM_IDENTITY_BINDING=

APP0_READBACK_SIZE=
APP0_READBACK_SHA256=
APP0_EXISTING_BINDING=
SECOND_APP0_FLASH_EXECUTED=false

PRECHANGE_OTADATA_READ=
PRECHANGE_SELECTED_SLOT=
OTADATA_PLAN_VALID=
SAME_CONNECTION_APP0_FRESHNESS=
SAME_CONNECTION_OTADATA_PREIMAGE_FRESHNESS=

OTADATA_MUTATION_ATTEMPTED=
OTADATA_MUTATION_ATTEMPT_COUNT=
MUTATION_RETRY_EXECUTED=false

POSTWRITE_OTADATA_READ=
POSTWRITE_VERIFY=
POSTWRITE_SELECTED_SLOT=
NON_TARGET_OTADATA_SECTOR_BYTE_IDENTICAL=

FAILURE_STATE_CAPTURE=
FAILURE_STATE_CLASSIFICATION=

NORMAL_BOOT_EXECUTED=
SCHEMA_V5_RUNTIME_OBSERVATION=

APP0_MUTATION=false
APP1_MUTATION=false
NVS_MUTATION=false
BOOTLOADER_MUTATION=false
PARTITION_TABLE_MUTATION=false
BOARD_A_ACCESS=false
T1_MUTATION=false

FIRST_FAILED_STAGE=
STOP_REASON=
RESULT=

=== END ===
```

## 12. Current disposition

```text
BOARD_B_PHYSICAL_SUCCESSOR_PRECLAIM_DESIGN=PASS
GITHUB_DESIGN_FREEZE=PASS
PRECLAIM_EXECUTION=NOT_STARTED
PHYSICAL_AUTHORIZATION_GRANTED=false
PHYSICAL_EXECUTION=false

NEXT_ONE_GATE=HOST_ONLY_PHYSICAL_SUCCESSOR_PRECLAIM_EXECUTION
```

The next gate is still host-only. It must freshly bind repository/tool/toolchain authority and return a preclaim closure before any request to touch Board B is made.