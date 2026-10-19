# N3-W T1 F5 failed-run terminalization — exact artifact and read-only preauth closure

Date: 2026-10-19

## Result

~~~text
TASK=N3W_T1_F5_FAILED_RUN_TERMINALIZATION_ARTIFACT_AND_READONLY_PREAUTH_20261019_01
RESULT=CLOSED_PASS_READY_FOR_EXPLICIT_LIVE_RECOVERY_AUTHORIZATION_DECISION

PR615_EXECUTABLE_SOURCE_HEAD=ebd76d1c6178ff0c0e392047769aeb562670f48b
PR615_EXECUTABLE_SOURCE_TREE=90e01232a77442c2b2856d49aa3b235cbdb9f96d
PR615_EXACT_HEAD_CI=PASS_12_OF_12
FOCUSED_TESTS=PASS_9

ARTIFACT_RUN_ID=39202619732
ARTIFACT_JOB_ID=117898622419
ARTIFACT_ID=12164835562
ARTIFACT_NAME=n3w-t1-f5-failed-run-terminalizer-ebd76d1c6178ff0c0e392047769aeb562670f48b
ARTIFACT_SIZE_BYTES=76490
ARTIFACT_ZIP_SHA256=a5d47bdc4ae1912e20414fd1d5d0ebf840166ec195496c0f821d9bb5cb9e2b4b

READONLY_PREAUTH=PASS
READONLY_PREAUTH_MUTATION=false
READONLY_PREAUTH_RECOVERY_ROOT_ABSENT=true
PRIVATE_T1_LOCATOR_EXCLUDED=true

FAILED_RUN_ID=56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e
FAILED_RUN_STATE=IN_PROGRESS
FAILED_RUN_LAST_CLAIMED_PHASE=HOST_BASELINE
FAILED_RUN_LAST_COMPLETED_PHASE=null
HOST_BASELINE_PHASE_STATE=APPLYING
PHASE_CLAIM_SHA256=737fcda8367319399157a05ec8a0b27fc9059ff5a90622f5ffb39452b2001c80
HOST_BASELINE_BUSINESS_EXECUTION_CLAIM_ABSENT=true
HOST_BASELINE_BUSINESS_EXECUTION_COMPLETE_ABSENT=true
FAILED_RUN_AUTHORIZATION_CONSUMED=true
FAILED_RUN_REPLAY_ALLOWED=false

PROPOSED_RECOVERY_AUTHORIZATION=N3W_T1_F5_FAILED_RUN_TERMINALIZATION_LIVE_20261019_01
RECOVERY_AUTHORIZATION_GRANTED=false
RECOVERY_AUTHORIZATION_CLAIMED=false
RECOVERY_AUTHORIZATION_CONSUMED=false

T1_ACCESS=true
T1_MUTATION=false
LIVE_RECOVERY_EXECUTED=false
PRODUCT_SERVICE_START=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F5_FAILED_RUN_TERMINALIZATION_LIVE_20261019_01
AUTO_EXECUTE_NEXT_GATE=false
EXPLICIT_LIVE_AUTHORIZATION_REQUIRED=true
STOP=true
~~~

## Closure

The fresh real-T1 read-only preauthorization passed with the exact reviewed recovery inspector loaded from the
exact recovery artifact without copying the recovery package onto the target filesystem.

The target still matches the incident state required for safe bounded terminalization:

- the historical F5 production run is still active at `IN_PROGRESS`;
- `HOST_BASELINE` remains exactly `APPLYING`;
- no prior phase is recorded complete;
- the original production authorization remains consumed and non-replayable;
- the exact current phase-claim SHA-256 is
  `737fcda8367319399157a05ec8a0b27fc9059ff5a90622f5ffb39452b2001c80`;
- both host-baseline business-execution claim and completion records derived from that claim remain absent;
- the recovery root remained absent before and after the read-only inspection;
- no target mutation, product service start, reboot, or board access occurred.

This is stronger than the earlier forensic snapshot because it freshly re-proves the exact current phase record and
business-execution absence immediately before the proposed recovery authorization decision.

## Live authorization boundary

This closure does not authorize terminalization.

The only next mutation gate is:

~~~text
AUTHORIZATION=N3W_T1_F5_FAILED_RUN_TERMINALIZATION_LIVE_20261019_01
RUN_ID=56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e
PHASE=HOST_BASELINE
EXPECTED_PHASE_CLAIM_SHA256=737fcda8367319399157a05ec8a0b27fc9059ff5a90622f5ffb39452b2001c80
MUTATION_SCOPE=f5_production_authority_and_recovery_ledger_only
OLD_RUN_REPLAY=false
HOST_BASELINE_BUSINESS_EXECUTION=false
PRODUCT_SERVICE_START=false
LIVE_REBOOT=false
BOARD_ACCESS=false
~~~

If that authorization is granted later, it is one-shot. The recovery executor must first durably claim and consume
the recovery authorization and may then change only the historical F5 authority/recovery ledgers to the exact failed
terminal state. Any interruption after the recovery claim remains bound to the same consumed authorization and may
resume only the bounded ledger finalization path.

A separate fresh F5-9 production authorization is still required after successful terminalization before the
replacement release may start a new production run.
