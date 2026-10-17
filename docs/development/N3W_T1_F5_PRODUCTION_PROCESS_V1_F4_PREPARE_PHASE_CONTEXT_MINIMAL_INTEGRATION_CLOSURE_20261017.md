# N3W T1 F5 Production Process V1 — F4_PREPARE Phase-Context Minimal Integration Closure

Date: 2026-10-17

## 1. Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_F4_PREPARE_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01
RESULT=CLOSED_PASS

PR=612
PR_STATE=OPEN_DRAFT
SOURCE_BRANCH=feat/n3w-t1-f5-production-process-v1-source-20261017
SOURCE_HEAD=f4e3a76d5c5ab9259f9e3d53ed57fb6b9626f527
BASE_MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

This gate integrates only the existing F4 prepare mutation boundary with the F5 durable production-run authority.

## 2. Closed contract

The normal F5 route now requires an already-consumed target production phase context for exact phase `F4_PREPARE`.

Before the existing F4 prepare primitive is entered, the adapter:

- validates the context against the target production authority;
- requires exact run, phase, source, release, artifact, target and predecessor bindings carried by that authority context;
- requires a non-null predecessor binding;
- forbids mixing the production context with the historical `--confirm` / `--authorization-id` route;
- validates the exact F4 package source binding;
- writes an immutable target-local production execution claim before the first F4 prepare mutation;
- treats the claim as consumed and non-replayable even if the underlying prepare later fails.

The existing `_prepare` F4 business state machine remains the mutation owner. The normal F5 adapter derives the legacy-compatible internal F4 authorization identifier from the production run instead of asking the operator for a second approval.

A successful F5 F4_PREPARE execution is durably hash-bound to:

- `FACTORY_ACCEPTED.json`;
- `F4_ACTIVATION_TRANSACTION.json`;
- the local production execution claim;
- the returned prepare result.

Historical engineering/recovery interfaces remain available and are not exposed as the normal F5 production path.

## 3. Scope review

~~~text
REUSE_EXISTING_F4_BUSINESS_LOGIC=PASS
REWRITE_F4_STATE_MACHINE=false
REPAIR_COMMANDS_IN_NORMAL_PATH=false

NORMAL_F5_F4_PREPARE_REQUIRES_PRODUCTION_PHASE_CONTEXT=PASS
REQUIRED_PHASE=F4_PREPARE
TARGET_AUTHORITY_VALIDATION=PASS
SOURCE_RELEASE_TARGET_PREDECESSOR_BINDING=PASS
SECOND_HUMAN_APPROVAL=false
LOCAL_EXECUTION_CLAIM_BEFORE_MUTATION=PASS
SAME_CONTEXT_REPLAY_BLOCKED=PASS
POST_CLAIM_FAILURE_REPLAY_BLOCKED=PASS
SUCCESS_BINDS_FACTORY_ACCEPTED=PASS
SUCCESS_BINDS_F4_TRANSACTION=PASS

F4_ACTIVATE_CHANGED=false
F4_ACCEPT_CHANGED=false
PERSISTENCE_CHANGED=false
CERTIFICATE_CHANGED=false
REBOOT_CHANGED=false
~~~

## 4. Exact CI evidence

All workflows observed for `f4e3a76d5c5ab9259f9e3d53ed57fb6b9626f527` completed successfully.

Key runs:

~~~text
N3W_T1_F5_PRODUCTION_PROCESS_V1_SOURCE_CI=PASS
RUN_ID=39027458937

N3W_T1_FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=PASS
RUN_ID=39027458931

N3W_T1_F4_ACTIVATION_SOURCE_CI=PASS
RUN_ID=39027458998

N3W_T1_F4_EXACT_CONTROL_PACKAGE=PASS
RUN_ID=39027459009

N3W_T1_EXPLICIT_PROVISIONING_SOURCE_CI=PASS
RUN_ID=39027458995

N3W_T1_GOLDEN_MASTER_SOURCE_CI=PASS
RUN_ID=39027458969

PUBLIC_REPOSITORY_SAFETY_CI=PASS
RUN_ID=39027459067

GREENHOUSE_MANAGER_CI=PASS
RUN_ID=39027458938
~~~

The observed M0, M2, H3 and C-07 regression workflows on the same head also passed.

## 5. Boundary and next gate

This closure does not authorize or execute live T1 work and does not merge PR #612.

The next source boundary is F4_ACTIVATE. It must receive its own F5 phase context and its own one-shot local execution claim while continuing to reuse the already accepted F4 activation primitive.

~~~text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_F4_ACTIVATE_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~
