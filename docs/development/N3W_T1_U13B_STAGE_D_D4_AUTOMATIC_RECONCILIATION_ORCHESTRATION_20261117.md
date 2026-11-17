# N3W T1 U13B Stage D D4 — Automatic reconciliation orchestration

Date: 2026-11-17  
Baseline: `3cdd1a2b55331ff8f876871f32d63bc69b44cf1c`  
PR: #807  
Scope: source orchestration only; no live/T1 execution authority.

## 1. Purpose

D3 provides a safe Host-only reconciliation writer for a legal one-phase
USB-ahead split. The existing normal rollback controller still fail-closes when
it sees that split. D4 connects the already-reviewed components without changing
rollback transition semantics.

## 2. Required order

```text
D3 writer reconcile()
  -> strict RO USB evidence
  -> Host-only exact mirror repair when required
  -> release reconciliation RO mount
  -> release shared transaction lock

normal U13B rollback controller rollback()
  -> acquire the same transaction lock again
  -> reread Host
  -> resolve media for normal writable transaction persistence
  -> reclassify Host/USB
  -> execute only the already-defined rollback step(s)
```

D4 must not hold an outer transaction lock around both calls. The D3 writer and
normal rollback controller each own their existing lock lifecycle. This avoids
non-reentrant nested `flock` acquisition and ensures the reconciliation RO
mount is released before the normal writable path begins.

## 3. Race behavior between the two calls

The gap between D3 completion and normal rollback is not treated as authority.

The normal rollback controller always rereads and reclassifies state under its
own lock. If another actor changes Host or USB in that gap, the existing
controller classification fails closed. D4 must not suppress or translate that
failure into progress.

## 4. Failure behavior

- D3 reconciliation failure => do not call normal rollback.
- D3 returns only `ALREADY_EXACT` or `RECONCILED` => eligible to call normal rollback.
- unknown D3 result => STOP before normal rollback.
- normal rollback revalidation failure => propagate unchanged.
- no rollback runtime operation is executed before reconciliation has completed.

## 5. Non-goals

D4 does not:

- change any U13B transition;
- weaken D3 postcondition observation;
- write USB metadata during reconciliation;
- bypass normal rollback revalidation;
- authorize T1 access or live rollback;
- add a Stage E;
- merge PR #807.

## 6. Acceptance

```text
D3_CLOSED_PASS=true
RECONCILIATION_BEFORE_ROLLBACK=true
NO_OUTER_NESTED_TRANSACTION_LOCK=true
RECONCILIATION_FAILURE_BLOCKS_ROLLBACK=true
NORMAL_CONTROLLER_REVALIDATION_PRESERVED=true
ROLLBACK_TRANSITION_SEMANTICS_UNCHANGED=true
U13B_LIVE_EXECUTION_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## 7. Next gate

After source CI and independent review:

```text
NEXT_ONE_GATE=U13B_STAGE_D_SOURCE_CLOSURE_AND_READONLY_PREEXECUTION_DESIGN
```
