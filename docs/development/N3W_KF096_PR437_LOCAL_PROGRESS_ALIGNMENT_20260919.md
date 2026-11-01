# N3-W KF-096 PR #437 Local Progress Alignment — 2026-09-19

Status: `CURRENT_PROGRESS_ALIGNMENT`

Fresh repository, build, runtime, and physical evidence takes precedence if later evidence proves drift.

## Scope

This record aligns the locally recovered KF-096 progress with GitHub after the PR #437 Direct-recovery repair, repository branch cleanup, and exact-artifact build/binding.

This alignment does not merge PR #437, access Board B, open serial, flash firmware, mutate T1, or close KF-096.

## Repository authority at alignment start

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

REPOSITORY_MAIN_AT_ALIGNMENT_START=
d9afc55b04042806ed8b6e1b1ae3553742aba2be

MERGED_PRODUCT_SOURCE_AUTHORITY=
d1b5c3acbd32cca95483743ffe2edba9aa3f904f

FROZEN_DEPLOYED_PRODUCT_SOURCE_HEAD=
096528fbf61948d6c69197f1c8994ce8e7d672f4

FROZEN_DEPLOYED_PRODUCT_SOURCE_TREE=
6cfa25f5168fc720590f186871c038e3d4a5307f
```

PR #431 remains the latest merged product-source authority. Board B still runs the frozen PR #425 artifact.

## PR #437 successor candidate

```text
PR437_STATE=OPEN_DRAFT
PR437_HEAD=
cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c

PR437_SOURCE_TREE=
b459fae0a054d45b0d09e60bffae9769e060a5c0

PR437_BASE_MAIN=
d9afc55b04042806ed8b6e1b1ae3553742aba2be

PR437_FINAL_GREENHOUSE_MANAGER_CI_RUN=
35373202121

PR437_HEAD_WORKFLOW_COUNT=11
PR437_HEAD_WORKFLOW_SUCCESS_COUNT=11
```

The successor repairs Direct recovery liveness and deadline handling without changing the overall single-radio architecture.

The source-level blockers recovered during local review are closed at the current exact HEAD:

```text
A1_PHASE_DEADLINE_LATE_PROGRESS_BYPASS=CLOSED
A2_ABSOLUTE_DEADLINE_SUCCESS_PATH_BYPASS=CLOSED
A3_BSSID_WALLCLOCK_EXPIRY_INTEGRATION_GAP=CLOSED
DIRECT_COMMIT_AFTER_ABSOLUTE_DEADLINE=CLOSED

FINAL_SOURCE_REVIEW=PASS
NEW_SOURCE_BLOCKER_FOUND=false
```

PR #437 metadata has been aligned from the original RED-test description to the current production-repair scope. PR #437 remains draft and unmerged.

## Repository cleanup alignment

The recent N3-W branch cleanup was completed before this alignment:

```text
RECENT_MERGED_BRANCHES_DELETED=18
PR436_STATE=CLOSED_SUPERSEDED
PR436_MERGED=false
PR437_BRANCH_PRESERVED=true
HISTORICAL_ARTIFACT_BUILD_BRANCHES_PRESERVED=true
```

PR #436 is bound to the historical PR #431 artifact and must not be used for PR #437 Board B validation.

## PR #437 exact artifact

The exact-source artifact build/binding gate passed.

```text
BUILD_BRANCH=
build/n3w-pr437-boardb-artifact-20260919

WORKFLOW_SOURCE_COMMIT=
f5dfdad292a1a9263a7f433b759a6def4d3d1153

WORKFLOW_RUN_ID=
35414060819

WORKFLOW_RESULT=SUCCESS

ARTIFACT_ID=
10575077512

ARTIFACT_NAME=
n3w-pr437-boardb-exact-source

ARTIFACT_CREATED_AT=
2026-09-19T01:58:22Z

ARTIFACT_EXPIRES_AT=
2026-09-26T01:58:22Z

ARTIFACT_ZIP_SIZE=727532

ARTIFACT_ZIP_SHA256=
b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814
```

Exact source / target / toolchain binding:

```text
SOURCE_HEAD=
cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c

SOURCE_TREE=
b459fae0a054d45b0d09e60bffae9769e060a5c0

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

Frozen inner artifact identity:

```text
APPLICATION_SIZE=1139600
APPLICATION_SHA256=
407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb

OTADATA_SIZE=8192
OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

MANIFEST_SIZE=575
MANIFEST_SHA256=
98a6dec323e8057a30d6b1e332d549fe54288f3b45fcbbbf460292871f7a91a0

ARTIFACT_MEMBER_SET_MATCH=PASS
ARCHIVE_DIGEST_MATCH=PASS
INNER_HASH_BINDING=PASS
```

The PR #431 artifact remains frozen historical evidence. It is not the current PR #437 physical-validation candidate.

## Physical boundary

```text
BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
T1_ACCESS=false

BOARD_B_CURRENT_DEPLOYED_SOURCE=
096528fbf61948d6c69197f1c8994ce8e7d672f4

PR437_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR437_PHYSICAL_VALIDATION=NOT_EXECUTED

KF096_STATUS=OPEN
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

Artifact binding proves source-to-binary identity only. It does not prove physical behavior.

## Current route

The historical PR #436 write executor is superseded because it is hard-bound to the PR #431 artifact. A PR #437-specific preflight/write executor must be rebound to the new artifact before any Board B access.

```text
NEXT_ONE_GATE=
N3W_KF096_PR437_BOARD_B_WRITE_PREFLIGHT_EXECUTOR_PREPARATION_20260919_01

CURRENT_CANDIDATE_SOURCE_HEAD=
cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c

CURRENT_CANDIDATE_ARTIFACT_ID=
10575077512

BOARD_ACCESS_REQUIRED=false
FLASH_WRITE=false
T1_MUTATION=false
```

## Public/private evidence boundary

Public GitHub may store source/tree/blob identifiers, workflow/run/artifact IDs, public-safe hashes, sanitized timing/acceptance results, and architecture decisions. Raw credentials, setup secrets, private keys, raw NVS, private host addresses, and raw board identity material remain outside the public repository.
