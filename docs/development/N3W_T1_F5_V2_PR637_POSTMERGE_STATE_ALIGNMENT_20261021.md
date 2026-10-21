# N3W T1 F5 V2 PR #637 post-merge state alignment — 2026-10-21

## 1. Merge closure

~~~text
TASK=N3W_T1_F5_V2_PR637_POSTMERGE_STATE_ALIGNMENT_20261021_01

PR=637
PR_STATE=CLOSED_MERGED

PREMERGE_BASE_MAIN=0654ab3f5b914acd278ffb7333344d86cf5878d2

INDEPENDENT_SOURCE_REVIEW_HEAD=a904244a6ab27d728092f90d145f0e9547a9c5a9
INDEPENDENT_SOURCE_REVIEW_TREE=dd7e1e3a6ee1401bcede7c03bddde10fb4954854
FINAL_PR_HEAD=593026795e8b186830b86e8a75d465359c0a1c66
FINAL_PR_HEAD_TREE=733d7225ced9c0d2a8cae0864e67dba3d27b98fa

MERGE_COMMIT=4ee659211b68138d0780a13a9eea32a347a2e71c
POSTMERGE_MAIN=4ee659211b68138d0780a13a9eea32a347a2e71c
POSTMERGE_MAIN_TREE=733d7225ced9c0d2a8cae0864e67dba3d27b98fa

TREE_IDENTITY=PASS
FINAL_PR_HEAD_TO_NEW_MAIN_CONTENT_DELTA=NONE
SOURCE_REVIEW_TO_FINAL_PR_HEAD_DELTA=DOCS_ONLY

PREMERGE_EXACT_HEAD_WORKFLOWS=14/14_PASS
UNRESOLVED_REVIEW_THREADS=0
CHANGE_REQUESTING_REVIEWS=0
MERGE_EXPECTED_HEAD_PROTECTION=PASS
~~~

The exact reviewed repair is now reachable from `main`. The only advance after the
independent A1-A10 source review was the docs-only closure alignment already verified
before merge, and the merge tree is byte-identical to the final PR head tree.

## 2. KF-125 disposition

The source repair for the post-reboot product-readiness race is now merged:

~~~text
KF_125_SOURCE_REPAIR=MERGED
KF_125_INDEPENDENT_SOURCE_REVIEW=CLOSED_PASS
KF_125_LIVE_REVALIDATION=PENDING
NEW_SOURCE_BLOCKER_COUNT=0
~~~

Merged behavior remains:

- SSH reachability is not treated as product readiness;
- after SSH epoch #2, a read-only `POST_REBOOT_READINESS` barrier polls for up to 300 seconds at 2-second intervals;
- transient normal boot convergence returns WAIT;
- explicit contradictions such as failed required units, binding drift, disabled timer, invalid states, or unexpected runtime services fail closed;
- READY is required before strict post-reboot acceptance starts;
- strict target-local reboot verification still runs after READY;
- the same five external probes and the existing 90-second continuity observation remain unchanged;
- target verifier error codes are sanitized before preservation, and only repository-defined/sanitized codes may reach Mac frozen failure evidence.

The failed real-T1 run remains terminal:

~~~text
FAILED_RUN_ID=15212aa98751a5a90677fbfd4f2ab51bf12ad8a5b5744ca050f3b872acdf1acc
FAILED_RUN_REPLAY=false
FAILED_TARGET_REFLASH_REQUIRED=true
T1_PRODUCTION_READY=false
~~~

Source merge alone does not close KF-125 live acceptance. A fresh exact release and a
new production run on a reflashed/qualified T1 are still required.

## 3. Related open live guards

~~~text
KF_122=OPEN
KF_124=SOURCE_REPAIR_MERGED_LIVE_REVALIDATION_PENDING
KF_125=SOURCE_REPAIR_MERGED_LIVE_REVALIDATION_PENDING
~~~

PR #637 does not close the remaining real-T1 evidence obligations for KF-122, KF-124,
or KF-125. Those guards can only advance on fresh evidence from a new exact-main release
and a separately authorized real-T1 production run.

## 4. Exact-release consequence

PR #637 changes production-relevant F5 V2 Mac/target verifier bytes carried by the
exact release chain. Therefore every release produced before the new main is historical
evidence only and is not production authority for another real-T1 run.

~~~text
OLD_EXACT_RELEASE_PRODUCTION_AUTHORITY=false

NEW_EXACT_MAIN=4ee659211b68138d0780a13a9eea32a347a2e71c
NEW_EXACT_TREE=733d7225ced9c0d2a8cae0864e67dba3d27b98fa

F3_EXACT_ARTIFACT_REBUILD=REQUIRED
F4_REBOOT_EXACT_ARTIFACT_REBUILD=REQUIRED
RELEASE_INPUTS_REBUILD=REQUIRED
FINAL_EXACT_RELEASE_REBUILD=REQUIRED
LOCAL_EXACT_RELEASE_VALIDATION=REQUIRED
STANDARD_FRESH_ARMBIAN_QUALIFICATION=REQUIRED_BEFORE_NEW_PRODUCTION_RUN
~~~

No artifact from a different source head may be mixed into this chain.

Required order:

~~~text
PR637_MERGED
-> POSTMERGE_STATE_ALIGNMENT
-> EXACT_MAIN_RELEASE_REBUILD_PREPARATION
-> EXACT_MAIN_F3_F4_ARTIFACT_REBUILD
-> RELEASE_INPUTS_BUILD
-> FINAL_EXACT_RELEASE_BUILD
-> LOCAL_EXACT_RELEASE_VALIDATION
-> REFLASH_FAILED_T1
-> STANDARD_FRESH_ARMBIAN_QUALIFICATION
-> NEW_PRODUCTION_RUN_ID
-> NEW_PRODUCTION_AUTHORIZATION
-> REAL_T1_PRODUCTION
-> POST_REBOOT_READINESS
-> STRICT_POST_REBOOT_ACCEPTANCE
-> FIVE_EXTERNAL_PROBES
-> EXISTING_90_SECOND_STABILITY_OBSERVATION
~~~

## 5. Safety boundary

This alignment gate is repository documentation only:

~~~text
PRODUCT_SOURCE_MUTATION=false
WORKFLOW_DISPATCH=false
GITHUB_ARTIFACT_PRODUCTION=false
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REFLASH=false
PRODUCTION_EXECUTION=false
MERGE=false
~~~

No T1 or board state is inferred from the merge.

## 6. Current route

~~~text
CURRENT_MAIN=4ee659211b68138d0780a13a9eea32a347a2e71c
CURRENT_MAIN_TREE=733d7225ced9c0d2a8cae0864e67dba3d27b98fa

ALIGNMENT_RESULT=DOCS_ONLY_PAYLOAD_PREPARED

NEXT_ONE_GATE=N3W_T1_F5_V2_PR637_POSTMERGE_ALIGNMENT_MERGE_DECISION_20261021_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

After this alignment reaches `main`, the next technical gate is a fresh exact-main
release-rebuild preparation bound to `4ee659211b68138d0780a13a9eea32a347a2e71c`.
It must re-check the producer workflows before any dispatch; it must not reuse the
historical preparation bound to an older main.
