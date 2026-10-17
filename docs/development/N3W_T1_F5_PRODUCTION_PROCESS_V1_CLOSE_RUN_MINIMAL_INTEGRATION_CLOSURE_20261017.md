# N3W T1 F5 Production Process V1 — CLOSE_RUN Minimal Integration Closure

Date: 2026-10-17

## Gate result

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_CLOSE_RUN_MINIMAL_INTEGRATION_20261017_01
RESULT=CLOSED_PASS

PR=612
PR_STATE=OPEN_DRAFT
SOURCE_BRANCH=feat/n3w-t1-f5-production-process-v1-source-20261017
SOURCE_HEAD=98566f72f89c8a2f81d606f8995be9dcbba99978
BASE_MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb

CI_RESULT=PASS:17/17
CI_FAILURE=0
CI_PENDING=0

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

## Closed contract

F5 `CLOSE_RUN` is now a specialized target-side closure boundary. The generic phase `complete` path is explicitly forbidden from closing `CLOSE_RUN`.

Before target-side terminal PASS is written, the production authority verifies:

- every previous F5 phase record is `SUCCEEDED`;
- every previous phase authorization is consumed and non-replayable;
- no prior phase carries a failure code;
- the stored FINALIZE phase result hash equals the exact supplied FINALIZE result;
- FINALIZE belongs to the same production run;
- FINALIZE proves `REBOOT_ACCEPTED`;
- FINALIZE proves `device_acceptance=true`;
- the CLOSE_RUN predecessor is the exact persisted FINALIZE phase record.

Only the dedicated `close-run` path may change the target production run to:

~~~text
state=TERMINAL
terminal_state=PASS
last_completed_phase=CLOSE_RUN
~~~

The target close result deliberately records:

~~~text
operator_session_closed_claimed=false
~~~

Target-side product acceptance is therefore not allowed to impersonate Mac/operator SSH cleanup.

## Evidence semantics

The normal production orchestrator now keeps three facts separate:

~~~text
device_acceptance
evidence_complete
operator_session_closed
~~~

`device_acceptance=true` is preserved if FINALIZE has already passed, even if later target closure or session cleanup fails.

`evidence_complete=true` is not asserted until target CLOSE_RUN itself has succeeded.

A later SSH/session cleanup failure preserves:

~~~text
device_acceptance=true
evidence_complete=true
operator_session_closed=false
final_outcome=FAIL
~~~

A target CLOSE_RUN failure preserves device acceptance but keeps:

~~~text
device_acceptance=true
evidence_complete=false
final_outcome=FAIL
~~~

This prevents a failed production-process closure from erasing the underlying device-acceptance fact while also preventing incomplete evidence from being published as complete.

## Focused review

~~~text
GENERIC_COMPLETE_CAN_CLOSE_RUN=false
SPECIALIZED_CLOSE_RUN_REQUIRED=true
ALL_PRIOR_PHASES_SUCCEEDED_REQUIRED=true
ALL_PRIOR_PHASES_CONSUMED_NONREPLAYABLE_REQUIRED=true
FINALIZE_RESULT_EXACT_HASH_BINDING=PASS
FINALIZE_REBOOT_ACCEPTED_REQUIRED=true
FINALIZE_DEVICE_ACCEPTANCE_REQUIRED=true
EXACT_FINALIZE_PREDECESSOR_REQUIRED=true
TARGET_TERMINAL_PASS_ONLY_AFTER_SPECIALIZED_CLOSE=PASS

DEVICE_ACCEPTANCE_SEPARATE_FACT=true
EVIDENCE_COMPLETENESS_SEPARATE_FACT=true
OPERATOR_SESSION_CLOSED_SEPARATE_FACT=true
TARGET_CLOSE_CLAIMS_SESSION_CLEANUP=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
~~~

## Source evolution inside the gate

Initial CLOSE_RUN integration:

`428a7264af266191697787c1245ad9e68b398b85`

The first F5 source CI exposed a negative-result-model inconsistency: target close failure correctly made overall outcome FAIL, but the orchestrator still hard-coded `evidence_complete=true`, which caused public result self-validation to reject the failure record.

Localized repair:

`adeb0c53fe67b917a65bfa16b35ab8d6f6215fb6`

Negative-test alignment and final source head:

`98566f72f89c8a2f81d606f8995be9dcbba99978`

The defect was in result/evidence semantics, not the target CLOSE_RUN authority path.

## Exact CI evidence

All 17 workflows observed on `98566f72f89c8a2f81d606f8995be9dcbba99978` completed successfully.

Key runs:

~~~text
F5_SOURCE_CI=PASS:39035937131
F4_ACTIVATION_SOURCE_CI=PASS:39035937159
FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=PASS:39035937143
EXPLICIT_PROVISIONING_SOURCE_CI=PASS:39035937104
GOLDEN_MASTER_SOURCE_CI=PASS:39035937136
PUBLIC_REPOSITORY_SAFETY_CI=PASS:39035937122
F4_EXACT_CONTROL_PACKAGE_CI=PASS:39035937526
GREENHOUSE_MANAGER_CI=PASS:39035937144
~~~

The observed M0, M2, H3 and C-07 regression workflows also passed.

## F5 phase-chain status

~~~text
F4_PREPARE=CLOSED_PASS
F4_ACTIVATE=CLOSED_PASS
F4_ACCEPT=CLOSED_PASS
PERSIST_CERT=CLOSED_PASS
REBOOT_CONTROL=CLOSED_PASS
FINALIZE=CLOSED_PASS
CLOSE_RUN=CLOSED_PASS
~~~

The normal F5 source phase chain is therefore source-complete at this boundary.

## Next boundary

The next work is no longer another F4/F5 business phase. It is the whole-F5 source-closure review and exact production release construction/binding.

~~~text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_WHOLE_SOURCE_CLOSURE_AND_EXACT_RELEASE_PREPARATION_20261017_01

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~
