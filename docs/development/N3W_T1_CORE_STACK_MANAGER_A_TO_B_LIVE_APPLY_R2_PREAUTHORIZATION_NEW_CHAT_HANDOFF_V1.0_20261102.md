# N3-W T1_Core_Stack Manager A -> B live apply R2
# Preauthorization new chat handoff V1.0 — 2026-11-02

```text
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.4
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

## 0. Current stop point

```text
CURRENT_STAGE=MANAGER_A_TO_B_R2_LIVE_APPLY_PREAUTHORIZATION
CURRENT_STOP_POINT=BEFORE_LIVE_APPLY_R2
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_APPLY_R2_20261102_01

LIVE_APPLY_AUTHORIZED=false
OLD_R1_AUTHORIZATION_REPLAY_PERMITTED=false
BOARD_ACCESS=false
```

## 1. Repository authority

```text
MAIN=9a606e579e3431d2e37e1f4378dab80b10f794f8
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd

EXPECTED_PREDECESSOR=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
TARGET_BUILD_IMAGE_ID=sha256:2a1362b828a1f09b392713ba7fb40e91359e932690e525e4d03fe9873b9c1522
MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0

UPDATER_REVIEWED_HEAD=667299b6053822ce56c2b27adb8c3c61cca12542
PACKAGE_RUN_ID=41465742145
PACKAGE_ARTIFACT_ID=13151876743
PACKAGE_ARTIFACT_DIGEST=sha256:42d8580c0e8e2f04363a49e4166ef4b8de0729fa4f25c05703594a2b9ad04b1c
UPDATER_PYZ_SHA256=69227fdb2d4778f53513ace1d9065848d7e2ad771c8291f52f0375a99a65c592

HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
```

## 2. R1 frozen failure

```text
R1_APPLY_RESULT=STOP
R1_REASON=target_image_binding_invalid
R1_TRANSACTION_STATUS=ROLLED_BACK
R1_TRANSACTION_PHASE=ROLLBACK_COMPLETE_PRESTOP
R1_RECOVERY_REQUIRED=false
R1_SERVICES_STOP_BOUNDARY_REACHED=false
R1_AUTHORIZATION_CONSUMED=true
R1_AUTHORIZATION_REPLAY_PERMITTED=false
```

R1 loaded Manager B into the T1 image store, then falsely rejected it because the old updater compared build-side Docker ID directly with T1 Docker 29/containerd runtime ID.

## 3. Replacement updater closure

```text
PR750_SOURCE_REPAIR=CLOSED_PASS
PR750_CI=14/14_SUCCESS
PR750_DEDICATED_TESTS=24_PASS
PR750_MERGE_COMMIT=c80bd9f1374ca33926cc76acbc2f2e2da1ebb67b

PORTABLE_IDENTITY_AUTHORITY=tools/n3w_t1_portable_image_identity.py
PORTABLE_IDENTITY_BINDS=exact_tar_sha256+rootfs_diff_ids+normalized_config_semantics
```

## 4. Fresh real-T1 read-only revalidation

```text
LOCAL_REPLACEMENT_PACKAGE_BINDING=PASS

STATUS=PASS
RECOVERY_REQUIRED=false
TRANSACTION_STATUS=ROLLED_BACK
TRANSACTION_PHASE=ROLLBACK_COMPLETE_PRESTOP
AUTHORIZATION_CONSUMED=true

INSPECT=PASS
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
BROKER_RESTART_COUNT=0

PLAN=PASS
MANAGER_TAR_VERIFIED=true
TARGET_IMAGE_PRESTATE=PRESENT_AND_EXACT
ROLLBACK_AVAILABLE=true
BROKER_MUTATION=false
HOMEASSISTANT_IMAGE_MUTATION=false
HOST_PLATFORM_MUTATION=false
MUTATION=false

PORTABLE_IDENTITY_REVALIDATION=PASS
KF106_LIVE_REVALIDATION=CLOSED_PASS
```

This is real-T1 proof that the preexisting Manager B image is exact in portable content and does not need to be deleted or reloaded before R2.

## 5. R2 authorized mutation scope

Only after a fresh explicit authorization:

```text
AUTHORIZED_SCOPE=
- consume a new R2 authorization ID
- verify exact tar again
- verify predecessor A again
- verify preexisting Manager B by portable identity
- stop Manager + Home Assistant through production owner
- keep Broker independent
- replace only GH_MANAGER_IMAGE A -> B
- validate Compose delta is Manager image only
- start Manager + Home Assistant through production owner
- verify Manager B and non-Manager continuity
```

Forbidden:

```text
- replay R1 authorization
- mutate HA image
- mutate Broker image
- mutate host platform
- Board access
- firmware/NVS mutation
- auto-run explicit rollback after a successful COMMITTED apply
```

## 6. R2 expected success

```text
APPLY.status=PASS
TRANSACTION_STATUS=COMMITTED
TRANSACTION_PHASE=COMMITTED
RECOVERY_REQUIRED=false

LIVE_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
TARGET_RUNTIME_IMAGE_ID=T1_LOCAL_VERIFIED_ID
MANAGER_RESTART_COUNT=0

HOMEASSISTANT_IMAGE_UNCHANGED=true
BROKER_IMAGE_UNCHANGED=true
BROKER_RESTART_COUNT=0

TCP_8883=1
TCP_47110=1
UDP_47111=1
TCP_47112=0
```

Home Assistant is expected to be recreated/restarted by the production owner together with Manager, while its image identity must remain unchanged. Broker must remain independent and continuous.

## 7. Failure handling

If apply returns nonzero or STOP:

1. always capture updater `status`;
2. always capture updater `inspect`;
3. do not issue explicit rollback blindly;
4. if transaction is terminal `ROLLED_BACK` and A is healthy, freeze failure evidence and diagnose;
5. if transaction is non-terminal or `recovery_required=true`, STOP at recovery boundary;
6. if `FAILED_EMERGENCY`, hard STOP.

## 8. After R2 PASS

Do not resume Board/R3 immediately.

Next required stage is a separate Manager-B post-upgrade live acceptance:
- Manager B exact runtime binding;
- HA/Broker continuity;
- listener/service owner state;
- updater COMMITTED transaction;
- no unexpected mutation;
- then repository live-deployment authority update from `NOT_YET_APPLIED` to applied/current B.

Only after that closure may R3 first-registration work resume.

## 9. Authorization boundary

```text
LIVE_APPLY_R2_AUTHORIZED=false
NEW_AUTHORIZATION_REQUIRED=true
```

The required explicit user authorization should unambiguously authorize:
`N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_APPLY_R2_20261102_01`.

