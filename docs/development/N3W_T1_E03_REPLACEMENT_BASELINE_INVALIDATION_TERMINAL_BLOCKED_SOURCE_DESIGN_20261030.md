# N3W T1 E03 replacement baseline invalidation — terminal BLOCKED source design

Date: 2026-10-30

## 1. Problem statement

The replacement E03 successor transaction is still READY generation 4, authorization-consumed and non-replayable, with no apply/rollback operation and no observed-after state.

The apply-authorization readonly preflight correctly stopped because the transaction's frozen Broker continuity baseline no longer matches live runtime:

- broker container_id: unchanged
- broker image_id: unchanged
- broker restart_count: unchanged at 0
- broker started_at: changed from 2026-10-25T14:40:59.136962496Z to 2026-10-30T14:04:04.311501262Z
- broker unit: active/enabled
- TCP/8883 listener count: 1
- broker unit NRestarts: 0
- services unit NRestarts: 0

Read-only boot evidence closes the cause:

- current kernel boot time: 2026-10-30T14:03:30Z
- broker activation: 2026-10-30 22:04:03 CST
- broker runtime StartedAt: 2026-10-30T14:04:04.311501262Z
- services activation: 2026-10-30 22:04:07 CST

Therefore the claim-time Broker continuity baseline was invalidated by the T1 reboot before any E03 product apply.

## 2. Why the existing retirement route must not be reused

The existing claimed-transaction retirement executor proves exact BEFORE reality by calling the same E03 Broker continuity check. It therefore correctly fails once the Broker StartedAt baseline has changed.

Creating another matching ABORTED retirement is also invalid for the current source contract. committed_supersession() requires exactly one matching ABORTED transaction and one matching COMMITTED retirement record for a predecessor/current-release/target-release/artifact tuple. A second matching ABORTED + retirement pair would make supersession ambiguous.

The current replacement transaction must therefore not be:
- applied;
- rewritten;
- re-claimed;
- replayed;
- converted into a second ordinary ABORTED supersession candidate.

## 3. Selected design

Use the existing maintenance terminal state BLOCKED as a narrow pre-apply invalidation state.

The current READY transaction may transition to BLOCKED only through a dedicated evidence-bound E03 baseline-invalidation executor.

This operation is maintenance-ledger-only. It must not:
- stop/start application services;
- mutate Docker or Compose;
- mutate Broker/Manager/Home Assistant;
- install/remove activation gate files;
- mutate predecessor or retirement evidence;
- access boards;
- perform product apply or rollback.

## 4. Eligibility contract

The invalidation executor must fail closed unless all of the following are true:

1. Target transaction is the exact expected replacement transaction.
2. State is READY.
3. authorization_consumed=true.
4. replay_allowed=false.
5. operation_seq=0.
6. operations=[].
7. no pending operation.
8. observed_after={}.
9. execution_sessions contains only the original claim session.
10. No apply or rollback execution session exists.
11. Immutable transaction binding still matches:
   - transaction identity
   - executor_source_head
   - executor_blob
   - module_set_sha256
   - plan_sha256 / plan
   - predecessor_sha256
   - host_binding_sha256
   - current_release_id / target_release_id / artifact_sha256
12. Deployment inputs remain exact BEFORE.
13. Application service semantic remains exact BEFORE.
14. Activation gate remains exact BEFORE.
15. Manager predecessor runtime remains the original Manager object/image with restart_count=0.
16. Home Assistant runtime/image remains valid with restart_count=0.
17. HA MQTT binding remains unchanged.
18. Current F4 authority remains valid.
19. No other active maintenance transaction exists.
20. Broker evidence proves a narrow baseline invalidation rather than a product mutation:
   - same broker container_id as plan baseline;
   - same broker image_id as plan baseline;
   - same broker image_ref;
   - same broker network_mode;
   - restart_count still 0;
   - TCP/8883 listener exactly 1;
   - broker unit active and enabled;
   - only broker started_at differs from plan baseline;
   - current kernel boot epoch is later than the plan baseline and precedes the current Broker StartedAt;
   - Broker StartedAt belongs to the current boot.
21. Product deployment reality remains BEFORE throughout the invalidation transaction mutation.

Any broader Broker difference must STOP instead of being treated as a baseline invalidation.

## 5. Maintenance transaction helper

Add a narrow helper to n3w_t1_maintenance_transaction.py:

block_claimed_ready_before_apply(document, reason=...)

Contract:
- accepts only READY;
- authorization must already be consumed;
- replay_allowed must be false;
- operation_seq must be 0;
- operations must be empty;
- no pending operation;
- observed_after must be empty;
- only claim execution sessions are allowed;
- transitions READY -> BLOCKED;
- increments generation through the existing transition() helper;
- sets last_operation to a dedicated value such as baseline_invalidated_before_apply;
- sets a bounded reason such as BROKER_STARTED_AT_CHANGED_AFTER_T1_REBOOT;
- does not alter immutable transaction bindings.

This helper is deliberately separate from abort_claimed_ready_before_apply(). ABORTED remains reserved for the existing supersession retirement model.

## 6. E03-specific invalidation executor

Add a dedicated narrow executor rather than widening the existing retirement executor.

Suggested source:
tools/n3w_t1_r10_e03_replacement_baseline_invalidation.py

Operations:
- preflight: read-only, emits a canonical invalidation plan hash.
- claim: consumes a one-shot invalidation authorization record; maintenance-ledger mutation only.
- execute: under the global maintenance lock, rebinds the exact target transaction and exact live invalidation evidence, then performs READY -> BLOCKED.
- status: read-only.

The invalidation evidence must bind:
- target transaction SHA/generation before;
- exact immutable transaction projection;
- exact plan SHA;
- broker baseline from plan;
- observed current broker identity;
- current boot_id_sha256 and boot_time;
- deployment/service/gate BEFORE fingerprints;
- current F4 authority SHA;
- executor source/blob/module-set;
- final BLOCKED transaction SHA/generation after execution.

Crash-resume semantics must be one-shot and fail closed, following the existing retirement evidence pattern without creating a retirement/supersession record.

## 7. Interaction with future preauthorization

BLOCKED is already a terminal maintenance state and is not included in ACTIVE_STATES. Therefore a correctly BLOCKED replacement transaction does not block a fresh E03 preauthorization.

committed_supersession() scans matching ABORTED transactions and retirement evidence only. The BLOCKED replacement transaction is intentionally ignored, preserving the single existing committed supersession pair.

Fresh preauthorization must still independently prove:
- current deployment BEFORE;
- current Broker baseline;
- current Manager/HA/F4 authority;
- the original committed supersession pair.

Fresh claim then creates a new transaction ID, new authorization, new execution session and new plan bound to the current post-reboot runtime reality.

## 8. Required regression tests

At minimum:

1. READY + consumed + no operations + only claim session + exact narrow reboot-started_at drift -> invalidation preflight PASS.
2. Same case -> execute transitions only READY -> BLOCKED.
3. BLOCKED transaction is terminal and excluded from ACTIVE_STATES.
4. Fresh E03 preauthorization succeeds with the original single ABORTED + COMMITTED supersession pair plus one unrelated BLOCKED replacement.
5. Broker container_id drift -> STOP.
6. Broker image_id drift -> STOP.
7. Broker restart_count > 0 -> STOP.
8. Broker listener missing/duplicate -> STOP.
9. Broker unit inactive/disabled -> STOP.
10. Broker StartedAt unchanged -> STOP because no invalidation condition exists.
11. Broker StartedAt changes without current-boot temporal proof -> STOP.
12. deployment/service/gate not exact BEFORE -> STOP.
13. apply/rollback execution session present -> STOP.
14. operation_seq > 0 / operations non-empty / pending operation -> STOP.
15. observed_after non-empty -> STOP.
16. immutable target binding drift -> STOP.
17. authorization replay -> STOP.
18. crash before target save -> recoverable without false BLOCKED.
19. crash after target save -> exact BLOCKED poststate can be resumed/finalized idempotently.
20. no second ABORTED transaction or second supersession retirement record is created.

## 9. Current gate decision

SOURCE_DESIGN=FROZEN
CURRENT_REPLACEMENT_APPLY_ALLOWED=false
CURRENT_REPLACEMENT_TRANSACTION_MUTATION_ALLOWED=false
BLOCKED_INVALIDATION_SOURCE_IMPLEMENTED=false
PRODUCT_MUTATION=false
SERVICE_STOP_START=false
DOCKER_MUTATION=false
BOARD_ACCESS=false
ROLLBACK_REQUIRED=false

Next ONE gate:
N3W_T1_E03_REPLACEMENT_BASELINE_INVALIDATION_TERMINAL_BLOCKED_SOURCE_REPAIR_20261030_01
