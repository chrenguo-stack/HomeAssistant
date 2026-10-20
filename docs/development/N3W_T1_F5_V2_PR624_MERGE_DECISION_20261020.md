# N3W T1 F5 V2 PR #624 merge decision — 2026-10-20

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_PR624_MERGE_DECISION_20261020_01
AUTHORIZATION=N3W_T1_F5_V2_PR624_MERGE_DECISION_20261020_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

RESULT=MERGE_READY_AWAITING_EXPLICIT_EXECUTION

REPOSITORY=chrenguo-stack/HomeAssistant
PR=624
PR_STATE=OPEN_DRAFT
PR_MERGED=false

BASE_BRANCH=main
BASE_SHA=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
PRE_DECISION_HEAD=ecd34d71da0618567ee200b290445aa82f2fa2d3
R3_FINAL_EXACT_SOURCE_HEAD=5233b08743f40a021844e4ce7f464f444de86ae1
R3_FINAL_EXACT_SOURCE_TREE=dfab4b7ffc455a3b1c26956744fa1197bbd55006

COMPARE_STATUS=ahead
AHEAD_BY=76
BEHIND_BY=0
MERGEABLE=true

CHANGED_FILE_COUNT=43

EXACT_SOURCE_CI_TOTAL=17
EXACT_SOURCE_CI_PASS=17
EXACT_SOURCE_CI_PENDING=0
EXACT_SOURCE_CI_FAIL=0

UNRESOLVED_REVIEW_THREADS=0
REVIEWS_REQUIRING_CHANGES=0
SOURCE_IMPLEMENTATION_BLOCKER_COUNT=0

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

## 1. Fresh repository binding

Fresh rebind confirms current main remains:

~~~text
4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
~~~

PR #624 remains open, Draft, mergeable, 76 commits ahead and 0 behind current main.

The exact reviewed source is:

~~~text
5233b08743f40a021844e4ce7f464f444de86ae1
~~~

The current pre-decision PR head is one docs-only closure commit above that source:

~~~text
ecd34d71da0618567ee200b290445aa82f2fa2d3
~~~

The source-to-closure delta contains only:

~~~text
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R3_POST_REBOOT_ACCEPTANCE_AND_RELEASE_INTEGRATION_CLOSURE_20261020.md
~~~

Therefore the exact source CI evidence remains directly applicable to the source implementation being proposed for merge.

## 2. Scope check

The full PR changes 43 files across:

- V2 production foundations, SSH transport, qualification, marker and failure forensics;
- exact HOST_BASELINE and F3 V2 authority adaptation;
- V2 orchestrator through post-reboot acceptance;
- V2 release builder and exact-production-release workflow;
- focused tests and dependent F2 exact-source binding alignment;
- development/current-state documentation.

The R3 implementation itself stayed inside the frozen R3 boundary. Provision/F4 conditional source was not modified. Firmware, ESP32, radio and pairing business logic were not modified.

The F2 exact-source binding alignment is the already-closed bounded dependent repair from R2 and changes source-binding constants/tests only, not F2 behavior.

## 3. Exact source CI

At exact source head `5233b08743f40a021844e4ce7f464f444de86ae1` all triggered workflows are terminal SUCCESS:

~~~text
WORKFLOW_TOTAL=17
WORKFLOW_SUCCESS=17
WORKFLOW_FAILURE=0
WORKFLOW_PENDING=0

N3W_T1_F5_V2_SOURCE_CI_RUN=39371652141
R1_FOUNDATIONS=PASS
R2_SOURCE=PASS
R2_FOCUSED_TESTS=96_PASS
R2_BOUNDARY=PASS
R3_SOURCE=PASS
R3_FOCUSED_TESTS=64_PASS
R3_BOUNDARY=PASS
OBSERVATION_WINDOW_SECONDS=90
PR_RELEASE_PRODUCTION_AUTHORITY=false

N3W_T1_F2_READONLY_PREFLIGHT_SOURCE_CI_RUN=39371652091
RESULT=PASS

N3W_T1_FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI_RUN=39371652102
RESULT=PASS

N3W_T1_PRODUCTION_STACK_STAGING_PAYLOAD_CI_RUN=39371652098
RESULT=PASS

N3W_T1_FRESH_INSTALL_HOST_ONLY_CI=PASS
N3W_T1_GOLDEN_MASTER_SOURCE_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI=PASS
GREENHOUSE_MANAGER_CI=PASS
~~~

## 4. Source/review closure

The source implementation authority records:

~~~text
R1_CLOSED_PASS=true
R2_CLOSED_PASS=true
R3_CLOSED_PASS=true
F5_V2_SOURCE_IMPLEMENTATION_CLOSED_PASS=true

WHOLE_SOURCE_BLOCKER_COUNT=0
UNRESOLVED_REVIEW_THREADS=0
REVIEWS_REQUIRING_CHANGES=0
~~~

The final R3 focused review repaired conservative STARTED/session boundaries and exact-main release-input provenance. No known source blocker remains.

## 5. Merge decision

PR #624 is technically ready to merge into main as the F5 V2 source implementation.

This gate is a decision only. It does not authorize or execute merge.

The PR remains Draft until an explicit merge-execution gate is authorized.

The exact production release must not be produced from the PR branch. Production release authority only becomes valid after successful merge, fresh main rebind, and exact-main release build.

## 6. Required post-merge order

After a separately authorized merge execution:

~~~text
PR624 MERGE
-> fresh main rebind
-> verify exact merged source/tree
-> run/confirm main CI as applicable
-> exact V2 production release build from merged main
-> fresh-T1 read-only qualification
-> separate explicit live deployment authorization
~~~

No real T1 deployment or board access is part of merge execution.

## 7. Stop

~~~text
MERGE_READY=true
MERGE_AUTHORIZED_BY_THIS_GATE=false
MERGE_EXECUTED=false

NEXT_ONE_GATE=N3W_T1_F5_V2_PR624_MERGE_EXECUTION_20261020_01
EXPLICIT_MERGE_AUTHORIZATION_REQUIRED=true
AUTO_MERGE=false

EXACT_PRODUCTION_RELEASE_BUILD_EXECUTED=false
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
STOP=true
~~~
