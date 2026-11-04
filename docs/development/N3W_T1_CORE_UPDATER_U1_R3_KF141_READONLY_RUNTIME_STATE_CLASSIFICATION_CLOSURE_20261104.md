# N3-W T1 Core Updater U1 R3 / KF-141 read-only runtime-state classification closure

Date: 2026-11-04

## 1. Gate

```text
TASK=N3W_T1_CORE_UPDATER_U1_R3_KF141_READONLY_RUNTIME_STATE_CLASSIFICATION_20261104_01
RESULT=CLOSED_PASS

PR=777
BRANCH=test/n3w-u1-manager-a-to-b-red-regression-20261104

EXACT_UPDATER_SOURCE_HEAD=fc1e1bee1f158cc199413ead26564938fca5b1a9
EXACT_PACKAGE_ARTIFACT_ID=13336359358
EXACT_PACKAGE_ARTIFACT_DIGEST_SHA256=e786d23deabe5bd6c8eafa4480f7ac13944a2a908d82973f385f7446183c9527
EXACT_UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46

RUNTIME_STATE_EXECUTION_COUNT=1
RUNTIME_STATE_EXIT_CODE=0
RUNTIME_STATE_STATUS=PASS
RUNTIME_STATE_MUTATION=false

UPDATER_APPLY=false
UPDATER_ROLLBACK=false
SERVICE_RESTART=false
TRANSACTION_CHANGED=false
BOARD_ACCESS=false
MERGE=false
```

This gate used the exact repaired updater pyz and executed exactly one
`runtime-state` command against the real T1. The returned document is
machine-readable, status PASS, and explicitly reports `mutation=false`.

No apply, rollback, service restart, transaction edit/delete, board operation,
credential mutation, production authority switch or merge was performed.

## 2. Fresh runtime classification

```text
RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
HEALTH_STATE=HEALTHY
APPLICATION_STATE=running
SERVICES_OWNER_STATE=active

MANAGER_BINDING=local/greenhouse-manager:fresh-b863ddd95909
HOMEASSISTANT_BINDING=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_BINDING=local/n3w-mosquitto:2.1.2-3184566d

MANAGER_RUNNING_COUNT=1
HOMEASSISTANT_RUNNING_COUNT=1
BROKER_RUNNING_COUNT=1

MANAGER_NETWORK_MODE=host
HOMEASSISTANT_NETWORK_MODE=host
BROKER_NETWORK_MODE=n3wfc4-private
```

The fresh real-T1 runtime is therefore the accepted predecessor Manager A,
not target Manager B and not an application-stopped state.

The runtime Manager image is:

```text
MANAGER_RUNTIME_IMAGE_ID=sha256:7c6133d87b9d378acc06ab20813b95d2e27d952f958f3ad33c7de3a4f6e9205e
MANAGER_RUNTIME_CONTRACT_SHA256=ad1d38f6191c0c00afcfbee3ca489d5f95a86fefcb17976c273597c04609d6e1
```

## 3. Fresh health evidence

```text
LISTENER_TCP_8883=1
LISTENER_TCP_47110=1
LISTENER_UDP_47111=1
LISTENER_TCP_47112=0

MANAGER_MQTT_AUTHENTICATED=true
HOMEASSISTANT_MQTT_AUTHENTICATED=true
HOMEASSISTANT_HTTP_STATUS=401

HEALTH_CLASSIFICATION=HEALTHY
```

This matches the repaired KF-141 canonical convergence contract. The current
runtime is structurally supported and soft health has converged.

## 4. Durable transaction remains unchanged

The same read-only response reported the existing durable U1 R3 transaction:

```text
TRANSACTION_SCHEMA=gh.n3w-t1-core-updater-transaction/2
TRANSACTION_STATUS=FAILED_EMERGENCY
TRANSACTION_PHASE=FAILED_EMERGENCY
RECOVERY_REQUIRED=true
AUTHORIZATION_CONSUMED=true
TRANSACTION_CHANGED=false
```

The transaction is evidence of the failed R3 upgrade attempt. It is not the
authority for current runtime binding or current runtime health.

The fresh runtime-state proves:

```text
CURRENT_REAL_MANAGER=PREDECESSOR_A
CURRENT_REAL_MANAGER_HEALTH=HEALTHY
TARGET_B_CURRENTLY_RUNNING=false
APPLICATION_STOPPED=false
CANONICAL_PRODUCTION_AUTHORITY_SWITCHED=false
```

The read-only gate does not reconcile, rewrite, archive or delete the failed
transaction.

## 5. Authorization boundary

```text
R3_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_U1_V2_20261104_02
R3_AUTHORIZATION_CONSUMED=true
R3_AUTHORIZATION_REPLAY_PERMITTED=false

NEW_APPLY_AUTHORIZED=false
ROLLBACK_AUTHORIZED=false
TRANSACTION_RECONCILIATION_AUTHORIZED=false
```

The consumed R3 authorization remains permanently non-replayable.

## 6. Classification

```text
READONLY_RUNTIME_STATE_CLASSIFICATION=CLOSED_PASS
STRUCTURAL_RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
CONVERGENCE_HEALTH=HEALTHY
RUNTIME_DEFECT_PROVEN=false
CURRENT_PRODUCT_RUNTIME_EMERGENCY=false
FAILED_EMERGENCY_LEDGER_RECONCILIATION_REQUIRED=true
```

KF-141's source-level defect remains the proven updater lifecycle defect. The
fresh runtime evidence does not expose a new product runtime defect and does
not contradict the current KF-141 design assumptions.

No new KF is required by this gate.

## 7. Next boundary

```text
NEXT_ROUTE=N3W_T1_CORE_UPDATER_U1_R3_KF141_TRANSACTION_RECONCILIATION_DECISION_20261104_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=true:ANY_TRANSACTION_OR_RUNTIME_MUTATION
STOP=true
```

This closure stops before transaction reconciliation. Any future transaction
write, explicit rollback, service mutation or new Manager A -> B apply requires
a separate gate and fresh authorization.

## 8. Closure

```text
=== N3W_T1_CORE_UPDATER_U1_R3_KF141_READONLY_RUNTIME_STATE_CLASSIFICATION_20261104_01 CLOSURE ===

AUTHORIZATION=NOT_APPLICABLE:READONLY_GATE
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

EXACT_PACKAGE_ARTIFACT_ID=13336359358
EXACT_UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46

RUNTIME_STATE_STATUS=PASS
RUNTIME_CLASS=PREDECESSOR_BOUND_RUNNING
HEALTH_STATE=HEALTHY
MANAGER_BINDING=local/greenhouse-manager:fresh-b863ddd95909
HOMEASSISTANT_RUNTIME_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_RUNTIME_IMAGE=local/n3w-mosquitto:2.1.2-3184566d

TRANSACTION_STATUS=FAILED_EMERGENCY
RECOVERY_REQUIRED=true
RUNTIME_STATE_MUTATION=false
TRANSACTION_CHANGED=false
SERVICE_RESTART=false

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

READONLY_RUNTIME_STATE_CLASSIFICATION=CLOSED_PASS
NEXT_ROUTE=N3W_T1_CORE_UPDATER_U1_R3_KF141_TRANSACTION_RECONCILIATION_DECISION_20261104_01
STOP=true

=== END ===
```
