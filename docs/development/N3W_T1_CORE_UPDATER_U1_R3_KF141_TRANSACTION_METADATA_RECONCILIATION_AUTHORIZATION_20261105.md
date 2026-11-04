# N3-W T1 Core Updater U1 R3 / KF-141 transaction metadata reconciliation authorization

Date: 2026-11-05

## Gate

```text
TASK=N3W_T1_CORE_UPDATER_U1_R3_KF141_TRANSACTION_METADATA_RECONCILIATION_20261105_01

AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_U1_R3_KF141_TRANSACTION_METADATA_RECONCILIATION_20261105_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false

PR=777
BRANCH=test/n3w-u1-manager-a-to-b-red-regression-20261104
FRESH_REBIND_HEAD=01d44d9e44b8cf1c00243ba6f9dd0b97e957be8e
FRESH_REBIND_DRIFT_FROM_PREVIOUS_ARCHIVE=DOCS_ONLY

EXACT_UPDATER_SOURCE_HEAD=fc1e1bee1f158cc199413ead26564938fca5b1a9
EXACT_PACKAGE_ARTIFACT_ID=13336359358
EXACT_PACKAGE_ARTIFACT_DIGEST_SHA256=e786d23deabe5bd6c8eafa4480f7ac13944a2a908d82973f385f7446183c9527
EXACT_UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46
ARTIFACT_EXPIRED=false
ARTIFACT_HEAD_SHA=fc1e1bee1f158cc199413ead26564938fca5b1a9

EXPECTED_PRE_RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
EXPECTED_PRE_HEALTH_STATE=HEALTHY
EXPECTED_PRE_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
EXPECTED_PRE_TRANSACTION_STATUS=FAILED_EMERGENCY

PERMITTED_ROLLBACK_INVOCATIONS=1
PERMITTED_APPLY_INVOCATIONS=0
SERVICE_RESTART_AUTHORIZED=false
BINDING_REWRITE_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MANUAL_TRANSACTION_EDIT_AUTHORIZED=false
MANUAL_TRANSACTION_DELETE_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

## Execution contract

This authorization is one-shot and fail-closed.

Before crossing the transaction-write boundary, the exact updater must perform
a fresh read-only runtime-state guard. The rollback invocation is permitted only
when all of the following remain true:

```text
status=PASS
mutation=false
runtime_class=PREDECESSOR_BOUND_RUNNING
health_state=HEALTHY
manager=local/greenhouse-manager:fresh-b863ddd95909
transaction.status=FAILED_EMERGENCY
```

If any guard differs, the executor must STOP before rollback.

If the guard passes, exactly one updater-owned:

```text
rollback --confirmation T1_CORE_UPDATER_ROLLBACK
```

may be invoked.

The selected source branch validates predecessor identity, peers, and A1 policy,
then writes only the durable transaction to terminal `ROLLED_BACK` with
`t1_mutation=false`. It must not quiesce, rewrite, activate, or restart the
application stack on this branch.

After the single rollback invocation, read-only `status` and
`runtime-state` evidence are permitted and required. No second rollback is
permitted regardless of success or failure.

## PASS postconditions

```text
ROLLBACK_STATUS=PASS
ROLLBACK_TRANSACTION_STATUS=ROLLED_BACK
ROLLBACK_T1_MUTATION=false

POST_STATUS=PASS
POST_RECOVERY_REQUIRED=false
POST_TRANSACTION_STATUS=ROLLED_BACK

POST_RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
POST_HEALTH_STATE=HEALTHY
POST_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
```

## Boundary

The earlier R3 apply authorization remains consumed and replay-forbidden.

This authorization does not authorize a new Manager A -> B apply.

```text
OLD_R3_AUTHORIZATION_REPLAY=false
NEW_APPLY=false
AUTO_RETRY=false
AUTO_SECOND_ROLLBACK=false
STOP_AFTER_SINGLE_EXECUTION_EVIDENCE=true
```

Authority for the selected path:
`docs/development/N3W_T1_CORE_UPDATER_U1_R3_KF141_TRANSACTION_RECONCILIATION_DECISION_20261105.md`.


## Execution closure

```text
EXECUTION_RESULT=CLOSED_PASS
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false

ROLLBACK_INVOCATION_COUNT=1
ROLLBACK_STATUS=PASS
ROLLBACK_TRANSACTION_STATUS=ROLLED_BACK
ROLLBACK_T1_MUTATION=false

POST_RECOVERY_REQUIRED=false
POST_RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
POST_HEALTH_STATE=HEALTHY
POST_MANAGER=local/greenhouse-manager:fresh-b863ddd95909

SECOND_ROLLBACK_ALLOWED=false
NEW_APPLY_ALLOWED=false
STOP=true
```

Closure authority:
`docs/development/N3W_T1_CORE_UPDATER_U1_R3_KF141_TRANSACTION_METADATA_RECONCILIATION_CLOSURE_20261105.md`.
