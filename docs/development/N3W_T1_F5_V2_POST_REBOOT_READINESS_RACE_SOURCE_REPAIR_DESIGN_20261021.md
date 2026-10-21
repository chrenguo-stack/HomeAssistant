# N3W T1 F5 V2 post-reboot readiness race source-repair design

Date: 2026-10-21

## 0. Gate and safety boundary

~~~text
TASK=N3W_T1_F5_V2_POST_REBOOT_READINESS_RACE_SOURCE_REPAIR_DESIGN_20261021_01
BASE_MAIN=0654ab3f5b914acd278ffb7333344d86cf5878d2
BASE_TREE=a4b31277c53e8497e78bce9ae352f940de1dd553

RESULT=SOURCE_REPAIR_DESIGN_FROZEN
PRODUCT_SOURCE_IMPLEMENTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
WORKFLOW_DISPATCH=false
PRODUCTION_EXECUTION=false
REFLASH=false
MERGE=false
~~~

This design is based on the terminal real-T1 run
`15212aa98751a5a90677fbfd4f2ab51bf12ad8a5b5744ca050f3b872acdf1acc`.
That run is terminal and must never be replayed.

The design does not authorize target-local repair or reuse of the failed target state.
The current failed target remains `REFLASH_REQUIRED`, but reflash is intentionally
deferred until the source repair is reviewed, merged, rebuilt into a new exact release,
and locally validated.

## 1. Real-T1 evidence and root-cause class

The real run passed all pre-reboot production work:

~~~text
HOST_BASELINE=PASS
F3_DEPLOY=PASS
PROVISION=PASS
F4_PREPARE=PASS
F4_ACTIVATE=PASS
F4_ACCEPT=PASS
F4_PERSISTENCE=PASS
F4_CERT_AUDIT=PASS
F4_CERT_TIMER=PASS
REBOOT_CONTROL_ARMING=PASS
CONTROLLED_REBOOT=EXECUTED
WAIT_FOR_SSH=PASS
SSH_EPOCH_2=PASS
~~~

It then failed immediately after:

~~~text
POST_REBOOT_ACCEPTANCE=STARTED
ERROR_CLASS=POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
TERMINAL_STAGE=POST_REBOOT_ACCEPTANCE
MARKER_STATE=STARTED
T1_PRODUCTION_READY=false
REFLASH_REQUIRED=true
~~~

Frozen forensics were complete and read-only:

~~~text
FORENSIC_MANIFEST=PASS
UNAVAILABLE_COUNT=0
PRODUCTION_MARKER=OBSERVED_STARTED
F4_TRANSACTION=PERSISTENCE_ENABLED
F4_RUNTIME_ACCEPTANCE_PASSED=true
F4_PERSISTENCE_ENABLED=true
F4_CERTIFICATE_FIRST_AUDIT_PASSED=true
F4_CERTIFICATE_TIMER_ENABLED=true
F4_PRE_REBOOT_READY=true
REBOOT_CLAIM=REBOOT_PENDING
REBOOT_AUTHORIZATION_CONSUMED=true
REBOOT_ACCEPTANCE_PASSED=false
SYSTEMD_STATE_AT_FORENSIC=starting
~~~

A later read-only timing diagnostic showed that the target converged normally:

~~~text
CURRENT_SYSTEMD_STATE=running
FAILED_UNITS=NONE
PENDING_JOBS=NONE

SSH_ACTIVE_ENTER_MONOTONIC_US=26480916
BROKER_ACTIVATION_ACTIVE_ENTER_MONOTONIC_US=30983251
SERVICES_ACTIVATION_ACTIVE_ENTER_MONOTONIC_US=35106427

BROKER_ACTIVE_AFTER_SSH_US=4502335
SERVICES_ACTIVE_AFTER_SSH_US=8625511

POST_REBOOT_ACCEPTANCE_STARTED_AT=2026-10-21T07:39:42.302688Z
BROKER_CONTAINER_STARTED_AT=2026-10-21T07:39:50.088198624Z
MANAGER_CONTAINER_STARTED_AT=2026-10-21T07:39:54.339106991Z
HOMEASSISTANT_CONTAINER_STARTED_AT=2026-10-21T07:39:54.350158557Z

BROKER_CONTAINER_STARTED_AFTER_ACCEPTANCE_START_SECONDS=7.785510624
MANAGER_CONTAINER_STARTED_AFTER_ACCEPTANCE_START_SECONDS=12.036418991
HOMEASSISTANT_CONTAINER_STARTED_AFTER_ACCEPTANCE_START_SECONDS=12.047470557

BROKER_RESTART_COUNT=0
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
~~~

Therefore the frozen root-cause class is:

~~~text
KF_125=F5_V2_POST_REBOOT_PRODUCT_READINESS_RACE
ROOT_CAUSE_CONFIDENCE=HIGH
PERSISTENT_RUNTIME_FAILURE_EVIDENCE=false
SOURCE_REPAIR_REQUIRED=true
~~~

The exact first target-verifier error code is not recoverable from the frozen run because
the executor collapsed a non-zero target verifier exit into a generic
`ProductionExecutorError`. This is a separate observability defect that must be repaired
in the same source gate.

## 2. Why the existing 90-second observation did not protect this run

The existing 90-second window is intentionally a **stability observation after the
system is already accepted as healthy enough to establish a runtime baseline**.

Current ordering is effectively:

~~~text
REBOOT
-> TCP/22 reachable
-> SSH_EPOCH_2
-> POST_REBOOT_ACCEPTANCE
   -> STARTED marker binding
   -> target-local reboot verify
   -> runtime baseline
   -> five external probes
   -> 90-second continuity observation
-> MARKER_ACCEPTED
~~~

The failed run never reached the 90-second observation. The target-local reboot verifier
contains fail-fast checks requiring key product units to already be active before its
later bounded waits. TCP/22 and a successful SSH login are therefore not a sufficient
product-readiness barrier.

The repair must preserve the existing observation semantics:

~~~text
RUNTIME_STABILITY_OBSERVATION_SECONDS=90
RUNTIME_STABILITY_SAMPLE_INTERVAL_SECONDS=2
RUNTIME_STABILITY_MAX_SAMPLE_GAP_SECONDS=15
SECOND_90_SECOND_WINDOW=false
~~~

The new mechanism is a distinct bounded **boot/product readiness barrier before full
post-reboot acceptance**, not a replacement for the 90-second stability window.

## 3. Frozen target flow

The repaired ordering is:

~~~text
REBOOT
-> WAIT_FOR_SSH
-> SSH_EPOCH_2
-> POST_REBOOT_READINESS
   -> repeated read-only readiness observations
   -> transient not-ready => WAIT
   -> explicit contradiction => FAIL immediately
   -> READY => continue
   -> bounded timeout => FAIL
-> POST_REBOOT_ACCEPTANCE
   -> existing strict target-local reboot verify exactly once
   -> existing runtime baseline
   -> existing five external probes
   -> existing 90-second continuity observation
-> MARKER_ACCEPTED
~~~

Frozen timing policy:

~~~text
POST_REBOOT_READINESS_TIMEOUT_SECONDS=300
POST_REBOOT_READINESS_POLL_SECONDS=2
POST_REBOOT_READINESS_MUTATION=false
POST_REBOOT_READINESS_NEW_SSH_EPOCH=false
POST_REBOOT_READINESS_NEW_PASSWORD_PROMPT=false
POST_REBOOT_READINESS_NEW_APPROVAL=false
~~~

The readiness barrier runs inside the already-established SSH epoch #2.

## 4. Readiness authority and state model

The single-shot readiness authority should live with the installed reboot verifier rather
than duplicating F4 product-unit knowledge in the Mac executor.

Preferred source seam:

~~~text
tools/n3w_t1_f4_reboot_verify.py --readiness
~~~

The readiness entrypoint is read-only and returns a sanitized structured report.

### 4.1 WAIT

WAIT is allowed only for states that can reasonably be normal boot convergence:

- systemd is still `initializing` or `starting`;
- a required N3W unit is still `activating` or not yet active without a failed Result;
- the expected runtime service set is still incomplete without unexpected services;
- a healthy certificate lifecycle oneshot is temporarily active/activating/reloading/deactivating.

WAIT never means PASS and never allows the full acceptance to start.

### 4.2 READY

READY requires enough product boot convergence that the strict verifier is no longer
being entered merely because SSH came up first.

At minimum:

- boot identity differs from the pre-reboot claim;
- reboot claim/control binding remains exact;
- provision-resume unit is active/successful;
- ingress-guard unit is active/successful;
- broker activation unit is active/successful;
- application services activation unit is active/successful;
- certificate lifecycle timer is active/enabled with no failed Result;
- the running application service set contains exactly broker, manager and Home Assistant;
- no required unit is in a failed state.

A global systemd `degraded` state alone is not sufficient to claim a product failure if
all required product units are healthy; the existing strict verifier and runtime error
checks remain the final authority.

### 4.3 FAIL

FAIL is immediate for explicit contradictions, including:

- reboot claim/control binding drift;
- boot identity did not change;
- required product unit `failed` or unsuccessful Result/ExecMainStatus;
- unexpected product runtime service/container in the controlled service set;
- structurally invalid readiness evidence.

The barrier must not turn an explicit failure into WAIT.

## 5. Strict acceptance remains unchanged

The readiness barrier is only a gate. It does not weaken or replace:

- STARTED marker exact binding;
- full `n3w_t1_f4_reboot_verify.py` verification;
- F4 transaction/hash checks;
- image/runtime/container guards;
- TLS and Dynamic Security validation;
- Manager and Home Assistant business-state checks;
- Mac TCP/TLS/SNI/negative-auth/HA external probes;
- runtime service authentication evidence;
- the existing 90-second non-disruptive continuity observation;
- ACCEPTED marker finalization.

The full target-local verifier still runs exactly once after readiness PASS.

~~~text
READINESS_PASS_IS_PRODUCTION_PASS=false
READINESS_PASS_SKIPS_FULL_VERIFY=false
READINESS_PASS_SKIPS_90S_OBSERVATION=false
~~~

## 6. Executor integration

Candidate source changes:

### 6.1 `tools/n3w_t1_production_v2.py`

Add an explicit R3 adapter step:

~~~text
wait_for_ssh
-> start_post_reboot_epoch
-> wait_for_post_reboot_readiness
-> post_reboot_acceptance
-> accept_marker
~~~

The orchestrator terminal stage must be `POST_REBOOT_READINESS` while that barrier is
running. A failure there remains a post-STARTED terminal failure and therefore follows the
existing forensic -> session close -> reflash-required ordering.

### 6.2 `tools/n3w_t1_production_v2_executor.py`

Add:

- constants for 300-second timeout and 2-second poll;
- a structured single-shot readiness call;
- bounded polling with no mutation;
- progress events:
  - `POST_REBOOT_READINESS STARTED`;
  - `POST_REBOOT_READINESS WAITING` with sanitized state/reason and elapsed time;
  - `POST_REBOOT_READINESS PASS`;
- no extra ControlMaster and no extra password prompt.

The executor must never use a fixed blind `sleep 30` or similar workaround.

## 7. Failure-code observability repair

Current behavior loses the target verifier's sanitized stderr `error_code` and freezes
only `error_type=ProductionExecutorError`.

Repair requirements:

1. parse only the final structured JSON failure record emitted by repository-owned target
   verifier/readiness commands;
2. accept only an allowlisted sanitized error-code form; never persist arbitrary stderr;
3. preserve evidence-insufficient versus explicit verification failure classification;
4. write the sanitized exact code into private `failure-summary.json`;
5. keep raw stderr, credentials, host address and unrestricted logs out of public GitHub
   evidence;
6. do not alter the original failure after freeze.

A candidate safe representation is:

~~~text
error_type=ProductionExecutorError|EvidenceInsufficientError
error_code=target_local_reboot_verify:<repository_defined_code>
~~~

The public final-result schema does not need to expand in this repair; durable private
forensics must become sufficient to identify the first structured verifier failure.

## 8. Test contract

Minimum focused tests:

1. systemd starting + product units not yet active => WAIT, not FAIL;
2. readiness transitions WAIT -> READY within the bound => acceptance is entered once;
3. broker/services become active several polls after SSH => no false failure;
4. required unit failed/unsuccessful => immediate FAIL, no waiting to timeout;
5. unexpected runtime service set => immediate FAIL;
6. timeout at 300 seconds => terminal readiness failure;
7. readiness performs no target mutation;
8. readiness does not open a third SSH epoch or trigger another password prompt;
9. readiness does not request a second production approval;
10. full target-local verifier still executes exactly once after READY;
11. external probes remain after full verifier;
12. existing 90-second observation remains exactly 90 seconds and begins only after the
    runtime baseline/external-probe sequence;
13. marker ACCEPTED remains impossible before full acceptance PASS;
14. target verifier structured failure code is preserved in frozen failure-summary;
15. evidence-insufficient structured failure preserves
    `POST_REBOOT_EVIDENCE_INSUFFICIENT_REFLASH_REQUIRED`;
16. explicit runtime contradiction preserves
    `POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED`;
17. reboot arming behavior, one production approval, two SSH password epochs and
    password non-persistence remain unchanged;
18. public-repository safety scan remains PASS.

## 9. Candidate implementation file boundary

Expected product-source delta:

~~~text
tools/n3w_t1_f4_reboot_verify.py
tools/n3w_t1_production_v2.py
tools/n3w_t1_production_v2_executor.py

tests/tools/test_n3w_t1_f4_reboot_verify.py
tests/tools/test_n3w_t1_production_v2.py
tests/tools/test_n3w_t1_production_v2_executor.py
~~~

`tools/n3w_t1_post_reboot_acceptance.py` should remain unchanged unless a narrowly
necessary regression assertion requires a source change. Its 90-second semantics are not
the defect being repaired.

F3, Provisioning, F4 activation business primitives, board firmware and wireless state
machines are out of scope.

## 10. Release and live-validation consequence

Any merged implementation changes the exact production authority. Therefore the next
real-T1 attempt must use a completely new chain:

~~~text
SOURCE_REPAIR
-> INDEPENDENT_SOURCE_REVIEW
-> CI PASS
-> MERGE
-> F3/F4 EXACT ARTIFACT REBUILD
-> RELEASE_INPUTS REBUILD
-> FINAL EXACT RELEASE REBUILD
-> MAC LOCAL EXACT-RELEASE VALIDATION
-> REFLASH FAILED T1
-> STANDARD FRESH ARMBIAN QUALIFICATION
-> NEW RUN_ID
-> NEW PRODUCTION APPROVAL
-> REAL T1 PRODUCTION
-> POST_REBOOT_READINESS
-> POST_REBOOT_ACCEPTANCE
-> 90-SECOND STABILITY OBSERVATION
-> MARKER_ACCEPTED
~~~

The failed run ID is never replayed.

## 11. Known-failure disposition

~~~text
KF_122=OPEN
KF_124=SOURCE_REPAIR_MERGED_LIVE_PATH_REVALIDATED_FULL_RUN_PENDING
KF_125=SOURCE_DESIGN_FROZEN_IMPLEMENTATION_PENDING

T1_PRODUCTION_READY=false
FAILED_RUN_REPLAY=false
TARGET_LOCAL_FIX_FORWARD=false
REFLASH_DEFERRED_PENDING_SOURCE_REPAIR=true
~~~

KF-124's operator-presence mechanism has now been exercised successfully through
arming, controlled reboot and SSH epoch #2 password authentication. It remains short of
full closure only because the overall run did not reach final production acceptance.

KF-122 cannot close from this run because the execution failed before the repaired
non-disruptive external-probe + 90-second observation path completed.

## 12. Source-review questions for the implementation gate

A focused source review must answer:

- A1: Are WAIT and FAIL states disjoint and fail-closed?
- A2: Can SSH readiness still bypass product readiness?
- A3: Can readiness ever mutate the target?
- A4: Can readiness open another SSH/password/approval boundary?
- A5: Is the full target-local verifier still executed exactly once?
- A6: Is the existing 90-second observation unchanged and still after external probes?
- A7: Is structured failure-code preservation sanitized and secret-free?
- A8: Do evidence-insufficient and explicit failure classes remain distinct?
- A9: Are failed-run no-replay and reflash-required semantics preserved?
- A10: Does the exact release rebuild invalidate all prior production authority as required?

## 13. Current stop

~~~text
SOURCE_REPAIR_DESIGN=FROZEN
PRODUCT_SOURCE_IMPLEMENTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
REFLASH=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F5_V2_POST_REBOOT_READINESS_RACE_SOURCE_REPAIR_IMPLEMENTATION_20261021_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
