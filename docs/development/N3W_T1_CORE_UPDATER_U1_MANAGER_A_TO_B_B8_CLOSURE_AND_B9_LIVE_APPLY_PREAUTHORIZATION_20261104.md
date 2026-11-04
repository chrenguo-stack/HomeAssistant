# N3-W T1 Core Updater U1 — B8 closure and B9 live apply preauthorization

Date: 2026-11-04

## 1. Gate position

```text
TASK=N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_B8_CLOSURE_AND_B9_LIVE_APPLY_PREAUTHORIZATION_20261104_01
B8=CLOSED_PASS
B9=ENTERED_PREAUTHORIZATION_ONLY
B10_NOT_ENTERED=true
LIVE_MUTATION_DEFAULT=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## 2. B8 exact closure

Dedicated U1 Pre-U1 simulation CI:

```text
B8_HEAD=1cddb747bc1b780167c3597c35caeedf19bfa3fe
WORKFLOW=N3W T1 Core Updater U1 Pre-U1 Simulation CI
RUN_ID=41830103737
RUN_NUMBER=1
RESULT=SUCCESS
TEST_RESULT=1_PASSED
U1_B8_PACKAGE_ARTIFACT_IDENTITY=PASS
U1_B8_PRE_U1_INSPECT_PLAN_SIMULATION=PASS
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
```

The simulation downloaded the frozen B7 Manager-only package and exercised the real
`CoreUpdater.inspect()`, `CoreUpdater.plan()`, simulated A -> B apply, and simulated B -> A rollback
against a host initialized from the frozen Pre-U1/current-stack authority.

B8 therefore proves:

- current frozen predecessor is Manager A `local/greenhouse-manager:fresh-b863ddd95909`;
- Target B predecessor binding matches that exact A;
- exact Manager B tar verifies;
- inspect and plan are read-only;
- planned mutation is Manager image only;
- Broker, Home Assistant image and host platform are not planned mutations;
- simulated apply commits B;
- simulated rollback restores A;
- no real T1 or board was accessed.

## 3. Exact B7 package authority

```text
PACKAGE_RUN_ID=41829022162
PACKAGE_ARTIFACT_ID=13322275752
PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-5b32e1ae8210
PACKAGE_ARTIFACT_DIGEST_SHA256=720611993fa80c1f29a39399183a2adee790a497292ca07c99bc270524d30366
UPDATER_PYZ_SHA256=0287d7e7d9c27cf50b842d2c39511cae773ed90526527c4c46a4bff6c368c2b2
TARGET_MANIFEST=infra/n3w-t1/upgrades/manager-5b32e1ae8210.json

EXPECTED_PREDECESSOR=local/greenhouse-manager:fresh-b863ddd95909
TARGET_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
TARGET_IMAGE_ID=sha256:80d34358094638ce9c8ce5fb2635fe0a5c75ee7cc5e8c628b38ab223134e585f
MANAGER_TAR_SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa
ROLLBACK_COMPATIBLE=true
MANAGER_REBUILT=false
```

## 4. B9 proposed single-use live authorization

Entering B9 does not itself grant B10 execution.

```text
PROPOSED_APPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_U1_20261104_01
APPLY_CONFIRMATION=T1_CORE_UPDATER_MANAGER_APPLY
APPLY_AUTHORIZATION_GRANTED=false
APPLY_AUTHORIZATION_CLAIMED=false
APPLY_AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
AUTO_EXECUTE_B10=false
```

If explicitly granted later, this authorization permits exactly one Manager A -> B apply transaction
using the exact B7 package and Target B manifest above.

Before the mutation boundary, B10 must freshly run status/inspect/plan with the same exact package and
stop before apply on any predecessor, transaction, target tar, portable image identity, service-owner,
listener, Home Assistant, Broker or other continuity drift.

## 5. Authorized scope after a later explicit grant

Allowed:

```text
- fresh updater status / inspect / plan using exact B7 package
- verify exact target manifest and Manager tar
- verify live predecessor is exact Manager A
- verify rollback is available
- exactly one updater apply A -> B
- stop Manager + Home Assistant only through the production lifecycle owner
- keep Broker independently running
- replace only GH_MANAGER_IMAGE A -> B
- validate effective Compose delta is Manager image only
- start Manager + Home Assistant through the production owner
- capture immediate post-apply status / inspect
```

Forbidden:

```text
- replay any historical authorization
- a second automatic apply attempt after any failure
- blind explicit rollback after failure
- manual updater transaction edit/delete
- Home Assistant image mutation
- Broker image mutation
- host-platform mutation
- credential / DynSec / registration / pairing mutation
- Board access
- firmware / NVS mutation
- merge
```

## 6. Failure boundary

If fresh status/inspect/plan fails, stop before apply and do not claim/consume the live authorization.

If an authorized apply is attempted and fails:

1. capture updater status and inspect;
2. do not blindly run explicit rollback;
3. if terminal `ROLLED_BACK` and Manager A is healthy, freeze evidence and diagnose;
4. if transaction is non-terminal or `recovery_required=true`, stop at recovery boundary;
5. `FAILED_EMERGENCY` is a hard stop requiring a separate recovery authorization.

## 7. B9 stop point

```text
B8=CLOSED_PASS
B9_PREAUTHORIZATION_READY=true
B9_RESULT=AWAITING_EXPLICIT_APPLY_GRANT
B10_REAL_T1_APPLY=false
U1_LIVE_APPLY_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_B10_LIVE_APPLY_AUTHORIZATION_20261104_01
STOP=true
```
