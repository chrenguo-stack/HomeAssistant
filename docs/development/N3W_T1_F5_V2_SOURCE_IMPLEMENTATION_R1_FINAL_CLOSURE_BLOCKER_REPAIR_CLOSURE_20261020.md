# N3W T1 F5 V2 R1 final closure blocker repair — closure

Date: 2026-10-20

## 0. Gate result

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_FINAL_CLOSURE_BLOCKER_REPAIR_20261020_01
AUTHORIZATION=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R1_FINAL_CLOSURE_BLOCKER_REPAIR_20261020_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

PRE_REPAIR_HEAD=fca5762fcf5539b968951b0d4e5ef39833d51013
POST_REPAIR_SOURCE_HEAD=169239395088e5d01dc3ccb7b8386a8ae1c2994e
BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
BEHIND_MAIN=0

RESULT_FORENSIC_ORDERING_REPAIR=PASS
QUALIFICATION_READ_FAILURE_REPAIR=PASS
R1_FOUNDATIONS_CI=PASS
R1_ALL_WORKFLOWS=12_OF_12_SUCCESS
FINAL_FOCUSED_REVIEW_BLOCKER_COUNT=0

R1_CLOSED_PASS=true
READY_FOR_R2_ENTRY_DECISION=true
R2_STARTED=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false

GATE_RESULT=CLOSED_PASS
NEXT_ROUTE=R2_ENTRY_DECISION
STOP=true
~~~

This gate closes the two R1 foundation blockers found at the final closure review. It does not enter R2.

## 1. Fresh authority

~~~text
REPOSITORY=chrenguo-stack/HomeAssistant
SOURCE_PR=624
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019
REVIEWED_SOURCE_HEAD=169239395088e5d01dc3ccb7b8386a8ae1c2994e
SOURCE_BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
PR_DRAFT=true
PR_MERGEABLE=true
UNRESOLVED_REVIEW_THREADS=0
REVIEWS_REQUIRING_CHANGES=0
~~~

The branch remained behind main by zero commits during the review.

## 2. Blocker A closure — final result forensic ordering

The final result contract now fails closed for every final result whose marker is still STARTED.

Required final STARTED invariant is now enforced:

~~~text
marker_state=STARTED
-> status=FAIL
-> device_acceptance!=PASS
-> T1_PRODUCTION_READY=false
-> evidence_complete=true
-> operator_session_closed=true
-> reflash_required=true
-> error_class in {
     MUTATION_FAIL_REFLASH_REQUIRED,
     POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
   }
~~~

The STARTED route no longer accepts `PROCESS_CLEANUP_FAIL`.

The durable accepted-device exception remains intact:

~~~text
marker_state=ACCEPTED
status=FAIL
error_class=PROCESS_CLEANUP_FAIL
device_acceptance=PASS
T1_PRODUCTION_READY=true
reflash_required=false
~~~

Focused regressions reject:

- STARTED with incomplete forensic evidence;
- STARTED with an unclosed operator session;
- STARTED with PROCESS_CLEANUP_FAIL.

The accepted-device cleanup-failure regression remains green.

Result:

~~~text
FINAL_RESULT_FORENSIC_ORDERING=CLOSED_PASS
~~~

## 3. Blocker B closure — firstboot read failure classification

The remote fresh-Armbian probe now promotes firstboot systemd read-command failure into the observation `unavailable[]` set.

The classification remains deliberately split:

~~~text
firstboot/systemd read unavailable
-> STOP_UNAVAILABLE
-> reflash_required=false

firstboot probe succeeds but state mismatches fresh contract
-> FAIL_REFLASH_REQUIRED
-> reflash_required=true
~~~

The same-gate implementation was tightened once before the final exact head so a successfully executed probe with an empty/mismatching state is still treated as observed nonstandard state rather than evidence unavailability.

Focused regressions cover:

- explicit firstboot probe unavailability -> STOP_UNAVAILABLE;
- remote probe construction includes the firstboot systemd unavailable guard;
- observed firstboot mismatch -> FAIL_REFLASH_REQUIRED;
- successful probe with missing state -> FAIL_REFLASH_REQUIRED.

Result:

~~~text
QUALIFICATION_FIRSTBOOT_READ_FAILURE_CLASSIFICATION=CLOSED_PASS
~~~

## 4. Focused closure review

The review checked the exact source at `169239395088e5d01dc3ccb7b8386a8ae1c2994e`.

The executable/test delta after the prior reviewed source `e86f95d71b2293a933e9ad38acc0cd42beb8e4b7` is limited to:

~~~text
tools/n3w_t1_production_v2_contract.py
tests/tools/test_n3w_t1_production_v2_contract.py
tools/n3w_t1_fresh_armbian_qualification.py
tests/tools/test_n3w_t1_fresh_armbian_qualification.py
~~~

All previously closed R1 SSH, marker, forensic, residue, release-binding and authority-root repairs therefore remain unchanged by this gate.

The dedicated R1 workflow compiled all R1 foundation tools, ran all five R1 foundation test modules and passed the R1 boundary check.

~~~text
N3W_T1_F5_V2_SOURCE_CI_RUN=39359396650
R1_FOUNDATIONS_JOB=SUCCESS
ALL_PR_WORKFLOWS_AT_REVIEW=12_OF_12_SUCCESS
FOCUSED_REVIEW_NEW_BLOCKER=NONE
~~~

## 5. R1 decision

~~~text
R1_CLOSED_PASS=true
READY_FOR_R2_ENTRY_DECISION=true
R2_ENTRY_GRANTED=false
R2_STARTED=false
~~~

R1 foundations are now stable enough for a separate R2 entry decision. This closure does not itself authorize HOST_BASELINE adaptation, F3 V2 context adaptation, V2 orchestrator implementation, T1 access, board access or merge.

## 6. Next gate

~~~text
NEXT_ONE_GATE=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_ENTRY_DECISION_20261020_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=true
~~~

Hard stop:

~~~text
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~

## 7. KNOWN_FAILURES classification

~~~text
KNOWN_FAILURES_UPDATE_REQUIRED=false
NEW_KF_REQUIRED=false
~~~

These were pre-merge source-review blockers and no field/runtime failure was established.
