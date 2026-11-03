# N3-W T1 Core Updater V2 post-reconciliation Manager A -> B preauthorization — 2026-11-03

## 0. Gate

```text
CURRENT_STAGE=POST_RECONCILIATION_MANAGER_A_TO_B_READONLY_PREAUTHORIZATION
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_POST_RECONCILIATION_MANAGER_A_TO_B_READONLY_PREAUTH_20261103_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
APPLY_AUTHORIZED=false
OLD_R1_R2_AUTHORIZATION_REPLAY_PERMITTED=false
```

This gate is read-only. It does not authorize Manager A -> B apply.

## 1. Repository authority

```text
MAIN=5aa000055b3ee48c424ceac4ef6437fb3f98c742
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
EXPECTED_PREDECESSOR=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
TARGET_BUILD_IMAGE_ID=sha256:2a1362b828a1f09b392713ba7fb40e91359e932690e525e4d03fe9873b9c1522
MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0

UPDATER_V2_REVIEWED_HEAD=43de966c70d527433a915f40b9b630227531580a
UPDATER_V2_MERGE_COMMIT=24fbc6cdf9b05796487459ad7cae038c0bdc7d5a
UPDATER_V2_PACKAGE_RUN=41544508199
UPDATER_V2_PACKAGE_ARTIFACT_ID=13187736541
UPDATER_V2_PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-3539c8f871e2
UPDATER_V2_PACKAGE_DIGEST=sha256:e09fb86c8444e0510b0200e759551d3571496064c743b4171992d46ab73babb9
UPDATER_V2_PYZ_SHA256=e92c093c7028d57ddc1e2c9c1eeb3fb97a0791a27b262b472c75482eaa3026bf
UPDATER_V2_ARTIFACT_EXPIRED=false
UPDATER_V2_ARTIFACT_EXPIRES_AT=2026-12-02T23:21:26Z

HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
```

## 2. Reconciliation closure baseline

```text
R2_TRANSACTION_RECONCILIATION=CLOSED_PASS
R2_TRANSACTION_STATUS=ROLLED_BACK
R2_TRANSACTION_PHASE=RECOVERY_COMPLETE_FAILED_EMERGENCY
R2_RECOVERY_REQUIRED=false
R2_RECONCILIATION_T1_MUTATION=false

LAST_FRESH_LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LAST_FRESH_RUNTIME_SNAPSHOT_UNCHANGED=true
LAST_FRESH_MANAGER_RESTART_COUNT=0
LAST_FRESH_HOMEASSISTANT_RESTART_COUNT=0
LAST_FRESH_BROKER_RESTART_COUNT=0
LAST_FRESH_LISTENER_CONTRACT=PASS
```

The stale R2 transaction no longer blocks a new transaction. The prior R1/R2 authorization remains consumed and must not be replayed.

## 3. Required fresh read-only preauthorization evidence

Before any new apply authorization is considered, run the exact V2 package against the real T1 and obtain a fresh:

```text
STATUS=PASS
RECOVERY_REQUIRED=false
TRANSACTION_STATUS=ROLLED_BACK
TRANSACTION_PHASE=RECOVERY_COMPLETE_FAILED_EMERGENCY

INSPECT=PASS
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
BROKER_RESTART_COUNT=0
LISTENER_CONTRACT=PASS

PLAN=PASS
MANAGER_TAR_VERIFIED=true
TARGET_IMAGE_PRESTATE=PRESENT_AND_EXACT
ROLLBACK_AVAILABLE=true
BROKER_MUTATION=false
HOMEASSISTANT_IMAGE_MUTATION=false
HOST_PLATFORM_MUTATION=false
PLAN_MUTATION=false
```

The read-only plan must bind the same exact target Manager tar and must prove the predecessor is still A. Any drift is STOP.

## 4. Proposed new apply authorization

Only after the fresh read-only gate closes PASS may the user separately grant:

```text
PROPOSED_APPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_POST_RECONCILIATION_20261103_01
APPLY_AUTHORIZATION_GRANTED=false
APPLY_AUTHORIZATION_CONSUMED=false
```

This authorization ID is intentionally new. It is not a replay or reinterpretation of R1/R2 authorization.

## 5. Expected apply scope after separate authorization

Allowed only under a later explicit apply authorization:

```text
- verify exact target manifest and Manager tar again
- verify predecessor Manager A again
- verify preexisting Manager B by portable identity
- create a new updater transaction
- stop Manager + Home Assistant through production owner
- keep Broker independent
- replace only GH_MANAGER_IMAGE A -> B
- validate Compose delta is Manager image only
- start Manager + Home Assistant through production owner
- verify Manager B exact runtime binding and non-Manager continuity
```

Forbidden:

```text
- replay old authorization
- mutate Home Assistant image
- mutate Broker image
- mutate host platform
- manual transaction edit/delete
- Board access
- firmware/NVS mutation
- automatic second apply attempt after any failure
```

## 6. Failure handling

If fresh status, inspect or plan fails, stop before apply authorization.

If a future apply fails:
1. capture updater status and inspect;
2. do not issue explicit rollback blindly;
3. if transaction is terminal ROLLED_BACK and predecessor A is healthy, freeze evidence and diagnose;
4. if transaction is non-terminal or recovery_required=true, stop at recovery boundary;
5. if FAILED_EMERGENCY, hard stop and use V2 reconciliation logic only after a separate recovery authorization.

## 7. After future apply PASS

A successful apply is not sufficient to resume Board/R3 immediately. The next separate stage must prove Manager B post-upgrade acceptance and then update repository live-deployment authority from NOT_YET_APPLIED to applied/current B.

Only after that closure may R3 first-registration work resume.
