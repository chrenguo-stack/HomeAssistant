# N3-W T1 E03 Claimed Transaction Retirement Source Repair Progress

Date: 2026-10-30

## Gate

~~~text
TASK=N3W_T1_E03_CLAIMED_TRANSACTION_RETIREMENT_SOURCE_REPAIR_20261030_01
PR740_EXACT_HEAD=9f8339209a19ab5142002eeb72a396cdfd482b46
SOURCE_IMPLEMENTATION=PASS
INDEPENDENT_SOURCE_REVIEW=PASS
SOURCE_REPAIR_CLOSED_PASS=false
CLOSURE_BLOCKER=EXISTING_F5_V2_SOURCE_CI_RESULT_PENDING
NEW_SOURCE_BLOCKER_COUNT=0
T1_ACCESS=false
LIVE_RETIREMENT_PREFLIGHT=false
RETIREMENT_AUTHORIZATION_CLAIMED=false
LIVE_TRANSACTION_MUTATION=false
PRODUCT_MUTATION=false
BOARD_ACCESS=false
ROLLBACK_REQUIRED=false
MERGE=false
CURRENT_STOP_POINT=SOURCE_REPAIR_IMPLEMENTED_REVIEW_PASS_WAITING_ONLY_FOR_EXISTING_F5_V2_SOURCE_CI
NEXT_ONE_GATE=N3W_T1_E03_CLAIMED_TRANSACTION_RETIREMENT_SOURCE_REPAIR_CLOSURE_AFTER_F5_20261030_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

## Implemented source

The repository now contains a dedicated claimed-transaction retirement path rather than
post-claim executor takeover.

Key source:

- tools/n3w_t1_maintenance_transaction.py
- tools/n3w_t1_r10_e03_claimed_transaction_retirement.py
- tools/n3w_t1_r10_e03_successor_recovery.py
- tests/tools/test_n3w_t1_maintenance_transaction.py
- tests/tools/test_n3w_t1_r10_e03_claimed_transaction_retirement.py
- tests/tools/test_n3w_t1_r10_e03_successor_recovery.py
- .github/workflows/n3w-r10-e03-manager-successor-refresh-live-source-ci.yml

The maintenance library now exposes a narrow
`abort_claimed_ready_before_apply()` helper. It permits only a claimed READY transaction
with replay disabled, zero operation history, no pending operation, no observed-after
state and no non-claim execution session to transition to terminal ABORTED.

The retirement executor exposes only preflight, claim, retire and status. It has no
product apply operation and no service stop/start, Docker load/tag/rmi or board path.

## Retirement authority

Retirement preflight binds:

- exact target transaction SHA-256 and generation;
- target transaction immutable executor/plan/authorization/release/artifact authority;
- exact host binding and predecessor evidence;
- exact deployment/service/maintenance-gate BEFORE reality;
- Manager, Home Assistant and Broker continuity;
- listener and service-owner continuity;
- current F4 authority;
- retirement executor source/blob/module-set authority.

Retirement authorization is separate, one-shot, consumed and non-replayable.

The only permitted target transaction change is READY -> ABORTED through the normal
TransactionStore. All immutable old-transaction bindings remain byte-stable.

The retirement executor binds continuation to the original execution-session hash.
PREPARED, CLAIMED-before-ABORTED and ABORTED-before-retirement-evidence-COMMITTED crash
windows are recoverable only under the same exact authority.

## Replacement E03 supersession

Replacement E03 preauthorization now discovers and freezes a terminal-replacement
supersession block only when both of these exist and match exactly:

1. the final ABORTED old transaction;
2. the COMMITTED retirement evidence.

Loss of either side, byte drift, generation drift, non-COMMITTED retirement evidence or
ambiguous multiplicity fails closed.

Replacement claim recomputes the complete preauthorization under the global maintenance
lock. Runtime mutation rebind and read-only status both revalidate the supersession
authority. The repaired executor cannot mutate the old executor-bound READY transaction.

The original E03 predecessor evidence remains the predecessor binding. The retired
successor transaction is linked only through the supersession block.

## Independent source review

The independent review found and repaired the following additional false-PASS or
crash-recovery gaps before this progress snapshot:

1. retirement eligibility lacked explicit host/predecessor/E03-plan binding;
2. retirement plan and durable record lacked full cross-binding;
3. PREPARED claim interruption needed exact resume semantics;
4. retire continuation needed the same execution-session binding;
5. one-sided retirement evidence could otherwise resemble a fresh system;
6. E03 read-only status did not yet revalidate supersession authority.

The maintenance activation gate was also independently checked: ABORTED is terminal and
is not considered active, so a successfully retired transaction does not permanently
block service startup.

## CI at bounded poll stop

~~~text
E03_LIVE_SOURCE_CI_RUN=41027728125
E03_LIVE_SOURCE_CI=SUCCESS
E03_PREFLIGHT_CI_RUN=41027728117
E03_PREFLIGHT_CI=SUCCESS
PUBLIC_REPOSITORY_SAFETY_RUN=41027727934
PUBLIC_REPOSITORY_SAFETY=SUCCESS
FAST_SOURCE_EXACT_RUN=41027728240
FAST_SOURCE_EXACT=SUCCESS
GREENHOUSE_MANAGER_CI_RUN=41027728173
GREENHOUSE_MANAGER_CI=SUCCESS
FRESH_EXACT_ARM64_RUN=41027728219
FRESH_EXACT_ARM64=SKIPPED_EXPECTED_DRAFT
F5_V2_SOURCE_CI_RUN=41027728040
F5_V2_SOURCE_CI=IN_PROGRESS_AT_POLL_LIMIT
~~~

An earlier exact-head focused run during final review,
`41027557075`, completed successfully with `286 passed in 0.79s`.

No latest-head workflow failure was observed at the bounded polling stop. The broad F5 V2
source workflow was still in progress, so this gate is not yet recorded CLOSED_PASS.

## Boundary

No T1 access, live retirement preflight, retirement authorization claim, live transaction
mutation, product mutation, board access or merge occurred in this source-repair gate.

The next gate is limited to checking the already-running F5 V2 source CI result and
closing the source-repair record if it succeeded. It must not enter live T1 retirement
preflight automatically.
