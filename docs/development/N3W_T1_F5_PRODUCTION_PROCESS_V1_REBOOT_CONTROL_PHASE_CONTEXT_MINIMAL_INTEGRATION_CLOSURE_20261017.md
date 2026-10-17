# N3W T1 F5 Production Process V1 — REBOOT_CONTROL Phase-Context Minimal Integration Closure

Date: 2026-10-17

## Gate result

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_REBOOT_CONTROL_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01
RESULT=CLOSED_PASS

PR=612
PR_STATE=OPEN_DRAFT
SOURCE_BRANCH=feat/n3w-t1-f5-production-process-v1-source-20261017
SOURCE_HEAD=ee5218b87ad9f3ea68f85d840173bf91c0dfcb4c
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

The normal F5 `REBOOT_CONTROL` route now requires an exact target-validated production phase context and a same-run F4 predecessor chain already closed through `PERSIST_CERT`.

The reboot-control package source must equal the approved production-run source. Before any reboot-control installation mutation, the adapter verifies the exact pre-reboot F4 transaction and writes a durable non-replayable production execution claim.

Existing F4 reboot-successor primitives remain authoritative for:
- control package validation;
- install authorization claim;
- control installation;
- post-install verification;
- reboot authorization claim;
- reboot-claim verification.

The control installation must prove the F4 transaction, runtime identity and certificate identity remained unchanged.

Successful `REBOOT_CONTROL` completion stops at durable `REBOOT_PENDING`. It binds the exact F4 transaction, installed-control claim, reboot pending claim and pre-boot identity. No host reboot is actuated by this source gate.

A separate production actuation-claim boundary marks `reboot_actuation_attempted=true` atomically before any future external reboot actuation. That marker is same-run bound, one-shot and non-replayable. It does not modify the frozen F4 transaction.

## Focused review

~~~text
NORMAL_F5_REBOOT_CONTROL_REQUIRES_PRODUCTION_PHASE_CONTEXT=PASS
TARGET_AUTHORITY_VALIDATION=PASS
SAME_RUN_PERSIST_CERT_PREDECESSOR=PASS
CONTROL_SOURCE_EQUALS_APPROVED_SOURCE=PASS
LOCAL_EXECUTION_CLAIM_BEFORE_MUTATION=PASS
EXISTING_F4_REBOOT_SUCCESSOR_PRIMITIVES_REUSED=true
F4_TRANSACTION_UNCHANGED_AFTER_CONTROL_INSTALL=PASS
RUNTIME_IDENTITY_UNCHANGED_AFTER_CONTROL_INSTALL=PASS
CERTIFICATE_IDENTITY_UNCHANGED_AFTER_CONTROL_INSTALL=PASS
SUCCESS_STOPS_AT_REBOOT_PENDING=PASS
REBOOT_ACTUATION_CLAIM_DURABLE_BEFORE_ACTUATION=PASS
REBOOT_ACTUATION_REPLAY_ALLOWED=false
RAW_REBOOT_COMMAND_PRESENT=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
~~~

## Exact CI evidence

All 17 workflows observed on `ee5218b87ad9f3ea68f85d840173bf91c0dfcb4c` completed successfully.

Key runs:

~~~text
F5_SOURCE_CI=PASS:39034085139
F4_ACTIVATION_SOURCE_CI=PASS:39034085114
FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=PASS:39034085231
EXPLICIT_PROVISIONING_SOURCE_CI=PASS:39034085131
GOLDEN_MASTER_SOURCE_CI=PASS:39034085055
PUBLIC_REPOSITORY_SAFETY_CI=PASS:39034085257
F4_EXACT_CONTROL_PACKAGE_CI=PASS:39034085038
GREENHOUSE_MANAGER_CI=PASS:39034085158
~~~

The observed M0, M2, H3 and C-07 regression workflows also passed.

## Next boundary

The next F5 phase is `FINALIZE`. It must run only after the planned reboot and post-reboot reconnection, require the same production run and an exact actuation-marked pending reboot claim, then reuse the existing durable reboot-acceptance finalizer and terminal verifier.

This next source gate does not authorize live T1 access or a real reboot.

~~~text
NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_FINALIZE_PHASE_CONTEXT_MINIMAL_INTEGRATION_20261017_01

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~
