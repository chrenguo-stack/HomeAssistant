# N3-W Production Multi-Relay Gateway Selection V1
## Exact Artifact Build and Binding — 2026-09-22

> **Physical-use correction — 2026-09-22**
>
> Subsequent physical-validation preparation proved that artifact `10691518958`
> compiled `firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml`,
> which loads the historical `greenhouse_n3w_core`, not the R2-modified
> `greenhouse_n3w_product_core`.
>
> Therefore the archive/hash binding below remains valid as a record of what was
> built, but the artifact is **not valid for Gateway Selection V1 physical use**.
>
> ```text
> INTENDED_PRODUCT_TARGET_BINDING=FAIL
> ARTIFACT_10691518958_PHYSICAL_USE=FORBIDDEN
> CORRECT_TARGET=firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
> ```
>
> Authoritative correction:
> `docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_VALIDATION_PREPARATION_20260922.md`

Status: `ARTIFACT_BINDING_AUTHORITY`

## Scope

This record closes:

```text
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_EXACT_ARTIFACT_BUILD_AND_BINDING_20260922_01
```

The gate built and independently bound a fresh exact artifact from the source that passed R2 CI and independent Astra source review.

No board access, serial open, flash write, NVS/OTA-data write, T1 access, Manager/Broker mutation, or physical RF validation occurred.

## Exact source authority

```text
SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

SOURCE_REVIEW_R2=PASS
R1_BLOCKER_1_LOCAL_FAULT_CONSUMPTION=CLOSED
R1_BLOCKER_2_RESOURCE_AND_TRANSACTION_BOUNDS=CLOSED
R1_BLOCKER_3_ACCEPT_DEADLINE_ORDERING=CLOSED

SOURCE_REVIEW_R2_CLOSURE=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_R2_CLOSURE_20260922.md
```

## Exact target binding

```text
TARGET_CONFIG=
firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml

TARGET_BLOB_SHA=
37654481747b21ca51ccecc246bf84ca437ab7a9

TARGET_DEVICE=ESP32-C6
TARGET_FLASH_SIZE=8MB
TARGET_FRAMEWORK=ESP-IDF

PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

## Build-only branch

```text
BUILD_BRANCH=
build/n3w-production-gwsel-v1-r2-artifact-20260922

BUILD_BRANCH_HEAD=
a54108c1482135c77f2bd4a8105e2fa756bc8375

BUILD_BRANCH_TREE=
76269541670db05dd53b5507c7917f8096d34060

BUILD_BRANCH_PARENT=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

BUILD_BRANCH_PARENT_MATCH=PASS
BUILD_BRANCH_AHEAD_BY=1
BUILD_BRANCH_BEHIND_BY=0
BUILD_BRANCH_CHANGED_FILE_COUNT=1
BUILD_BRANCH_CHANGED_FILE=
.github/workflows/n3w-production-gwsel-v1-r2-artifact-build.yml

BUILD_BRANCH_DIFF_ALLOWLIST=PASS
WORKFLOW_BLOB_SHA=
3c96e11d08703f0d19c9bbd58f98df720d050aa2
```

The build-only branch changed no product source.

The workflow explicitly checked out `SOURCE_HEAD=8c445f2b...` and fail-closed on source HEAD, source tree, and target blob mismatch before compile.

## Build workflow authority

```text
WORKFLOW_RUN_ID=
35722701651

WORKFLOW_RUN_EVENT=push
WORKFLOW_RUN_HEAD_SHA=
a54108c1482135c77f2bd4a8105e2fa756bc8375

WORKFLOW_RUN_RESULT=SUCCESS
```

All relevant steps passed:

```text
Checkout exact R2 source=PASS
Bind exact source and target=PASS
Install exact ESPHome=PASS
Compile exact-source physical harness=PASS
Verify ESP-IDF toolchain=PASS
Freeze exact candidate artifacts=PASS
Upload exact-source artifacts=PASS
```

## Frozen GitHub artifact

```text
ARTIFACT_ID=
10691518958

ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-exact-source

ARTIFACT_SIZE_BYTES=
731025

ARTIFACT_CREATED_AT=
2026-09-22T11:43:42Z

ARTIFACT_EXPIRES_AT=
2026-09-29T11:43:41Z

ARTIFACT_EXPIRED=false

GITHUB_ARTIFACT_DIGEST_SHA256=
cfe05f3d1c51f95f3549ee5874423757e4ed213513472ae30c6c53f8256437ef
```

## Independent download and archive verification

Artifact `10691518958` was independently downloaded after the workflow completed.

```text
INDEPENDENT_ARCHIVE_SIZE=
731025

INDEPENDENT_ARCHIVE_SHA256=
cfe05f3d1c51f95f3549ee5874423757e4ed213513472ae30c6c53f8256437ef

ARCHIVE_DIGEST_MATCH_GITHUB_METADATA=PASS

ARTIFACT_MEMBER_COUNT=3
ARTIFACT_MEMBER_SET_MATCH=PASS

ARTIFACT_MEMBER_1=MANIFEST.txt
ARTIFACT_MEMBER_2=firmware.bin
ARTIFACT_MEMBER_3=ota_data_initial.bin
```

## Frozen inner files

```text
MANIFEST_SIZE=
575

MANIFEST_SHA256=
2eb94caf60498a724ed2ff9d74598ba2b61c45f2cf8a10ef131cb43b830425ae

APPLICATION_SIZE=
1145984

APPLICATION_SHA256=
5e0dc5d950061dd6685b11ee972090036a5af6d576920621550582d216ce38e6

OTADATA_SIZE=
8192

OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Independent hashes exactly match `MANIFEST.txt`.

## Manifest binding

The downloaded manifest records:

```text
SOURCE_HEAD=8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c
SOURCE_TREE=e9c0216c4a25e99038ff81e54036455cb32b4181
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_BLOB_SHA=37654481747b21ca51ccecc246bf84ca437ab7a9
PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
WORKFLOW_TRIGGER_SHA=a54108c1482135c77f2bd4a8105e2fa756bc8375
APPLICATION_SIZE=1145984
OTADATA_SIZE=8192
APPLICATION_SHA256=5e0dc5d950061dd6685b11ee972090036a5af6d576920621550582d216ce38e6
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Independent comparison:

```text
SOURCE_HEAD_MATCH=PASS
SOURCE_TREE_MATCH=PASS
TARGET_CONFIG_MATCH=PASS
TARGET_BLOB_MATCH=PASS
PYTHON_VERSION_BINDING=PASS
ESPHOME_VERSION_BINDING=PASS
ESP_IDF_VERSION_BINDING=PASS
WORKFLOW_TRIGGER_SHA_MATCH=PASS
APPLICATION_SIZE_HASH_MATCH=PASS
OTADATA_SIZE_HASH_MATCH=PASS
MANIFEST_MATCH=PASS
```

## Artifact identity guard

This archive and its inner hashes are the frozen candidate identity for the next physical route.

A later rebuild from the same source is a new artifact and must not silently replace this artifact authority.

## Physical and product boundaries

```text
EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS

BOARD_ACCESS=false
SERIAL_OPEN=false
BOARD_RESET=false
FLASH_WRITE=false
NVS_WRITE=false
OTA_DATA_WRITE=false

PHYSICAL_RF_VALIDATION=NOT_EXECUTED
THREE_BOARD_GATEWAY_SELECTION_PHYSICAL_ACCEPTANCE=NOT_PROVEN

REAL_SENSOR_DATA_USED_IN_CURRENT_COMMUNICATION_PHYSICAL_TEST=false
REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN

T1_ACCESS=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
MERGE=false
```

## Gate closure

```text
=== N3W PRODUCTION MULTI RELAY GATEWAY SELECTION V1 EXACT ARTIFACT BINDING ===

SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

WORKFLOW_RUN_ID=
35722701651

ARTIFACT_ID=
10691518958

ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-exact-source

ARCHIVE_SHA256=
cfe05f3d1c51f95f3549ee5874423757e4ed213513472ae30c6c53f8256437ef

APPLICATION_SHA256=
5e0dc5d950061dd6685b11ee972090036a5af6d576920621550582d216ce38e6

OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS

AUTO_BOARD_WRITE=false
AUTO_PHYSICAL_EXECUTION=false
AUTO_MERGE=false
STOP=true
```

## Proposed next gate

The next route should prepare the physical validation plan and exact target-board preflight before any flash write.

```text
PROPOSED_NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_VALIDATION_PREPARATION_20260922_01

ARTIFACT_ID=
10691518958

BOARD_ACCESS=false
FLASH_WRITE=false
PHYSICAL_MUTATION=false
AUTO_EXECUTE_NEXT_GATE=false
```
