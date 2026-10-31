# N3W T1 E03 Pre-Apply Pending Operation Recovery Source Repair

Date: 2026-10-31

## 1. Live failure evidence

The authorized E03 fresh replacement apply entered with exact fresh readonly preconditions:

- PR #740 source head: `4bec6c071af547615955602ac8d6232f0a54bc63`
- transaction SHA-256 before apply: `7c9c65a5119022fef5e99687f4708536eb09c4450cff69e2000bc2ec39739802`
- transaction state/generation: `READY/4`
- operation_seq: `0`
- no other active transaction
- Broker continuity: PASS
- deployment/service/gate reality: BEFORE

The apply call was invoked exactly once and returned an ambiguous outer error:

`transition_pending_operation`

No retry was performed.

Fresh readonly recovery forensic then proved:

- transaction state: `READY`
- generation: `6`
- operation_seq: `1`
- pending operation: `activation_gate_install`
- pending status: `INTENT`
- gate reality: `AFTER`
- service reality: `BEFORE`
- deployment reality: `BEFORE`
- Broker continuity: PASS, restart_count 0
- Manager remains exact predecessor runtime
- Home Assistant remains exact predecessor runtime
- reconciled terminal ledger binding remains exact
- no other active maintenance transaction
- apply session was durably recorded
- apply was not retried
- rollback was not invoked

Therefore the product cutover did not begin. The only proven mutation is activation-gate installation.

## 2. Root cause

The generic durable operation helper writes an `INTENT` before executing a mutation.

For the observed failure, activation-gate installation reached its intended `AFTER` reality, but the operation completion record was not durably written before an exception escaped.

The outer apply exception handler then called the generic blocking transition while the last operation was still `INTENT`. The transaction state machine intentionally rejects a state transition with a pending operation, producing:

`transition_pending_operation`

This secondary exception masked the original operation/probe error.

Two defects are therefore proven:

1. a post-execute reality/probe exception can leave a successfully applied operation as a dangling `INTENT`;
2. apply/rollback exception handling can mask the original failure by attempting a terminal transition while a pending operation exists.

## 3. Source repair

The successor operation helper now:

- retries a readonly reality observation after an operation/probe exception;
- if the second observation proves exact `AFTER`, records the operation as `COMPLETE` and continues;
- if exact `BEFORE` is proven after an exception, records `FAILED` before propagating the error;
- if a concrete unknown fingerprint is observed, records `BLOCKED` before propagating a blocked result;
- prevents apply/rollback exception handling from attempting another state transition while an unresolved pending operation still exists;
- returns an explicit STOP/review classification instead of masking the original error.

Focused tests cover the live failure shape.

## 4. Current transaction recovery policy

The already-affected transaction MUST NOT be resumed by calling `apply()` again.

It MUST NOT call ordinary `rollback()` because the current transaction is still `READY`, while normal rollback only accepts `VERIFYING/ROLLING_BACK`.

A dedicated bounded recovery tool is added for the exact live shape.

Recovery preconditions require all of the following before any transaction write:

- exact affected executor source head/blob/module-set;
- exact affected apply execution session;
- transaction state `READY`;
- operation_seq exactly `1`;
- the sole pending operation is exact `activation_gate_install`;
- pending before/after fingerprints match the frozen plan;
- activation gate reality is exact `AFTER`;
- service reality remains exact `BEFORE`;
- deployment reality remains exact `BEFORE`;
- Manager remains predecessor runtime;
- Home Assistant remains predecessor runtime;
- Broker continuity remains exact;
- reconciled ledger binding remains exact;
- no other active maintenance transaction.

If any check fails, recovery stops before mutation.

## 5. Recovery mutation

The dedicated recovery does not continue replacement.

It performs only:

1. record a dedicated recovery execution session;
2. reconcile the existing `activation_gate_install` INTENT to `COMPLETE` using the already-proven gate AFTER fingerprint;
3. transition the transaction from `READY` to terminal `ABORTED` with reason:
   `PENDING_ACTIVATION_GATE_RECONCILED_NO_PRODUCT_CUTOVER`;
4. re-prove service/deployment/Broker/ledger continuity;
5. prove the installed activation gate is non-blocking once there is no active transaction;
6. prove active maintenance transaction count becomes zero.

The activation-gate files are intentionally not deleted because the frozen transaction stores only the prior gate fingerprint, not sufficient byte authority to reconstruct or delete an unknown predecessor gate installation safely.

A future fresh transaction may treat the already-installed exact gate as its current baseline.

## 6. Hard boundaries

This repair/recovery does NOT:

- retry apply;
- invoke ordinary rollback;
- stop/start Manager or Home Assistant;
- modify deployment inputs;
- restart/recreate/replace Broker;
- load/tag/remove Docker images;
- access boards;
- flash firmware;
- mutate NVS;
- edit a transaction file manually;
- move PR #740 source head;
- merge PR #740 or PR #741.

## 7. Repository structure

- frozen affected source authority: PR #740 exact head `4bec6c071af547615955602ac8d6232f0a54bc63`
- source-repair branch: `fix/n3w-t1-e03-pending-operation-recovery-20261031`
- source-repair PR: #741
- PR #741 is stacked directly on PR #740 frozen head.

The current live recovery remains a separate authorization boundary after source/CI review.
