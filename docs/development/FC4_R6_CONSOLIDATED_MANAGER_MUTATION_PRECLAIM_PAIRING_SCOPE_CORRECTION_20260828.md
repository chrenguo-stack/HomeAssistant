# FC4 R6 Consolidated Manager Mutation Preclaim — Pairing Scope Correction

## Route Lock

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=CONSOLIDATED_MANAGER_MUTATION_EXECUTION
ACTIVE_DETOUR=T1_RUNTIME_BASELINE_RECOVERY
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION
NEW_BRANCH_ALLOWED=false
```

## Observed pre-CLAIM result

The authorized transaction `R6-CONSOLIDATED-MANAGER-SUCCESSOR-MUTATION-20260828-01` reached all exact private-successor, prechange-backup, Broker and FC4 Home Assistant bindings, then stopped before authorization CLAIM with:

```text
FAILURE_STAGE=CLAIM_BOUNDARY_PAIRING_REBIND_TIMEOUT
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
HOMEASSISTANT_MUTATION=false
DYNSEC_MUTATION=false
BOARD_C_ACCESS=false
```

No production mutation occurred and the authorization remains unclaimed/unconsumed.

## Classification

This timeout is classified as an executor / transaction-scope overconstraint, not as a newly proven product defect.

The fresh Board C pairing-pointer precondition belonged to the original monolithic R6 transaction because that transaction continued from Manager recreate directly into Board C Setup Secret import and first-registration operations. The route has since been deliberately decomposed into:

```text
consolidated Manager recreate
-> R6D2 DynSec authority repair
-> Board C first registration
```

The current Manager mutation authorization explicitly excludes Board C access, Setup Secret import, pairing mutation, NODE_ID assignment, credential issuance and application-key/peer-trust state transitions. Therefore requiring a live/fresh Board C `PENDING` pointer before CLAIM couples an out-of-scope physical/product-liveness condition to a Manager-only runtime repair.

## Corrected contract

For the Manager-only mutation transaction:

- retain exact private successor / plan / source Compose / Manager service hash binding;
- retain fresh prechange backup;
- retain exact current Manager, Broker and FC4 Home Assistant runtime binding;
- retain exact DynSec continuation as unclaimed;
- do not require Board C pairing liveness or current PENDING state before CLAIM;
- do not access, reset, flash, reprovision or mutate Board C;
- do not import or change Setup Secret in this transaction;
- recreate exactly one Manager using the frozen successor;
- verify MQTT 8883/TLS transport and the corrected `4 file binds -> 1 common-parent directory bind` topology;
- preserve registration and relay-key mounts;
- leave DynSec untouched;
- allow the expected temporary MQTT `Not authorized` state until the immediately following R6D2 DynSec repair.

The mandatory fresh `CLAIM_BOUNDARY_PAIRING_REBIND` is moved to the Board C first-registration transaction, after the Manager baseline and DynSec authority have been restored. At that later point it again becomes a direct correctness authority because Setup Secret import and pairing completion are in scope.

## Route consequence

```text
PRODUCT_DEFECT_PROVEN=false
EXECUTOR_SCOPE_OVERCONSTRAINT=true
PAIRING_PRECONDITION_MOVED_TO_BOARD_C_TRANSACTION=true
NEW_BRANCH_ALLOWED=false
```

This is a same-route-node executor correction. It does not open a sibling diagnostic or repair branch and does not alter product source.
