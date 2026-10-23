# N3-W Board D R4 dual-slot normalization write-route repair design — 2026-10-23

## Status

```text
TASK=N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_WRITE_ROUTE_REPAIR_DESIGN_20261023_01
PARENT_PR=659
BLOCKED_EXECUTOR_PR=660

BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_MUTATION=false
WRITE_AUTHORIZATION_GRANTED=false
MERGE=false
```

This source-only design repairs the write route after the exact-head review of
PR #660 found that an app0-only image write can leave historical application
bytes in the app0 tail and the entire app1 OTA slot.

No Board D operation is performed by this design.

## 1. Blocker being repaired

```text
BLOCKER=B1_BOARD_D_UNKNOWN_STALE_APPLICATION_BYTES_OUTSIDE_APP0_IMAGE
BLOCKER_SCOPE=APP0_TAIL_AND_APP1
CURRENT_THREE_OFFSET_ROUTE=SUPERSEDED
```

The repository already contains physical precedent from the KF-089 cleanup:
unknown historical application code in an alternate OTA slot was treated as an
unnecessary physical variable, and the clean baseline was accepted only after
both complete application partitions were normalized.

Board D is known to contain historical firmware with low-battery behavior.
Therefore the write route must not claim production normalization while bytes
outside the exact app image remain unproven.

## 2. Frozen Board D and R4 authorities

```text
BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

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
```

## 3. Exact partition boundaries

```text
OTADATA_OFFSET=0x00009000
OTADATA_SIZE=0x00002000

PHY_INIT_OFFSET=0x0000B000
PHY_INIT_SIZE=0x00001000

APP0_OFFSET=0x00010000
APP0_SIZE=0x003C0000
APP0_END=0x003D0000

APP1_OFFSET=0x003D0000
APP1_SIZE=0x003C0000
APP1_END=0x00790000

NVS_OFFSET=0x00790000
NVS_SIZE=0x00070000
FLASH_END=0x00800000
```

The observed Board D partition table already matches the exact R4 table and
therefore remains protected from write.

## 4. Deterministic full-slot image

The exact R4 application is smaller than one OTA partition:

```text
R4_APPLICATION_SIZE=1413616
R4_APPLICATION_SIZE_HEX=0x1591F0

OTA_SLOT_SIZE=3932160
OTA_SLOT_SIZE_HEX=0x3C0000

NORMALIZATION_TAIL_SIZE=2518544
NORMALIZATION_TAIL_SIZE_HEX=0x266E10
```

The future executor must derive a temporary full-slot image only from the already
validated exact R4 `firmware.bin`:

```text
normalized_slot.bin =
    exact firmware.bin
    + 0xFF repeated until total size is exactly 0x3C0000
```

Independent byte-level calculation from artifact 12478974186 gives:

```text
NORMALIZED_SLOT_SIZE=3932160
NORMALIZED_SLOT_SHA256=539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195

NORMALIZATION_TAIL_SHA256=50b46211550f22ac7f9bcb795c7a784f2a14f96de618032f600e722f0418b12e
```

The normalized slot is not a new production artifact. It is a deterministic
temporary transformation of the exact bound R4 application and must be
re-derived locally after release validation.

## 5. Repaired selected write route

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
ERASE_REGION_COMMAND_REQUIRED=false
```

The route intentionally does not use a separate `erase-region` command.
Writing a complete 0x3C0000 normalized-slot file causes both application
partitions to be covered to their exact boundaries, while the 0xFF tail removes
historical application bytes after the R4 image.

The app0 write ends exactly at the app1 boundary. The app1 write ends exactly at
the NVS boundary.

## 6. Flash-header preservation

The exact R4 bootloader already comes from the bound R4 build. The later executor
must avoid changing its bytes during flashing.

The write command should therefore use the esptool `keep` behavior for boot
image flash-header parameters:

```text
FLASH_MODE_WRITE_OPTION=keep
FLASH_FREQ_WRITE_OPTION=keep
FLASH_SIZE_WRITE_OPTION=keep
```

The executor still separately validates the exact R4 build contract:

```text
R4_BUILD_FLASH_MODE=dio
R4_BUILD_FLASH_FREQ=80m
R4_BUILD_FLASH_SIZE=8MB
```

This separates two concerns:

1. prove that the release was built for DIO / 80 MHz / 8 MB;
2. write the exact already-built bootloader bytes without asking esptool to
   rewrite its image header.

The detected physical flash size must still be freshly proven as 8 MB before the
write claim.

## 7. OTA-data final state

The exact R4 `ota_data_initial.bin` is 8192 bytes of 0xFF.

The frozen partition table has no factory application and has app0 as the first
OTA slot. ESP-IDF specifies that erased OTA-data selects the factory app if one
exists, otherwise the first available OTA slot.

Therefore the final expected boot selection is:

```text
OTADATA_FINAL_STATE=ALL_FF
FACTORY_APP_PRESENT=false
EXPECTED_DEFAULT_BOOT_SLOT=APP0
APP0_CONTENT=EXACT_R4_NORMALIZED_SLOT
APP1_CONTENT=EXACT_R4_NORMALIZED_SLOT
```

Because both slots contain identical normalized R4 application content, an OTA
slot-selection change cannot expose historical application code after this
normalization.

## 8. One bounded mutation command

The later executor should use one repository-generated `write-flash` command,
not raw `flash_args`, with:

```text
--chip esp32c6
--before no-reset
--after no-reset

write-flash
--flash-mode keep
--flash-freq keep
--flash-size keep

0x000000 bootloader.bin
0x009000 ota_data_initial.bin
0x010000 normalized_slot.bin
0x3D0000 normalized_slot.bin
```

The target must already be in the ROM/serial-loader state before the one-shot
authorization claim.

Using one bounded command minimizes mode transitions. The operation is not
claimed to be power-fail atomic. After the claim is consumed, manual reset,
disconnect and power-cycle are forbidden until post-write readback is complete or
the executor stops with failure.

## 9. Erase-boundary proof required in source

Before any live write, the executor must prove using 0x1000-byte erase-sector
rounding that every selected range stays inside its intended region.

Required ranges:

```text
BOOTLOADER_ERASE_RANGE=0x000000..0x006000
OTADATA_ERASE_RANGE=0x009000..0x00B000
APP0_ERASE_RANGE=0x010000..0x3D0000
APP1_ERASE_RANGE=0x3D0000..0x790000
```

Protected ranges:

```text
PARTITION_TABLE=0x008000..0x009000
PHY_INIT=0x00B000..0x00C000
NVS=0x790000..0x800000
```

Any overlap must fail closed before authorization is claimed.

## 10. Fresh preclaim evidence

The repaired executor must freshly prove before the one-shot claim:

1. exact R4 release bundle and every member hash;
2. deterministic normalized-slot size and SHA256;
3. esptool major version 5;
4. ESP32-C6;
5. physical flash size 8 MB;
6. Secure Boot disabled;
7. Flash Encryption disabled;
8. exact frozen Board D hardware-ID SHA256;
9. exact R4 partition-table SHA256;
10. current `phy_init` full-region SHA256;
11. current NVS full-region SHA256;
12. erase-boundary non-overlap.

The preclaim readback does not need to trust the existing app0/app1 content.

## 11. Post-write acceptance

A successful esptool return code is not sufficient.

After the mutation command, while still in the serial loader, the executor must
read back and require:

```text
BOOTLOADER_SHA256=ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

APP0_FULL_SLOT_SHA256=539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195
APP1_FULL_SLOT_SHA256=539a7b7fb14d44a4336526ff64ec4ee8b45737dc74c0e95eac15b5e06c84a195

PHY_INIT_SHA256_POSTWRITE=PHY_INIT_SHA256_PREWRITE
NVS_SHA256_POSTWRITE=NVS_SHA256_PREWRITE

POSTWRITE_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
```

Only these full-slot hashes permit:

```text
APP0_EXACT_R4=true
APP1_EXACT_R4=true
APP0_TAIL_ERASED=true
APP1_TAIL_ERASED=true
OLD_APPLICATION_CODE_REMAINS=false
DUAL_SLOT_NORMALIZATION=PASS
```

No claim about application boot, pairing, telemetry, Direct/Relay or RF behavior
is permitted until later physical gates.

## 12. Manual-reset / low-battery boundary

The previously frozen operator constraint remains:

```text
MANUAL_RESET_ALLOWED_DURING_READONLY_PRECLAIM=true
MANUAL_RESET_ALLOWED_BEFORE_WRITE_AUTHORIZATION_CLAIM=true

MANUAL_RESET_ALLOWED_AFTER_WRITE_AUTHORIZATION_CLAIM=false
MANUAL_RESET_ALLOWED_DURING_FLASH_WRITE=false
MANUAL_RESET_ALLOWED_DURING_POSTWRITE_READBACK=false
```

The executor must enter and retain ROM/serial-loader state before the claim so the
historical low-battery application cannot start during the mutation/readback
window.

## 13. Design closure

```text
B1_STALE_APPLICATION_BLOCKER=RESOLVED_BY_DESIGN

IDENTITY_FREEZE=PASS
WRITE_ROUTE_REPAIR_DESIGN=PASS

SELECTED_WRITE_ROUTE=DUAL_SLOT_PADDED_NORMALIZATION_BOOTLOADER_OTADATA

BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false
MERGE=false

CURRENT_GATE_RESULT=CLOSED_PASS_DESIGN_ONLY
```

## 14. Next one gate

```text
NEXT_ONE_GATE=N3W_BOARD_D_R4_DUAL_SLOT_NORMALIZATION_WRITE_EXECUTOR_SOURCE_REPAIR_20261023_01

BOARD_ACCESS_DEFAULT=false
LIVE_MUTATION_DEFAULT=false
WRITE_AUTHORIZATION_GRANTED=false
AUTO_EXECUTE_LIVE_WRITE=false
```

The next gate may repair PR #660 source and tests against this design. A later
real Board D write remains a separate physical gate requiring a new explicit
one-shot authorization.
