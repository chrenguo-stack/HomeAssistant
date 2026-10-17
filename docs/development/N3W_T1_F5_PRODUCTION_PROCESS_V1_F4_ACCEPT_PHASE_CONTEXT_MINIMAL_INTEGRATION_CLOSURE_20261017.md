# N3W T1 F5 Production Process V1 — F4_ACCEPT Phase-Context Minimal Integration Closure

Date: 2026-10-17

## Gate result

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_F4_ACCEPT_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01
RESULT=CLOSED_PASS

PR=612
PR_STATE=OPEN_DRAFT
SOURCE_BRANCH=feat/n3w-t1-f5-production-process-v1-source-20261017
SOURCE_HEAD=7f214750128138d7bfaf2b374d9e3302b12d442a
BASE_MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb

CI_RESULT=PASS:17/17
CI_FAILURE=0
CI_PENDING=0

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

## Closed contract

The normal F5 runtime-acceptance route now requires an exact target-validated `F4_ACCEPT` production phase context.

Before runtime acceptance begins, the adapter verifies the local F4 predecessor chain belongs to the same production run, the transaction is exactly `RUNTIME_STARTED`, production services are active, runtime acceptance remains required, and persistence is still disabled.

The adapter writes a durable non-replayable local acceptance claim before entering the existing runtime acceptance primitive. The claim binds the run, phase claim, plan, source, release, artifact, predecessor, target, the exact pre-acceptance F4 transaction SHA256 and the derived internal F4 acceptance authorization.

No second operator approval is introduced. The existing `_accept_runtime` implementation remains the owner of runtime topology/TLS/identity/business-state checks and fail-closed rollback.

Success is accepted only at `RUNTIME_ACCEPTED`, with production services still active, persistence disabled, certificate timer disabled, board access false, and an exact durable runtime-acceptance report SHA256. The completion record binds the local claim, post-acceptance F4 transaction, runtime acceptance report and returned result.

A post-claim failure consumes the local phase execution and is not silently replayable.

## Focused review

~~~text
NORMAL_F5_F4_ACCEPT_REQUIRES_PRODUCTION_PHASE_CONTEXT=PASS
TARGET_AUTHORITY_VALIDATION=PASS
PRODUCTION_PREDECESSOR_CHAIN=PASS
PRESTATE_REQUIRES_RUNTIME_STARTED=PASS
PRESTATE_REQUIRES_SERVICES_ACTIVE=PASS
PRESTATE_REQUIRES_PERSISTENCE_DISABLED=PASS
LOCAL_EXECUTION_CLAIM_BEFORE_MUTATION=PASS
SECOND_HUMAN_APPROVAL=false
EXISTING_F4_RUNTIME_ACCEPTANCE_PRIMITIVE_REUSED=true
POST_CLAIM_REPLAY_ALLOWED=false
SUCCESS_REQUIRES_RUNTIME_ACCEPTED=PASS
SUCCESS_BINDS_RUNTIME_ACCEPTANCE_REPORT=PASS

PERSIST_CERT_CHANGED=false
REBOOT_CHANGED=false
BOARD_ACCESS=false
~~~

## Exact CI evidence

All 17 workflows observed on `7f214750128138d7bfaf2b374d9e3302b12d442a` completed successfully.

Key runs:

~~~text
F5_SOURCE_CI=PASS:39029307121
F4_ACTIVATION_SOURCE_CI=PASS:39029307114
FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=PASS:39029307171
EXPLICIT_PROVISIONING_SOURCE_CI=PASS:39029307156
GOLDEN_MASTER_SOURCE_CI=PASS:39029307115
PUBLIC_REPOSITORY_SAFETY_CI=PASS:39029307137
F4_EXACT_CONTROL_PACKAGE_CI=PASS:39029307155
GREENHOUSE_MANAGER_CI=PASS:39029307178
~~~

The observed M0, M2, H3 and C-07 regression workflows also passed.

## Next boundary

The next F5 phase is `PERSIST_CERT`. It must reuse the existing F4 persistence enablement, first certificate audit and certificate timer enable-only primitives, under one exact production phase context, without entering reboot control.

~~~text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_PERSIST_CERT_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~
