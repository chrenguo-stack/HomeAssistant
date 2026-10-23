# N3-W Board D identity freeze and write-route review — 2026-10-23

## Status

```text
TASK=N3W_BOARD_D_IDENTITY_FREEZE_AND_WRITE_ROUTE_REVIEW_20261023_01
BASE_MAIN=5bd4b60b3b4f4727c712fa0a04fbcb137451b3ff
REVIEW_MODE=SOURCE_ARTIFACT_AND_EXISTING_LIVE_EVIDENCE_ONLY

BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_MUTATION=false
WRITE_AUTHORIZATION_GRANTED=false

ROUTE_REVIEW_REPAIR_STATUS=SUPERSEDED_BY_DUAL_SLOT_REPAIR_DESIGN
ACTIVE_REPAIR_DESIGN=docs/development/N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_WRITE_ROUTE_REPAIR_DESIGN_20261023.md
```

This review starts only after the separately authorized Board D live read-only
preflight closed PASS. It freezes the public-safe Board D identity and originally
selected a minimal later write route. Exact-head review of the downstream executor
then proved that the app0-only route could leave stale historical application
bytes in the app0 tail and app1. The active write-route decision is therefore
superseded by the dual-slot repair design referenced above. This document does not
authorize or execute a flash write.

## 1. Frozen Board D identity

The operator explicitly confirmed that the physically attached target during the
live preflight was Board D.

```text
OPERATOR_CONFIRMS_PHYSICAL_TARGET_IS_BOARD_D=true
BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
RAW_ROM_IDENTITY_PUBLICLY_PERSISTED=false
BOARD_D_IDENTITY_FREEZE=PASS
```

The frozen value is the public-safe hash produced by the repository-owned
preflight executor. Raw ROM identity material is not stored here.

## 2. Live read-only preflight evidence

```text
PREFLIGHT_STATUS=PASS
PREFLIGHT_EVIDENCE_SHA256=541b23f67d3ff7cd1fd694c06d556a3f94e30952a77684b6dbcaf147fd69ef98
PREFLIGHT_CREATED_AT=2026-10-23T07:21:18.703936+00:00

CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
ESPTOOL_VERSION=5.3.1

OBSERVED_BOOTLOADER_SHA256=985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5
BOOTLOADER_MATCHES_R4_RELEASE=false

OBSERVED_PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
PARTITION_TABLE_MATCHES_R4_RELEASE=true

PREFLIGHT_WRITE_MODE_CANDIDATE=FACTORY_OR_NORMALIZED_OFFSETS_REVIEW_REQUIRED
```

The bootloader mismatch is not classified as a hardware failure. It only proves
that the bytes currently stored in the bootloader region are not the R4 V2
release bootloader.

## 3. Exact R4 V2 artifact binding

```text
R4_PRODUCT_SOURCE=ec5f6d68e33db7757d91c807fff708ca81b075dc
R4_PRODUCT_TREE=16740efa8ad24d423adc0b2de32b99d56e2d23d1

ARTIFACT_RUN_ID=39901919230
ARTIFACT_ID=12478974186
GITHUB_ARTIFACT_SHA256=898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f
RELEASE_BUNDLE_SHA256=b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5
MANIFEST_SHA256=173fcc978284170e0918c94269195191be0fc8a262b758851f16ee0609a638eb

BOOTLOADER_SHA256=ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46
PARTITIONS_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
APPLICATION_SHA256=ea50b147b7cb76bf442c0bbc7fe8d54e4abff87fa48926b9160ca903b6fa5c08
FACTORY_SHA256=c982c5d56f62ddddbba5b4734c1d9f0c36d4ce6996754157b017159ac630e2c6
```

## 4. Exact partition layout

Independent parsing of the exact R4 V2 `partitions.bin` gives:

| Label | Offset | Size |
| --- | ---: | ---: |
| otadata | 0x9000 | 0x2000 |
| phy_init | 0xB000 | 0x1000 |
| app0 | 0x10000 | 0x3C0000 |
| app1 | 0x3D0000 | 0x3C0000 |
| nvs | 0x790000 | 0x70000 |

The observed Board D partition table already matches this exact release table.

## 5. Factory-image composition review

The exact `firmware.factory.bin` is 0x1691F0 bytes long. Byte-level comparison
against the other exact release members proves that it contains:

```text
0x000000  bootloader.bin
0x008000  partitions.bin
0x009000  ota_data_initial.bin
0x010000  firmware.bin
```

All bytes between those members are 0xFF. The factory image ends well before the
NVS partition at 0x790000, so writing the factory image would not reach product
NVS.

However, a factory-image write is broader than necessary for the observed Board D
state: it would also rewrite the already-correct partition-table sector and erase
the gap that contains the `phy_init` partition.

## 6. Selected write route — repaired

The original route
`NORMALIZED_OFFSETS_BOOTLOADER_OTADATA_APPLICATION` is superseded.

The active source authority is:

`docs/development/N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_WRITE_ROUTE_REPAIR_DESIGN_20261023.md`

The repaired route is:

```text
SELECTED_WRITE_ROUTE=DUAL_SLOT_PADDED_NORMALIZATION_BOOTLOADER_OTADATA

WRITE_BOOTLOADER=0x000000:bootloader.bin
WRITE_OTADATA=0x009000:ota_data_initial.bin
WRITE_APP0=0x010000:normalized_slot.bin
WRITE_APP1=0x3D0000:normalized_slot.bin

NORMALIZED_SLOT_SIZE=0x3C0000
NORMALIZED_SLOT_SHA256=539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195

PARTITION_TABLE_WRITE=false
PHY_INIT_WRITE=false
NVS_WRITE=false
FACTORY_IMAGE_DIRECT_WRITE=false
RAW_FLASH_ARGS_DIRECT_EXECUTION=false
FULL_FLASH_ERASE=false
ERASE_REGION_COMMAND_REQUIRED=false
```

The temporary `normalized_slot.bin` is derived deterministically from the exact
R4 `firmware.bin` plus 0xFF padding to the complete 0x3C0000 OTA-slot size.
Writing the complete slot to app0 and app1 removes historical application bytes
from both slot tails while ending app1 exactly at the NVS boundary.

## 7. Required write executor safety contract — repaired

The later executor must be repository-owned and tested before any live write.
At minimum it must:

1. freshly validate the exact R4 release bundle and every member hash;
2. derive the complete normalized-slot image and require SHA256
   `539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195`;
3. require esptool major version 5;
4. freshly re-observe ESP32-C6 / 8 MB / Secure Boot off / Flash Encryption off;
5. freshly require the frozen Board D hardware-ID SHA256;
6. freshly verify the exact R4 partition table;
7. capture full prewrite `phy_init` and NVS SHA256 values;
8. prove 0x1000-sector erase boundaries do not overlap partition table,
   `phy_init` or NVS;
9. require a new explicit one-shot Board D write authorization;
10. claim/consume authorization only after every read-only precondition passes;
11. use one bounded repository-generated write command for bootloader, OTA-data,
    app0 full slot and app1 full slot;
12. keep partition table, `phy_init`, NVS, factory image and raw `flash_args`
    outside the write scope;
13. read back both complete 0x3C0000 application slots and require the normalized
    slot SHA256 on each;
14. require exact bootloader, partition-table and OTA-data readback hashes;
15. require `phy_init` and NVS postwrite hashes to equal their fresh prewrite
    hashes;
16. freshly re-check the Board D hardware identity after write;
17. stop after post-write integrity proof.

Only complete-slot readback permits
`OLD_APPLICATION_CODE_REMAINS=false`. Pairing, telemetry and RF acceptance
remain later gates.

## 8. Manual reset / low-battery handling

The operator reported that the firmware currently on Board D contains low-battery
behavior that may trigger after USB connection and may require a manual board
restart.

The exact R4 source also contains a 300-second startup low-battery grace period
before low-voltage samples can enter low-battery mode.

The next live write contract therefore freezes:

```text
MANUAL_RESET_ALLOWED_DURING_READONLY_PRECLAIM=true
MANUAL_RESET_ALLOWED_BEFORE_WRITE_AUTHORIZATION_CLAIM=true

MANUAL_RESET_ALLOWED_AFTER_WRITE_AUTHORIZATION_CLAIM=false
MANUAL_RESET_ALLOWED_DURING_FLASH_WRITE=false
MANUAL_RESET_ALLOWED_DURING_POSTWRITE_READBACK=false
```

All optional/manual reset handling must occur before the one-shot write claim.
Once the claim is consumed, the operator must not manually reset, unplug, power
cycle, or replace the board until the executor has completed write plus readback
or has stopped with an explicit failure.

The write executor should keep the target in ROM/serial-loader state between the
write and post-write readback where practical, so the application low-battery
policy cannot interfere with integrity verification.

## 9. Scope decision

```text
IDENTITY_FREEZE=PASS
ORIGINAL_WRITE_ROUTE=SUPERSEDED
WRITE_ROUTE_REPAIR_DESIGN=PASS
SELECTED_WRITE_ROUTE=DUAL_SLOT_PADDED_NORMALIZATION_BOOTLOADER_OTADATA

BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false

CURRENT_GATE_RESULT=CLOSED_PASS_REPAIRED_DESIGN
```

No live write is authorized by this review.

## 10. Next one gate

```text
NEXT_ONE_GATE=N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_WRITE_EXECUTOR_SOURCE_REPAIR_20261023_01
```

That next gate is source-only and may repair PR #660 against the dual-slot design.

```text
BOARD_ACCESS_DEFAULT=false
LIVE_MUTATION_DEFAULT=false
WRITE_AUTHORIZATION_GRANTED=false
AUTO_EXECUTE_LIVE_WRITE=false
```

A later real Board D write remains a separate physical gate requiring a new,
explicit one-shot write authorization.
