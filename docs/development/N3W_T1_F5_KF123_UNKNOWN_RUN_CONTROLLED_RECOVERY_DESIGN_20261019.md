# N3-W / T1 F5 — KF-123 UNKNOWN run controlled recovery design

Date: 2026-10-19

## 0. Scope

~~~text
TASK=N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_DESIGN_20261019_01
RESULT=DESIGN_CLOSED_PASS

DESIGN_ONLY=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
SOURCE_MUTATION=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~

This design handles the preserved historical F5 run created by the KF-123 incident.

It does not replay the run, does not resume F3, does not start a new production run, and does not authorize any target mutation in this gate.

The required recovery is a bounded adjudication of an already terminal failed run whose outer F3 phase is still classified UNKNOWN even though later independent evidence proved the actual failure boundary.

## 1. Frozen proven incident facts

~~~text
RUN_ID=3e37993537f9317dfb8070fd53fa20384de86cbd7c2a234857b55602c1280799
RUN_STATE=TERMINAL
RUN_TERMINAL_STATE=FAIL
RUN_FAILURE_CLASS=UNKNOWN
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false

LAST_COMPLETED_PHASE=HOST_BASELINE
LAST_CLAIMED_PHASE=F3_DEPLOY

HOST_BASELINE_STATE=SUCCEEDED
HOST_BASELINE_RESULT_SHA256=a9ce1c749617193f2da6b66374c7a287868085b87e8eca246da34ff149470806
HOST_BASELINE_EXECUTION_RECORD_COUNT=2

F3_PHASE_STATE=UNKNOWN
F3_FAILURE_CODE=production_f3_claimed_or_unknown:production_f3_execution_not_proven
F3_RESULT_SHA256=null
F3_PRODUCTION_EXECUTION_RECORD_COUNT=0

PRODUCT_PATH_COUNT=0
CONTAINER_COUNT=0
IMAGE_COUNT=0
VOLUME_COUNT=0
PRODUCT_NETWORK_COUNT=0
PRODUCT_UNIT_LOADED_COUNT=0
REMOTE_F3_STAGING_COUNT=0
DOCKER_ACTIVE=true

PRODUCT_SERVICE_START=false
LIVE_REBOOT=false
BOARD_ACCESS=false
~~~

Independent target forensic proved that the F3 business executor did not create its production execution claim and that product deployment did not begin. The KF-123 source defect is separately CLOSED_PASS at PR #618 exact head.

These values are historical proven facts. Any future live recovery must first perform a new smallest read-only preauthorization check and must stop on drift.

## 2. Recovery choice

The recovery should use controlled reclassification, not replay and not a new F3 apply.

The current target production authority blocks a new approval when any run for the same target remains terminal with `failure_class=UNKNOWN`. That guard is correct and must not be weakened or bypassed.

The chosen recovery is:

~~~text
F3 phase: UNKNOWN -> FAILED
run failure_class: UNKNOWN -> FAILED

run state remains TERMINAL
run terminal_state remains FAIL
last_completed_phase remains HOST_BASELINE
last_claimed_phase remains F3_DEPLOY
authorization_consumed remains true
replay_allowed remains false
~~~

The historical F3 `failure_code` is preserved exactly. The recovery record carries the later forensic adjudication reason instead of rewriting the original failure text.

This is a classification repair only. It must not create a production-success result, phase result SHA, product material, or a new execution claim.

## 3. Why the phase may be reclassified

The original runtime conservatively marked F3 UNKNOWN because the Mac-side wrapper could not prove the target business claim after the dispatch error.

Later source inspection plus an independent target read-only session resolved that uncertainty:

- target bootstrap stopped at `payload_file_set_invalid`;
- the stop occurred before production phase context load and before target F3 business claim;
- F3 production execution ledger count is zero;
- product paths, images, containers, volumes, product networks and product units are absent;
- remote F3 staging residue is absent;
- no product service started and no reboot occurred.

Therefore the uncertainty that justified UNKNOWN has been resolved without replaying the historical mutation.

## 4. Dedicated recovery authority

Do not generalize the normal production approval path or weaken `existing_unknown_run_blocks_approval`.

Use a dedicated repository-owned recovery helper and a separate durable recovery ledger.

Proposed stable responsibility:

~~~text
tools/n3w_t1_f5_unknown_run_adjudicator.py
tests/tools/test_n3w_t1_f5_unknown_run_adjudicator.py
.github/workflows/n3w-t1-f5-unknown-run-adjudication-ci.yml

RECOVERY_ROOT=/var/lib/n3w-t1-f5-unknown-run-adjudications
RECOVERY_SCHEMA=gh.n3w-t1-f5-unknown-run-adjudication/1
RECOVERY_STATE=CLAIMED -> APPLYING -> ADJUDICATED
~~~

The recovery executable authority is separate from the future product release authority. Building or executing this helper must not silently redefine the repaired PR #618 product source.

## 5. Read-only inspector contract

The packaged helper must provide an `inspect` operation that performs no target mutation.

It may report ELIGIBLE only if all of the following are freshly true:

1. exact target identity matches the expected T1-B binding;
2. the exact historical run exists and is consumed/no-replay;
3. run state is TERMINAL, terminal state FAIL, failure class UNKNOWN;
4. last completed phase is HOST_BASELINE and last claimed phase is F3_DEPLOY;
5. HOST_BASELINE is SUCCEEDED and remains bound to its existing result;
6. F3 phase is UNKNOWN, result SHA is null, and the historical failure code is unchanged;
7. F3 production business-execution ledger count is exactly zero;
8. no product paths, containers, images, volumes, product networks or product units are present;
9. no preserved F3 staging root is present;
10. Docker baseline remains active as expected;
11. no prior KF-123 UNKNOWN-run adjudication record exists;
12. no later production run has been approved for the same target.

The read-only preauthorization must capture, at minimum:

~~~text
CURRENT_RUN_RECORD_SHA256=<fresh>
CURRENT_F3_PHASE_RECORD_SHA256=<fresh>
TARGET_BINDING_SHA256=<fresh verified binding>
RECOVERY_ROOT_ABSENT=true
~~~

Those fresh hashes become frozen inputs to any later live adjudication authorization.

## 6. Live adjudication contract

A later live mutation requires a new explicit one-shot authorization dedicated only to this recovery.

Proposed authorization scope:

~~~text
ONE_EXACT_UNKNOWN_RUN_ADJUDICATION=true
RUN_ID=3e37993537f9317dfb8070fd53fa20384de86cbd7c2a234857b55602c1280799
PHASE=F3_DEPLOY
EXPECTED_RUN_RECORD_SHA256=<fresh preauth value>
EXPECTED_F3_PHASE_RECORD_SHA256=<fresh preauth value>
MUTATION_SCOPE=f5_production_authority_and_adjudication_ledger_only
PRODUCT_SERVICE_START=false
LIVE_REBOOT=false
BOARD_ACCESS=false
PRODUCTION_RUN_REPLAY=false
NEW_PRODUCTION_RUN=false
~~~

The tool must require an exact literal confirmation and the exact fresh run/phase hashes.

Before touching the production run it must durably create and read back the recovery record as consumed/no-replay, then persist APPLYING.

## 7. Exact target mutation

Under the production-authority exclusive lock, the only allowed historical-run changes are:

### Phase record

~~~text
state: UNKNOWN -> FAILED
failure_code: unchanged
result_sha256: remains null
authorization_consumed: remains true
replay_allowed: remains false
binding: unchanged
~~~

### Run record

~~~text
state: remains TERMINAL
terminal_state: remains FAIL
failure_class: UNKNOWN -> FAILED
last_completed_phase: remains HOST_BASELINE
last_claimed_phase: remains F3_DEPLOY
authorization_consumed: remains true
replay_allowed: remains false
plan: unchanged
board_access: remains false
~~~

No other field may change except the existing mutable update timestamp.

The helper then records ADJUDICATED in its own recovery ledger.

## 8. Interruption and resume semantics

The two historical records cannot be treated as a database transaction. The helper must therefore be resumable under the same consumed recovery authorization only.

Allowed resumable substates:

~~~text
A. recovery=APPLYING
   phase=UNKNOWN
   run.failure_class=UNKNOWN
   -> perform phase and run adjudication

B. recovery=APPLYING
   phase=FAILED with exact preserved failure_code
   run.failure_class=UNKNOWN
   -> complete only the run classification

C. recovery=APPLYING
   phase=FAILED
   run.failure_class=FAILED
   -> complete only recovery ledger ADJUDICATED

D. recovery=ADJUDICATED
   exact final phase/run state
   -> report ALREADY_ADJUDICATED, no historical-run mutation
~~~

Any other mixed state is a hard STOP.

A different authorization ID must never resume the same recovery record.

Errors after the recovery ledger is created must conservatively report authorization consumed and mutation state UNKNOWN/PARTIAL rather than claiming no mutation.

## 9. Accepted final state

~~~text
RUN_STATE=TERMINAL
RUN_TERMINAL_STATE=FAIL
RUN_FAILURE_CLASS=FAILED
RUN_REPLAY_ALLOWED=false

LAST_COMPLETED_PHASE=HOST_BASELINE
LAST_CLAIMED_PHASE=F3_DEPLOY

HOST_BASELINE_STATE=SUCCEEDED
F3_PHASE_STATE=FAILED
F3_FAILURE_CODE=production_f3_claimed_or_unknown:production_f3_execution_not_proven
F3_RESULT_SHA256=null

F3_PRODUCTION_EXECUTION_RECORD_COUNT=0
PRODUCT_PATH_COUNT=0
CONTAINER_COUNT=0
IMAGE_COUNT=0
VOLUME_COUNT=0
PRODUCT_NETWORK_COUNT=0
PRODUCT_UNIT_LOADED_COUNT=0

RECOVERY_STATE=ADJUDICATED
RECOVERY_AUTHORIZATION_CONSUMED=true
RECOVERY_REPLAY_ALLOWED=false

PRODUCT_SERVICE_START=false
LIVE_REBOOT=false
BOARD_ACCESS=false
~~~

The historical run remains a failed run forever. This recovery does not convert it to PASS.

## 10. Independent postexecution verification

After any live adjudication, a separate fresh read-only session must independently verify:

- exact run and phase terminal classifications;
- recovery record ADJUDICATED and consumed/no-replay;
- HOST_BASELINE remains SUCCEEDED;
- F3 business execution record count remains zero;
- product material remains absent;
- no product service start and no reboot occurred.

Only after that separate read-only closure may the historical UNKNOWN-run blocker be considered cleared.

## 11. Product-source and release boundary

The KF-123 product source repair remains PR #618:

~~~text
PR618_HEAD=4afd89b56e9925d7330b27f3f734ebcefc09182c
PR618_TREE=da864ffb6c44de3efccb93516e5e786f16219cd9
PR618_FINAL_SOURCE_REVIEW=CLOSED_PASS
~~~

The UNKNOWN-run recovery helper is an engineering recovery artifact, not a new product capability.

A new exact F3/F5 production release must still be built from the approved repaired product source before another F5-9 production run. No previous replacement release may be reused because it predates the KF-123 repair.

A future new F5-9 run also requires its own separate fresh production authorization.

## 12. Source implementation requirements

The next source-only gate should implement and review only the bounded helper described above.

Required regression cases:

1. exact eligible TERMINAL/FAIL/UNKNOWN prestate;
2. reject nonterminal or PASS run;
3. reject already FAILED without matching recovery record;
4. reject wrong run/phase hash before recovery claim;
5. reject changed F3 failure code/binding;
6. reject any F3 production business-execution record;
7. reject any product material or product service state;
8. exact one-shot recovery authorization binding;
9. split-state resume after phase reclassification;
10. split-state resume after run reclassification;
11. different authorization cannot resume;
12. ADJUDICATED repeated call is read-only/idempotent;
13. no reboot, service start, Docker mutation, package install, board access or production replay path exists;
14. conservative mutation reporting after any recovery-ledger or historical-ledger write.

## 13. Current gate closure

~~~text
KF123_UNKNOWN_RUN_RECOVERY_DESIGN=CLOSED_PASS

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
SOURCE_MUTATION=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false

NEXT_ONE_GATE=
N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_IMPLEMENTATION_20261019_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~

No live recovery authorization is granted by this design.
