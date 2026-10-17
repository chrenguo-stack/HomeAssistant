# N3W T1 F5 Production Process V1 — F4_ACTIVATE Phase-Context Minimal Integration Closure

Date: 2026-10-17

## Gate result

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_F4_ACTIVATE_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01
RESULT=CLOSED_PASS

PR=612
PR_STATE=OPEN_DRAFT
SOURCE_BRANCH=feat/n3w-t1-f5-production-process-v1-source-20261017
SOURCE_HEAD=c400c1d9b09a497c2537c10f9afceff726437b48
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

The normal F5 F4_ACTIVATE route now requires an exact target-validated `F4_ACTIVATE` production phase context.

Before the existing F4 activation primitive is entered, the adapter verifies that the F4 transaction is exactly `PREPARED`, production services are still stopped, and the F5 phase context is bound to the approved run, release, source, artifact, target and predecessor. It then writes a durable non-replayable local activation claim containing the pre-activation F4 transaction SHA256.

No second operator approval is introduced. The adapter derives a legacy-compatible internal activation authorization ID from the approved F5 production run. The existing `_activate` implementation remains the owner of Broker/Services startup and the existing rollback behavior.

Success is accepted only when the existing primitive reaches `RUNTIME_STARTED`, runtime acceptance remains required, production services are active, persistence remains disabled, the certificate timer remains disabled, and board access remains false. A completion record binds the local claim, post-activation F4 transaction and returned result.

A post-claim failure consumes the local phase execution and cannot be silently replayed.

## Focused review

~~~text
NORMAL_F5_F4_ACTIVATE_REQUIRES_PRODUCTION_PHASE_CONTEXT=PASS
TARGET_AUTHORITY_VALIDATION=PASS
PRESTATE_REQUIRES_PREPARED=PASS
PRESTATE_REQUIRES_SERVICES_STOPPED=PASS
LOCAL_EXECUTION_CLAIM_BEFORE_MUTATION=PASS
SECOND_HUMAN_APPROVAL=false
EXISTING_F4_ACTIVATE_PRIMITIVE_REUSED=true
POST_CLAIM_REPLAY_ALLOWED=false
SUCCESS_REQUIRES_RUNTIME_STARTED=PASS
SUCCESS_REQUIRES_RUNTIME_ACCEPTANCE_PENDING=PASS

F4_ACCEPT_CHANGED=false
PERSISTENCE_CHANGED=false
CERTIFICATE_CHANGED=false
REBOOT_CHANGED=false
~~~

The only CI repair in this gate was a missing `re` import in the new test. It was test-only and did not change product behavior.

## Exact CI evidence

All 17 workflows observed on `c400c1d9b09a497c2537c10f9afceff726437b48` completed successfully.

Key runs:

~~~text
F5_SOURCE_CI=PASS:39028305189
F4_ACTIVATION_SOURCE_CI=PASS:39028305201
FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=PASS:39028305210
EXPLICIT_PROVISIONING_SOURCE_CI=PASS:39028305150
GOLDEN_MASTER_SOURCE_CI=PASS:39028305166
PUBLIC_REPOSITORY_SAFETY_CI=PASS:39028305130
F4_EXACT_CONTROL_PACKAGE_CI=PASS:39028305075
GREENHOUSE_MANAGER_CI=PASS:39028305157
~~~

The observed M0, M2, H3 and C-07 regression workflows also passed.

## Next boundary

This closure does not execute live T1 work and does not merge PR #612.

The next source boundary is `F4_ACCEPT`: the normal F5 path must give the existing runtime-acceptance primitive its own exact target production phase context and one-shot local execution claim, without changing the runtime-acceptance business checks or entering persistence/certificate/reboot work.

~~~text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_F4_ACCEPT_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~
