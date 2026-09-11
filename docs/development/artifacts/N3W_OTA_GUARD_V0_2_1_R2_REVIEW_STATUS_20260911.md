# N3W OTA Guard R2 code + semantic review freeze — 2026-09-11

This document freezes the R2 host/source review of the GitHub-shared `N3W OTA Guard` candidate. No board, USB, Flash, RF, T1, Broker, Manager, or Home Assistant access occurred during this gate.

```text
GATE=N3W_OTA_GUARD_R2_CODE_AND_SEMANTIC_REVIEW
R2_FINAL_RESULT=PASS

TOOL_PATH=tools/n3w_ota_guard.py
TEST_PATH=tests/tools/test_n3w_ota_guard.py
CI_WORKFLOW=.github/workflows/n3w-ota-guard-ci.yml

TOOL_VERSION=0.2.2-review
TOOL_MODE=BOARD_B_RECOVERY_ONLY
REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
TEST_GIT_BLOB=5b4405b178384e2f3326c6ad0a3a963508d723e4

PHYSICAL_USE_READY_FOR_SEPARATE_SUCCESSOR_AUTHORIZATION=true
PHYSICAL_USE_AUTHORIZED=false
BOARD_ACCESS=false
USB_ACCESS=false
FLASH_EXECUTED=false
RF_EXECUTION=false
```

`PHYSICAL_USE_READY_FOR_SEPARATE_SUCCESSOR_AUTHORIZATION=true` means only that the reviewed tool may now be used as the candidate for a separately designed and explicitly authorized physical successor gate. It does **not** grant board access or authorize a mutation.

## R2 semantic authority

The implementation was checked against ESP-IDF 5.5.4 OTA-selection behavior and esptool 5.2.0 ROM-flash semantics.

```text
OTA_ENTRY_SIZE=32
OTA_CRC_SCOPE=ota_seq_only
OTA_CRC_SEED=UINT32_MAX
ACTIVE_COPY_SELECTION=max_valid_ota_seq
SLOT_MAPPING=(ota_seq-1)%ota_app_count
TARGET_COPY=inactive_copy
OTADATA_ERASE_GRANULARITY=0x1000
ROM_FLASH_WRITE_BLOCK_SIZE=0x400
TARGET_ENTRY_WRITE_SIZE=32
NON_TARGET_OTADATA_SECTOR_MUST_REMAIN_BYTE_IDENTICAL=true
```

The guard intentionally fails closed on equal valid `ota_seq` copies, unsafe active/target OTA states, erase-marker/overflow sequence boundaries, unexpected target-sector bytes, or any unrecognized state rather than normalizing them.

## Board B scope and second-flash guard

v0.2.2 is deliberately **Board-B-recovery-only**.

```text
FRESH_DEPLOY_CLI=false
APP0_WRITE_PRIMITIVE=false
APP0_WRITE_COMMAND_BUILDER=false
GENERIC_WRITE_FLASH_CLI=false
STOCK_ESPTOOL_WRITE_FLASH_FOR_MUTATION=false
```

The recovery workflow has no app0 write path. It first reads existing app0 exactly from:

```text
APP0_OFFSET=0x10000
APP0_READBACK_LENGTH=1115648
EXPECTED_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
```

Mismatch means STOP. There is no second-flash fallback.

## Mutation primitive and retry contract

R2 proved that esptool 5.2.0's high-level `write_flash` path has retry/reconnect behavior that is too broad for this mutation contract. The candidate therefore bypasses it.

```text
PROJECT_OWNED_DIRECT_ROM_MUTATION=true
HIGH_LEVEL_WRITE_RECONNECT_RETRY_PATH_BYPASSED=true
DIRECT_CONNECT_ATTEMPTS=1
DIRECT_WRITE_BLOCK_ATTEMPTS=1
WORKFLOW_MUTATION_RETRY=false
HOST_RESET_REQUESTED=false
OTADATA_MUTATION_OFFSETS_ALLOWLIST=0x9000,0xA000
OTADATA_MUTATION_PAYLOAD_SIZE=32
```

The direct path performs one aligned ROM `flash_begin(32, target_copy_start)`, then one `0x400` flash block whose first 32 bytes are the planned OTA entry and whose remainder is `0xFF`, followed by `flash_finish(reboot=False)`.

## Pre-mutation freshness and identity

Before crossing the `flash_begin` mutation boundary the same direct ROM connection must prove all of the following:

1. fresh BASE_MAC equals the externally expected board identity;
2. the host app0 readback still matches the frozen SHA-256 authority;
3. device-side MD5 of `0x10000 + 1115648` equals the MD5 of that SHA-bound host readback;
4. device-side MD5 of the full `0x9000 + 0x2000` otadata region equals the exact pre-read snapshot used to build the plan;
5. the external physical authorization id is non-empty and is written into evidence.

```text
SAME_CONNECTION_IDENTITY_RECHECK=true
SAME_CONNECTION_APP0_MD5_FRESHNESS=true
SAME_CONNECTION_OTADATA_PREIMAGE_MD5_FRESHNESS=true
SHA256_REMAINS_FIRMWARE_AUTHORITY=true
AUTHORIZATION_ID_REQUIRED=true
AUTHORIZATION_REPLAY_ENFORCEMENT=EXTERNAL_GATE_REQUIRED
```

MD5 is freshness-only. It does not replace the frozen firmware SHA-256 authority.

## Failure-state evidence after mutation boundary

`flash_begin` itself may erase persistent flash. The guard therefore writes a durable phase marker immediately before entering it. If any exception occurs after that boundary, the tool does **not** retry mutation. It closes the direct connection and performs one bounded read-only full-otadata capture when possible.

The captured state is classified only as:

```text
PRECHANGE_EXACT
EXPECTED_POSTCHANGE_EXACT
PARTIAL_OR_OTHER_STATE
UNKNOWN
```

No classification causes an automatic repair or retry.

```text
MUTATION_BOUNDARY_PHASE_EVIDENCE=true
POST_FAILURE_READONLY_CAPTURE=true
POST_FAILURE_MUTATION_RETRY=false
```

## Toolchain binding

The exact ESP-IDF v5.5.4 wrapper SHA-256 is frozen:

```text
ESPTOOL_WRAPPER_SHA256=a8461ddc0852eb1d00cf9d13bfc7698a3cad92871e51f2c4d1ff7ee2561150be
ESPTOOL_VERSION=5.2.0
```

The reviewed ESP-IDF wrapper is a small delegate that launches `sys.executable -m esptool`; therefore runtime package files legitimately live in the bound Python environment rather than under the wrapper directory. v0.2.2 requires the exact supplied Python interpreter, exact wrapper hash, esptool version 5.2.0, one common runtime package root, and the reviewed runtime constants. It records SHA-256 values for `esptool.__init__`, `esptool.loader`, `esptool.cmds`, and `esptool.targets.esp32c6` in private execution evidence.

The retry configuration is bound before importing esptool, and a prior esptool import is rejected.

```text
FLASH_SECTOR_SIZE=0x1000
FLASH_WRITE_SIZE=0x400
WRITE_BLOCK_ATTEMPTS=1
CHIP_NAME=ESP32-C6
```

## OTA selection semantics

The host recovery contract deliberately preserves the target copy's `seq_label` and `ota_state`, mutating only:

```text
ota_seq
crc
```

The sequence arithmetic is an O(1) equivalent of the ESP-IDF two-slot selection loop and fails closed at the `UINT32_MAX` erase-marker/overflow boundary.

```text
OTA_SEQ_ALGORITHM=O1_IDF_EQUIVALENT
OTA_STATE_PRESERVED=true
SEQ_LABEL_PRESERVED=true
CRC_REGENERATED=true
```

Post-write verification reads the entire `0x2000` otadata partition and requires:

```text
NON_TARGET_SECTOR_BYTE_IDENTICAL=true
TARGET_SECTOR=PLANNED_32_BYTE_ENTRY_PLUS_FF_REMAINDER
EXPECTED_SLOT_SELECTED=true
EXPECTED_SEQ_VALID=true
EXPECTED_CRC_VALID=true
```

## Evidence handling

```text
DURABLE_EVIDENCE_REQUIRED=true
EVIDENCE_DIRECTORY_MUST_BE_EMPTY=true
EVIDENCE_DIRECTORY_INSIDE_GIT_WORKTREE=false
PRIVATE_FILE_MODE_BEST_EFFORT=0600
PRIVATE_DIRECTORY_MODE_BEST_EFFORT=0700
```

Evidence includes the workflow/authorization binding, toolchain/module hashes, ROM identity, app0 readback binding, pre/post otadata, plan, mutation phase transitions, and postcondition/failure-state capture.

## GitHub regression evidence

Reviewed implementation commit:

```text
HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
N3W_OTA_GUARD_CI_RUN=34586037986
N3W_OTA_GUARD_CI=PASS
PY_COMPILE_WITH_WARNINGS_AS_ERRORS=PASS
TARGETED_TEST_COUNT=45
TARGETED_TEST_RESULT=PASS
PUBLIC_REPOSITORY_SAFETY_RUN=34586037947
PUBLIC_REPOSITORY_SAFETY=PASS
ALL_OBSERVED_PR_WORKFLOWS_AT_REVIEWED_HEAD=PASS
```

The 45-test R2 suite covers OTA parsing/CRC/sequence boundaries, exact read argv, forbidden high-level writes, app0 second-flash absence, direct mutation geometry, single-attempt behavior, identity/app0/otadata freshness gates, authorization-id requirement, mutation-boundary evidence, failure-state capture, and the exact ESP-IDF wrapper hash.

## Frozen disposition

```text
R2_SEMANTIC_DEFECTS_FOUND=true
R2_REPAIR_IMPLEMENTED=true
R2_GITHUB_HOST_REGRESSION=PASS
R2_FINAL_RESULT=PASS

NEXT_ROUTE=DESIGN_SEPARATE_BOARD_B_PHYSICAL_SUCCESSOR_PRECLAIM_AND_AUTHORIZATION
AUTO_BOARD_ACCESS=false
AUTO_MUTATION=false
PR_MERGE_NOT_AUTHORIZED_BY_THIS_REVIEW=true
```

No physical successor authorization and no PR merge are granted by this document.
