# N3W T1 F5 V2 PR #634 post-merge state alignment — 2026-10-21

## 1. Merge closure

~~~text
TASK=N3W_T1_F5_V2_PR634_POSTMERGE_STATE_ALIGNMENT_20261021_01

PR=634
PR_STATE=CLOSED_MERGED

PREMERGE_BASE_MAIN=4292481f07b6ed89fe3d275be9fa4a51d7b26e6a
REVIEWED_HEAD=dc39f969e563655c14e2ed05a1b7a6eb97f868a6
REVIEWED_HEAD_TREE=2dc95ef325aec6f2aec9a25b9b36cca7d89c9a2a

MERGE_COMMIT=1b881ff052ebdace68a901fe41e96cee3b33e98d
POSTMERGE_MAIN=1b881ff052ebdace68a901fe41e96cee3b33e98d
POSTMERGE_MAIN_TREE=2dc95ef325aec6f2aec9a25b9b36cca7d89c9a2a

TREE_IDENTITY=PASS
PR_HEAD_TO_NEW_MAIN_CONTENT_DELTA=NONE

PREMERGE_EXACT_HEAD_WORKFLOWS=12/12_PASS
MERGE_EXPECTED_HEAD_PROTECTION=PASS
~~~

The reviewed source tree is now reachable from main without content drift.

## 2. KF-124 disposition

The real-T1 failed run remains terminal and is never replayed:

~~~text
FAILED_RUN_ID=c715fdee2bbd55c4ed7e3d8d0dd2e1cd2d147651e5ba8390ab4e696dc9a43519
FAILED_RUN_REPLAY=false
FAILED_TARGET_REFLASH_REQUIRED=true
T1_PRODUCTION_READY=false
~~~

The source repair for the operator-presence defect is now merged:

~~~text
KF_124_SOURCE_REPAIR=MERGED
KF_124_LIVE_REVALIDATION=PENDING
~~~

Merged behavior:

- long-running HOST_BASELINE/F3/Provision/F4 paths emit sanitized progress;
- reboot-control staging/install/verify may complete unattended;
- the executor then blocks indefinitely at a run-bound local operator-presence arming point;
- the one-shot reboot claim and actual reboot remain forbidden until exact arming;
- after reboot, the distinct second SSH epoch explicitly surfaces that a password is required;
- password non-persistence, host-key checking, one production approval and failed-run no-replay semantics are unchanged.

KF-124 is not claimed CLOSED_LIVE until a new exact release completes a real-T1 production run through the repaired arming boundary and post-reboot acceptance.

## 3. Exact-release consequence

The previous repaired-release authority was built from pre-PR634 main:

~~~text
OLD_EXACT_MAIN=4292481f07b6ed89fe3d275be9fa4a51d7b26e6a
OLD_RELEASE_ID=ea1dddc090f5a75c5186b78204820a1d8870975904ed110cad76ade632d4acb2
OLD_RELEASE_SHA256=8a3dfabf7cf48894dde382cb2ac5a0e5ccc7cd1cdb9315186457b6c6f17876ed
OLD_FINAL_ARTIFACT_ID=12318548092
OLD_FINAL_ARTIFACT_DIGEST=sha256:4c5b8bb2bb1177d46178de266ebe691fce1f480245ec38760e3bd51bc5483675
~~~

PR #634 changes the F5 V2 Mac executor carried in `v2_mac_tools`. Therefore the old release remains evidence only and is not production authority for the new main.

A new exact-main chain is mandatory:

~~~text
NEW_EXACT_MAIN=1b881ff052ebdace68a901fe41e96cee3b33e98d
NEW_EXACT_TREE=2dc95ef325aec6f2aec9a25b9b36cca7d89c9a2a

F3_EXACT_ARTIFACT_REBUILD=REQUIRED
F4_REBOOT_EXACT_ARTIFACT_REBUILD=REQUIRED
RELEASE_INPUTS_REBUILD=REQUIRED
FINAL_EXACT_RELEASE_REBUILD=REQUIRED
LOCAL_EXACT_RELEASE_VALIDATION=REQUIRED
~~~

The new chain must never mix artifacts from the old exact main.

## 4. Failed-target boundary

No T1/board/live action occurs in this alignment gate:

~~~text
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
REFLASH=false
NEW_PRODUCTION_RUN=false
~~~

The failed T1 still requires reflash before any later production retry, but reflash must wait until the new exact release has been built and locally validated. After reflash, Standard Fresh Armbian qualification must PASS before a new production RUN_ID and new explicit production authorization may be issued.

Required order:

~~~text
PR634_MERGED
-> EXACT_MAIN_RELEASE_REBUILD
-> LOCAL_EXACT_RELEASE_VALIDATION
-> REFLASH_FAILED_T1
-> STANDARD_FRESH_ARMBIAN_QUALIFICATION
-> NEW_PRODUCTION_RUN_ID
-> NEW_PRODUCTION_AUTHORIZATION
-> REAL_T1_PRODUCTION
-> POST_REBOOT_ACCEPTANCE
~~~

## 5. Current state

~~~text
KF_122=OPEN
KF_124=SOURCE_REPAIR_MERGED_LIVE_REVALIDATION_PENDING

FAILED_RUN_REPLAY=false
FAILED_TARGET_REFLASH_REQUIRED=true
T1_PRODUCTION_READY=false

NEXT_ONE_GATE=N3W_T1_F5_V2_PR634_POSTMERGE_ALIGNMENT_MERGE_DECISION_20261021_01
~~~

The alignment payload is docs-only. Merging this alignment remains a separate repository action. After the alignment reaches main, the next technical gate is exact-main F3/F4 artifact rebuild preparation/execution for `1b881ff052ebdace68a901fe41e96cee3b33e98d`.
