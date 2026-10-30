# N3-W T1 E03 Claimed Transaction Successor Authority Source Design

Date: 2026-10-30

## 0. Gate

~~~text
TASK=N3W_T1_E03_CLAIMED_TRANSACTION_SUCCESSOR_AUTHORITY_SOURCE_DESIGN_20261030_01
RESULT=SOURCE_DESIGN_FROZEN
PR740_REPAIRED_SOURCE_HEAD=19af94566ead0c08a8d3665cc2b538b90f2b500b
LIVE_T1_ACCESS=false
LIVE_TRANSACTION_MUTATION=false
PRODUCT_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

## 1. Problem

The live E03 successor transaction was claimed under the older executor/source plan at
`16d568ed577a050e23ee0061203d2a4d09cd19a0`.

That transaction is durably `READY`, its authorization is already consumed, replay is
forbidden, and no product-side apply operation has run.

The current repaired E03 source is
`19af94566ead0c08a8d3665cc2b538b90f2b500b`. It adds current-F4 generation authority
and a current-runtime authenticated snapshot that does not misuse the historical reboot
claim generation.

The maintenance transaction contract intentionally makes the following fields immutable:

- executor_source_head
- executor_blob
- module_set_sha256
- plan_sha256
- plan
- authorization_id_sha256
- current/target release binding
- artifact binding
- before/intended-after state

Therefore the repaired executor must not silently take over the already-claimed old
transaction.

## 2. Decision

Use **terminal replacement**, not post-claim executor takeover.

The old transaction will be separately retired from `READY` to terminal `ABORTED`
only after a new, explicit, one-shot maintenance-ledger retirement authorization.

After the old transaction is terminal, a completely new E03 successor transaction may
be prepared using:

- a new transaction ID;
- a new authorization ID;
- a new execution session;
- the repaired executor/source authority;
- a new preauth-plan hash;
- the current F4 generation authority;
- an immutable supersession link to the retired old transaction and its retirement
  evidence.

The old authorization remains consumed and non-replayable forever.

## 3. Rejected route: post-claim executor takeover

Do not add a rule that says a new executor may run product mutation while the old
transaction still names the old executor.

That route is rejected because it would split authority across two places:

1. the maintenance transaction would still bind the old executor and old plan;
2. an external successor document would authorize a different executor and different
   plan.

Every apply, resume, rollback and crash-recovery path would then need to understand and
verify an executor-successor chain. A missed check would create a false-PASS path where
the transaction says one executor while another actually performs the write.

The current simple invariant is stronger:

> the executor and plan that perform a transaction are exactly the executor and plan
> frozen by that transaction.

Keep that invariant.

## 4. Why terminal replacement is valid

The existing maintenance state machine already allows:

~~~text
READY -> ABORTED
~~~

`ABORTED` is terminal and is not part of `ACTIVE_STATES`.

`TransactionStore.save()` also preserves all immutable transaction bindings and forbids
reverting `authorization_consumed=true`.

Therefore retiring a pre-apply transaction does not require rewriting its executor,
plan, authorization, target, artifact, before state or intended-after state.

The only permitted old-transaction changes are the normal durable transition fields:

- state: READY -> ABORTED
- generation: increment
- last_operation
- last_reason

No operation record is created and no product state is written.

## 5. Retirement eligibility contract

A claimed E03 transaction is eligible for terminal replacement only when all of the
following are freshly proven under the global maintenance lock:

~~~text
state=READY
authorization_consumed=true
replay_allowed=false
operation_seq=0
operations=[]
pending_operation=None
observed_after={}
no apply execution session
no rollback execution session
deployment reality=EXACT_BEFORE
service reality=EXACT_BEFORE
activation-gate reality=EXACT_BEFORE
manager predecessor continuity=PASS
homeassistant continuity=PASS
broker continuity=PASS
listener contract=PASS
current F4 authority=PASS
other active maintenance transaction count=0
~~~

The retirement preflight must freeze the exact current old-transaction file SHA-256 and
generation. Any byte/generation drift before retirement claim or execution is STOP.

The reason for requiring all three mutable-surface checks (deployment, service, gate) is
that `operation_seq=0` proves no recorded operation began, while the live reality checks
also reject external or unrecorded drift.

## 6. New retirement executor

Add an E03-specific host tool rather than a generic executor-takeover mechanism.

Proposed source:

`tools/n3w_t1_r10_e03_claimed_transaction_retirement.py`

It may depend on the maintenance transaction library and reviewed read-only E03 probes,
but it must not expose any product mutation operation.

Public operations:

~~~text
preflight
claim
retire
status
~~~

No `apply`, service stop/start, Compose/env write, Docker load/tag/rmi, or board operation
is allowed in this executor.

### 6.1 Preflight

`preflight` is read-only and produces a canonical retirement plan containing at least:

- target transaction ID hash;
- exact target transaction SHA-256;
- target transaction generation;
- target authorization ID hash;
- target executor source/blob/module-set binding;
- target plan SHA-256;
- target current/target release and artifact bindings;
- target state/authorization/replay/operation-sequence facts;
- exact deployment-before fingerprint;
- exact service-before fingerprint;
- exact gate-before fingerprint;
- current F4 authority digest;
- retirement executor source/blob/module-set binding;
- reason `SOURCE_REPAIR_BEFORE_APPLY`;
- `product_mutation=false`;
- `board_access=false`.

The plan receives its own SHA-256 and becomes the exact authorization input.

### 6.2 Retirement authorization record

Use a separate durable one-shot record, for example under:

`/var/lib/n3w-t1-maintenance/retirements/`

Schema target:

`gh.n3w-t1-maintenance-transaction-retirement/1`

Immutable claim fields must include:

- retirement ID;
- retirement authorization ID hash;
- execution-session ID hash;
- retirement preflight-plan SHA-256;
- retirement executor source/blob/module-set;
- target transaction ID hash;
- target transaction SHA-256 before retirement;
- target generation before retirement;
- target executor/plan/authorization hashes;
- expected exact-before runtime fingerprints;
- reason.

Lifecycle:

~~~text
PREPARED -> CLAIMED -> COMMITTED
                 |
                 +-> BLOCKED
~~~

The claim is one-shot:

~~~text
authorization_consumed=true
replay_allowed=false
~~~

### 6.3 Crash ordering

Retirement execution must be durable in this order:

1. acquire global maintenance lock;
2. revalidate exact target transaction and exact BEFORE reality;
3. durably create/claim retirement authorization record;
4. transition old transaction READY -> ABORTED using normal TransactionStore.save();
5. verify old transaction immutable fields remain unchanged;
6. finalize retirement record COMMITTED with the exact post-retirement transaction
   SHA-256 and generation.

Crash recovery:

- crash before step 3: no mutation;
- crash after step 3 but before step 4: retirement record CLAIMED, old transaction READY;
  same exact retirement authority may resume only the retirement operation;
- crash after step 4 but before step 6: old transaction ABORTED, retirement record CLAIMED;
  same exact authority may only finalize evidence;
- after step 6: terminal; no replay.

A second retirement authorization for the same exact target transaction is forbidden.

## 7. Maintenance library addition

Do not use the broad `transition(..., "ABORTED")` call directly from arbitrary callers.

Add a narrow helper such as:

`abort_claimed_ready_before_apply(document, reason=...)`

The helper must require:

- state READY;
- authorization consumed;
- replay false;
- operation_seq 0;
- operations empty;
- no pending operation;
- observed_after empty.

It returns the normal READY -> ABORTED transition and changes no immutable binding.

Add direct unit tests proving all ineligible states fail closed.

## 8. New E03 transaction after retirement

Retirement does **not** automatically create or claim the replacement E03 transaction.

A later fresh read-only E03 preauth must independently pass.

The replacement E03 plan must add an immutable supersession block:

~~~text
supersession.mode=TERMINAL_REPLACEMENT
supersession.reason=SOURCE_REPAIR_BEFORE_APPLY
supersession.retired_transaction_id_sha256=<old id hash>
supersession.retired_transaction_sha256=<exact final ABORTED file sha>
supersession.retirement_evidence_sha256=<exact COMMITTED retirement record sha>
supersession.retired_state=ABORTED
supersession.retired_authorization_consumed=true
supersession.retired_replay_allowed=false
supersession.retired_operation_seq=0
~~~

The normal E03 `predecessor_sha256` remains the original E03 predecessor-evidence
binding. The retired successor transaction is linked through the supersession block; it
must not be substituted for the predecessor schema.

The replacement claim must recompute and reverify the complete preauth plan under the
global lock before it creates a new maintenance transaction.

## 9. Authorization boundaries

The following are distinct and must never be collapsed:

1. source implementation/review — repository only;
2. live retirement preflight — read-only;
3. retirement authorization + retirement execution — T1 maintenance-ledger mutation,
   no product mutation;
4. fresh replacement E03 preauth — read-only;
5. new replacement E03 transaction claim — new explicit authorization;
6. apply-authorization preflight — read-only;
7. real E03 apply — separate explicit product-mutation authorization.

Retiring the old transaction does not authorize the new claim.
Claiming the new transaction does not authorize apply.

## 10. Required regression tests

At minimum cover:

1. READY + consumed + no operations + exact BEFORE -> retirement eligible.
2. operation_seq > 0 -> retirement forbidden.
3. pending INTENT -> retirement forbidden.
4. APPLYING/VERIFYING/ROLLING_BACK -> retirement forbidden.
5. deployment/service/gate not exact BEFORE -> retirement forbidden.
6. target transaction SHA/generation drift -> retirement forbidden.
7. immutable binding change during retirement -> store rejects.
8. authorization_consumed cannot revert.
9. retirement crash after CLAIMED before ABORTED -> resumable only by same exact
   retirement authority.
10. retirement crash after ABORTED before evidence COMMITTED -> evidence finalization
    only.
11. second retirement authorization/replay -> forbidden.
12. ABORTED old transaction is ignored by active-transaction exclusion.
13. replacement E03 preauth requires exact retirement evidence.
14. replacement E03 claim rechecks exact supersession evidence under global lock.
15. retired transaction byte drift after retirement -> replacement preauth/claim STOP.
16. historical old authorization remains consumed/non-replayable.
17. old executor cannot resume ABORTED transaction.
18. repaired executor cannot mutate the old transaction as an apply transaction.

## 11. Current decision

~~~text
POSTCLAIM_EXECUTOR_TAKEOVER=REJECTED
TERMINAL_REPLACEMENT=SELECTED
OLD_TRANSACTION_DIRECT_EDIT=FORBIDDEN
OLD_AUTHORIZATION_REPLAY=FORBIDDEN
OLD_TRANSACTION_RECREATE=FORBIDDEN
OLD_TRANSACTION_TARGET_STATE=ABORTED
NEW_TRANSACTION_ID_REQUIRED=true
NEW_AUTHORIZATION_REQUIRED=true
NEW_PREAUTH_PLAN_REQUIRED=true
SUPERSESSION_EVIDENCE_REQUIRED=true
PRODUCT_MUTATION_THIS_GATE=false
T1_ACCESS_THIS_GATE=false
BOARD_ACCESS=false
MERGE=false
~~~

## 12. Next gate

~~~text
NEXT_ONE_GATE=N3W_T1_E03_CLAIMED_TRANSACTION_RETIREMENT_SOURCE_REPAIR_20261030_01
~~~

That gate is repository/source only. It should implement the narrow retirement helper,
E03-specific retirement executor, supersession binding in the replacement E03 plan and
the regression matrix above. It must stop before any live T1 retirement preflight or
maintenance-ledger mutation.
