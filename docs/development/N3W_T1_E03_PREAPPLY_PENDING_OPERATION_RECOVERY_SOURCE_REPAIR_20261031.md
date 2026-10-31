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

The current live recovery authorization boundary has now been crossed and closed. The actual live execution and subsequent gate-compatibility closure are recorded below.

## 8. Actual live recovery result

The exact recovery preflight passed against:

- transaction state `READY`;
- generation `6`;
- operation_seq `1`;
- pending `activation_gate_install`;
- gate reality `AFTER`;
- service/deployment reality `BEFORE`;
- Broker restart_count `0`.

The recovery mutation then:

1. recorded the dedicated recovery execution session;
2. reconciled `activation_gate_install` from `INTENT` to `COMPLETE`;
3. transitioned the transaction to terminal `ABORTED`;
4. preserved Manager, Home Assistant, Broker and deployment inputs unchanged.

The final transaction evidence is:

- state: `ABORTED`;
- generation: `9`;
- transaction SHA-256:
  `035a42c1d8b60da1e2e70f9030e290870e64ed2ab88a2fabc395c0eae0251a3e`;
- operation_seq: `1`;
- last operation: `preapply_pending_recovery_abort`;
- last reason:
  `PENDING_ACTIVATION_GATE_RECONCILED_NO_PRODUCT_CUTOVER`;
- `activation_gate_install` status: `COMPLETE`.

The recovery command returned STOP only during its final gate-nonblocking assertion. The transaction mutation itself had already completed and MUST NOT be replayed.

## 9. Historical BLOCKED gate compatibility defect

Readonly forensic proved the remaining gate block came from the older transaction
`n3w-t1-e03-replacement-successor-20261030-01`.

That historical transaction is:

- terminal `BLOCKED`;
- generation `5`;
- operation_seq `0`;
- operations empty;
- observed_after empty;
- last operation `baseline_invalidated_before_apply`;
- last reason `BROKER_STARTED_AT_CHANGED_AFTER_T1_REBOOT`;
- bound to the exact COMMITTED baseline-invalidation evidence;
- proven to have caused no product apply, service stop/start, Docker mutation or board access.

The maintenance transaction contract classifies `BLOCKED` as terminal/non-active, while the activation gate historically classified every `BLOCKED` transaction as permanently blocking. This contract mismatch caused the recovery final assertion to return
`MAINTENANCE_BLOCKING`.

The activation gate repair therefore does NOT allow generic BLOCKED transactions.
It skips a BLOCKED transaction only when all of the following are true:

- exact pre-apply invalidation operation/reason;
- authorization consumed and replay disabled;
- operation_seq zero;
- operations empty;
- observed_after empty;
- exactly one matching baseline-invalidation record exists;
- that invalidation record is structurally valid and COMMITTED;
- its plan hash and executor/target bindings are valid;
- target transaction id, post-transaction SHA and generation bind exactly;
- product/service/Docker/board mutation flags remain false.

Missing, malformed, duplicated, tampered or unrelated invalidation evidence remains fail-closed.

## 10. Live activation-gate hotfix closure

The live helper was changed only after:

- old installed gate blob was proven as
  `ab6a0905cc257a6a7f62a0589f2fea66f9f1677f`;
- the repaired candidate was independently executed and returned `0`;
- all transaction and invalidation evidence remained exact.

The live hotfix result was:

- old gate rc: `1`;
- candidate gate rc: `0`;
- installed repaired gate rc: `0`;
- current recovery transaction remained `ABORTED`;
- historical invalidated transaction remained `BLOCKED`;
- invalidation evidence remained `COMMITTED`;
- Manager unchanged;
- Home Assistant unchanged;
- Broker unchanged;
- service unit remained active;
- product cutover false;
- apply/recovery replay false;
- rollback false;
- board access false.

The repaired live gate blob at that closure point was
`4caa7f195afe3f436763006d6a20c0b53fa1b138`.

## 11. Merge-review hardening

Independent merge review found one additional false-PASS risk in the first gate compatibility repair: the gate checked the critical invalidation bindings but did not require the complete authoritative invalidation record key set.

The source was hardened so gate acceptance now mirrors the baseline-invalidation authority for:

- exact record key set;
- invalidation identifier/hash binding;
- SHA-40/SHA-256 field shapes;
- plan schema/hash binding;
- executor source/blob/module-set binding;
- generation and poststate binding;
- no-product-mutation flags.

Regression tests also prove that extra-key and missing-key invalidation records remain blocking.

This hardening does not broaden the live mutation scope. It only makes future gate evaluation more fail-closed.

## 12. Current source-convergence boundary

PR #741 remains stacked directly on PR #740.

Before merge, the remaining requirements are:

1. latest PR #741 CI all SUCCESS;
2. PR #741 base remains exact PR #740 head;
3. GitHub mergeability remains true;
4. no new review blocker;
5. merge remains a separate explicit decision.

No further T1 recovery/apply/rollback is required for this incident.
