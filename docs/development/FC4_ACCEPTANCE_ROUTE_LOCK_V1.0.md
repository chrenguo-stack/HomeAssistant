# FC4 Acceptance Route Lock V1.0

> Status: active process contract for N3-W / FC4 Final Physical Acceptance.
>
> Purpose: prevent acceptance execution from drifting into unbounded diagnostic, successor, authorization, or repair branches while preserving fail-closed safety.
>
> Scope: process / harness contract only. This document does not change product source, firmware, Manager behavior, Broker policy, pairing semantics, credentials, or production runtime state.

## 1. North-star route

The active FC4 acceptance route is:

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE
  -> T1_RUNTIME_BASELINE_RECOVERY
  -> R6_CONSOLIDATED_MANAGER_SUCCESSOR
  -> R6D2_DYNSEC_AUTHORITY_REPAIR
  -> BOARD_C_FIRST_REGISTRATION
  -> FC4_FINAL_PHYSICAL_ACCEPTANCE_CLOSURE
```

A temporary diagnostic or repair detour is valid only when it restores a prerequisite for the next route node and preserves an explicit return pointer.

## 2. Mandatory Route Lock fields

Every significant FC4 preclaim, successor, mutation executor, failure closure, and acceptance closure must publish these fields:

```text
NORTH_STAR=
CURRENT_ROUTE_NODE=
ACTIVE_DETOUR=
RETURN_TO_ROUTE=
NEW_BRANCH_ALLOWED=
```

If any field is absent at a boundary that can lead to mutation authorization:

```text
ROUTE_LOCK_BINDING=FAIL
```

and no new mutation authorization may be entered from that result.

`ACTIVE_DETOUR=NONE` is valid when execution is directly on the main route.

## 3. One Gate, one route decision

A Gate may contain multiple checks, but it must answer one route-level question only:

```text
May execution advance from CURRENT_ROUTE_NODE to its already-defined successor?
```

A Gate must not use an incidental observation to silently redefine the product goal, create a sibling acceptance route, or expand the acceptance scope.

## 4. Single active detour

At most one active detour may exist at a time.

While `ACTIVE_DETOUR != NONE`:

- a second nested detour is forbidden;
- a new anomaly is first classified inside the current route node;
- the anomaly may create a new route branch only if a distinct product-level blocker is proven and `NEW_BRANCH_ALLOWED=true` has been deliberately established by a route audit;
- executor, parser, selector, oracle, transport, packaging, evidence-serialization, or host-classification defects do not by themselves create product branches.

## 5. Mandatory return pointer

Every detour must declare:

```text
RETURN_TO_ROUTE=<existing route node>
```

A proposed Gate without a return pointer is incomplete and must not execute.

Successful repair closes the detour immediately and returns to the frozen route. Do not continue with opportunistic adjacent checks merely because the execution context is already open.

## 6. Failure classification before route change

A failed Gate must be classified into exactly one primary class before any route modification:

```text
PRODUCT_BLOCKER
INFRASTRUCTURE_BLOCKER
SECURITY_AUTHORITY_BLOCKER
PHYSICAL_HARNESS_DEFECT
EXECUTOR_OR_ORACLE_DEFECT
EVIDENCE_GAP
TRANSIENT_INFRASTRUCTURE_FAILURE
```

Only a proven blocker that changes a prerequisite of the next route node may justify route restructuring.

`UNKNOWN`, `UNPROVEN`, or missing evidence never qualifies as proof of a new blocker.

## 7. Harness / product separation

The following failures are harness/process failures unless independent runtime evidence proves a product defect:

- current-runtime authority selector chose the wrong container or artifact;
- parser, shell, transport adapter, stdin framing, timeout, or platform portability failure;
- an oracle encoded an invalid invariant;
- evidence absence was serialized as boolean false;
- a preclaim hard-coded a runtime value that should have come from the active authority;
- a closure failed before the relevant product state was observed.

The repair for such failures is to correct the current executor / Gate contract while keeping `CURRENT_ROUTE_NODE` unchanged.

## 8. UNKNOWN propagation

Three-state evidence semantics are mandatory:

```text
OBSERVED_TRUE
OBSERVED_FALSE
UNKNOWN_OR_UNPROVEN
```

An unobserved fact cannot be emitted as `false` and cannot satisfy a PASS condition.

An `UNKNOWN_OR_UNPROVEN` result does not authorize a new mutation branch. It either blocks the current Gate or triggers a bounded evidence check inside the same route node.

## 9. Mutation consolidation

When multiple already-proven repairs affect the same component and each independently requires a recreate/restart, they should be consolidated when this reduces state transitions without expanding mutation scope or weakening rollback.

For the current R6 FC4 path, this rule means the planned Manager successor should combine, when all preclaims pass:

```text
Manager MQTT transport correction
+
original R6 four SQLite directory-bind corrections
+
one Manager recreate
```

Broker/DynSec persisted-state mutation remains a separate transaction because it has a different authority object, rollback artifact, and authorization boundary.

## 10. Authorization is permission, not route authority

An authorization means only that a bounded action is permitted if its current claim-boundary preconditions remain true.

It does not prove that the action is still the correct next route step.

An authorization that remains `CLAIMED=false` may be deferred while the route is reconverged. It must not force execution merely because it already exists.

After `AUTHORIZATION_CLAIMED=true`, normal replay rules remain unchanged: the authorization is consumed regardless of success or failure.

## 11. Two-failure fuse

For the same `CURRENT_ROUTE_NODE`:

```text
2 consecutive preclaim / executor failures
```

triggers a mandatory route audit before a third successor is generated.

The audit must answer:

```text
NORTH_STAR_UNCHANGED=?
CURRENT_ROUTE_NODE_STILL_CORRECT=?
FAILURES_PRODUCT_OR_HARNESS=?
ACTIVE_DETOUR_STILL_NECESSARY=?
RETURN_POINTER_STILL_VALID=?
NEW_BRANCH_REQUIRED_AND_PROVEN=?
```

If the failures are harness/oracle defects and the route remains correct, the next executor is a corrected successor of the same route node, not a new sibling stage.

## 12. New-branch rule

Default during FC4 acceptance:

```text
NEW_BRANCH_ALLOWED=false
```

A new branch may be created only when all of the following are true:

1. a new product-level prerequisite failure is directly proven;
2. it cannot be resolved within the current route node without changing the mutation authority or product objective;
3. the existing return pointer remains defined;
4. a route audit explicitly sets `NEW_BRANCH_ALLOWED=true` for that one branch;
5. the branch has a bounded exit condition and may not spawn another nested branch.

After that branch closes, `NEW_BRANCH_ALLOWED` returns to `false`.

## 13. No opportunistic scope expansion

The following pattern is prohibited:

```text
observed adjacent anomaly
  -> "while we are here" investigation
  -> additional repair
  -> additional authorization
```

unless the anomaly blocks the already-defined next route node.

Acceptance execution is not a general system cleanup exercise.

## 14. Route-node closure contract

A successful route node must state at minimum:

```text
ROUTE_NODE_RESULT=PASS
ACTIVE_DETOUR_CLOSED=true|false
NEXT_ROUTE_NODE=
NEW_BRANCH_ALLOWED=false
```

If a detour closed, the next node must equal the previously frozen `RETURN_TO_ROUTE` or an already-defined intermediate node on that route.

## 15. Current FC4 lock state

At adoption of V1.0, the intended lock is:

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=R6_CONSOLIDATED_MANAGER_SUCCESSOR_PRECLAIM
ACTIVE_DETOUR=T1_RUNTIME_BASELINE_RECOVERY
RETURN_TO_ROUTE=BOARD_C_FIRST_REGISTRATION
NEW_BRANCH_ALLOWED=false
```

The current consolidated Manager work is intended to produce one Manager successor, then return to the already-preclaimed bounded DynSec authority repair, then resume Board C first registration.

No S1C/S1D/R6D3-style sibling diagnostic chain is intended unless a new product-level blocker is independently proven under this contract.

## 16. Relationship to other project guards

This contract complements rather than replaces:

- exact source / artifact binding;
- single-authority rules;
- fail-closed authorization claim boundaries;
- UNKNOWN propagation;
- public-repository safety;
- current-runtime authority discrimination;
- DynSec rollback ownership;
- physical-harness preclaim completeness;
- known-failure and regression-guard indexing.

If Route Lock conflicts with a stronger safety rule, the stronger safety rule wins; execution stops rather than bypassing the safety rule.

## 17. Future machine enforcement

A future repository guard should be allowed to check FC4 executor/closure templates for the five mandatory Route Lock fields and fail CI when a mutation-capable FC4 artifact omits them.

Until that machine guard is implemented, V1.0 is a mandatory review/execution contract and must be explicitly checked before issuing a new FC4 mutation authorization.
