# N3W T1 F5 V2 PR #628 post-merge 状态对齐 — 2026-10-21

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_PR628_POSTMERGE_STATE_ALIGNMENT_20261021_01
STATUS=DOCS_ONLY_ALIGNMENT_PAYLOAD_READY

SOURCE_MAIN=3252a204f1cb6ecd09818bca9bd50d1a6ced586c

PR628_STATE=CLOSED_MERGED
PR628_HEAD=291ab6b27f50457314472049768663bc7e744e79
PR628_MERGE_COMMIT=3252a204f1cb6ecd09818bca9bd50d1a6ced586c
PR628_MERGE_PARENT_1=1a0689f2c1c6566a397f065ff546ad26ef02046d
PR628_MERGE_PARENT_2=291ab6b27f50457314472049768663bc7e744e79
PR628_HEAD_TREE=b36d949f9077fe74c92d664170d2937278644218
MERGE_TREE=b36d949f9077fe74c92d664170d2937278644218
TREE_IDENTITY=PASS
PR_HEAD_TO_NEW_MAIN_CONTENT_DELTA=NONE
MERGE_ONLY_CONTENT_DRIFT=NONE

PREMERGE_EXACT_HEAD_CI=PASS:17/17
READY_TRANSITION_COMPLETED=true
MERGE_METHOD=merge
EXPECTED_HEAD_ENFORCED=true

REAL_T1_PRODUCTION_EXECUTOR_SOURCE_REPAIR=CLOSED_PASS
NONDISRUPTIVE_POST_REBOOT_ACCEPTANCE_REPAIR=CLOSED_PASS
POST_REBOOT_EVIDENCE_CLASSIFICATION_R2=CLOSED_PASS
SOURCE_BLOCKER=CLOSED

REAL_T1_PRODUCTION_EXECUTOR_IN_MAIN=true
TARGET_LOCAL_RUNTIME_AUTH_EVIDENCE_IN_MAIN=true
NEGATIVE_EXTERNAL_AUTH_PROBE_IN_MAIN=true
OBSERVATION_90S_IN_MAIN=true
MIDWINDOW_FAILURE_STICKY_IN_MAIN=true
POST_REBOOT_EVIDENCE_INSUFFICIENT_CLASSIFICATION_IN_MAIN=true
F4_REBOOT_PACKAGE_BINDING_IN_MAIN=true
MAC_TOOLS_BINDING_IN_MAIN=true

PREVIOUS_EXACT_RELEASE_PRODUCTION_AUTHORITY_FOR_CURRENT_MAIN=false
EXACT_MAIN_F4_REBOOT_ARTIFACT_REBUILD_REQUIRED=true
EXACT_MAIN_RELEASE_INPUTS_REBUILD_REQUIRED=true
EXACT_MAIN_PRODUCTION_RELEASE_REBUILD_REQUIRED=true
LOCAL_EXACT_RELEASE_VALIDATION_REQUIRED=true
STANDARD_FRESH_ARMBIAN_READONLY_QUALIFICATION_REQUIRED=true

REAL_T1_PRODUCTION_EXECUTION=false
REAL_T1_NONDISRUPTIVE_ACCEPTANCE=false
KF_122=OPEN

ALIGNMENT_SCOPE=DOCS_ONLY
PRODUCT_SOURCE_MUTATION=false
WORKFLOW_DISPATCH=false
GITHUB_ARTIFACT_PRODUCTION=false
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false

TERMINATING_CLOSURE_RULE=THIS_ALIGNMENT_PAYLOAD_REACHABLE_FROM_MAIN
F5_V2_PR628_REPOSITORY_ALIGNMENT_FINAL=false
AUTO_MERGE=false
~~~

## 1. Purpose

PR #628 has merged the reviewed real-T1 production executor, non-disruptive post-reboot acceptance repair and evidence-classification repair into main.

The merged current-state ledgers intentionally still contain the pre-merge PR state. This docs-only alignment updates durable repository bookkeeping to the facts proven after merge. It does not alter product source, workflows, tests, release artifacts, T1 runtime state, board state, credentials or services.

Historical source-repair and review documents remain historical records. They are not rewritten to pretend that their earlier pre-merge state was different.

## 2. Exact merged facts

~~~text
OLD_MAIN=1a0689f2c1c6566a397f065ff546ad26ef02046d
PR628_HEAD=291ab6b27f50457314472049768663bc7e744e79
PR628_MERGE_COMMIT=3252a204f1cb6ecd09818bca9bd50d1a6ced586c
NEW_MAIN=3252a204f1cb6ecd09818bca9bd50d1a6ced586c

MERGE_PARENT_1=1a0689f2c1c6566a397f065ff546ad26ef02046d
MERGE_PARENT_2=291ab6b27f50457314472049768663bc7e744e79

PR_HEAD_TREE=b36d949f9077fe74c92d664170d2937278644218
MERGE_TREE=b36d949f9077fe74c92d664170d2937278644218
TREE_IDENTITY=PASS

PREMERGE_EXACT_HEAD_CI=PASS:17/17
PR_HEAD_TO_NEW_MAIN_CONTENT_DELTA=NONE
MERGE_ONLY_CONTENT_DRIFT=NONE
~~~

The merge commit contains exactly the reviewed PR head tree. No source content changed during merge.

At this alignment preparation point no post-merge workflow run was visible for merge SHA `3252a204...`. That does not change the pre-merge 17/17 exact-head CI result or the tree-identity proof above.

## 3. Source now reachable from main

The merged main now contains the reviewed path:

~~~text
exact release verify
-> managed SSH epoch #1
-> Standard Fresh Armbian qualification
-> one top-level production approval
-> STARTED marker
-> exact-release F3 deployment
-> Provision
-> F4 prepare / activate / runtime / persistence / certificate lifecycle
-> controlled reboot
-> target-local post-reboot verification
-> non-disruptive external probes
-> 90-second continuous observation
-> ACCEPTED marker only after acceptance
~~~

The acceptance implementation now preserves these distinctions:

~~~text
explicit runtime contradiction
-> POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
-> device_acceptance=FAIL

evidence unavailable / ambiguous
-> POST_REBOOT_EVIDENCE_INSUFFICIENT_REFLASH_REQUIRED
-> device_acceptance=NOT_REACHED
~~~

Both remain fail-closed after STARTED and before durable ACCEPTED. Neither path may silently continue to production-ready state.

## 4. Existing release is not authority for the merged source

A production release built before PR #628 merged cannot authorize execution of the repaired source. The source-repair authority already requires a newly built exact-main release after merge.

Therefore the next artifact chain must be rebuilt from current main:

~~~text
main=3252a204f1cb6ecd09818bca9bd50d1a6ced586c
-> exact-main F3 deployable payload
-> exact-main F4 control + reboot-control packages
-> exact-main V2 release inputs
-> exact-main production release
-> local exact-release verification
-> Standard Fresh Armbian read-only qualification
-> only then a separate real-T1 production authorization decision
~~~

No older release artifact is promoted merely because its earlier source was valid at the time it was built.

## 5. What remains unexecuted

~~~text
EXACT_MAIN_F3_ARTIFACT_REBUILD_EXECUTED=false
EXACT_MAIN_F4_REBOOT_ARTIFACT_REBUILD_EXECUTED=false
EXACT_MAIN_RELEASE_INPUTS_REBUILD_EXECUTED=false
EXACT_MAIN_PRODUCTION_RELEASE_REBUILD_EXECUTED=false
LOCAL_EXACT_RELEASE_VALIDATION_EXECUTED=false
STANDARD_FRESH_ARMBIAN_READONLY_QUALIFICATION_EXECUTED=false
REAL_T1_PRODUCTION_EXECUTION=false
REAL_T1_NONDISRUPTIVE_ACCEPTANCE=false
KF_122=OPEN
~~~

PR #628 source/CI closure does not close KF-122. KF-122 requires real-T1 evidence.

## 6. Safety boundary

This alignment gate is docs-only.

~~~text
PRODUCT_SOURCE_MUTATION=false
WORKFLOW_DISPATCH=false
GITHUB_ARTIFACT_PRODUCTION=false
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

## 7. Terminating closure rule

~~~text
PR #628 post-merge repository alignment is final when this exact alignment payload is reachable from main.
~~~

Once this alignment PR is merged and a fresh main rebind proves that condition, no second alignment-of-alignment commit is needed merely to record the alignment merge.

The alignment PR merge remains a separate explicit authorization decision.

## 8. Next boundary

~~~text
CURRENT_STAGE=F5_V2_PR628_POSTMERGE_STATE_ALIGNMENT
CURRENT_STOP_POINT=ALIGNMENT_PAYLOAD_READY_FOR_PR_CI_AND_SEPARATE_MERGE_DECISION

NEXT_AFTER_ALIGNMENT_MERGE=
N3W_T1_F5_V2_EXACT_MAIN_RELEASE_REBUILD_PREPARATION_20261021_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
