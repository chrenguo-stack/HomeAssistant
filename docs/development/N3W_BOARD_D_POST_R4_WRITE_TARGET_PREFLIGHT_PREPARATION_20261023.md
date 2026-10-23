# N3-W Board_D post-R4 write-target preflight preparation — 2026-10-23

## Status

    TASK=N3W_BOARD_D_POST_R4_WRITE_TARGET_PREFLIGHT_PREPARATION_20261023_01
    BASE_MAIN=e24b5af4a271867c613dd52012bc83a6d40b06a5
    PR656_MERGED=true
    MERGE_TIME_SOURCE_DRIFT=false
    POSTMERGE_PUSH_CI=14_SUCCESS_2_KNOWN_STAGE2D_BOUNDARY_FALSE_FAIL
    POSTMERGE_NEW_VALID_FAILURE_COUNT=0
    R4_EXACT_PRODUCT_SOURCE_HEAD=ec5f6d68e33db7757d91c807fff708ca81b075dc
    R4_EXACT_PRODUCT_SOURCE_TREE=16740efa8ad24d423adc0b2de32b99d56e2d23d1
    R4_EXACT_ARTIFACT_RUN_ID=39901919230
    R4_EXACT_ARTIFACT_ID=12478974186
    R4_EXACT_ARTIFACT_NAME=n3w-board-d-r4-f1rc2-ec5f6d68-exact-source
    R4_GITHUB_ARTIFACT_SHA256=898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f
    R4_RELEASE_BUNDLE_SHA256=b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5
    R4_MANIFEST_SHA256=173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb
    ARTIFACT_EXPIRED=false
    ARTIFACT_EXPIRES_AT=2026-11-22T04:48:45Z
    BOARD_ACCESS=false
    SERIAL_OPEN=false
    FLASH_WRITE=false
    NVS_WRITE=false
    PERSISTENT_MUTATION=false
    RF_EXECUTION=false
    T1_ACCESS=false
    PREPARATION_RESULT=SOURCE_PREPARED_LOCAL_TEST_PASS
    PREPARATION_LOCAL_TEST=8_PASS
    WRITE_COMMAND_PRESENT=false
    RAW_FLASH_ARGS_DIRECT_EXECUTION_ALLOWED=false

## Purpose

This gate prepares the first Board D physical boundary after R1-R4 convergence and PR #656 merge. It does not access Board D and does not authorize a write.

The repository-owned executor has exactly one operation: preflight.

Board D has no frozen hardware-identity hash yet. The first live read-only preflight therefore observes the ROM identity, converts it to the public hardware-ID SHA256, and marks that identity as requiring operator confirmation that the physically connected target is Board D.

Raw ROM MAC is not emitted in the executor's public result.

## Frozen artifact binding

The preflight accepts the deterministic inner release bundle produced by R4 V2 and requires:

    RELEASE_BUNDLE=n3w-board-d-r4-f1rc2-ec5f6d68-exact-source.zip
    RELEASE_BUNDLE_SHA256=b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5
    MEMBER_COUNT=8
    MANIFEST_SHA256=173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb

It validates the exact member set, deterministic 1980 ZIP timestamps, stored compression, all member sizes and SHA256 values, and exact manifest content.

Frozen members:

    MANIFEST.txt
    bootloader.bin
    firmware.bin
    firmware.factory.bin
    firmware.ota.bin
    flash_args
    ota_data_initial.bin
    partitions.bin

## Read-only Board D checks

The future live preflight will:

1. require esptool major version 5;
2. verify firmware.bin and firmware.factory.bin are ESP32-C6 images;
3. query the connected target with ESP32-C6 ROM operations;
4. observe ROM MAC but publish only the derived hardware-ID SHA256;
5. require 8 MB Flash;
6. require Secure Boot disabled;
7. require Flash Encryption disabled;
8. read back the existing bootloader region and partition-table region;
9. compare those readbacks with the exact R4 release;
10. classify the next write route without performing it.

Classification:

    BOOTLOADER_MATCH=true AND PARTITION_TABLE_MATCH=true
    -> APP_PLUS_OTADATA_CANDIDATE

    otherwise
    -> FACTORY_OR_NORMALIZED_OFFSETS_REVIEW_REQUIRED

A mismatch is evidence for later write-route design. The preflight does not repair or write anything.

## Hard safety boundary

The executor intentionally contains no write subcommand and no write-flash or erase-flash operation.

Its output always records:

    FLASH_WRITE=false
    NVS_WRITE=false
    PERSISTENT_MUTATION=false
    WRITE_COMMAND_PRESENT=false
    WRITE_AUTHORIZATION_GRANTED=false
    RAW_FLASH_ARGS_DIRECT_EXECUTION_ALLOWED=false

The R4 bundle's raw flash_args remains forbidden for direct execution because its paths are build-tree-relative and do not match the flat release bundle.

Board reset may occur as part of ROM/esptool read-only access. No persistent Flash/NVS mutation is allowed.

## Next boundary after preflight PASS

A successful live preflight is not write authorization.

After the operator confirms that the observed target is physically Board D, the hardware-ID SHA256 must be frozen into a separate write gate. That write gate must also freeze the selected write mode from the preflight evidence and consume a separate explicit one-shot write authorization.

    AUTO_EXECUTE_WRITE=false
    NEW_WRITE_AUTHORIZATION_REQUIRED=true
    BOARD_D_IDENTITY_FREEZE_REQUIRED=true
    STOP_AFTER_LIVE_PREFLIGHT=true


## Source/preparation closure

```text
PREPARATION_EXECUTABLE_SOURCE_HEAD=6e4499155ee6b2c6d93d32697eb12ca627e7ab6d
PREPARATION_EXECUTOR_BLOB=ef4299c6aaffd3ca0a76a59ed250fa5bf2cf8444
PREPARATION_TEST_BLOB=eebf34baf032aab870f74b2305d4b37e6d91ffa0
PREPARATION_WORKFLOW_BLOB=97d4fc7bc982008e08527dd733dcdb49d607ce14

SOURCE_REVIEW_NO_WRITE_SUBCOMMAND=PASS
SOURCE_REVIEW_NO_WRITE_FLASH=PASS
SOURCE_REVIEW_NO_ERASE_FLASH=PASS
SOURCE_REVIEW_READ_ONLY_ROM_OPERATIONS=PASS
SOURCE_REVIEW_RAW_MAC_NOT_PERSISTED=PASS
SOURCE_REVIEW_IDENTITY_HASH_ONLY=PASS
SOURCE_REVIEW_ARTIFACT_BINDING=PASS
SOURCE_REVIEW_FAIL_CLOSED_CI=PASS

FINAL_HEAD_CI_TOTAL=12
FINAL_HEAD_CI_SUCCESS=12
FINAL_HEAD_CI_FAILURE=0
FINAL_HEAD_CI_UNFINISHED=0

PUBLIC_REPOSITORY_SAFETY=PASS
BOARD_D_PREFLIGHT_DEDICATED_CI=PASS
NEW_SOURCE_BLOCKER_COUNT=0
PREPARATION_SOURCE_CLOSURE=CLOSED_PASS

BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_MUTATION=false
RF_EXECUTION=false
T1_ACCESS=false

NEXT_ROUTE=PR657_MERGE_THEN_SEPARATE_BOARD_D_LIVE_READONLY_PREFLIGHT_AUTHORIZATION
AUTO_EXECUTE_LIVE_PREFLIGHT=false
```

The executable source authority remains `6e449915...`. Any later commit that only
advances this closure document does not redefine the executor authority.

The preparation gate is source-complete. It is safe to merge as a repository-owned
read-only preflight package. Merge does not authorize Board D access.

The first real Board D preflight remains a separate physical gate because the
target has no frozen Board D hardware identity yet. That live gate may observe the
ROM identity and read Flash regions, but it must stop after producing the preflight
evidence and operator identity confirmation. A later write gate requires a new
one-shot write authorization.
