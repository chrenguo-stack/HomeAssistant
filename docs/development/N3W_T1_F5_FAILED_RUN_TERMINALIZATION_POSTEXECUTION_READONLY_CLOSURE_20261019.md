# N3-W T1 F5 failed-run terminalization — postexecution read-only closure

Date: 2026-10-19

## Result

~~~text
TASK=N3W_T1_F5_FAILED_RUN_TERMINALIZATION_POSTEXECUTION_READONLY_20261019_01
RESULT=CLOSED_PASS

PR615_EXECUTABLE_SOURCE_HEAD=ebd76d1c6178ff0c0e392047769aeb562670f48b
RECOVERY_ARTIFACT_ID=12164835562
RECOVERY_ARTIFACT_ZIP_SHA256=a5d47bdc4ae1912e20414fd1d5d0ebf840166ec195496c0f821d9bb5cb9e2b4b
RECOVERY_MANIFEST_SHA256=1dfd1df5ce1c6106d537ed8ab563aa1d1e19ebbc1a9edd2235bd88558c485e2a

RECOVERY_AUTHORIZATION=N3W_T1_F5_FAILED_RUN_TERMINALIZATION_LIVE_20261019_01
RECOVERY_AUTHORIZATION_CONSUMED=true
RECOVERY_AUTHORIZATION_REPLAY_ALLOWED=false

FAILED_RUN_ID=56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e
FAILED_RUN_STATE=TERMINAL
FAILED_RUN_TERMINAL_STATE=FAIL
FAILED_RUN_FAILURE_CLASS=FAILED
FAILED_RUN_REPLAY_ALLOWED=false

LAST_CLAIMED_PHASE=HOST_BASELINE
LAST_COMPLETED_PHASE=null
ONLY_PRODUCTION_PHASE_RECORD=HOST_BASELINE_FAILED
HOST_BASELINE_PHASE_STATE=FAILED
HOST_BASELINE_FAILURE_CODE=KF122_PHASE_CONTEXT_CLI_STATUS_MISSING
HOST_BASELINE_RESULT_SHA256=null
ORIGINAL_PHASE_CLAIM_SHA256=737fcda8367319399157a05ec8a0b27fc9059ff5a90622f5ffb39452b2001c80

RECOVERY_STATE=TERMINALIZED
HOST_BASELINE_BUSINESS_EXECUTION_CLAIM_ABSENT=true
HOST_BASELINE_BUSINESS_EXECUTION_COMPLETE_ABSENT=true

T1_ACCESS=true
T1_MUTATION=false
PRODUCT_SERVICE_START=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false

KF_122=RECOVERY_CLOSED_PASS
NEW_F5_9_AUTHORIZATION=NOT_GRANTED
~~~

## Closure

A separate fresh SSH session independently verified the durable target state after live terminalization.

The historical F5 run is now durably `TERMINAL/FAIL` with failure class `FAILED`. The only production phase
record is `HOST_BASELINE=FAILED` with failure code `KF122_PHASE_CONTEXT_CLI_STATUS_MISSING`; there is no completed
production phase and no phase result payload.

The dedicated recovery record is durably `TERMINALIZED`, remains bound to the exact original phase-claim SHA-256,
and records the one-shot recovery authorization as consumed and non-replayable.

The host-baseline business-execution claim and completion records are still absent. Therefore the failed run did not
cross into the APT/Docker host-baseline business executor, F3 deployment, explicit provisioning, product-service
activation, or reboot path.

The independent verifier itself was read-only: no target mutation, service start, reboot, or board access occurred.

## Recovery route closure

The failed-run recovery route is closed.

Do not:

- replay the historical run;
- reuse the consumed recovery authorization;
- delete or rewrite the historical failed-run or recovery records;
- reflash T1-B solely because of KF-122.

The next production action, if authorized, must be a new F5-9 run using the repaired source and the already approved
replacement release. That requires a separate fresh production authorization and is not granted by this closure.
