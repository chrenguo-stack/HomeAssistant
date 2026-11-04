# N3-W T1 Core Updater U1 R3 / KF-141 post-reconciliation disposition

Date: 2026-11-05

## Gate

```text
TASK=N3W_T1_CORE_UPDATER_U1_R3_KF141_POST_RECONCILIATION_DISPOSITION_20261105_01
RESULT=CLOSED_PASS

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
APPLY=false
ROLLBACK=false
TRANSACTION_WRITE=false
BOARD_ACCESS=false
MERGE=false
```

This gate decides what should follow the successful KF-141 transaction reconciliation.

## Fresh authority

```text
CURRENT_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
CURRENT_RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
CURRENT_HEALTH_STATE=HEALTHY

CURRENT_TRANSACTION_STATUS=ROLLED_BACK
CURRENT_RECOVERY_REQUIRED=false

KF141_SOURCE_REPAIR_PACKAGE=CLOSED_PASS
KF141_TRANSACTION_RECONCILIATION=CLOSED_PASS
KF141_REAL_REPAIRED_A_TO_B_REAPPLY=NOT_EXECUTED
```

The production authority remains healthy Manager A. The failed R3 transaction debt is cleared.

## Exact repaired package remains reusable

```text
EXACT_UPDATER_SOURCE_HEAD=fc1e1bee1f158cc199413ead26564938fca5b1a9
EXACT_PACKAGE_ARTIFACT_ID=13336359358
EXACT_PACKAGE_ARTIFACT_DIGEST_SHA256=e786d23deabe5bd6c8eafa4480f7ac13944a2a908d82973f385f7446183c9527
EXACT_UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46
ARTIFACT_EXPIRED=false
CI_RUN_ID=41854863798
CI_RESULT=SUCCESS
SOURCE_JOB=SUCCESS
EXACT_MANAGER_SLICE_JOB=SUCCESS
PRE_U1_V2_SIMULATION_JOB=SUCCESS
```

Fresh comparison from exact source head to the current PR #777 head shows only documentation/state-record drift. No updater or Manager source changed after the exact package source head.

Therefore rebuilding the exact package is not required before the next live attempt.

## Manager B disposition

The R3 failure is attributed to KF-141 updater readiness/recovery behavior, not to a proven Manager B product defect.

Manager B bytes remain unchanged:

```text
TARGET_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
TARGET_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
MANAGER_TAR_SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa
```

The repaired updater package is specifically bound to this unchanged target and has already passed source tests plus the Pre-U1 V2 simulation.

```text
MANAGER_B_REJECTED=false
MANAGER_B_REBUILD_REQUIRED=false
UPDATER_PACKAGE_REBUILD_REQUIRED=false
```

## Disposition options

### Stop permanently on Manager A

Rejected as the default route.

Manager A is a safe current production state, but stopping here would leave the intended Manager B product repair without real production acceptance and would leave the repaired KF-141 apply path unproven in the exact scenario that exposed it.

### Merge PR #777 now

Rejected.

PR #777 contains the Manager B product repair, updater V2 work, tests, CI changes and closure records. The repaired A -> B live path is not yet accepted. Merging before that acceptance would weaken the current candidate-before-merge discipline.

```text
PR777_MERGE_READY=false
MERGE_BEFORE_R4_LIVE_ACCEPTANCE=false
```

### Execute a fresh repaired A -> B live reapply

Selected.

This is the smallest test that closes the remaining uncertainty:

1. start from the already-proven healthy Manager A runtime;
2. use the same exact repaired updater package;
3. fresh status/runtime-state/inspect/plan before mutation;
4. allow the V2 state store to archive the terminal ROLLED_BACK transaction through its normal prepare_new path;
5. invoke exactly one new A -> B apply under a new one-shot authorization;
6. require bounded canonical convergence and terminal COMMITTED;
7. verify Manager B, Home Assistant and Broker continuity after apply;
8. stop on any failure; no second apply and no blind rollback.

## R4 contract

Proposed next live stage:

```text
STAGE=U1_R4_REPAIRED_A_TO_B_LIVE_REAPPLY
REUSE_EXACT_PACKAGE=true
REBUILD_EXACT_PACKAGE=false

EXPECTED_PRE_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
EXPECTED_PRE_RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
EXPECTED_PRE_HEALTH_STATE=HEALTHY
EXPECTED_PRE_TRANSACTION_STATUS=ROLLED_BACK
EXPECTED_PRE_RECOVERY_REQUIRED=false

TARGET_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210

EXPECTED_POST_TRANSACTION_STATUS=COMMITTED
EXPECTED_POST_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
EXPECTED_POST_HEALTH_STATE=HEALTHY
EXPECTED_HOMEASSISTANT_UNCHANGED=true
EXPECTED_BROKER_UNCHANGED=true
```

The preflight must fail closed before apply on any authority, package, runtime, baseline, peer, service-owner or policy drift.

## Authorization boundary

All previous live authorizations are consumed or otherwise unusable and must not be replayed.

A new one-shot authorization is required for R4.

Proposed authorization:

```text
N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_REAPPLY_U1_R4_20261105_01
```

It is not granted by this disposition gate.

## Decision

```text
POST_RECONCILIATION_DISPOSITION=CLOSED_PASS
SELECTED_ROUTE=R4_REPAIRED_A_TO_B_LIVE_REAPPLY
REUSE_EXACT_PACKAGE=true
REBUILD_REQUIRED=false
MANAGER_B_REBUILD_REQUIRED=false
PR777_MERGE_BEFORE_R4=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U1_R4_MANAGER_A_TO_B_LIVE_REAPPLY_AUTHORIZATION_20261105_01
PROPOSED_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_REAPPLY_U1_R4_20261105_01
AUTHORIZATION_GRANTED=false
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```
