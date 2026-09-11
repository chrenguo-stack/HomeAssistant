# N3W OTA Guard v0.2.1 R2 code + semantic review status — 2026-09-11

This note records the R2 review and repair of the GitHub-shared `N3W OTA Guard` candidate. It is a host-only/source-only review boundary; no board, USB, Flash, RF, T1, Broker, Manager, or Home Assistant access occurred.

```text
GATE=N3W_OTA_GUARD_R2_CODE_AND_SEMANTIC_REVIEW
TOOL_PATH=tools/n3w_ota_guard.py
TEST_PATH=tests/tools/test_n3w_ota_guard.py
TOOL_VERSION=0.2.1-review
TOOL_MODE=BOARD_B_RECOVERY_ONLY
PHYSICAL_USE_READY=false
BOARD_ACCESS=false
```

## R2 authoritative semantic checks

The review compared the candidate against ESP-IDF 5.5.4 OTA-selection semantics and esptool 5.2.0 ROM flash behavior.

Confirmed:

```text
OTA_ENTRY_SIZE=32
OTA_CRC_SCOPE=ota_seq_only
OTA_CRC_SEED=UINT32_MAX
ACTIVE_COPY_SELECTION=max_valid_ota_seq
SLOT_MAPPING=(ota_seq-1)%ota_app_count
TARGET_COPY=inactive_copy
OTADATA_ERASE_GRANULARITY=0x1000
TARGET_ENTRY_WRITE_SIZE=32
NON_TARGET_OTADATA_SECTOR_MUST_REMAIN_BYTE_IDENTICAL=true
```

The guard intentionally fails closed on equal valid `ota_seq` copies and on active/target states outside the bounded recovery contract instead of silently normalizing them.

## R2 blocker found and repaired

R2 found that esptool 5.2.0's high-level `cmds.write_flash` path has its own whole-operation reconnect/retry loop in addition to per-block retry behavior. Therefore setting `write_block_attempts=1` alone did **not** prove the project's no-mutation-retry contract.

Repair:

```text
STOCK_ESPTOOL_WRITE_FLASH_FOR_MUTATION=false
PROJECT_OWNED_DIRECT_ROM_MUTATION=true
DIRECT_CONNECT_ATTEMPTS=1
DIRECT_WRITE_BLOCK_ATTEMPTS=1
HIGH_LEVEL_WRITE_RECONNECT_RETRY_PATH_BYPASSED=true
HOST_RESET_REQUESTED=false
```

The recovery tool now uses stock esptool CLI only for read-only `read-mac` / exact `read-flash` operations. The persistent otadata mutation uses the reviewed low-level ESP32-C6 ROM API directly and never calls `esptool.cmds.write_flash`.

## Board B second-flash and bypass guard

R2 also removed all fresh-deploy/app0-write surfaces from this candidate. v0.2.1 is deliberately **Board-B-recovery-only**.

```text
FRESH_DEPLOY_CLI=false
APP0_WRITE_PRIMITIVE=false
APP0_WRITE_COMMAND_BUILDER=false
GENERIC_WRITE_FLASH_CLI=false
OTADATA_MUTATION_OFFSETS_ALLOWLIST=0x9000,0xA000
OTADATA_MUTATION_PAYLOAD_SIZE=32
```

Before any otadata mutation:

1. the existing app0 is read exactly from `0x10000`, length `1115648`;
2. the readback must match the frozen firmware SHA-256;
3. the mutation connection re-verifies the expected ROM BASE_MAC;
4. on the same mutation connection, the device-side MD5 of the same app0 range must equal the MD5 derived from the SHA-bound readback;
5. only then may `flash_begin` start the target otadata sector mutation.

The MD5 check is a same-connection freshness guard only; SHA-256 remains the firmware authority.

## Sequence arithmetic repair

The prior loop-shaped Python translation of the ESP-IDF `ota_seq` computation could be pathological near `UINT32_MAX`. R2 replaced it with O(1) closed-form arithmetic preserving the ESP-IDF result and failing closed before the erase marker / overflow boundary.

```text
OTA_SEQ_ALGORITHM=O1_IDF_EQUIVALENT
UINT32_NEAR_BOUNDARY_TESTED=true
ERASE_MARKER_REJECTED=true
```

## Toolchain binding hardening

Physical recovery now requires the guard itself to run under the exact Python interpreter supplied as the toolchain authority. esptool must not have been imported before the evidence-local retry configuration is bound.

The execution evidence records the loaded esptool package/module paths and SHA-256 values for:

```text
esptool.__init__
esptool.loader
esptool.cmds
esptool.targets.esp32c6
```

and verifies:

```text
ESPTOOL_VERSION=5.2.0
FLASH_SECTOR_SIZE=0x1000
FLASH_WRITE_SIZE=0x400
WRITE_BLOCK_ATTEMPTS=1
CHIP_NAME=ESP32-C6
```

The high-level write-attempt value is recorded as evidence but is not used by the mutation primitive.

## Evidence handling hardening

```text
DURABLE_EVIDENCE_REQUIRED=true
EVIDENCE_DIRECTORY_MUST_BE_EMPTY=true
EVIDENCE_DIRECTORY_INSIDE_GIT_WORKTREE=false
PRIVATE_FILE_MODE_BEST_EFFORT=0600
PRIVATE_DIRECTORY_MODE_BEST_EFFORT=0700
```

The mutation preclaim is written before `flash_begin` and records that identity, SHA authority, and same-connection app0 freshness all passed.

## Host regression

Local R2 host-side regression before GitHub push:

```text
PY_COMPILE=PASS
R2_TARGETED_TEST_COUNT=34
R2_TARGETED_TEST_RESULT=PASS
PHYSICAL_EXECUTION=false
```

GitHub CI remains authoritative for repository integration status after this commit lands on PR #385.

## Current disposition

```text
R2_SEMANTIC_DEFECTS_FOUND=true
R2_REPAIR_IMPLEMENTED=true
R2_LOCAL_HOST_REGRESSION=PASS
R2_GITHUB_CI=NOT_YET_RECORDED
R2_FINAL_RESULT=NOT_YET_FROZEN
PHYSICAL_USE_READY=false
NEXT_DECISION=WAIT_FOR_GITHUB_CI_AND_FINAL_R2_FREEZE
```

No physical successor authorization is granted by this document.
