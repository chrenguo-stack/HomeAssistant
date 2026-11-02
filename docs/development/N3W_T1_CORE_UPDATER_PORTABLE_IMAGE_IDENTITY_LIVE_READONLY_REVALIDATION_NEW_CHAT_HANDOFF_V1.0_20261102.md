# N3-W T1_Core_Updater portable image identity live read-only revalidation
# New chat handoff V1.0 — 2026-11-02

```text
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.4
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

## 0. Current stage

```text
CURRENT_STAGE=REPLACEMENT_UPDATER_READY_BEFORE_LIVE_READONLY_REVALIDATION
CURRENT_STOP_POINT=BEFORE_REPLACEMENT_PACKAGE_STATUS_INSPECT_PLAN
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_PORTABLE_IMAGE_IDENTITY_LIVE_READONLY_REVALIDATION_20261102_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

## 1. Frozen repository authority

```text
MAIN=c80bd9f1374ca33926cc76acbc2f2e2da1ebb67b
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
EXPECTED_PREDECESSOR=local/greenhouse-manager:fresh-24382caae4a1
MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0

UPDATER_REVIEWED_HEAD=667299b6053822ce56c2b27adb8c3c61cca12542
UPDATER_PR=750
UPDATER_MERGE_COMMIT=c80bd9f1374ca33926cc76acbc2f2e2da1ebb67b

PACKAGE_RUN_ID=41465742145
PACKAGE_ARTIFACT_ID=13151876743
PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-3539c8f871e2
PACKAGE_ARTIFACT_DIGEST=sha256:42d8580c0e8e2f04363a49e4166ef4b8de0729fa4f25c05703594a2b9ad04b1c
UPDATER_PYZ_SHA256=69227fdb2d4778f53513ace1d9065848d7e2ad771c8291f52f0375a99a65c592
```

## 2. Previous live R1 failure

```text
R1_PRE_STATUS=PASS
R1_PRE_INSPECT=PASS
R1_PRE_PLAN_WITH_TAR=PASS
R1_TARGET_IMAGE_PRESTATE=ABSENT

R1_APPLY_RESULT=STOP
R1_REASON=target_image_binding_invalid
R1_TRANSACTION_STATUS=ROLLED_BACK
R1_TRANSACTION_PHASE=ROLLBACK_COMPLETE_PRESTOP
R1_RECOVERY_REQUIRED=false
R1_SERVICES_STOP_BOUNDARY_REACHED=false

R1_AUTHORIZATION_CONSUMED=true
R1_AUTHORIZATION_REPLAY_PERMITTED=false
```

The target image was loaded before the pre-stop rollback. Its current T1 store state must be treated as UNKNOWN_FRESH until the replacement updater proves it by portable identity.

## 3. Source repair closure

```text
KF106_RECURRENCE_SOURCE_REPAIR=CLOSED_PASS
PR750_CI=14/14_SUCCESS
DEDICATED_UPDATER_TESTS=24_PASS

PORTABLE_IDENTITY_AUTHORITY=tools/n3w_t1_portable_image_identity.py
PORTABLE_IDENTITY_BINDS=exact_tar_sha256+rootfs_diff_ids+normalized_config_semantics
BUILD_SIDE_IMAGE_ID=PROVENANCE_ONLY_ACROSS_STORE
T1_LOCAL_RUNTIME_IMAGE_ID=TRANSACTION_RUNTIME_BINDING
```

## 4. Next gate scope

Allowed:

```text
- download/verify exact replacement package on Mac
- bounded tmpfs staging on T1
- updater status
- updater inspect
- updater plan --target-manifest ... --manager-tar ...
- public-safe result capture
```

Forbidden:

```text
- apply
- rollback
- docker load
- service restart/stop/start
- GH_MANAGER_IMAGE rewrite
- credential/DynSec mutation
- Board access
- firmware/NVS mutation
```

## 5. PASS conditions

```text
STATUS.status=PASS
STATUS.recovery_required=false
STATUS.transaction.status=ROLLED_BACK

INSPECT.status=PASS
INSPECT.manager_image=local/greenhouse-manager:fresh-24382caae4a1
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
BROKER_RESTART_COUNT=0

PLAN.status=PASS
PLAN.manager_tar_verified=true
PLAN.target_image_prestate=PRESENT_AND_EXACT
PLAN.rollback_available=true
PLAN.broker_mutation=false
PLAN.homeassistant_image_mutation=false
PLAN.host_platform_mutation=false
```

If target image prestate is ABSENT, STOP and investigate why the previously loaded target disappeared; do not automatically reload it in this read-only gate.

If portable verification fails, STOP; do not delete/reload the target image automatically.

## 6. Closure

```text
GATE_RESULT=
LIVE_MANAGER_IMAGE=
UPDATER_TRANSACTION_STATUS=
TARGET_IMAGE_PRESTATE=
PORTABLE_TARGET_VERIFIED=
MANAGER_TAR_VERIFIED=
ROLLBACK_AVAILABLE=
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

AFTER_PASS_NEXT_STAGE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_APPLY_R2_20261102_01
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true
```

## 7. Start prompt

```text
Read:
- docs/development/N3W_T1_CORE_UPDATER_PORTABLE_IMAGE_IDENTITY_LIVE_READONLY_REVALIDATION_NEW_CHAT_HANDOFF_V1.0_20261102.md
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- infra/n3w-t1/production/t1-core-stack-current.json

Fresh rebind main and execute only:
N3W_T1_CORE_UPDATER_PORTABLE_IMAGE_IDENTITY_LIVE_READONLY_REVALIDATION_20261102_01

Do not apply/rollback, do not restart product services, do not touch Board.
```
