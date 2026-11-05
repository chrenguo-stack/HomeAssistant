# N3-W T1 Core Updater U1 R4 post-merge canonical authority promotion

Date: 2026-11-05

## Result

```text
TASK=N3W_T1_CORE_UPDATER_U1_R4_POST_MERGE_CANONICAL_AUTHORITY_PROMOTION_20261105_01
RESULT=SOURCE_CANDIDATE_READY_FOR_CI

PR777_MERGED=true
PR777_FROZEN_HEAD=304ac2401ff930e5b0a8d19636ed4e1073c81f63
PR777_MERGE_COMMIT=62e498e2eefb9b5eedb70529b07e7354bd2921dc

T1_MUTATION=false
BOARD_ACCESS=false
NEW_APPLY=false
NEW_ROLLBACK=false
```

## Accepted live authority

The R4 real T1 acceptance is already CLOSED_PASS:

```text
LIVE_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
LIVE_RUNTIME_CLASS=TARGET_BOUND_RUNNING
LIVE_HEALTH_STATE=HEALTHY
LIVE_TRANSACTION_STATUS=COMMITTED
LIVE_TRANSACTION_PHASE=COMMITTED
LIVE_RECOVERY_REQUIRED=false
HOMEASSISTANT_UNCHANGED=true
BROKER_UNCHANGED=true
KF141=CLOSED_PASS
```

A fresh read-only Docker inspection after PR #777 merge proved the exact T1-local runtime identity:

```text
MANAGER_CONTAINER=/n3wfc4-manager-1
MANAGER_IMAGE_REF=local/greenhouse-manager:fresh-5b32e1ae8210
MANAGER_RUNTIME_IMAGE_ID=sha256:228a42a8b14f36694cca6778b18c7be880def25c567ea5492a9e2a40a8ce912e
```

No service restart, image load, binding rewrite or other T1 mutation was used to obtain this value.

## Build identity versus runtime identity

The accepted Manager B exact artifact retains its portable/build identity:

```text
TARGET_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
TARGET_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
MANAGER_BUILD_IMAGE_ID=sha256:80d34358094638ce9c8ce5fb2635fe0a5c75ee7cc5e8c628b38ab223134e585f
MANAGER_TAR_SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa
```

The build image ID and T1-local runtime image ID are deliberately represented as different authority fields. The runtime ID must not be replaced by the build image ID.

## Exact repaired updater provenance

```text
UPDATER_REVIEWED_HEAD=fc1e1bee1f158cc199413ead26564938fca5b1a9
PACKAGE_RUN_ID=41854863798
PACKAGE_ARTIFACT_ID=13336359358
PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-v2-5b32e1ae8210
PACKAGE_ARTIFACT_DIGEST=sha256:e786d23deabe5bd6c8eafa4480f7ac13944a2a908d82973f385f7446183c9527
UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46
TARGET_SCHEMA=gh.n3w-t1-core-updater-target/2
TRANSACTION_SCHEMA=gh.n3w-t1-core-updater-transaction/2
BASELINE_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
```

## Repository promotion

The canonical manifest is promoted from predecessor Manager A `fresh-b863ddd95909` to accepted Manager B `fresh-5b32e1ae8210`.

The promotion preserves:
- immutable historical Clean Reference;
- Home Assistant image authority;
- Broker image authority;
- manager-only mutation scope;
- prior accepted business-state evidence;
- exact PR #777 merge provenance.

The authority checker is minimally evolved from Manager-target schema `/1` to the current component-target schema `/2`. It verifies V2 target source, image, platform, archive SHA, predecessor, Manager build image identity, and the final KF-141/live runtime state.

## CI boundary

This document is not itself evidence that the promotion is merged to main.

```text
CANONICAL_PROMOTION_CANDIDATE=true
CANONICAL_PROMOTION_CI=NOT_YET_EXECUTED
CANONICAL_PROMOTION_MERGED_TO_MAIN=false
```

The next step is a dedicated repository-only PR and CI. No T1 or board access is required.
