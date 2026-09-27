# N3-W PR #474 exact artifact build and binding closure

Updated: 2026-09-27  
Status: `CLOSED_PASS_FOR_PHYSICAL_PREFLIGHT`

## Source / PR binding

```text
PR474_STATE=OPEN_DRAFT
PR474_HEAD=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PR474_SOURCE_TREE=5916ae2dfa45b02c9d5369c5312930c7b2bee59e
PR474_BASE_HEAD=8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c
PR474_SOURCE_REVIEW=PASS
PR474_HEAD_CI=13_OF_13_PASS
PR474_MERGEABLE=true
PR474_PHYSICAL_VALIDATION=PENDING
```

Fresh disposition after T1 infrastructure closure found no source overlap or reason to rebase/retarget the reviewed exact PR head before physical validation.

## Exact artifact workflow

```text
BUILD_BRANCH=build/n3w-pr474-d3c158b-exact-artifact-20260927
BUILD_COMMIT=7dc3f549669468737dce800bad2e3f9580104376
WORKFLOW_RUN_ID=36316340016
WORKFLOW_RESULT=SUCCESS

ARTIFACT_ID=10930753742
ARTIFACT_NAME=n3w-pr474-d3c158b-exact-source
ARTIFACT_EXPIRES_AT=2026-10-27T11:42:01Z
GITHUB_ARTIFACT_SIZE=4294064
GITHUB_ARTIFACT_SHA256=54709a7bcd7c63ebd705e3152fed27692f2624b27d5b7549ef9fbc3aafc9ffba
```

The independently downloaded GitHub artifact ZIP SHA-256 exactly matched the GitHub artifact digest.

## Frozen release bundle

```text
RELEASE_BUNDLE=n3w-pr474-d3c158b-exact-source.zip
RELEASE_BUNDLE_SIZE=4293607
RELEASE_BUNDLE_SHA256=60044a56516d822c32796b16a3b6f0993a32d32ae69a7db23159ce796eac5875

MANIFEST_SHA256=e326b615ac84052fa9aeb9453d79cfd3a9c0403ce5caa74fed7f152484a8d11d
RELEASE_MEMBER_COUNT=8
MEMBER_SET_MATCH=PASS
MANIFEST_MEMBER_BINDING=PASS
```

Exact member set:

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

## Manifest source / toolchain binding

```text
BINDING_SCHEMA=N3W_PRODUCTION_EXACT_ARTIFACT_V1
SOURCE_HEAD=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
SOURCE_TREE=5916ae2dfa45b02c9d5369c5312930c7b2bee59e
PR=474
PR_BASE_HEAD=8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

TARGET_BLOB_SHA=32a2b3cb29be4e1bce46807d8825b6a4c37999ec
TELEMETRY_BRIDGE_BLOB_SHA=ce16f2389d146f9b25e95cbb628547e11ce36bd6
TRANSPORT_BLOB_SHA=aa39d4b083f2db1b30a76efb1afef156db355a35
PRODUCT_CORE_INIT_BLOB_SHA=7e86aa2f3fb1bff6f5813e431da501970263e33a
RADIO_BLOB_SHA=e6ae3c4512a4d7f171fdcc5e0f2a0a9eb36770f4
RUNTIME_BLOB_SHA=ec7b3fec95070bb1367805e43f24c6bfb762b994
COMPONENT_BLOB_SHA=c4c7be5207b9860691edd36e03d2c55069271306

PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
BINARY_DEHARNESS_PROOF=PASS
PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false
```

The source/tree and listed blob hashes were independently rebound to the exact PR #474 head before artifact use.

## Binary binding

```text
FIRMWARE_BIN_SIZE=1397136
FIRMWARE_BIN_SHA256=4d6bef5b6f5c9ac18686f514d5c3e767b70fb9fce45076bc2a8df67e59b3bb6b

FIRMWARE_OTA_BIN_SIZE=1397136
FIRMWARE_OTA_BIN_SHA256=4d6bef5b6f5c9ac18686f514d5c3e767b70fb9fce45076bc2a8df67e59b3bb6b

FIRMWARE_FACTORY_BIN_SIZE=1462672
FIRMWARE_FACTORY_BIN_SHA256=eee71ec6a5b3f2f07f1b0288870583918ed1aef1b2c63a1f3c47c55b4b2928bb

BOOTLOADER_BIN_SIZE=22576
BOOTLOADER_BIN_SHA256=2f475d35f069bedfde974c088880d8cd05d8e926b4793af5510490fa7530c740

PARTITIONS_BIN_SIZE=3072
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTA_DATA_INITIAL_BIN_SIZE=8192
OTA_DATA_INITIAL_BIN_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

FLASH_ARGS_SIZE=167
FLASH_ARGS_SHA256=5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713
```

All independently extracted member sizes and SHA-256 values exactly matched the manifest.

## Factory image mapping proof

The frozen `firmware.factory.bin` was independently decomposed against the bundle members:

```text
0x00000 bootloader.bin        BYTE_FOR_BYTE_MATCH
0x08000 partitions.bin        BYTE_FOR_BYTE_MATCH
0x09000 ota_data_initial.bin  BYTE_FOR_BYTE_MATCH
0x10000 firmware.bin          BYTE_FOR_BYTE_MATCH

FACTORY_EXACT_MERGE_MATCH=PASS
FACTORY_IMAGE_SIZE=1462672
FACTORY_IMAGE_END=0x165190
```

The bound partition table decodes to:

```text
otadata   offset=0x009000 size=0x002000
phy_init  offset=0x00b000 size=0x001000
app0      offset=0x010000 size=0x3c0000
app1      offset=0x3d0000 size=0x3c0000
nvs       offset=0x790000 size=0x070000
```

Therefore the exact factory image ends far below the NVS partition:

```text
FACTORY_IMAGE_OVERLAPS_NVS=false
FACTORY_WRITE_AT_0X0_PRESERVES_NVS_REGION=true
```

This proves the artifact layout only. A later physical gate must still fresh-bind the target board and exact local artifact before write.

## Flash-procedure guard

The frozen bundle is flat, but its generated `flash_args` still references build-tree paths such as:

```text
bootloader/bootloader.bin
gh.bin
partition_table/partition-table.bin
```

Those paths do not exist in the flat bundle. Therefore:

```text
FLASH_ARGS_BLIND_EXECUTION=FORBIDDEN
PHYSICAL_WRITE_PROCEDURE_REVIEW_REQUIRED=true
```

A later Board write gate must use a separately reviewed exact procedure, such as a correctly validated factory-image path, or an independently normalized multi-image mapping. Artifact binding alone does not authorize a flash.

## Board B readonly write-target preflight

The operator executed the bounded macOS ROM/Flash preflight against the intended Board B target.

```text
PREFLIGHT=PASS
TARGET=BOARD_B
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false

HARDWARE_ID_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
PORT_SHA256=3dbd58fb2a751780ce45dab2216fc0ffbcb9e70e8ff0a6fe00c85bd0055420b5
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

ARTIFACT_RELEASE_BUNDLE_SHA256=60044a56516d822c32796b16a3b6f0993a32d32ae69a7db23159ce796eac5875
TARGET_APPLICATION_SHA256=4d6bef5b6f5c9ac18686f514d5c3e767b70fb9fce45076bc2a8df67e59b3bb6b
TARGET_FACTORY_SHA256=eee71ec6a5b3f2f07f1b0288870583918ed1aef1b2c63a1f3c47c55b4b2928bb

ARTIFACT_BINDING=PASS
BOARD_IDENTITY_BINDING=PASS
PARTITION_BINDING=PASS

FLASH_WRITE=false
ERASE=false
NVS_MUTATION=false
PERSISTENT_MUTATION=false
READY_FOR_WRITE_AUTHORIZATION=true
```

The current target partition table exactly matches the bound production artifact. Therefore the preferred later write scope is the narrower existing production pattern:

```text
0x9000  ota_data_initial.bin
0x10000 firmware.bin
```

This preserves the already-matching bootloader/partition table and the NVS region. The broader factory-image-at-0x0 path remains valid as a layout proof, but is not preferred when the live partition table is already exact.

## Disposition

```text
EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS
READY_FOR_BOARD_WRITE_TARGET_PREFLIGHT=false
BOARD_B_WRITE_TARGET_PREFLIGHT=PASS
READY_FOR_BOARD_WRITE_AUTHORIZATION=true

BOARD_ACCESS=false
USB_ACCESS=false
FLASH_WRITE=false
RF_EXECUTION=false
T1_MUTATION=false
PR474_SOURCE_MUTATION=false
PR474_MERGE=false

NEXT_ONE_GATE=N3W_PR474_BOARD_B_EXACT_ARTIFACT_WRITE_AUTHORIZATION_20260927_01
```
