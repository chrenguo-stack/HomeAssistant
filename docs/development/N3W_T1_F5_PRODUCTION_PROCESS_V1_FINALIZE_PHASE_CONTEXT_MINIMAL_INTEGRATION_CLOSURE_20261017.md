# N3W T1 F5 Production Process V1 — FINALIZE Phase-Context Minimal Integration Closure

Date: 2026-10-17

## Gate result

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_FINALIZE_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01
RESULT=CLOSED_PASS

PR=612
PR_STATE=OPEN_DRAFT
SOURCE_BRANCH=feat/n3w-t1-f5-production-process-v1-source-20261017
SOURCE_HEAD=894a26e2e2f7dcc98ae1340abb0712d286634c57
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

The normal F5 `FINALIZE` route now requires an exact target-validated production phase context and the same production run that previously consumed the one-shot reboot actuation boundary.

Before the durable finalizer is entered, FINALIZE proves:
- the reboot claim is still `REBOOT_PENDING`;
- reboot authorization is consumed and non-replayable;
- `reboot_actuation_attempted=true`;
- the actuation record belongs to the same production run;
- the current boot identity differs from the recorded pre-reboot identity;
- the frozen F4 transaction hash remains unchanged;
- source/control-package identity matches the approved production source.

FINALIZE writes its own durable non-replayable execution claim before entering the existing F4 reboot-acceptance finalizer.

The existing `finalize_reboot_acceptance` remains the mutation owner for durable `REBOOT_ACCEPTED`. The existing `verify_reboot_accepted` then provides terminal verification. Only after both pass does the F5 adapter return `device_acceptance=true`.

The FINALIZE completion record binds:
- the pre-acceptance pending reboot claim;
- the accepted reboot claim;
- the acceptance report;
- the current post-reboot boot identity;
- the F5 run/phase authorization.

A post-claim failure remains consumed and cannot silently replay the finalizer.

## Focused review

~~~text
NORMAL_F5_FINALIZE_REQUIRES_PRODUCTION_PHASE_CONTEXT=PASS
TARGET_AUTHORITY_VALIDATION=PASS
SAME_RUN_REBOOT_ACTUATION_REQUIRED=PASS
REBOOT_ACTUATION_ATTEMPTED_REQUIRED=PASS
NEW_BOOT_ID_REQUIRED=PASS
F4_TRANSACTION_UNCHANGED=PASS
SOURCE_BINDING=PASS
LOCAL_EXECUTION_CLAIM_BEFORE_FINALIZER=PASS
EXISTING_REBOOT_FINALIZER_REUSED=true
EXISTING_REBOOT_TERMINAL_VERIFY_REUSED=true
SUCCESS_REQUIRES_REBOOT_ACCEPTED=PASS
DEVICE_ACCEPTANCE_ONLY_AFTER_TERMINAL_VERIFY=PASS
POST_CLAIM_REPLAY_ALLOWED=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
~~~

## Exact CI evidence

All 17 workflows observed on `894a26e2e2f7dcc98ae1340abb0712d286634c57` completed successfully.

Key runs:

~~~text
F5_SOURCE_CI=PASS:39034820768
F4_ACTIVATION_SOURCE_CI=PASS:39034820804
FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=PASS:39034820772
EXPLICIT_PROVISIONING_SOURCE_CI=PASS:39034820751
GOLDEN_MASTER_SOURCE_CI=PASS:39034820790
PUBLIC_REPOSITORY_SAFETY_CI=PASS:39034820807
F4_EXACT_CONTROL_PACKAGE_CI=PASS:39034820770
GREENHOUSE_MANAGER_CI=PASS:39034820780
~~~

The observed M0, M2, H3 and C-07 regression workflows also passed.

## Next boundary

The next F5 phase is `CLOSE_RUN`. It must not redo product mutation. It closes the target-side production authority only after FINALIZE has succeeded and exact durable device-acceptance evidence is available. It must preserve the distinction between device acceptance and operator/session cleanup.

~~~text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_CLOSE_RUN_MINIMAL_INTEGRATION_20261017_01

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~
