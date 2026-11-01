# N3W T1 F5 V2 PR #622 post-merge 状态对齐 — 2026-10-19

## 1. Gate

~~~text
TASK=N3W_T1_F5_V2_PR622_POSTMERGE_STATE_ALIGNMENT_20261019_01
STATUS=DOCS_ONLY_ALIGNMENT_PAYLOAD_READY

SOURCE_MAIN=5bb415cbd282768cf6bebea252b0673e2d1d9304

PR622_STATE=CLOSED_MERGED
PR622_HEAD=0c50e6abff4617bb3e0755aae2d269a89356c7c4
PR622_MERGE_COMMIT=5bb415cbd282768cf6bebea252b0673e2d1d9304
PR622_HEAD_TO_MAIN_CONTENT_DELTA=NONE

F5_V2_ARCHITECTURE_IN_MAIN=true
F5_V2_SOURCE_DESIGN_IN_MAIN=true
F5_V2_SOURCE_DESIGN_REVIEW_IN_MAIN=true
F5_V1_IMPLEMENTATION_LINE=ARCHIVED_SUPERSEDED
F5_V2_PRODUCT_SOURCE_IMPLEMENTATION_STARTED=false

ALIGNMENT_SCOPE=DOCS_ONLY
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

TERMINATING_CLOSURE_RULE=THIS_ALIGNMENT_PAYLOAD_REACHABLE_FROM_MAIN
F5_V2_REPOSITORY_ALIGNMENT_FINAL=false
AUTO_MERGE=false
~~~

## 2. Purpose

PR #622 has merged the reviewed F5 V2 architecture contract and source design into main.

The current-state ledgers inside PR #622 were intentionally written before merge, so they still contain candidate-era
facts such as PR #622 being open/draft and the next gate being merge decision.

This alignment payload updates only that durable repository bookkeeping.

No product source, workflow, tests, T1 runtime state, board state, service state, credentials or release artifact is changed.

## 3. Exact merged facts

~~~text
OLD_MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb
PR622_HEAD=0c50e6abff4617bb3e0755aae2d269a89356c7c4
PR622_MERGE_COMMIT=5bb415cbd282768cf6bebea252b0673e2d1d9304
NEW_MAIN=5bb415cbd282768cf6bebea252b0673e2d1d9304

EXACT_HEAD_CI=PASS:11/11
READY_TRANSITION_COMPLETED=true
MERGE_METHOD=merge
EXPECTED_HEAD_ENFORCED=true
PR_HEAD_TO_NEW_MAIN_CONTENT_DELTA=NONE
MERGE_ONLY_CONTENT_DRIFT=NONE
~~~

## 4. F5 V2 authority now in main

The active F5 production direction is now the V2 simplified route:

~~~text
OFFICIAL_ARMBIAN_INSTALLED
-> EXACT_RELEASE_VALIDATION
-> STANDARD_FRESH_ARMBIAN_QUALIFICATION
-> ONE_PRODUCTION_APPROVAL
-> PRODUCTION_RUN_CLAIM
-> HOST_BASELINE_INSTALL
-> PRODUCT_DEPLOY
-> DEVICE_PROVISION
-> PRODUCT_ACTIVATE_AND_PERSIST
-> ONE_CONTROLLED_REBOOT
-> INDEPENDENT_POST_REBOOT_ACCEPTANCE
-> PRODUCTION_READY
~~~

Key frozen rules remain:

- normal production accepts only Standard Fresh Armbian;
- nonstandard or failed pre-accepted targets are reflashed instead of repaired in place;
- deployment failure after STARTED requires evidence freeze and forensic snapshot before reflash;
- exact release binds host package versions;
- F3 dynamic run context stays outside immutable payload;
- existing F4 transaction/no-replay/rollback guards remain;
- final production PASS requires independent post-reboot acceptance;
- an already durable-ACCEPTED T1 is not reflashed merely because later Mac cleanup/archive work fails.

## 5. V1 boundary

~~~text
F5_V1_OPEN_PR_STACK_612_TO_621=CLOSED_UNMERGED
F5_V1_NORMAL_DEVELOPMENT_CONTINUES=false
F5_V1_BRANCH_HISTORY_PRESERVED=true
F5_V1_CI_EVIDENCE_PRESERVED=true
F5_V1_RELEASE_HISTORY_PRESERVED=true
F5_V1_DURABLE_ARCHIVE_PRESERVED=true
~~~

The V1 implementation line remains historical evidence only.

## 6. Source-implementation boundary

F5 V2 product source implementation has not started.

After this alignment becomes reachable from main, the next source work must start from that aligned main on a new clean
implementation branch.

The source work must remain bounded to the reviewed V2 design:

~~~text
FRESH_ARMBIAN_QUALIFICATION
RELEASE_BOUND_HOST_BASELINE
MINIMAL_START_ACCEPT_RUN_MARKER
F3_EXTERNAL_RUN_CONTEXT
V2_ORCHESTRATOR
FAILURE_FORENSICS
POST_REBOOT_ACCEPTANCE_WRAPPER
CI_AND_NEGATIVE_TESTS
~~~

No T1 access or board access is authorized by this alignment gate.

## 7. Terminating closure rule

This alignment uses the repository terminating rule:

~~~text
F5 V2 repository alignment is final when this exact alignment payload is reachable from main.
~~~

Once the alignment PR is merged and fresh main verification proves that condition, no second alignment-of-alignment
commit is required merely to record that same merge.

The alignment PR merge remains a separate explicit authorization decision.

## 8. Next boundary

~~~text
CURRENT_STAGE=F5_V2_POSTMERGE_STATE_ALIGNMENT
CURRENT_STOP_POINT=ALIGNMENT_PAYLOAD_READY_FOR_PR_CI_AND_SEPARATE_MERGE_DECISION

NEXT_AFTER_ALIGNMENT_MERGE=
N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_WORK_PACKAGE_PREPARATION_20261019_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
