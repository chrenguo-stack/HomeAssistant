# N3-W Production Multi-Relay Gateway Selection V1
## Correct Production Exact Artifact Rebuild and Binding — 2026-09-22

Status: `ARTIFACT_BINDING_AUTHORITY`

## 1. Gate

```text
TASK=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PRODUCTION_EXACT_ARTIFACT_REBUILD_AND_BINDING_20260922_01

BOARD_ACCESS=false
FLASH_WRITE=false
PHYSICAL_MUTATION=false
T1_ACCESS=false
MERGE=false
```

This gate replaces the previously hash-valid but wrong-target artifact
`10691518958` with a correctly composed F1.0-RC2 production artifact.

No board, T1, Broker, Manager, credential, NVS, OTA-data or physical RF operation
occurred in this gate.

## 2. Exact R2 source authority

```text
SOURCE_BASE=
c1b3d9d016d06c21c9ff7070c0043163739565ca

SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

SOURCE_REVIEW_R2=PASS
R1_BLOCKER_1_LOCAL_FAULT_CONSUMPTION=CLOSED
R1_BLOCKER_2_RESOURCE_AND_TRANSACTION_BOUNDS=CLOSED
R1_BLOCKER_3_ACCEPT_DEADLINE_ORDERING=CLOSED
```

Fresh compare from production base to R2:

```text
SOURCE_COMPARE_STATUS=ahead
SOURCE_AHEAD_BY=24
SOURCE_BEHIND_BY=0
SOURCE_CHANGED_FILE_COUNT=7
```

Changed-file set:

```text
.github/workflows/n3w-production-multi-relay-gateway-selection-v1-ci.yml
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h
tests/n3w_production/n3w_multi_relay_gateway_selection_v1_host_test.cpp
tests/n3w_production/test_multi_relay_gateway_selection_v1_contract.py
```

The production F1.0-RC2 YAML/packages were not modified by Gateway Selection V1.

## 3. Correct production composition

```text
TARGET_CONFIG=
firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml

TARGET_BLOB_SHA=
32a2b3cb29be4e1bce46807d8825b6a4c37999ec

TELEMETRY_BRIDGE=
firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml

TELEMETRY_BRIDGE_BLOB_SHA=
ce16f2389d146f9b25e95cbb628547e11ce36bd6

TRANSPORT_PACKAGE=
firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml

TRANSPORT_BLOB_SHA=
aa39d4b083f2db1b30a76efb1afef156db355a35

PRODUCT_CORE_INIT_BLOB_SHA=
7e86aa2f3fb1bff6f5813e431da501970263e33a

PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

The target explicitly loads `greenhouse_n3w_product_core`.

This closes the target-composition defect found in the first physical-validation
preparation gate.

## 4. Build-only branch authority

```text
BUILD_BRANCH=
build/n3w-production-gwsel-v1-r2-production-artifact-20260922

BUILD_BRANCH_HEAD=
4e662a67ed24b258a4c17ace4e08fb370f06f26e

BUILD_BRANCH_TREE=
25f30c722d1f57f553777de95d5cd66bbe6de62e

BUILD_BRANCH_PARENT=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

BUILD_BRANCH_PARENT_MATCH=PASS
BUILD_BRANCH_AHEAD_BY=1
BUILD_BRANCH_BEHIND_BY=0
BUILD_BRANCH_CHANGED_FILE_COUNT=1

BUILD_BRANCH_CHANGED_FILE=
.github/workflows/n3w-production-gwsel-v1-r2-production-artifact-build.yml

BUILD_BRANCH_DIFF_ALLOWLIST=PASS
WORKFLOW_BLOB_SHA=
cedfd62d932d05d570b7118ce089b518eac0d6d4
```

The build-only branch changes no product source.

## 5. Workflow and compile result

```text
WORKFLOW_RUN_ID=
35727909715

WORKFLOW_RUN_HEAD_SHA=
4e662a67ed24b258a4c17ace4e08fb370f06f26e

WORKFLOW_RUN_EVENT=push
WORKFLOW_RUN_RESULT=SUCCESS
```

All relevant workflow steps completed successfully:

```text
Checkout exact production source=PASS
Bind exact source and production target=PASS
Install exact ESPHome=PASS
Compile exact production target=PASS
Verify ESP-IDF toolchain=PASS
Prove production binary and R2 selection code are linked=PASS
Freeze exact production release bundle=PASS
Upload exact production release artifact=PASS
```

## 6. Binary composition proof

The build performed the existing production de-harness proof and additional
Gateway Selection R2 positive controls.

Runner evidence:

```text
N3W_PRODUCTION_BINARY_DEHARNESS_PROOF=PASS
N3W_GATEWAY_SELECTION_R2_LINK_PROOF=PASS

PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false
```

Positive controls included:

```text
GreenhouseN3wCore
SimpleProductComponent
gateway_selection_local_fault_requires_restore
N3W-GWSEL-V1
gh.telemetry/1
air_temperature_c
```

Independent inspection of the downloaded release confirmed that all three
application-bearing binary forms:

```text
firmware.bin
firmware.ota.bin
firmware.factory.bin
```

contain:

```text
N3W-GWSEL-V1
gh.telemetry/1
air_temperature_c
```

and do not contain:

```text
PHASE4_LAB_TELEMETRY
phase4_source_harness
phase4_lab_diagnostics
```

Therefore:

```text
CORRECT_PRODUCT_CORE_COMPOSED=true
GATEWAY_SELECTION_V1_R2_BINARY_PROOF=PASS
REAL_F1RC2_TELEMETRY_BRIDGE_BINARY_PROOF=PASS
OLD_PHASE4_LAB_TARGET_COMPOSED=false
```

## 7. GitHub artifact metadata

```text
ARTIFACT_ID=
10693728323

ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-8c445f2-exact-source

ARTIFACT_SIZE_BYTES=
4281423

ARTIFACT_CREATED_AT=
2026-09-22T12:38:38Z

ARTIFACT_EXPIRES_AT=
2026-10-22T12:38:37Z

ARTIFACT_EXPIRED=false

GITHUB_ARTIFACT_DIGEST_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814
```

## 8. Independent outer-artifact verification

The GitHub Actions artifact was independently downloaded after the run completed.

```text
INDEPENDENT_OUTER_ARTIFACT_SIZE=
4281423

INDEPENDENT_OUTER_ARTIFACT_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

OUTER_DIGEST_MATCH_GITHUB_METADATA=PASS
OUTER_MEMBER_COUNT=2
```

Outer members:

```text
n3w-production-gwsel-v1-r2-8c445f2-exact-source.zip
n3w-production-gwsel-v1-r2-8c445f2-exact-source.zip.sha256
```

## 9. Inner release bundle

```text
RELEASE_BUNDLE=
n3w-production-gwsel-v1-r2-8c445f2-exact-source.zip

RELEASE_BUNDLE_SIZE=
4280881

RELEASE_BUNDLE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

SIDECAR_SHA256_MATCH=PASS
RELEASE_MEMBER_COUNT=8
RELEASE_MEMBER_SET_MATCH=PASS
```

Inner member set:

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

## 10. Frozen inner hashes

```text
MANIFEST_SIZE=1592
MANIFEST_SHA256=
eefa4580940302094d74e5e6228e82c683ba9b2a4c3c5e5b8d59fbee5ad0851e

FIRMWARE_BIN_SIZE=1392960
FIRMWARE_BIN_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

FIRMWARE_OTA_BIN_SIZE=1392960
FIRMWARE_OTA_BIN_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

FIRMWARE_FACTORY_BIN_SIZE=1458496
FIRMWARE_FACTORY_BIN_SHA256=
d8aa60082eca0482fe14806d8f4445223d3ccd4f87ba05d433b3ef31c187d304

BOOTLOADER_BIN_SIZE=22576
BOOTLOADER_BIN_SHA256=
de9616925b2a868feb7c616762d9173899e5b947d0de5da7117268872c8297d1

PARTITIONS_BIN_SIZE=3072
PARTITIONS_BIN_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTA_DATA_INITIAL_BIN_SIZE=8192
OTA_DATA_INITIAL_BIN_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

FLASH_ARGS_SIZE=167
FLASH_ARGS_SHA256=
5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713
```

All sizes and hashes independently match `MANIFEST.txt`.

## 11. Manifest binding

The independently downloaded manifest binds:

```text
BINDING_SCHEMA=N3W_PRODUCTION_EXACT_ARTIFACT_V1

SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

TARGET_CONFIG=
firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml

TARGET_BLOB_SHA=
32a2b3cb29be4e1bce46807d8825b6a4c37999ec

TELEMETRY_BRIDGE_BLOB_SHA=
ce16f2389d146f9b25e95cbb628547e11ce36bd6

TRANSPORT_BLOB_SHA=
aa39d4b083f2db1b30a76efb1afef156db355a35

PRODUCT_CORE_INIT_BLOB_SHA=
7e86aa2f3fb1bff6f5813e431da501970263e33a

PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4

WORKFLOW_TRIGGER_SHA=
4e662a67ed24b258a4c17ace4e08fb370f06f26e

WORKFLOW_RUN_ID=
35727909715

BINARY_DEHARNESS_PROOF=PASS
GATEWAY_SELECTION_R2_LINK_PROOF=PASS

PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false
```

Independent field-by-field verification result:

```text
SOURCE_HEAD_MATCH=PASS
SOURCE_TREE_MATCH=PASS
TARGET_CONFIG_MATCH=PASS
TARGET_BLOB_MATCH=PASS
TELEMETRY_BRIDGE_BLOB_MATCH=PASS
TRANSPORT_BLOB_MATCH=PASS
PRODUCT_CORE_INIT_BLOB_MATCH=PASS
WORKFLOW_TRIGGER_SHA_MATCH=PASS
WORKFLOW_RUN_ID_MATCH=PASS
TOOLCHAIN_BINDING=PASS
DEHARNESS_PROOF_BINDING=PASS
R2_LINK_PROOF_BINDING=PASS
MEMBER_SIZE_HASH_MATCH=PASS
MANIFEST_MATCH=PASS
```

## 12. Cross-artifact reproducibility review

The new R2 production artifact was compared with the prior production artifact
`10644667734`, built on 2026-09-21 from the same unchanged production target
and the same declared Python / ESPHome / ESP-IDF versions.

Unchanged members:

```text
partitions.bin=BYTE_IDENTICAL
ota_data_initial.bin=BYTE_IDENTICAL
flash_args=BYTE_IDENTICAL
```

The bootloader has the same size but a new hash:

```text
OLD_BOOTLOADER_SHA256=
07865c91e04285282a43188ef326af650b9ecb28c7de74b50006c4917cdea445

NEW_BOOTLOADER_SHA256=
de9616925b2a868feb7c616762d9173899e5b947d0de5da7117268872c8297d1

BOOTLOADER_BYTE_DIFF_COUNT=38
```

The only readable string difference is the build timestamp:

```text
OLD=Sep 21 2026 14:34:30
NEW=Sep 22 2026 12:38:22
```

The remaining changed bytes are in the image tail/checksum region.

Classification:

```text
BOOTLOADER_CONFIG_DRIFT_PROVEN=false
BUILD_TIMESTAMP_NONDETERMINISM_OBSERVED=true
EXACT_ARTIFACT_IDENTITY_GUARD_REQUIRED=true
BLOCKING=false
```

This reinforces the existing rule that a later rebuild must never inherit binary
hashes from a prior artifact even when source and declared toolchain versions appear
equivalent.

## 13. Flash-args guard

The frozen `flash_args` remains byte-identical to the prior production artifact and
contains build-tree-relative names:

```text
--flash_mode dio --flash_freq 80m --flash_size 8MB
0x0 bootloader/bootloader.bin
0x10000 gh.bin
0x8000 partition_table/partition-table.bin
0x9000 ota_data_initial.bin
```

The release bundle itself is flat and contains `firmware.bin`,
`bootloader.bin`, and `partitions.bin`.

Therefore:

```text
BLIND_EXECUTION_OF_RELEASE_FLASH_ARGS=FORBIDDEN
```

A later board-write preparation must either use a separately reviewed
`firmware.factory.bin` route or independently normalize and verify the multi-image
address/file mapping against this artifact's frozen hashes.

This gate does not choose or execute that write method.

## 14. Superseded wrong-target artifact

```text
SUPERSEDED_ARTIFACT_ID=
10691518958

SUPERSEDED_APPLICATION_SHA256=
5e0dc5d950061dd6685b11ee972090036a5af6d576920621550582d216ce38e6

SUPERSEDED_DISPOSITION=
FROZEN_WRONG_TARGET_NOT_FOR_GATEWAY_SELECTION_PHYSICAL_USE

SUPERSEDED_ARTIFACT_REUSE_FOR_PHYSICAL_VALIDATION=false
```

It remains historical evidence only.

## 15. Binding conclusion

```text
CORRECT_PRODUCTION_EXACT_ARTIFACT_BUILD=PASS
CORRECT_PRODUCTION_EXACT_ARTIFACT_BINDING=PASS

CORRECT_TARGET_BINDING=PASS
R2_PRODUCT_CORE_BINARY_LINK=PASS
PRODUCTION_DEHARNESS_PROOF=PASS
REAL_TELEMETRY_BRIDGE_BINARY_PROOF=PASS

OUTER_ARTIFACT_DIGEST_BINDING=PASS
INNER_RELEASE_DIGEST_BINDING=PASS
INNER_MEMBER_SET_BINDING=PASS
MANIFEST_BINDING=PASS

READY_FOR_CORRECTED_PHYSICAL_VALIDATION_PREPARATION=true
```

## 16. Physical acceptance boundary

Nothing in this gate proves physical behavior.

```text
BOARD_ACCESS=false
SERIAL_OPEN=false
BOARD_RESET=false
FLASH_WRITE=false
NVS_WRITE=false
OTA_DATA_WRITE=false

THREE_BOARD_GATEWAY_SELECTION_PHYSICAL_ACCEPTANCE=NOT_PROVEN
REAL_RSSI_RANKING_PHYSICAL_ACCEPTANCE=NOT_PROVEN
HEALTHY_RELAY_STICKINESS_PHYSICAL_ACCEPTANCE=NOT_PROVEN
FAILED_GATEWAY_RESELECTION_PHYSICAL_ACCEPTANCE=NOT_PROVEN
R2_SAME_BOOT_DIRECT_RELAY_DIRECT_PHYSICAL_ACCEPTANCE=NOT_PROVEN

REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
```

## 17. Gate closure

```text
=== N3W GATEWAY SELECTION V1 CORRECT PRODUCTION EXACT ARTIFACT BINDING ===

TASK=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PRODUCTION_EXACT_ARTIFACT_REBUILD_AND_BINDING_20260922_01

SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

WORKFLOW_RUN_ID=
35727909715

ARTIFACT_ID=
10693728323

ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-8c445f2-exact-source

OUTER_ARTIFACT_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

RELEASE_BUNDLE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

FIRMWARE_BIN_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

FIRMWARE_FACTORY_BIN_SHA256=
d8aa60082eca0482fe14806d8f4445223d3ccd4f87ba05d433b3ef31c187d304

BOOTLOADER_BIN_SHA256=
de9616925b2a868feb7c616762d9173899e5b947d0de5da7117268872c8297d1

PARTITIONS_BIN_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

MANIFEST_SHA256=
eefa4580940302094d74e5e6228e82c683ba9b2a4c3c5e5b8d59fbee5ad0851e

CORRECT_PRODUCTION_EXACT_ARTIFACT_BUILD=PASS
CORRECT_PRODUCTION_EXACT_ARTIFACT_BINDING=PASS

BOARD_ACCESS=false
FLASH_WRITE=false
PHYSICAL_MUTATION=false
T1_ACCESS=false
AUTO_BOARD_WRITE=false
AUTO_PHYSICAL_EXECUTION=false
AUTO_MERGE=false

STOP=true

=== END ===
```

## 18. Proposed next ONE gate

The previous physical-validation-preparation authorization was consumed by its
fail-closed wrong-target result and must not be reinterpreted as authorization for
a later physical route.

Proposed successor:

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_VALIDATION_PREPARATION_R2_20260922_01

ARTIFACT_ID=
10693728323

FIRMWARE_BIN_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

FIRMWARE_FACTORY_BIN_SHA256=
d8aa60082eca0482fe14806d8f4445223d3ccd4f87ba05d433b3ef31c187d304

BOARD_ACCESS=false
FLASH_WRITE=false
PHYSICAL_MUTATION=false
```

That successor gate should re-freeze the three-board physical plan against this
correct artifact and stop before board write.
