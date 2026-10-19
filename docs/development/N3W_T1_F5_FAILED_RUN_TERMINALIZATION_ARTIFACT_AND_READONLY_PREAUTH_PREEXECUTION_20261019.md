# N3-W T1 F5 failed-run terminalization — exact artifact and read-only preauth preexecution

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_FAILED_RUN_TERMINALIZATION_ARTIFACT_AND_READONLY_PREAUTH_20261019_01
STATE=READY_FOR_REAL_T1_READONLY_PREAUTH

PR=615
EXECUTABLE_SOURCE_HEAD=ebd76d1c6178ff0c0e392047769aeb562670f48b
EXECUTABLE_SOURCE_TREE=90e01232a77442c2b2856d49aa3b235cbdb9f96d
PR_STATE=OPEN_DRAFT_NOT_MERGED
SOURCE_CI=PASS_12_OF_12
FOCUSED_TESTS=PASS_9
RECOVERY_PACKAGE_LOCAL_VERIFY=PASS

ARTIFACT_RUN_ID=39202619732
ARTIFACT_JOB_ID=117898622419
ARTIFACT_ID=12164835562
ARTIFACT_NAME=n3w-t1-f5-failed-run-terminalizer-ebd76d1c6178ff0c0e392047769aeb562670f48b
ARTIFACT_SIZE_BYTES=76490
ARTIFACT_ZIP_SHA256=a5d47bdc4ae1912e20414fd1d5d0ebf840166ec195496c0f821d9bb5cb9e2b4b
ARTIFACT_EXPIRES_AT=2026-11-18T05:04:15Z

FAILED_RUN_ID=56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e
FAILED_PHASE=HOST_BASELINE
EXPECTED_RUN_STATE=IN_PROGRESS
EXPECTED_PHASE_STATE=APPLYING
EXPECTED_HOST_BASELINE_BUSINESS_EXECUTION=ABSENT
EXPECTED_REPLAY_ALLOWED=false

PROPOSED_RECOVERY_AUTHORIZATION=N3W_T1_F5_FAILED_RUN_TERMINALIZATION_LIVE_20261019_01
RECOVERY_AUTHORIZATION_GRANTED=false
RECOVERY_AUTHORIZATION_CLAIMED=false
RECOVERY_AUTHORIZATION_CONSUMED=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_RECOVERY_EXECUTED=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

## Exact recovery artifact

The recovery artifact packages only the exact reviewed recovery executable and its two source dependencies plus
a manifest:

~~~text
n3w_t1_f5_failed_run_terminalizer.py
n3w_t1_production_authority.py
n3w_t1_production_contract.py
manifest.json
~~~

CI compiled the executable sources, passed the focused recovery test suite, enforced the static no-reboot/no-APT/
no-Docker/no-F3/no-provisioning boundary, built the package, verified all package file hashes locally, and uploaded
the exact artifact.

The previous recovery artifacts from earlier PR #615 heads are superseded and must not be used.

## Read-only preauthorization objective

The real T1-B read-only preauthorization must execute the exact packaged inspector in memory without copying the
recovery package to the target filesystem. It must prove, fresh from the target:

1. target binding and ED25519 SSH host-key binding still equal the frozen T1-B identity;
2. the historical production run is still `IN_PROGRESS`, consumed and non-replayable;
3. `last_claimed_phase=HOST_BASELINE` and `last_completed_phase=null`;
4. the phase remains exactly `APPLYING` with no result or failure code;
5. old source/release/target bindings remain exact;
6. the exact phase-claim SHA-256 is obtained fresh;
7. both host-baseline business-execution claim and completion records derived from that phase-claim SHA-256 remain absent;
8. no recovery ledger is created by the read-only preauthorization;
9. no product service start, reboot or board access occurs.

Expected successful report:

~~~text
status=PASS
state=ELIGIBLE_FOR_TERMINALIZATION
phase=HOST_BASELINE
phase_state=APPLYING
host_baseline_business_execution_claim_absent=true
host_baseline_business_execution_complete_absent=true
authorization_consumed=true
replay_allowed=false
mutation_performed=false
mutation_state=NONE
product_service_start=false
reboot_executed=false
board_access=false
~~~

The returned `phase_claim_sha256` becomes part of the later one-shot live recovery authorization binding.

## Stop rule

A read-only preauthorization PASS does not authorize terminalization.

After PASS:

~~~text
NEXT_ONE_GATE=N3W_T1_F5_FAILED_RUN_TERMINALIZATION_LIVE_20261019_01
AUTO_EXECUTE_NEXT_GATE=false
EXPLICIT_LIVE_AUTHORIZATION_REQUIRED=true
~~~

The live mutation may only be considered after the exact phase-claim SHA-256 and fresh T1 read-only evidence are
durably recorded. No private T1 password is stored in GitHub.
