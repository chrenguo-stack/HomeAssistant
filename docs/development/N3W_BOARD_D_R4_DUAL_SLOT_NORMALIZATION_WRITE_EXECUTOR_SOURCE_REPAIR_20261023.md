# N3-W Board D R4 dual-slot normalization write executor source repair — 2026-10-23

## Status

```text
TASK=N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_WRITE_EXECUTOR_SOURCE_REPAIR_20261023_01
PARENT_DESIGN_PR=659
PARENT_DESIGN_HEAD=d72fb5cadbc03ab6eb327794bf7d72290842a3d0
TARGET_PR=660

BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_MUTATION=false
WRITE_AUTHORIZATION_GRANTED=false
MERGE=false

SOURCE_REPAIR_IMPLEMENTED=true
FOCUSED_TEST_COUNT=20
CI_STATE=12_OF_12_SUCCESS
```

This gate repairs PR #660 against the dual-slot padded normalization design. It
does not access Board D and does not execute the live write path.

## 1. Superseded executor removed from the candidate tree

The old source path is intentionally absent from the repaired PR candidate:

```text
OLD_EXECUTOR=tools/execution_packages/n3w/board_d/r4_normalized_offsets_write/executor.py
OLD_TESTS=tests/execution_packages/n3w/board_d/r4_normalized_offsets_write/test_executor.py
OLD_WORKFLOW=.github/workflows/n3w-board-d-r4-normalized-offsets-write-executor-ci.yml

OLD_APP0_ONLY_ROUTE_PRESENT=false
```

The repaired candidate uses:

```text
EXECUTOR=tools/execution_packages/n3w/board_d/r4_dual_slot_normalization_write/executor.py
TESTS=tests/execution_packages/n3w/board_d/r4_dual_slot_normalization_write/test_executor.py
WORKFLOW=.github/workflows/n3w-board-d-r4-dual-slot-normalization-write-executor-ci.yml
```

## 2. Frozen artifact and Board D identity

```text
BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

R4_PRODUCT_SOURCE=ec5f6d68e33db7757d91c807fff708ca81b075dc
R4_PRODUCT_TREE=16740efa8ad24d423adc0b2de32b99d56e2d23d1

ARTIFACT_RUN_ID=39901919230
ARTIFACT_ID=12478974186
GITHUB_ARTIFACT_SHA256=898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f
RELEASE_BUNDLE_SHA256=b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5
MANIFEST_SHA256=173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb
```

## 3. Independent exact-byte derivation

The repair independently re-read artifact 12478974186 and confirmed:

```text
R4_APPLICATION_SIZE=1413616
R4_APPLICATION_SIZE_HEX=0x1591F0
R4_APPLICATION_SHA256=ea50b147b7cb76bf442c0bbc7fe8d54e4abff87fa48926b9160ca903b6fa5c08

OTADATA_SIZE=8192
OTADATA_ALL_FF=true
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

OTA_SLOT_SIZE=3932160
OTA_SLOT_SIZE_HEX=0x3C0000
NORMALIZATION_TAIL_SIZE=2518544
NORMALIZATION_TAIL_SIZE_HEX=0x266E10
NORMALIZATION_TAIL_SHA256=50b46211550f22ac7f9bcb795c7a784f2a14f96de618032f600e722f0418b12e

NORMALIZED_SLOT_SHA256=539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195
```

The executor re-derives this temporary normalized slot from the already validated
exact R4 application and refuses to continue if the size or SHA256 differs.

## 4. Repaired selected route

```text
SELECTED_WRITE_ROUTE=DUAL_SLOT_PADDED_NORMALIZATION_BOOTLOADER_OTADATA

WRITE_BOOTLOADER=0x000000:bootloader.bin
WRITE_OTADATA=0x009000:ota_data_initial.bin
WRITE_APP0=0x010000:normalized_slot.bin
WRITE_APP1=0x3D0000:normalized_slot.bin

PARTITION_TABLE_WRITE=false
PHY_INIT_WRITE=false
NVS_WRITE=false
FACTORY_IMAGE_DIRECT_WRITE=false
RAW_FLASH_ARGS_DIRECT_EXECUTION=false
FULL_FLASH_ERASE=false
ERASE_REGION_COMMAND_USED=false
```

The write command uses the same complete 0x3C0000 normalized-slot file for both
app0 and app1.

## 5. Header-preserving write command

The executor binds the build artifact's original flash contract from
`flash_args`, but the live command does not ask esptool to rewrite boot image
header fields:

```text
--before no-reset
--after no-reset

write-flash
--flash-mode keep
--flash-freq keep
--flash-size keep
```

This keeps the exact bound bootloader bytes as the write authority.

## 6. Erase-boundary fail-closed proof

The executor validates the partition relationships and then calculates
0x1000-sector-rounded erase ranges before a write authorization may be claimed.

Expected ranges:

```text
bootloader  0x000000..0x006000
otadata     0x009000..0x00B000
app0        0x010000..0x3D0000
app1        0x3D0000..0x790000
```

Protected ranges remain:

```text
partition table  0x008000..0x009000
phy_init         0x00B000..0x00C000
NVS              0x790000..0x800000
```

Any overlap stops before the one-shot claim.

## 7. Fresh preclaim contract

Before a later live write claim, the executor must freshly verify:

1. exact release bundle and exact member set/hashes;
2. erased OTA-data semantics;
3. deterministic normalized-slot SHA256;
4. esptool major version 5;
5. ESP32-C6;
6. 8 MB physical flash;
7. Secure Boot disabled;
8. Flash Encryption disabled;
9. frozen Board D identity;
10. exact R4 partition table;
11. current full phy_init SHA256;
12. current full NVS SHA256;
13. exact erase-range binding.

The preflight file freezes the selected route, normalized-slot binding and erase
ranges. A later write rejects any drift.

## 8. One-shot and manual-reset boundary

```text
WRITE_CONFIRMATION=N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_WRITE_AUTHORIZED

MANUAL_RESET_ALLOWED_BEFORE_WRITE_CLAIM=true
MANUAL_RESET_ALLOWED_AFTER_WRITE_CLAIM=false

AUTHORIZATION_CLAIMED_BEFORE_WRITE=true
AUTHORIZATION_CONSUMED_ON_CLAIM=true
REPLAY_PERMITTED=false
```

The live confirmation label is only an executor guard. This source-repair gate
does not grant the later real Board D authorization.

## 9. Post-write integrity proof

The repaired executor requires readback of:

```text
bootloader exact-size SHA256
partition table exact-size SHA256
OTA-data exact-size SHA256
app0 complete 0x3C0000 SHA256
app1 complete 0x3C0000 SHA256
phy_init complete region SHA256
NVS complete region SHA256
Board D ROM identity
```

Acceptance requires:

```text
APP0_FULL_SLOT_SHA256=539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195
APP1_FULL_SLOT_SHA256=539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195

APP0_TAIL_ERASED=true
APP1_TAIL_ERASED=true
OLD_APPLICATION_CODE_REMAINS=false

PHY_INIT_SHA256_POSTWRITE=PHY_INIT_SHA256_PREWRITE
NVS_SHA256_POSTWRITE=NVS_SHA256_PREWRITE

POSTWRITE_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
```

A successful esptool return code by itself is never accepted as completion.

## 10. Focused source tests

The 20 focused tests cover:

- frozen identity, route and partition boundaries;
- frozen normalized-slot binding;
- exact erase ranges;
- deterministic 0xFF slot padding;
- erased OTA-data semantics;
- exact dual-slot write command and `keep` header behavior;
- absence of erase-flash / erase-region commands;
- fresh preflight acceptance;
- wrong-route rejection;
- normalized-slot drift rejection;
- erase-range drift rejection;
- wrong-identity rejection;
- stale-preflight rejection;
- one-shot claim;
- complete app0/app1 readback;
- app1 mismatch rejection;
- NVS continuity rejection;
- postwrite ROM identity continuity;
- claim -> single write -> full readback -> identity ordering;
- rejection of a wrong confirmation label before any action.

## 11. Candidate source objects

```text
EXECUTOR_BLOB=c7f2f4dcf9206de76d2654c9a1fa3e8e597f0ecd
TEST_BLOB=2c7631c4c2e4243167face3e2c62bb7b5d29b81f
WORKFLOW_BLOB=b1de5e3f9818d8587442c24232684f51e7b64c4c
```

## 12. Current boundary

```text
SOURCE_REPAIR_IMPLEMENTED=true
BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false
AUTO_EXECUTE_LIVE_WRITE=false
MERGE=false
```

Exact-head implementation evidence:

```text
IMPLEMENTATION_HEAD=45859f78c24daaa822658479a8ad95b051867dde
IMPLEMENTATION_PARENT_DESIGN_HEAD=d72fb5cadbc03ab6eb327794bf7d72290842a3d0

DEDICATED_CI_RUN=39924615411
DEDICATED_CI_RESULT=PASS
PY_COMPILE=PASS
FOCUSED_TESTS=20_OF_20_PASS

PUBLIC_REPOSITORY_SAFETY_RUN=39924615524
PUBLIC_REPOSITORY_SAFETY=PASS

PR_WORKFLOW_TOTAL=12
PR_WORKFLOW_SUCCESS=12
PR_WORKFLOW_FAILURE=0

EXACT_SOURCE_REVIEW=PASS
NEW_SOURCE_BLOCKER_COUNT=0
B1_STALE_APPLICATION_FALSE_PASS=CLOSED
```

Independent source review verified that the superseded app0-only route and old
confirmation label are absent, complete app0/app1 slot readbacks are required,
protected ranges remain outside the write command, and the postwrite Board D ROM
identity is freshly checked.

```text
SOURCE_REPAIR_RESULT=CLOSED_PASS
SOURCE_REPAIR_REQUIRED=false
BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false
MERGE=false

NEXT_ONE_GATE=N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_WRITE_EXECUTOR_SOURCE_CLOSURE_REVIEW_20261023_01
```

The next gate is read-only source closure review. No merge or live Board D write
is authorized by this document.
