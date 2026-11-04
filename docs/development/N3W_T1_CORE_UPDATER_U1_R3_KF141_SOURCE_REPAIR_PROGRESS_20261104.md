# N3-W T1 Core Updater U1 R3 / KF-141 source repair progress

Date: 2026-11-04

## 1. Current gate

```text
TASK=N3W_T1_CORE_UPDATER_U1_R3_KF141_SOURCE_REPAIR_20261104_01
PR=777
BRANCH=test/n3w-u1-manager-a-to-b-red-regression-20261104

R3_REAL_APPLY_INVOKED=true
R3_AUTHORIZATION_CONSUMED=true
R3_AUTHORIZATION_REPLAY_PERMITTED=false
R3_SECOND_APPLY_INVOKED=false

LIVE_TRANSACTION_STATUS=FAILED_EMERGENCY
LIVE_RECOVERY_REQUIRED=true
LIVE_RUNTIME_CLASS=NOT_YET_FRESHLY_REBOUND

NEW_LIVE_APPLY_ALLOWED=false
BLIND_ROLLBACK_ALLOWED=false
TRANSACTION_DELETE_ALLOWED=false
BOARD_ACCESS=false
MERGE=false
```

## 2. Frozen design authority

`docs/development/N3W_T1_CORE_UPDATER_U1_R3_READINESS_RECOVERY_ARCHITECTURE_REPAIR_DESIGN_20261104.md`

KF: `KF-141`.

## 3. Source repair implemented so far

### Host observation / readiness split

`LocalHost` now separates:

- running structural observation;
- V2 structural observation with soft-health values;
- strict converged-health validation;
- application stopped/running/unresolved state observation.

`wait_services()` now waits for:

- production service owner active;
- Manager and Home Assistant containers present;
- strict listener contract;
- Manager current MQTT authentication;
- Home Assistant current MQTT authentication;
- Home Assistant HTTP status in the allowed healthy set.

Listener/container absence is treated as transient within the bounded window.
Once the basic runtime exists, structural/hard errors are not swallowed into a
timeout.

### Runtime state

A read-only updater command `runtime-state` has been added.

Its intended result includes:

```text
PREDECESSOR_BOUND_RUNNING
TARGET_BOUND_RUNNING
APPLICATION_STOPPED_PREDECESSOR
APPLICATION_STOPPED_TARGET
UNRESOLVED
```

plus:

```text
HEALTHY
CONVERGING
NOT_RUNNING
FAILED
```

It does not claim authorization or mutate transaction/product state.

### Recovery

Explicit V2 rollback/reconciliation now classifies fresh runtime before deciding
whether to mutate.

If predecessor is already running:

- HEALTHY -> close transaction without service mutation;
- CONVERGING -> bounded wait only, then close without service mutation;
- do not stop/restart merely because soft health was not true on the first
  read.

Target-running or application-stopped supported states may enter the existing
controlled rollback sequence.

UNRESOLVED stops before service mutation.

### Automatic rollback

Apply failures now persist exact sanitized `apply_error_code`.

Automatic rollback failures persist:

- `rollback_error_code`;
- `last_runtime_class`;
- `last_health_state`.

The pre-stop failure path also uses fresh structural classification so a
transient soft-health read does not create a false emergency before any service
mutation occurred.

## 4. Tests added / updated

The focused tests now cover:

- listener convergence separate from soft-health convergence;
- Manager MQTT then HA MQTT then HA HTTP delayed readiness;
- structural observation remains available while MQTT is still converging;
- hard runtime drift is not masked as a readiness timeout;
- predecessor-running runtime classification;
- target-running runtime classification;
- stopped-predecessor runtime classification;
- predecessor CONVERGING recovery waits without restart;
- durable apply / rollback error codes;
- Pre-U1 V2 reference simulation implements the new observation API.

## 5. CI governance repair

Two PR #777 workflows that predated policy registration were found by the
fast-source gate:

- `n3w-t1-core-updater-u1-pre-u1-simulation-ci.yml`;
- `n3w-u1-manager-a-to-b-v2-live-executor-ci.yml`.

The repair:

- adds a bounded timeout to the superseded simulation workflow;
- adds PR concurrency cancellation to the live-executor CI;
- registers both workflows in `N3W_CI_POLICY_MANIFEST_V1.json`.

No policy exception debt was added.

## 6. Pending closure

Before any new T1 mutation:

1. exact-head updater source CI must pass;
2. exact updater package must be produced and bound to that source;
3. read-only `runtime-state` must be executed against the real T1;
4. the real runtime class and health state must be archived;
5. if predecessor A is already structurally present, transaction reconciliation
   is handled separately from any future A->B apply;
6. a future A->B apply requires a fresh one-shot authorization.

The consumed `_02` authorization is never reused.
