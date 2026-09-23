# N3-W Production Gateway Selection V1
## Three-Board Exact Artifact Write Preparation — 2026-09-23

Status: `PREPARED_AWAITING_CI`

## 1. Gate

```text
TASK=N3W_PRODUCTION_GWSEL_V1_THREE_BOARD_EXACT_ARTIFACT_WRITE_PREPARATION_20260923_01

BOARD_ACCESS=false
SOURCE_AND_EXECUTOR_PREPARATION_ONLY=true
ARTIFACT_INSPECTION_REQUIRED=true
WRITE_ROUTE_FREEZE_REQUIRED=true
AUTO_EXECUTE=false

FLASH_WRITE=false
NVS_WRITE=false
```

This gate prepares and validates the write path only. It does not access or mutate
Board A, Board B or Board C.

## 2. Preparation base

```text
BASE=
d0ac88dcd7b8730e54599f694dddf1a4bc2c8a06

THREE_BOARD_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
```

Current summary authority:

```text
docs/development/N3W_PRODUCTION_GWSEL_V1_THREE_BOARD_WRITE_TARGET_PREFLIGHT_SUMMARY_20260923.md
```

## 3. Exact artifact inspection

The GitHub Actions artifact was downloaded again by exact artifact ID and inspected
directly.

```text
ARTIFACT_ID=
10693728323

ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-8c445f2-exact-source

ARTIFACT_OUTER_SIZE=
4281423

ARTIFACT_OUTER_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

RELEASE_BUNDLE_SIZE=
4280881

RELEASE_BUNDLE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598
```

The inner release contains exactly eight files:

```text
MANIFEST.txt
bootloader.bin
firmware.bin
firmware.factory.bin
firmware.ota.bin
flash_args
ota_data_initial.bin
partitions.bin
```

All frozen member sizes and SHA-256 values match the manifest.

## 4. flash_args inspection

The exact artifact contains:

```text
--flash_mode dio --flash_freq 80m --flash_size 8MB
0x0 bootloader/bootloader.bin
0x10000 gh.bin
0x8000 partition_table/partition-table.bin
0x9000 ota_data_initial.bin
```

The flat release artifact does not contain the build-directory paths
`bootloader/bootloader.bin`, `partition_table/partition-table.bin`, or
`gh.bin`.

Therefore:

```text
FLASH_ARGS_LAYOUT_EVIDENCE=VALID
BLIND_EXECUTION_OF_RELEASE_FLASH_ARGS=FORBIDDEN
```

The build workflow at trigger commit
`4e662a67ed24b258a4c17ace4e08fb370f06f26e` copied the production build outputs
from the exact `.pioenvs/gh` environment into the release artifact.

## 5. Partition-table binary inspection

The exact `partitions.bin` was parsed directly:

```text
otadata   type=0x01 subtype=0x00 offset=0x9000   size=0x2000
phy_init  type=0x01 subtype=0x01 offset=0xb000   size=0x1000
app0      type=0x00 subtype=0x10 offset=0x10000  size=0x3c0000
app1      type=0x00 subtype=0x11 offset=0x3d0000 size=0x3c0000
nvs       type=0x01 subtype=0x02 offset=0x790000 size=0x70000
```

Partition-table binding:

```text
PARTITION_TABLE_SIZE=3072
PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

The application image size is `1392960` bytes and fits completely within the
`app0` partition.

## 6. Factory-image composition proof

The artifact's `firmware.factory.bin` was independently compared byte-for-byte
against the flat component files.

The factory image contains:

```text
offset 0x0:
bootloader.bin exact bytes = PASS

offset 0x8000:
partitions.bin exact bytes = PASS

offset 0x9000:
ota_data_initial.bin exact bytes = PASS

offset 0x10000:
firmware.bin exact bytes = PASS
```

The factory image ends exactly at:

```text
0x10000 + len(firmware.bin)
```

Also:

```text
firmware.bin SHA256 =
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

firmware.ota.bin SHA256 =
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

FIRMWARE_BIN_EQUALS_FIRMWARE_OTA_BIN=true
```

This provides direct artifact evidence that the flat `firmware.bin` is the
application image associated with the `0x10000` application slot in this exact
factory composition.

## 7. Frozen minimal write route

Given:

- all three boards already proved the exact partition-table binding;
- bootloader replacement is unnecessary for this product-source update;
- partition-table replacement is unnecessary because the target layout already
  matches exactly;
- product NVS must be preserved;
- the exact artifact composition independently maps the application and OTA-data
  bytes to their offsets;

the Gateway Selection V1 exact write route is frozen as:

```text
WRITE 0x9000  ota_data_initial.bin
WRITE 0x10000 firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FACTORY_IMAGE_WRITE=false
FULL_FLASH_ERASE=false
```

The full `firmware.factory.bin` is not an allowed write target for this route.

## 8. Prepared exact write executor

Prepared path:

```text
tools/execution_packages/n3w/production/gwsel_v1_three_board_write/executor.py
```

The executor binds all three current public-safe identities:

```text
BOARD_A_HARDWARE_ID_SHA256=
f1f1e36fe4784a26b936d6a2bc5d239ab531f5683aca91356a5e39f3f566b1eb

BOARD_B_HARDWARE_ID_SHA256=
cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0

BOARD_C_HARDWARE_ID_SHA256=
d6ef3f98a35f06a5a8b8e7716a015e17336242128b314a1b3244b114fc6f72e2
```

It uses the repaired ESP32-C6 identity parser and does not use OTA-data as board
identity.

## 9. Two-stage execution contract

The prepared executor requires:

```text
STAGE_1=FRESH_READONLY_PREFLIGHT
STAGE_2=EXPLICITLY_AUTHORIZED_WRITE
```

Fresh preflight:

```text
MAX_AGE_SECONDS=900
FRESH_ROM_IDENTITY_REQUIRED=true
CHIP=ESP32-C6_REQUIRED
FLASH_SIZE=8MB_REQUIRED
SECURE_BOOT=false_REQUIRED
FLASH_ENCRYPTION=false_REQUIRED
PARTITION_TABLE_BINDING_REQUIRED
EXACT_ARTIFACT_BINDING_REQUIRED
```

The preflight file is private mode-0600 state and is single-use for a later write.

Before the first write command, the executor revalidates the artifact and board
again, then consumes the preflight authorization.

If anything fails after authorization is claimed:

```text
AUTO_RETRY=false
AUTO_ERASE=false
AUTO_REPAIR=false
AUTO_PARTITION_MIGRATION=false
STOP_AND_REVIEW=true
```

## 10. Post-write verification

A write is not PASS merely because `esptool write-flash` returns success.

The executor must read back:

```text
0x9000 / 0x2000
EXPECTED_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

0x10000 / 1392960
EXPECTED_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

0x8000 / 0x0c00
EXPECTED_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

All three must match.

## 11. Sequential three-board deployment

The prepared executor is generic across A/B/C, but authorizations remain
board-specific.

Required deployment order:

```text
A -> STOP -> B -> STOP -> C -> STOP
```

Each board needs its own:

```text
physical connection confirmation
temporary reset / ROM read authorization
fresh exact-write preflight
explicit firmware-write authorization
write execution
post-write readback closure
STOP
```

No authorization carries across board boundaries.

## 12. RUNBOOK alignment

The reusable authority was extended in this gate:

```text
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md
```

The RUNBOOK now freezes the same minimal route, single-use preflight consumption,
no-auto-retry policy and mandatory post-write readback verification.

## 13. Prepared test / CI scope

Focused tests cover:

```text
EXACT_ARTIFACT_AND_BOARD_BINDINGS
CORRECTED_EUI64_IDENTITY_PARSER
EXPLICIT_BASE_MAC_PREFERENCE
MALFORMED_EUI64_FAIL_CLOSED
FROZEN_PARTITION_LAYOUT
FACTORY_COMPOSITION_ROUTE
WRITE_COMMAND_ONLY_0x9000_AND_0x10000
IDENTITY_MISMATCH_BEFORE_FLASH_ID_OR_READBACK
READ_ONLY_FRESH_PROBE
RAW_MAC_NOT_PUBLISHED
POSTWRITE_THREE_REGION_READBACK
WRITE_CONFIRMATION_BEFORE_ANY_BOARD_ACTION
NO_AUTOMATIC_DESTRUCTIVE_RECOVERY
```

CI also downloads artifact `10693728323` again and runs the executor's exact
artifact/write-route validator against the real artifact bytes.

## 14. Artifact lifetime guard

Current artifact metadata:

```text
ARTIFACT_EXPIRES_AT=2026-10-22T12:38:37Z
```

If the artifact is unavailable or expired before a future board operation:

```text
AUTO_REBUILD=false
AUTO_SUBSTITUTE_ARTIFACT=false
STOP_FOR_EXACT_ARTIFACT_REBIND=true
```

## 15. Current mutation boundary

```text
BOARD_ACCESS=false
ROM_ACCESS=false
FLASH_READ=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_BOARD_MUTATION=false
WRITE_AUTHORIZATION_GRANTED=false
```

## 16. Current status

```text
GWSEL_V1_EXACT_WRITE_ROUTE_FROZEN=true
GWSEL_V1_EXACT_WRITE_EXECUTOR_PREPARED=true
GWSEL_V1_EXACT_WRITE_EXECUTOR_CI=PENDING

AUTO_EXECUTE=false
STOP=true
```

## 17. Proposed next ONE gate after CI PASS

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_A_EXACT_WRITE_PREFLIGHT_20260923_01

BOARD_A_ACCESS_REQUIRED=true
READ_ONLY=true
FLASH_WRITE=false
NVS_WRITE=false
EXPLICIT_RESET_ROM_AUTHORIZATION_REQUIRED=true
AUTO_EXECUTE=false
```

That next gate remains read-only. A separate explicit authorization is required
after Board A's fresh exact-write preflight before any firmware write.
