# N3-W T1 Core Updater U1 R3 / KF-141 transaction reconciliation decision

Date: 2026-11-05

## 1. Gate

```text
TASK=N3W_T1_CORE_UPDATER_U1_R3_KF141_TRANSACTION_RECONCILIATION_DECISION_20261104_01
RESULT=CLOSED_PASS

PR=777
BRANCH=test/n3w-u1-manager-a-to-b-red-regression-20261104

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
TRANSACTION_MUTATION=false
SERVICE_RESTART=false
APPLY=false
ROLLBACK_EXECUTED=false
BOARD_ACCESS=false
MERGE=false
```

This gate is decision-only. It does not access the real T1 and does not mutate
the durable transaction.

## 2. Fresh input authority

The immediately preceding real-T1 read-only classification is authoritative:

```text
RUNTIME_STATE_STATUS=PASS
RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
HEALTH_STATE=HEALTHY
CURRENT_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
CURRENT_MANAGER_IS_PREDECESSOR=true
TARGET_MANAGER_CURRENTLY_RUNNING=false

TRANSACTION_STATUS=FAILED_EMERGENCY
TRANSACTION_PHASE=FAILED_EMERGENCY
RUNTIME_STATE_MUTATION=false
```

Authority:
`docs/development/N3W_T1_CORE_UPDATER_U1_R3_KF141_READONLY_RUNTIME_STATE_CLASSIFICATION_CLOSURE_20261104.md`.

## 3. Candidate reconciliation paths reviewed

### A. Manual edit/delete of upgrade.json

Rejected.

Reasons:

- bypasses updater-owned transaction validation and locking;
- destroys or rewrites forensic evidence outside the state machine;
- is unnecessary because the updater already has a supported recovery path;
- would create a separate operational contract that is not covered by the
  updater source tests.

```text
MANUAL_TRANSACTION_EDIT=REJECTED
MANUAL_TRANSACTION_DELETE=REJECTED
```

### B. Blind service rollback/restart

Rejected.

The fresh runtime already proves the exact predecessor is running and healthy.
Stopping/restarting services or rewriting the Manager binding would add product
risk without solving a runtime problem.

```text
BLIND_RUNTIME_ROLLBACK=REJECTED
SERVICE_RESTART=REJECTED
BINDING_REWRITE=REJECTED
```

### C. Updater-owned explicit rollback with healthy predecessor already running

Selected.

Exact repaired updater source:
`fc1e1bee1f158cc199413ead26564938fca5b1a9`.

The V2 `rollback()` implementation first classifies the current runtime. For
`PREDECESSOR_BOUND_RUNNING` it:

1. waits only if health is not yet HEALTHY;
2. validates the current predecessor binding;
3. validates predecessor image ID and runtime-contract identity;
4. validates peer runtime authority;
5. validates the post A1 policy;
6. updates only the transaction to terminal `ROLLED_BACK`;
7. records `last_runtime_class=PREDECESSOR_BOUND_RUNNING`;
8. records `last_health_state=HEALTHY`;
9. records `t1_mutation=false`;
10. returns without quiescing, rewriting or activating the application stack.

The source test
`test_nonterminal_predecessor_healthy_closes_without_mutation` requires:

```text
transaction_status=ROLLED_BACK
t1_mutation=false
host.events=[]
```

The recovery test for a converging predecessor likewise requires no restart;
the updater waits for health and then closes the transaction without host
events.

```text
SELECTED_RECONCILIATION_PATH=UPDATER_OWNED_EXPLICIT_ROLLBACK
EXPECTED_RUNTIME_BRANCH=PREDECESSOR_BOUND_RUNNING_HEALTHY
EXPECTED_T1_MUTATION=false
EXPECTED_SERVICE_RESTART=false
EXPECTED_BINDING_REWRITE=false
EXPECTED_TRANSACTION_FINAL_STATUS=ROLLED_BACK
```

## 4. recovery_required semantics

No manual `recovery_required` field repair is required.

The exact updater `status()` computes recovery requirement from transaction
terminality:

```text
recovery_required =
  current transaction status not in {COMMITTED, ROLLED_BACK}
  OR legacy transaction status not in {COMMITTED, ROLLED_BACK}
```

Therefore, after a successful metadata-only reconciliation to
`ROLLED_BACK`, the updater status is expected to report:

```text
RECOVERY_REQUIRED=false
```

This should be verified through the updater status result after the authorized
transaction write. It must not be achieved by editing a field manually.

## 5. Transaction preservation and future archive

The V2 state store treats `COMMITTED` and `ROLLED_BACK` as terminal
transactions.

A terminal transaction remains available as the current transaction after
reconciliation. It should NOT be deleted merely to make the state look clean.

On a future separately authorized apply, `V2StateStore.prepare_new()`:

1. rejects a non-terminal current transaction;
2. accepts a terminal current transaction;
3. atomically moves that terminal transaction into the private
   `history/` directory;
4. only then permits creation of the new transaction.

The Pre-U1 V2 simulation covers this terminal-transaction archive behavior.

```text
DELETE_TRANSACTION_AFTER_RECONCILIATION=false
IMMEDIATE_MANUAL_ARCHIVE=false
PRESERVE_TERMINAL_TRANSACTION=true
FUTURE_PREPARE_NEW_ARCHIVES_TERMINAL_TRANSACTION=true
```

## 6. Execution safety contract

The selected execution must be narrow and fail closed.

Before the transaction write:

```text
EXACT_UPDATER_SOURCE_HEAD=fc1e1bee1f158cc199413ead26564938fca5b1a9
EXACT_PACKAGE_ARTIFACT_ID=13336359358
EXACT_UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46
EXPECTED_RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
EXPECTED_HEALTH_STATE=HEALTHY
EXPECTED_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
```

The execution must invoke exactly one updater-owned rollback operation with the
V2 confirmation token. It must not invoke apply, manually edit the transaction,
restart services, rewrite Compose/env, or touch boards.

Postconditions required for PASS:

```text
ROLLBACK_STATUS=PASS
TRANSACTION_STATUS=ROLLED_BACK
T1_MUTATION=false

POST_STATUS=PASS
POST_RECOVERY_REQUIRED=false
POST_TRANSACTION_STATUS=ROLLED_BACK

MANAGER_REMAINS=local/greenhouse-manager:fresh-b863ddd95909
SERVICE_RESTART=false
BINDING_REWRITE=false
```

If the updater reports any runtime class other than the supported predecessor
path, any health/policy/identity validation failure, or returns STOP, execution
must stop without a second rollback attempt.

## 7. Authorization boundary

Even though the selected branch is expected to perform no application/runtime
mutation, it **does write the durable transaction**. That is outside the
completed read-only gate.

The consumed R3 apply authorization must not be reused.

```text
OLD_R3_AUTHORIZATION_REPLAY=false
TRANSACTION_WRITE_REQUIRED=true
NEW_EXPLICIT_AUTHORIZATION_REQUIRED=true
AUTO_EXECUTE=false
```

Proposed one-shot authorization:

```text
N3W_T1_CORE_UPDATER_U1_R3_KF141_TRANSACTION_METADATA_RECONCILIATION_20261105_01
```

Its permitted scope is only:

- exact repaired updater package binding verification;
- one updater-owned `rollback --confirmation T1_CORE_UPDATER_ROLLBACK`;
- only if the updater itself validates the supported predecessor state;
- post-operation updater `status` and read-only runtime verification;
- evidence archive.

It does not authorize a new Manager A -> B apply.

## 8. Decision closure

```text
TRANSACTION_RECONCILIATION_DECISION=CLOSED_PASS
SELECTED_PATH=UPDATER_OWNED_METADATA_ONLY_ROLLBACK_IF_PREDECESSOR_HEALTHY
MANUAL_EDIT=false
MANUAL_DELETE=false
SERVICE_RESTART=false
BLIND_ROLLBACK=false
NEW_APPLY=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U1_R3_KF141_TRANSACTION_METADATA_RECONCILIATION_AUTHORIZATION_20261105_01
NEXT_GATE_AUTHORIZED=false
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```
