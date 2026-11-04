# N3-W T1 Core Updater U1 R3 readiness / recovery architecture repair design

Date: 2026-11-04

## 1. Gate

```text
TASK=N3W_T1_CORE_UPDATER_U1_R3_READINESS_RECOVERY_ARCHITECTURE_REPAIR_DESIGN_20261104_01
RESULT=DESIGN_FROZEN

PR=777
INPUT_HEAD=459e240c351ca04c01b94e1ed9ddeb8f21315f0c

LIVE_T1_MUTATION=false
APPLY_RETRY=false
AUTHORIZATION_REPLAY=false
EXPLICIT_ROLLBACK=false
BOARD_ACCESS=false
MERGE=false
```

The R3 one-shot apply authorization
`N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_U1_V2_20261104_02`
is consumed and must never be replayed.

## 2. R3 evidence

The fresh pre-plan passed and proved the exact predecessor, exact target
archive, rollback compatibility and exact Manager-only target.

The real apply then entered the mutation boundary and returned
`automatic_rollback_failed`. The durable V2 transaction is
`FAILED_EMERGENCY` with `recovery_required=true`.

The post-attempt inspect could not return a structural runtime snapshot because
the current `LocalHost.inspect_v2()` aborts on
`mqtt_current_authentication_missing`.

This is sufficient to prove an updater lifecycle defect. It is not sufficient
to prove a Manager B product defect.

## 3. Upper-layer contract

The updater must distinguish four different concepts.

### 3.1 Observation

Observation answers only what is true now.

It must expose structural facts even when a SOFT_RUNTIME_CHECK has not yet
converged:

- current component image bindings;
- current running image identities when containers exist;
- service owner state;
- running service/container counts;
- network modes;
- current listener snapshot;
- Manager and Home Assistant MQTT current-authentication booleans when
  observable;
- Home Assistant HTTP current status when observable.

A transient false soft-health value must not destroy the structural snapshot.

### 3.2 Structural runtime classification

The generic updater must be able to distinguish at least:

```text
PREDECESSOR_BOUND_RUNNING
TARGET_BOUND_RUNNING
APPLICATION_STOPPED_PREDECESSOR
APPLICATION_STOPPED_TARGET
UNRESOLVED
```

This classification is about binding/runtime structure, not whether all soft
health is already converged.

### 3.3 Convergence health

Convergence health is time-dependent:

```text
CONVERGING
HEALTHY
FAILED
```

The following A1 fields are soft runtime health, not immutable identity:

- Manager current MQTT authentication;
- Home Assistant current MQTT authentication;
- Home Assistant HTTP availability/status;
- listener readiness while a controlled service start is still within its
  bounded convergence window.

They MUST be healthy before apply or rollback is declared terminal, but they
MUST NOT be required on the first instantaneous read after process/container
creation.

### 3.4 Terminal validation

Only after structural state is the expected state and convergence health is
HEALTHY may the updater write terminal `COMMITTED` or `ROLLED_BACK`.

Hard authority drift remains immediate fail-closed.

## 4. One canonical convergence predicate

There must be one post-start convergence predicate used by both apply and
rollback.

For the current product generation, HEALTHY requires:

```text
services owner active
exact Manager + Home Assistant runtime present
expected Manager/HA/Broker structural identities
listener snapshot:
  tcp_8883=1
  tcp_47110=1
  udp_47111=1
  tcp_47112=0
Manager current MQTT authenticated=true
Home Assistant current MQTT authenticated=true
Home Assistant HTTP status in {200, 401}
```

The bounded wait may observe intermediate states such as:

```text
listeners ready
Manager MQTT=false
Home Assistant MQTT=false
Home Assistant HTTP unavailable
```

and continue polling without declaring failure.

The timeout remains fail-closed.

## 5. Apply contract

After authorization claim:

```text
durable transaction
-> verify/load target
-> quiesce target owner
-> publish target binding
-> validate target-only compose delta
-> activate production owner
-> wait canonical convergence
-> inspect/validate target + peers + A1 hard policy
-> COMMITTED
```

A failure after mutation begins enters automatic recovery.

## 6. Automatic recovery contract

Automatic recovery must use the same canonical convergence predicate.

If target verification fails after mutation:

```text
restore predecessor binding if needed
-> activate predecessor through production owner
-> wait canonical convergence
-> validate predecessor + peers + A1 hard policy
-> ROLLED_BACK
```

A normal convergence delay must not be promoted to
`FAILED_EMERGENCY`.

`FAILED_EMERGENCY` is reserved for conditions such as:

- binding cannot be classified;
- predecessor/target image identity cannot be proven;
- hard peer/runtime authority drift;
- predecessor cannot be restored;
- service owner cannot be brought to a structurally supported state;
- bounded convergence expires;
- hard post-recovery validation fails.

## 7. Error evidence

The transaction must preserve sanitized machine-readable reasons, not only
exception class names.

At minimum:

```text
apply_error_code
rollback_error_code
last_runtime_class
last_health_state
```

Secret values and private paths remain excluded.

## 8. Executor boundary

The live executor must not duplicate updater-owned product policy.

Executor responsibilities:

- exact package/artifact authority;
- exact staging/hash verification;
- one-shot authorization claim boundary;
- exactly one apply invocation;
- evidence preservation;
- no automatic second apply;
- no executor-driven automatic rollback.

Updater responsibilities:

- transaction compatibility;
- predecessor/target/baseline policy;
- image-binding eligibility;
- runtime classification;
- readiness/convergence;
- apply/rollback state machine.

A future updater-owned read-only `preflight` / `apply_ready` result should be
used instead of re-implementing those rules in the executor.

## 9. Required source tests before another live apply

Tests must include real time-sequenced LocalHost semantics, not only a FakeHost
that is instantly healthy.

Required sequences:

```text
S1 listeners ready -> Manager MQTT delayed -> HA MQTT delayed -> HA HTTP ready -> PASS
S2 target never reaches MQTT convergence -> bounded timeout -> rollback
S3 rollback predecessor converges after delay -> ROLLED_BACK
S4 rollback predecessor never converges -> FAILED_EMERGENCY
S5 hard runtime identity drift -> immediate fail-closed
S6 soft health false does not erase structural observation
S7 exact sanitized apply/rollback error codes persist
S8 explicit recovery can classify predecessor already running without rewriting binding
```

## 10. Current live boundary

Until source repair and read-only live classification are closed:

```text
NEW_LIVE_APPLY_ALLOWED=false
OLD_AUTHORIZATION_REPLAY_ALLOWED=false
BLIND_ROLLBACK_ALLOWED=false
TRANSACTION_DELETE_ALLOWED=false
STAGING_DELETE_ALLOWED=false
BOARD_ACCESS=false
```

The next live action is read-only runtime classification only.
