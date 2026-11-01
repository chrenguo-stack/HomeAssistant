# N3W T1 F5 V2 readiness partial-unit evidence source repair

Date: 2026-10-22

## Gate

~~~text
TASK=N3W_T1_KF127_PR642_POST_KF128_FRESH_REBIND_AND_MERGE_DECISION_20261022_01
ORIGINAL_BASE_MAIN=84cdc4faeb1f5afd5eb5f5df276ac669f9fdf7e0
REBIND_BASE_MAIN=58dec8e0bdcb2882aff6ffaa5bf991e97505a69a
PRE_REBIND_PR642_HEAD=65864bcdea4083281e0b64c940dfc2e894bf4a2d
REAL_T1_FAILED_RUN=TERMINAL_NO_REPLAY
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
REFLASH=false
PRODUCTION_EXECUTION=false
PR642_MERGED=true
~~~

## Real-T1 evidence

~~~text
TERMINAL_STAGE=POST_REBOOT_READINESS
ERROR_CODE=readiness_unit_evidence_invalid
TARGET_FAILURE_CLASS=VERIFY_FAILED
SYSTEMD_STATE_AT_FORENSIC=starting
FORENSIC_MANIFEST=PASS
FORENSIC_UNAVAILABLE_COUNT=0
MARKER_STATE=STARTED
~~~

This proves the prior reboot-boundary defect is no longer the active failure:
the new boot was observed and execution advanced into readiness.

## Root cause

`readiness()` reads `systemd` state first, but before applying the intended
`systemd=starting -> WAIT` rule it probes six units. The helper previously
required every `systemctl show` call to immediately contain all four fields:

~~~text
LoadState
ActiveState
Result
ExecMainStatus
~~~

During early boot, systemd can legitimately expose a partial property set.
The helper therefore raised `readiness_unit_evidence_invalid` before the
caller could return the already-designed `WAIT/systemd_starting` result.

A second contract defect was found during source review: the six required units
include `CERT_TIMER` (`.timer`), but the old helper imposed the service-only
`ExecMainStatus` property on every unit type. Timer readiness only needs the
common `LoadState` / `ActiveState` plus timer `Result`; requiring a service main
process status from a timer creates a deterministic false failure once the new
boot reaches this code path.

The existing unit test covered `systemd=starting` only with complete mocked
service-shaped evidence for every unit, including the timer, and therefore
missed both the real boot-convergence case and the unit-type contract mismatch.

## Repair invariant

During `systemd=starting` or `initializing`:

- partial unit evidence is transient and may produce WAIT;
- explicit failure evidence already present in a partial record remains fatal;
- missing fields must never create PASS.

Field completeness is unit-type specific:

- service units require `LoadState`, `ActiveState`, `Result`, `ExecMainStatus`;
- `CERT_TIMER` requires `LoadState`, `ActiveState`, `Result` and is not required
  to expose service-only `ExecMainStatus`.

Once systemd is `running` or `degraded`:

- incomplete evidence relative to the correct unit-type contract remains
  `readiness_unit_evidence_invalid`;
- the strict final readiness contract is unchanged.

## Implementation

`_readiness_unit_state()` now preserves a non-empty partial property map
instead of raising before the caller knows the boot-convergence state.

`readiness()` separately tracks:

- unit command unavailable;
- unit evidence incomplete against the correct service/timer field contract;
- explicit negative evidence.

Explicit negative fields remain fail-closed even if other fields are absent.
The existing `systemd_starting` WAIT branch occurs before strict completeness
is required. For operational systemd states, incomplete unit evidence still
raises `readiness_unit_evidence_invalid`.

## Regression coverage

Added tests prove:

1. starting + partial normal service evidence -> WAIT/systemd_starting;
2. running + incomplete service evidence -> hard FAIL;
3. starting + partial explicit failed-unit evidence -> hard FAIL;
4. timer evidence without service-only `ExecMainStatus` can still reach PASS;
5. service evidence still requires `ExecMainStatus` after convergence;
6. the low-level helper preserves partial non-empty output.

Existing strict verifier, external probes, 90-second observation and marker
acceptance are unchanged.

## State

~~~text
KF_127=F5_V2_READINESS_PARTIAL_UNIT_EVIDENCE_DURING_SYSTEMD_STARTING
ROOT_CAUSE_CONFIDENCE=HIGH
SOURCE_REPAIR_IMPLEMENTED=true
PRIOR_SOURCE_REVIEW_RESULT=CLOSED_PASS
PRIOR_OPEN_SOURCE_BLOCKER_COUNT=0
PRIOR_EXACT_HEAD_CI=14/14_PASS
POST_KF128_READINESS_SOURCE_DRIFT=false
POST_REBIND_HEAD=693bdfe98f16dbb55796203b30f443d02e2025e5
POST_REBIND_EXACT_HEAD_CI=14/14_PASS
MERGE_DECISION=PASS
PR642_MERGE_COMMIT=116e247af33af3e0e97e1e3696fdc5e59e925249
PR642_MERGE_TREE=c126faf04028914c0eb5c1d8015651f826c0f5dc
MERGE_TIME_SOURCE_DRIFT=false

NEXT_ONE_GATE=N3W_T1_POST_KF127_KF128_FRESH_EXACT_MAIN_RELEASE_REBUILD_PREPARATION_20261022_01
~~~


## Post-KF128 fresh rebind

PR #643/KF-128 and PR #644 are now in main. Fresh comparison against aligned
main `58dec8e0bdcb2882aff6ffaa5bf991e97505a69a` shows that KF-128 did not
modify the readiness unit-evidence region repaired by KF-127.

The rebind therefore preserves the reviewed KF-127 semantics without expansion:

~~~text
STARTING_PARTIAL_NORMAL_EVIDENCE=WAIT
STARTING_EXPLICIT_FAILED_EVIDENCE=FAIL
RUNNING_SERVICE_PARTIAL_EVIDENCE=FAIL
RUNNING_TIMER_WITHOUT_EXEC_MAIN_STATUS=VALID
MISSING_TIMER_RESULT=FAIL
KF128_SNAPSHOT_SESSION_REPAIR_PRESERVED=true
~~~

The previous PR #642 `mergeable=false` state is treated as branch/document
convergence after main advanced, not as evidence of a new functional conflict.
The fresh rebound exact-head CI completed 14/14 PASS. PR #642 then merged with an expected-head lock; the merge tree exactly equals the reviewed/rebound head tree, so no merge-time source drift occurred.


## Merge closure

~~~text
POST_REBIND_HEAD=693bdfe98f16dbb55796203b30f443d02e2025e5
POST_REBIND_SOURCE_REVIEW=CLOSED_PASS
POST_REBIND_OPEN_SOURCE_BLOCKER_COUNT=0
POST_REBIND_EXACT_HEAD_CI=14/14_PASS
PR642_MERGED=true
PR642_MERGE_COMMIT=116e247af33af3e0e97e1e3696fdc5e59e925249
PR642_FINAL_HEAD_TREE=c126faf04028914c0eb5c1d8015651f826c0f5dc
PR642_MERGE_TREE=c126faf04028914c0eb5c1d8015651f826c0f5dc
MERGE_TIME_SOURCE_DRIFT=false
KF127_SOURCE_CLOSURE=CLOSED_PASS
~~~

KF-127 and KF-128 acceptance-tool source repairs are now both in main. This
invalidates all older exact release/source authorities for any future production
attempt. A fresh exact-main release rebuild and local exact-release validation
are required before separately authorized live revalidation.
