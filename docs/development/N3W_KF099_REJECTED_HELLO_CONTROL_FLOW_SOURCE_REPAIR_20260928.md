# N3-W KF-099 Rejected-Hello Control-Flow Source Repair — 2026-09-28

Status: `SOURCE_REPAIR_MERGED_PHYSICAL_VALIDATION_PASS`

The source-repair-stage facts below are preserved as historical gate evidence. The current KF-099 closure authority is `docs/development/N3W_KF099_PHYSICAL_VALIDATION_CLOSURE_20260928.md`, which records the later exact-firmware Board B deployment and physical PASS.

## Problem

A fresh passive capture after KF-098 closure proved the following live sequence on the currently deployed Board firmware:

```text
/v2/pairing/hello
-> HTTP 200
-> gh.pair.simple-hello-result/1
-> status=rejected
-> reason=repair_intent_required
-> transaction_disposition=continue

/v2/pairing/begin
-> HTTP 403
-> gh.pair.simple-error/1
-> error=setup_secret_unavailable
```

The Manager-side security behavior is fail-closed and correct: without a matching one-shot repair intent, a fresh pairing identity must not replace an existing durable identity.

The defect is on the Board client control-flow boundary. The firmware previously interpreted every wire-level `transaction_disposition=continue` as immediate permission to proceed to `/v2/pairing/begin`, even when the hello result itself was `status=rejected`.

That caused the Board to enter `/begin` before the repair transaction was accepted and before a Setup Secret existed in the Manager coordinator for that `hardware_id + pairing_id`.

## Root cause

The client reduced a two-dimensional hello result:

```text
status
transaction_disposition
```

to a single two-state local interpretation:

```text
CONTINUE
TERMINAL
```

As a result, `rejected + continue` was treated the same as `created/superseded + continue`.

## Source repair

PR #500 is merged at `c578bcb2e31f50771b6b08c231704da6bf36b729` with 14/14 CI PASS. It changes only the client interpretation. It does not change the Manager wire schema or weaken repair authorization.

The local decision becomes:

```text
created/duplicate/superseded/repaired_after_retirement + continue
-> PROCEED
-> /begin allowed

rejected + continue
-> WAIT
-> preserve current pairing_id
-> do not call /begin
-> return to bounded pairing retry loop

rejected + terminal + expired/replay_detected
-> RENEW
-> generate a fresh random pairing_id
```

The existing component already treats `SimplePairingClientError::NOT_READY` as a normal waiting result and retries on the existing pairing cadence.

## Security boundary

The repair does not:

- authorize repair;
- import a Setup Secret;
- mutate registration state;
- rotate credentials;
- bypass the one-shot repair intent;
- change Manager `repair_intent_required` behavior.

It only stops the Board from issuing a logically premature `/begin`.

## Regression guard

Repository tests now require:

- `rejected + continue` maps to a local WAIT action;
- WAIT returns `NOT_READY`;
- `run_once()` stops before `pair_with_()` when hello returns WAIT;
- the pairing ID is not renewed on WAIT;
- terminal `expired/replay_detected` behavior still renews the pairing ID;
- successful non-rejected `continue` results still proceed.

The temporary test that would have frozen the old `repair_intent_required -> /begin -> 403 setup_secret_unavailable` behavior as a desired contract was removed.

## Closure boundary

```text
KF099_SOURCE_DEFECT_CONFIRMED=true
KF099_SOURCE_REPAIR=PASS
KF099_MANAGER_SECURITY_BOUNDARY=UNCHANGED
SOURCE_REPAIR_GATE_REGISTRATION_MUTATION=false
SOURCE_REPAIR_GATE_REPAIR_AUTHORIZATION=false
SOURCE_REPAIR_GATE_BOARD_FLASH_MUTATION=false
KF099_REPAIR_MERGE_COMMIT=c578bcb2e31f50771b6b08c231704da6bf36b729
KF099_SOURCE_CI=14_OF_14_PASS

KF099_EXACT_ARTIFACT_BINDING=PASS
KF099_BOARD_B_WRITE=PASS
KF099_PHYSICAL_VALIDATION=PASS
KF099_ROUTE_STATUS=CLOSED_PASS
KF099_KNOWN_FAILURE_STATUS=GUARDED
KF099_FINAL_CLOSURE_AUTHORITY=docs/development/N3W_KF099_PHYSICAL_VALIDATION_CLOSURE_20260928.md

PAIRING_REPAIR_AUTHORIZATION=false
KF098_REOPEN=false
KF098_ROUTE_STATUS=CLOSED_PASS
```

The five required physical conditions were subsequently satisfied by the exact repaired firmware on Board B:

1. hello reached the Manager;
2. the Manager returned `repair_intent_required` without authorization;
3. the Board issued no `/v2/pairing/begin` while hello remained rejected;
4. the Board preserved one pairing transaction across retries;
5. the target registration and credential state remained unchanged.

KF-099 is therefore `CLOSED_PASS / GUARDED`. The detailed public-safe physical evidence is recorded in `docs/development/N3W_KF099_PHYSICAL_VALIDATION_CLOSURE_20260928.md`.
