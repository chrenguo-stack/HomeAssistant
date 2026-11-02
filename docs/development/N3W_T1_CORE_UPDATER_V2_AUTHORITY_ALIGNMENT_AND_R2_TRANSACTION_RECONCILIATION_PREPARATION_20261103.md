# N3-W T1 Core Updater V2 authority alignment and R2 transaction reconciliation preparation — 2026-11-03

## Current stop

```text
TASK=N3W_T1_CORE_UPDATER_V2_AUTHORITY_ALIGNMENT_AND_R2_TRANSACTION_RECONCILIATION_PREPARATION_20261103_01
STOP=BEFORE_LIVE_TRANSACTION_RECONCILIATION

LIVE_T1_MUTATION=false
R2_TRANSACTION_RECONCILIATION_AUTHORIZED=false
APPLY_RETRY=false
BOARD_ACCESS=false
```

## Repository authority

```text
MAIN=24fbc6cdf9b05796487459ad7cae038c0bdc7d5a
UPDATER_V2_REVIEWED_HEAD=43de966c70d527433a915f40b9b630227531580a
UPDATER_V2_PR=754
UPDATER_V2_MERGE_COMMIT=24fbc6cdf9b05796487459ad7cae038c0bdc7d5a

PACKAGE_RUN_ID=41544508199
PACKAGE_ARTIFACT_ID=13187736541
PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-3539c8f871e2
PACKAGE_ARTIFACT_DIGEST=sha256:e09fb86c8444e0510b0200e759551d3571496064c743b4171992d46ab73babb9
UPDATER_PYZ_SHA256=e92c093c7028d57ddc1e2c9c1eeb3fb97a0791a27b262b472c75482eaa3026bf
MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0
MANAGER_REBUILT=false
```

The reviewed-head package was built from PR #754 exact source, uploaded, re-downloaded, hash-verified, package-binding-verified and executed with `--help` successfully. The reviewed head and merge commit have zero tree drift.

## Live T1 frozen facts

```text
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_RUNTIME=PREDECESSOR_A_HEALTHY
LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED

R2_TRANSACTION_STATUS=FAILED_EMERGENCY
R2_TRANSACTION_PHASE=ROLLBACK_FAILED
R2_AUTHORIZATION_CONSUMED=true
R2_AUTHORIZATION_REPLAY_PERMITTED=false
```

Fresh evidence before PR #754 proved Manager A, HA and Broker healthy with stable listener contract. No later live mutation has been authorized or performed.

## V2 reconciliation semantics

The next live transaction action is **not** a new Manager A->B apply.

First:
1. stage the exact V2 updater package;
2. read-only verify package SHA/binding;
3. run updater status and inspect;
4. prove current binding/runtime is still predecessor A;
5. prove HA/Broker continuity and strict listener readiness;
6. prove transaction remains FAILED_EMERGENCY / ROLLBACK_FAILED.

Only after a fresh read-only PASS may a separate explicit recovery authorization be requested.

Under V2, if predecessor A is already strictly healthy, explicit rollback/recovery must only close the transaction to terminal ROLLED_BACK and report `t1_mutation=false`; it must not restart Manager/HA or rewrite the Manager binding.

After reconciliation:
- fresh status must show `recovery_required=false`;
- transaction must be terminal `ROLLED_BACK`;
- fresh inspect must still prove predecessor A healthy;
- repository authority must remain `NOT_YET_APPLIED`.

Only then may a new A->B apply be planned under another fresh authorization.

## Forbidden

- replay R1 or R2 apply authorization;
- use the pre-V2 updater artifact;
- delete/hand-edit the transaction file;
- manually restart Manager/HA as part of reconciliation;
- change Broker or HA images;
- change host platform;
- access Board firmware/NVS;
- begin a new A->B apply before reconciliation closure.

## Next one gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_R2_TRANSACTION_RECONCILIATION_READONLY_PREFLIGHT_20261103_01
```
