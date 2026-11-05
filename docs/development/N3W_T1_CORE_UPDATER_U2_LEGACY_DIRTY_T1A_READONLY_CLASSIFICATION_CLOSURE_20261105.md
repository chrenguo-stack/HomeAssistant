# N3-W T1 Core Updater U2 legacy/dirty T1_A read-only classification closure

Date: 2026-11-05

## 1. Gate

```text
TASK=N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01
RESULT=CLOSED_PASS

REPOSITORY_MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774
PR779_HEAD_AT_PREFLIGHT=bef7256d647bfc0f254b6b293b6af6108c6dc6fc

T1_A_ACCESS=true
T1_A_MUTATION=false
BOARD_ACCESS=false
APPLY=false
ROLLBACK=false
SERVICE_RESTART=false
TRANSACTION_EDIT=false
TRANSACTION_DELETE=false
CLEANUP=false
IMAGE_LOAD=false
CREDENTIAL_MUTATION=false
```

This closure is based on a fresh read-only inspection of the operator-designated T1_A.
No private locator is stored in the repository.

## 2. Fresh source/package rebind

```text
EXACT_UPDATER_SOURCE_HEAD=fc1e1bee1f158cc199413ead26564938fca5b1a9
CURRENT_MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774
UPDATER_SOURCE_DRIFT=false

EXACT_UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46
EXACT_PYZ_MATCH=true
```

Comparison from the exact updater source head to current main found no changes to the
T1 Core Updater product source. PR #779 remains documentation-only.

## 3. Fresh T1_A runtime classification

Read-only service/runtime observations:

```text
BROKER_ACTIVATION_UNIT=active
SERVICES_ACTIVATION_UNIT=active
REGISTRATION_INGRESS_GUARD=active
BROKER_INGRESS_GUARD=active

MANAGER_RUNNING=true
HOMEASSISTANT_RUNNING=true
BROKER_RUNNING=true

MANAGER_IMAGE=local/greenhouse-manager:fresh-5b32e1ae8210
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d

UPDATER_STATUS=PASS
UPDATER_RUNTIME_STATE=PASS
UPDATER_INSPECT_MANAGER=PASS

CURRENT_RUNTIME_CLASS=TARGET_BOUND_RUNNING
CURRENT_HEALTH_STATE=HEALTHY
RECOVERY_REQUIRED=false
```

The current runtime is the accepted Manager B binding and is healthy. Home Assistant and
Broker remain on the accepted peer bindings.

## 4. Current transaction state

```text
CURRENT_V2_TRANSACTION_PRESENT=true
CURRENT_V2_TRANSACTION_SCHEMA=gh.n3w-t1-core-updater-transaction/2
CURRENT_V2_TRANSACTION_STATUS=COMMITTED
CURRENT_V2_TRANSACTION_PHASE=COMMITTED
CURRENT_V2_TRANSACTION_COMPONENT=manager
CURRENT_V2_AUTHORIZATION_CONSUMED=true

LEGACY_TRANSACTION_PRESENT=false
LEGACY_MANAGER_TRANSACTION_FROM_UPDATER=null
```

There is no active legacy transaction file requiring reconciliation or cleanup.

## 5. Historical transaction disposition

The updater history directory contains six archived transactions:

```text
HISTORY_JSON_COUNT=6
HISTORY_V1_COUNT=5
HISTORY_V2_COUNT=1

HISTORY_NONTERMINAL_COUNT=0
HISTORY_AUTHORIZATION_NOT_CONSUMED_COUNT=0
```

Observed terminal history:

```text
V1_1=ROLLED_BACK / ROLLBACK_COMPLETE_PRESTOP / authorization_consumed=true
V1_2=ROLLED_BACK / RECOVERY_COMPLETE_FAILED_EMERGENCY / authorization_consumed=true
V1_3=ROLLED_BACK / ROLLBACK_COMPLETE / authorization_consumed=true
V1_4=COMMITTED / COMMITTED / authorization_consumed=true
V1_5=COMMITTED / COMMITTED / authorization_consumed=true
V2_1=ROLLED_BACK / ROLLED_BACK / authorization_consumed=true
```

The fresh T1_A therefore no longer contains a current unresolved legacy/dirty transaction.
Historical failed/recovery paths are retained only as terminal history.

## 6. Consumed authorization replay classification

```text
CONSUMED_AUTHORIZATION_PRESENT_IN_CURRENT_TRANSACTION=true
CONSUMED_AUTHORIZATION_PRESENT_IN_ALL_OBSERVED_HISTORY=true
SILENT_HISTORICAL_AUTHORIZATION_REUSE_OBSERVED=false
CONSUMED_AUTHORIZATION_REPLAY_RISK=RESOLVED_BY_EXPLICIT_FRESH_AUTHORIZATION_CONTRACT
```

Direct source review confirms that a new apply receives an explicit authorization identifier
from the caller and records only its hash in the new transaction. The updater does not
automatically select an authorization identifier from a current or archived transaction.
Terminal transactions may be archived before a new apply, but they are not used as an
implicit authorization source.

Important boundary: authorization uniqueness/replay prohibition remains an external
authorization-ledger/execution-contract responsibility. This U2 gate proves that historical
transaction state is not silently reused as authority; it does not claim that the updater
independently provides a global authorization-ID deduplication ledger.

## 7. Legacy/dirty classification

The original plan expected T1_A to remain a preserved legacy/dirty specimen. Fresh evidence
supersedes that historical assumption:

```text
T1_A_PRESERVED_DIRTY_ASSUMPTION=SUPERSEDED_BY_FRESH_EVIDENCE
T1_A_CURRENT_DIRTY_STATE=false
T1_A_HISTORICAL_DIRTY_EVIDENCE_PRESENT=true
T1_A_HISTORICAL_DIRTY_EVIDENCE_TERMINAL=true

LEGACY_STATE_DISPOSITION=NO_ACTION_REQUIRED
BOUNDED_CLEANUP_REQUIRED=false
CURRENT_RUNTIME_REPAIR_REQUIRED=false
```

This is not a false PASS: U2's bounded gate required fresh classification and explicit replay
risk resolution. Both are now available. It did not require manufacturing a dirty state or
mutating T1_A merely to preserve the historical test shape.

## 8. Closure

```text
=== N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01 CLOSURE ===

AUTHORIZATION=N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01
AUTHORIZATION_CLAIMED=NOT_APPLICABLE:READONLY
AUTHORIZATION_CONSUMED=NOT_APPLICABLE:READONLY

LEGACY_TRANSACTION_PRESENT=false
LEGACY_TRANSACTION_TERMINAL=NOT_APPLICABLE_CURRENT_PATH
LEGACY_HISTORY_PRESENT=true
LEGACY_HISTORY_TERMINAL=true

CURRENT_V2_TRANSACTION_PRESENT=true
CURRENT_V2_TRANSACTION_TERMINAL=true
RECOVERY_REQUIRED=false
CURRENT_RUNTIME_CLASS=TARGET_BOUND_RUNNING
CURRENT_HEALTH_STATE=HEALTHY

CONSUMED_AUTHORIZATION_REPLAY_RISK=NO_SILENT_REPLAY_PATH_OBSERVED
LEGACY_STATE_DISPOSITION=NO_ACTION_REQUIRED

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

U2_READONLY_CLASSIFICATION_RESULT=CLOSED_PASS
NEXT_ROUTE=N3W_T1_CORE_UPDATER_HOMEASSISTANT_PRODUCT_GRADE_UPGRADE_VALIDATION_PREPARATION_20261105_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true

=== END ===
```

## 9. Next boundary

U2 is complete. Do not perform cleanup on T1_A. Do not replay any consumed Manager
authorization. Do not reopen Manager U1/KF-141.

The next stage is Home Assistant product-grade upgrade validation preparation, followed only
after its closure by Broker product-grade upgrade validation.
