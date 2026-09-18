# N3-W KF-096 PR #431 Exact Artifact Build and Binding — 2026-09-18

Status: `ARTIFACT_BINDING_AUTHORITY`

Fresh repository/build/physical evidence takes precedence if later evidence proves drift.

## Scope

This record closes only the GitHub/host exact-artifact build-and-binding gate for merged PR #431.

No Board A/B access, serial open, flash write, T1 mutation, Broker/Manager/DynSec mutation, credential mutation, or physical validation occurred in this gate.

## Exact product source

```text
REPOSITORY=chrenguo-stack/HomeAssistant

PRODUCT_SOURCE_HEAD=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
PRODUCT_SOURCE_TREE=3f161c1550e1df48db7cd5a5970db1b11932bef0

FINAL_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f

REPOSITORY_MAIN_AT_ARTIFACT_GATE=d0211efcede3dc3d7fd99434180a825176f7e7ae
REPOSITORY_MAIN_TREE_AT_ARTIFACT_GATE=0df0f7d6cf2e73e273aea76b2a25a50163875c52
```

The repository main tip already contains later documentation-only preparation records. The artifact is intentionally bound to the PR #431 merge commit, not to that later documentation-only main tip.

## Build-only workflow authority

```text
BUILD_BRANCH=build/n3w-pr431-boardb-artifact-20260918
WORKFLOW_PATH=.github/workflows/n3w-pr431-boardb-artifact-build.yml
WORKFLOW_SOURCE_COMMIT=f09bcf414e5395f4fbe456c79666cef461ecf0d7
WORKFLOW_CHANGED_PRODUCT_SOURCE=false

FROZEN_WORKFLOW_TEMPLATE_SHA256=
5c5313bb627d50ca8337ebea310c588fefc3b32c5eedd08f99d09fa03b6f6bfc

WORKFLOW_EXACT_TEMPLATE_MATCH=PASS
WORKFLOW_BRANCH_AHEAD_BY=1
WORKFLOW_BRANCH_BEHIND_BY=0
WORKFLOW_ONLY_CHANGED_FILE=
.github/workflows/n3w-pr431-boardb-artifact-build.yml

WORKFLOW_RUN_ID=35339630187
WORKFLOW_RESULT=SUCCESS
```

The build-only branch must not be merged into `main`.

## Exact source / target / toolchain binding

The runner completed all frozen gates:

```text
CHECKOUT_EXACT_PR431_MERGE_SOURCE=PASS
BIND_EXACT_SOURCE_AND_TARGET=PASS
COMPILE_EXACT_SOURCE_PHYSICAL_HARNESS=PASS
VERIFY_ESP_IDF_TOOLCHAIN=PASS
FREEZE_BOARD_B_WRITE_ARTIFACTS=PASS
UPLOAD_EXACT_SOURCE_ARTIFACTS=PASS

SOURCE_HEAD=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
SOURCE_TREE=3f161c1550e1df48db7cd5a5970db1b11932bef0

TARGET_CONFIG=
firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml

TARGET_BLOB_SHA=
3d13e2197520c375b56d682b37773ef28e194421

PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
TARGET_DEVICE=ESP32-C6
TARGET_FLASH_SIZE=8MB
```

## Frozen artifact

```text
ARTIFACT_ID=10544254111
ARTIFACT_NAME=n3w-pr431-boardb-exact-source
ARTIFACT_RUN_ID=35339630187
ARTIFACT_CREATED_AT=2026-09-18T11:30:39Z
ARTIFACT_EXPIRES_AT=2026-09-25T11:30:37Z

ARTIFACT_ZIP_SIZE=725587
ARTIFACT_ZIP_SHA256=
94ff922ce50314ed6f3275376eb5b1e71ae27f27f6edd16f9dd0743259dd13b6

GITHUB_ARTIFACT_DIGEST=
sha256:94ff922ce50314ed6f3275376eb5b1e71ae27f27f6edd16f9dd0743259dd13b6

ARCHIVE_DIGEST_MATCH=PASS
```

The artifact archive was independently downloaded after the workflow completed. Its SHA-256 exactly matches the digest reported by GitHub Actions.

## Frozen inner files

The downloaded archive contained exactly:

```text
MANIFEST.txt
firmware.bin
ota_data_initial.bin
```

No additional file was present.

```text
firmware.bin
APPLICATION_SIZE=1137488
APPLICATION_SHA256=
c6cdab938a58ac1bc29f3a04a69d157acc23625ab239f8a644841de241af3730

ota_data_initial.bin
OTADATA_SIZE=8192
OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

MANIFEST_SIZE=575
MANIFEST_SHA256=
683369c9b9eec7e24d4a864d8b0b3a674c9703ae25abd6abb75c6182f038802d
```

The independently calculated application and otadata hashes match `MANIFEST.txt`.

## Manifest binding

The downloaded manifest records:

```text
SOURCE_HEAD=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
SOURCE_TREE=3f161c1550e1df48db7cd5a5970db1b11932bef0
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_BLOB_SHA=3d13e2197520c375b56d682b37773ef28e194421
PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
WORKFLOW_TRIGGER_SHA=f09bcf414e5395f4fbe456c79666cef461ecf0d7
APPLICATION_SIZE=1137488
OTADATA_SIZE=8192
APPLICATION_SHA256=c6cdab938a58ac1bc29f3a04a69d157acc23625ab239f8a644841de241af3730
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

All frozen source, tree, target, toolchain, trigger, size, and inner-hash fields match the independently recovered evidence.

## Build resource report

```text
RAM_USED=50696
RAM_TOTAL=327680
RAM_USED_PERCENT=15.5

FLASH_USED=1137130
FLASH_TOTAL=3932160
FLASH_USED_PERCENT=28.9
```

The compile completed successfully.

## Binding conclusion

```text
PR431_EXACT_ARTIFACT_BUILD=PASS
PR431_EXACT_ARTIFACT_BINDING=PASS

SOURCE_HEAD_MATCH=PASS
SOURCE_TREE_MATCH=PASS
TARGET_BLOB_MATCH=PASS
WORKFLOW_TEMPLATE_MATCH=PASS
TOOLCHAIN_VERSION_BINDING=PASS
ARTIFACT_MEMBER_SET_MATCH=PASS
ARCHIVE_HASH_FROZEN=true
APPLICATION_HASH_FROZEN=true
OTADATA_HASH_FROZEN=true
MANIFEST_HASH_FROZEN=true
```

This proves source-to-artifact identity only. It does not prove that any board runs this artifact.

## KF-084 reproducibility / artifact identity guard

This exact archive and its inner hashes are now the only PR #431 candidate-artifact authority for the next physical route.

A later rebuild from the same source is a different artifact unless separately rebuilt and rebound with a new record.

The old PR #428 artifact remains historical/non-deployable and must not be substituted for this candidate.

## Physical boundary

```text
BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
T1_MUTATION=false

PR431_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR431_PHYSICAL_VALIDATION=NOT_EXECUTED

KF096_STATUS=OPEN
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

Board B remains on its previously frozen PR #425 artifact.

## Next ONE gate

```text
NEXT_ONE_GATE=N3W_KF096_PR431_BOARD_B_WRITE_TARGET_PREFLIGHT_20260918_01

PRODUCT_SOURCE_AUTHORITY=
d1b5c3acbd32cca95483743ffe2edba9aa3f904f

ARTIFACT_ID=10544254111
APPLICATION_SHA256=
c6cdab938a58ac1bc29f3a04a69d157acc23625ab239f8a644841de241af3730
OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

BOARD_ACCESS_REQUIRED=true
PREFLIGHT_READ_ONLY=true
FLASH_WRITE=false
SERIAL_OPEN=false
T1_MUTATION=false
PHYSICAL_WRITE_AUTHORIZATION_REQUIRED_LATER=true
```

A later preflight requires separate explicit authorization. It must freshly identify the intended Board B and prove target silicon/flash/security state plus exact artifact hash binding before any write.

## Public/private evidence boundary

Public GitHub may store source/tree/blob identifiers, workflow/run/artifact IDs, public-safe hashes, toolchain versions, and sanitized build facts. Raw credentials, setup secrets, private keys, raw NVS, private host addresses, and private board identity material remain outside the public repository.
