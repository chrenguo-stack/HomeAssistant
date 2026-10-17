# N3W T1 F5 Production Process V1 — PERSIST_CERT Phase-Context Minimal Integration Closure

Date: 2026-10-17

## Gate result

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_PERSIST_CERT_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01
RESULT=CLOSED_PASS

PR=612
PR_STATE=OPEN_DRAFT
SOURCE_BRANCH=feat/n3w-t1-f5-production-process-v1-source-20261017
SOURCE_HEAD=12703d0f0383140cb9655a4042818d08e5c15e54
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

The normal F5 `PERSIST_CERT` route now requires an exact target-validated production phase context and verifies the same-run F4 chain has already reached `RUNTIME_ACCEPTED`.

Before any persistence/certificate mutation, the adapter verifies the F4_PREPARE, F4_ACTIVATE and F4_ACCEPT internal authorization chain, the durable runtime-acceptance report binding, active production services, persistence still disabled, and certificate timer still disabled.

The adapter writes one durable non-replayable local `PERSIST_CERT` claim before entering the existing F4 primitives. The claim binds the production run, phase claim, plan, source, release, artifact, predecessor, target and the exact pre-phase F4 transaction SHA256.

Within that single F5 phase, three distinct deterministic internal F4 authorization IDs are used in order:

1. existing `_enable_persistence`;
2. existing `_certificate_first_audit`;
3. existing `_enable_certificate_timer`.

The three existing F4 primitives remain the business/mutation owners. Their fail-closed behavior is unchanged.

Success requires `PRE_REBOOT_READY`, persistence enabled, first certificate audit passed, certificate status hash-bound, certificate timer enabled but not active before reboot, production services still active, and board access false. The completion record verifies all three internal authorization IDs were claimed, consumed and non-replayable, then binds the final F4 transaction, runtime acceptance report, certificate status and all three substep result digests.

A post-claim failure consumes the F5 local phase execution and cannot be silently replayed.

## Focused review

~~~text
NORMAL_F5_PERSIST_CERT_REQUIRES_PRODUCTION_PHASE_CONTEXT=PASS
TARGET_AUTHORITY_VALIDATION=PASS
SAME_RUN_F4_PREDECESSOR_CHAIN=PASS
RUNTIME_ACCEPTANCE_BINDING=PASS
LOCAL_EXECUTION_CLAIM_BEFORE_MUTATION=PASS
SECOND_HUMAN_APPROVAL=false
EXISTING_F4_PERSISTENCE_PRIMITIVE_REUSED=true
EXISTING_F4_CERTIFICATE_AUDIT_PRIMITIVE_REUSED=true
EXISTING_F4_CERTIFICATE_TIMER_PRIMITIVE_REUSED=true
SUBSTEP_AUTHORIZATION_IDS_DISTINCT=true
SUBSTEP_AUTHORIZATION_CONSUMED_BINDING=PASS
POST_CLAIM_REPLAY_ALLOWED=false
SUCCESS_REQUIRES_PRE_REBOOT_READY=PASS

REBOOT_EXECUTED=false
REBOOT_CONTROL_CHANGED=false
BOARD_ACCESS=false
~~~

## Exact CI evidence

All 17 workflows observed on `12703d0f0383140cb9655a4042818d08e5c15e54` completed successfully.

Key runs:

~~~text
F5_SOURCE_CI=PASS:39033060543
F4_ACTIVATION_SOURCE_CI=PASS:39033060482
FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=PASS:39033060512
EXPLICIT_PROVISIONING_SOURCE_CI=PASS:39033060555
GOLDEN_MASTER_SOURCE_CI=PASS:39033060520
PUBLIC_REPOSITORY_SAFETY_CI=PASS:39033060591
F4_EXACT_CONTROL_PACKAGE_CI=PASS:39033060527
GREENHOUSE_MANAGER_CI=PASS:39033060509
~~~

The observed M0, M2, H3 and C-07 regression workflows also passed.

## Next boundary

The next F5 phase is `REBOOT_CONTROL`. It must bind the exact PRE_REBOOT_READY F4 state to the existing reboot authority/control package and provide one durable, non-replayable reboot actuation boundary. This next source gate must not perform a live reboot.

~~~text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_REBOOT_CONTROL_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~
