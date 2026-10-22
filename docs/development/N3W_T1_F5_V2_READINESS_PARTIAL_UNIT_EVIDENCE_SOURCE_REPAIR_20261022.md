# N3W T1 F5 V2 readiness partial-unit evidence source repair

Date: 2026-10-22

## Gate

~~~text
TASK=N3W_T1_F5_V2_READINESS_PARTIAL_UNIT_EVIDENCE_SOURCE_REPAIR_20261022_01
BASE_MAIN=84cdc4faeb1f5afd5eb5f5df276ac669f9fdf7e0
REAL_T1_FAILED_RUN=TERMINAL_NO_REPLAY
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
REFLASH=false
PRODUCTION_EXECUTION=false
MERGE=false
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

The existing unit test covered `systemd=starting` only with complete mocked
unit evidence and missed this real boot-convergence case.

## Repair invariant

During `systemd=starting` or `initializing`:

- partial unit evidence is transient and may produce WAIT;
- explicit failure evidence already present in a partial record remains fatal;
- missing fields must never create PASS.

Once systemd is `running` or `degraded`:

- incomplete structured unit evidence remains
  `readiness_unit_evidence_invalid`;
- the strict final readiness contract is unchanged.

## Implementation

`_readiness_unit_state()` now preserves a non-empty partial property map
instead of raising before the caller knows the boot-convergence state.

`readiness()` separately tracks:

- unit command unavailable;
- unit evidence incomplete;
- explicit negative evidence.

Explicit negative fields remain fail-closed even if other fields are absent.
The existing `systemd_starting` WAIT branch occurs before strict completeness
is required. For operational systemd states, incomplete unit evidence still
raises `readiness_unit_evidence_invalid`.

## Regression coverage

Added tests prove:

1. starting + partial normal unit evidence -> WAIT/systemd_starting;
2. running + the same partial evidence -> hard FAIL;
3. starting + partial explicit failed-unit evidence -> hard FAIL;
4. the low-level helper preserves partial non-empty output.

Existing strict verifier, external probes, 90-second observation and marker
acceptance are unchanged.

## State

~~~text
KF_127=F5_V2_READINESS_PARTIAL_UNIT_EVIDENCE_DURING_SYSTEMD_STARTING
ROOT_CAUSE_CONFIDENCE=HIGH
SOURCE_REPAIR_IMPLEMENTED=true
SOURCE_REVIEW_PENDING=true

NEXT_ONE_GATE=N3W_T1_F5_V2_READINESS_PARTIAL_UNIT_EVIDENCE_SOURCE_REVIEW_20261022_01
~~~
