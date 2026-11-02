# N3-W T1 Core Updater V2 architecture and fault matrix — 2026-11-03

## 0. Purpose

This document is the architecture gate inserted after the Manager A->B R2 incident.

It deliberately stops the patch-and-live-retry loop.

```text
LIVE_T1_MUTATION=false
APPLY_RETRY=false
EXPLICIT_ROLLBACK=false
BOARD_ACCESS=false

DEVELOPMENT_PR=754
INCIDENT_PR=753
```

The goal is not a rewrite. The goal is to make the existing updater lifecycle complete, small and testable before another live apply.

## 1. Product facts vs transaction history

A transaction record answers:

```text
what operation was attempted?
what phase was last durably recorded?
what authorization was consumed?
what failure occurred?
```

It must not be the sole authority for:

```text
what is healthy right now?
which Manager image is actually active?
are application services ready?
is rollback already physically complete?
```

Current live R2 evidence proved this distinction is necessary:

```text
transaction = FAILED_EMERGENCY / ROLLBACK_FAILED
runtime     = predecessor A healthy
listeners   = healthy and stable
HA/Broker   = healthy and stable
```

Therefore V2 uses live runtime facts to reconcile an interrupted or failed transaction.

## 2. Minimal runtime fact model

The runtime classifier is intentionally small.

### 2.1 PREDECESSOR_HEALTHY

All must be true:

```text
GH_MANAGER_IMAGE == predecessor
running Manager image_ref == predecessor
running Manager image_id == recorded predecessor runtime ID
Manager network == host
Home Assistant identity/network satisfy preserved baseline
Broker identity/start/restart satisfy preserved baseline
strict listener contract == expected
services supervision contract == expected
```

### 2.2 TARGET_HEALTHY

All must be true:

```text
GH_MANAGER_IMAGE == target
running Manager image_ref == target
running Manager runtime image matches exact target archive by portable identity
Manager network == host
Home Assistant identity/network satisfy preserved baseline
Broker continuity satisfies preserved baseline
strict listener contract == expected
services supervision contract == expected
```

### 2.3 APPLICATION_STOPPED_PREDECESSOR_BOUND

```text
application service owner is stopped/inactive
Manager + HA application containers are absent
GH_MANAGER_IMAGE == predecessor
Broker continuity remains valid
```

### 2.4 APPLICATION_STOPPED_TARGET_BOUND

```text
application service owner is stopped/inactive
Manager + HA application containers are absent
GH_MANAGER_IMAGE == target
Broker continuity remains valid
```

### 2.5 UNRESOLVED

Anything not matching the exact states above.

UNRESOLVED is fail-closed. No automatic guess, promotion or deletion is allowed.

## 3. One readiness authority

There must be one canonical application-readiness predicate.

systemd `active` is not application readiness.
Container existence is not application readiness.

For this product generation the canonical post-start readiness contract remains:

```text
services unit active
exactly one Manager container
exactly one Home Assistant container
Manager binding/runtime match
Manager host network
Home Assistant host network
Broker continuity valid
TCP 8883 == 1
TCP 47110 == 1
UDP 47111 == 1
TCP 47112 == 0
```

Static supervision/compose contracts remain strict.

`wait_services()` may poll transient runtime conditions, but it must converge on the same listener/readiness contract that final `inspect()` enforces. It must never define a weaker competing concept of ready.

## 4. Transaction model

The existing durable transaction phases remain useful as operation history:

```text
AUTHORIZED
TARGET_IMAGE_LOADED
STOPPING_APPLICATION_SERVICES
APPLICATION_SERVICES_STOPPED
MANAGER_BINDING_PUBLISHED
TARGET_RUNTIME_STARTED
COMMITTED
ROLLBACK_*
RECOVERY_*
```

They are not runtime authority.

### 4.1 Terminal transaction statuses

```text
COMMITTED
ROLLED_BACK
```

### 4.2 Non-terminal transaction statuses

```text
APPLYING
ROLLING_BACK
FAILED_EMERGENCY
```

`FAILED_EMERGENCY` means: the previous recovery attempt could not prove a terminal state at that instant.

It does not mean the runtime is permanently damaged.

## 5. Apply contract

Before claim:

```text
package exact
target manifest exact
predecessor runtime PREDECESSOR_HEALTHY
target archive identity exact
no active non-terminal transaction
```

After claim:

```text
authorization is consumed
transaction is durable before destructive action
```

Apply sequence:

```text
verify/load target
stop application services
publish only Manager binding
validate compose delta
start application services
wait canonical readiness
verify target portable identity + HA/Broker continuity
commit
```

Any failure before application service stop completes must recover without restarting services.

Any failure after stop begins enters recovery/reconciliation.

## 6. Recovery contract

Recovery is based on both transaction history and fresh runtime classification.

### 6.1 Runtime already PREDECESSOR_HEALTHY

Close transaction to:

```text
ROLLED_BACK
t1_mutation=false
```

No service restart and no env rewrite.

This is the required closure for the observed R2 incident.

### 6.2 Runtime TARGET_HEALTHY with non-terminal apply

Do not silently promote the failed/interrupted transaction to COMMITTED.

Default recovery policy remains rollback-to-predecessor because the original apply did not prove completion.

### 6.3 Runtime application stopped

If target-bound, rewrite only Manager binding to predecessor and start through the product service owner.

If predecessor-bound, start through the product service owner.

Then wait canonical readiness and verify predecessor identity + HA/Broker continuity.

### 6.4 Runtime UNRESOLVED

Hard STOP.

Do not delete transaction state.
Do not delete images.
Do not blindly rewrite env.
Do not restart product services.

## 7. Restart/power-loss rule

A host reboot or updater process death may leave the durable transaction in any non-terminal phase.

On the next explicit recovery action:

```text
transaction phase gives historical context
fresh runtime classification gives current fact
recovery action is selected from the current fact
```

The system must not require the operator to infer the correct recovery command from a stale phase string.

## 8. Fault injection matrix

All rows are host simulation / unit-integration tests before another T1 mutation.

| ID | Injection point / condition | Expected terminal behavior |
|---|---|---|
| F01 | wrong apply confirmation | no transaction, no mutation |
| F02 | target tar/hash/portable identity invalid | ROLLED_BACK_PRESTOP or no transaction; services untouched |
| F03 | target image absent, load succeeds | continue with exact portable proof |
| F04 | target image load fails | predecessor remains healthy; transaction recoverable without service restart |
| F05 | process dies after AUTHORIZED | explicit recovery closes PREDECESSOR_HEALTHY without restart |
| F06 | process dies after TARGET_IMAGE_LOADED | explicit recovery closes PREDECESSOR_HEALTHY without restart |
| F07 | process dies while STOPPING_APPLICATION_SERVICES | reconciliation decides from fresh runtime, never from phase alone |
| F08 | process dies after APPLICATION_SERVICES_STOPPED | recovery starts predecessor through owner and verifies readiness |
| F09 | process dies after MANAGER_BINDING_PUBLISHED | recovery restores predecessor and verifies readiness |
| F10 | target containers appear before listeners | wait, do not fail early |
| F11 | target listeners never become ready | bounded timeout then rollback |
| F12 | target post-check detects HA identity drift | rollback to predecessor |
| F13 | target post-check detects Broker continuity drift | fail/recover without mutating Broker |
| F14 | rollback containers appear before listeners | wait, do not create false FAILED_EMERGENCY |
| F15 | rollback listeners never become ready | FAILED_EMERGENCY / recovery_required, runtime not guessed |
| F16 | FAILED_EMERGENCY but predecessor is now fully healthy | explicit recovery closes ROLLED_BACK with t1_mutation=false |
| F17 | FAILED_EMERGENCY while target still active | fail closed; no automatic mutation |
| F18 | FAILED_EMERGENCY with unknown binding/runtime | fail closed |
| F19 | host reboot with APPLYING + predecessor healthy | close to ROLLED_BACK without restart |
| F20 | host reboot with application stopped + target bound | restore predecessor via controlled recovery |
| F21 | host reboot with application stopped + predecessor bound | start predecessor via controlled recovery |
| F22 | host reboot with target healthy but transaction non-terminal | rollback policy, never silent commit |
| F23 | compose candidate changes non-Manager field | fail closed and rollback |
| F24 | Broker changes during apply | fail closed; never rewrite/restart Broker as recovery side effect |
| F25 | transaction write/history/lock integrity failure | fail closed before new destructive action |
| F26 | successful COMMITTED transaction then explicit rollback | predecessor restored and verified |
| F27 | new apply after terminal COMMITTED/ROLLED_BACK | prior transaction archived exactly once |
| F28 | repeated recovery after terminal ROLLED_BACK | no replay/no mutation |

## 9. Merge and live gates

PR #754 is not merge-ready merely because the original CI is green.

Before merge:

```text
V2_ARCHITECTURE_REVIEW=PASS
FAULT_MATRIX_REQUIRED_ROWS=PASS
NEW_SOURCE_BLOCKER_COUNT=0
CI=PASS
```

Before another live T1 apply:

```text
main contains reviewed V2 repair
replacement updater exact artifact is rebuilt
T1 current runtime read-only classified PREDECESSOR_HEALTHY
stuck R2 transaction is safely reconciled to ROLLED_BACK
fresh apply authorization is issued
```

The stuck transaction reconciliation and the later A->B apply are separate mutation claims. They must not share or replay an authorization.

## 10. Scope limits

This V2 closure does not:
- redesign Manager product behavior;
- rebuild Manager B;
- modify Home Assistant;
- modify Mosquitto;
- modify Board firmware;
- change R3/KF-131 product scope;
- add generic orchestration frameworks.

The updater stays a narrowly scoped Manager-image replacement tool.

## 11. Current decision

```text
PRODUCT_ARCHITECTURE=KEEP
UPDATER_CONCEPT=KEEP
REWRITE_FROM_SCRATCH=false
PR754=SOLE_DEVELOPMENT_PR_FOR_THIS_INCIDENT
PR753=INCIDENT_EVIDENCE_ONLY
IMMEDIATE_LIVE_RETRY=false
NEXT_GATE=FAULT_MATRIX_IMPLEMENTATION_AND_SOURCE_REVIEW
```
