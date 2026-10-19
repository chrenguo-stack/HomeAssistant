# N3-W T1 F5 phase-context live failure — source repair and replacement release preparation

Date: 2026-10-19

## 0. State

~~~text
TASK=N3W_T1_F5_PHASE_CONTEXT_LIVE_FAILURE_SOURCE_REPAIR_AND_RELEASE_PREPARATION_20261019_01
RESULT=SOURCE_REPAIR_AND_EXACT_RELEASE_CLOSED_PASS
LIVE_RECOVERY_NOT_AUTHORIZED=true

FAILED_RUN_ID=56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e
FAILED_RUN_STATE=IN_PROGRESS
FAILED_RUN_LAST_CLAIMED_PHASE=HOST_BASELINE
FAILED_RUN_LAST_COMPLETED_PHASE=null
FAILED_RUN_TERMINAL_STATE=null
HOST_BASELINE_PHASE_STATE=APPLYING
HOST_BASELINE_EXECUTION_LEDGER=ABSENT
FAILED_RUN_REPLAY_ALLOWED=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

The first authorized F5-9 T1-B production run stopped immediately after the target durable
`HOST_BASELINE` phase entered `APPLYING`. The target-side host-baseline execution ledger was
independently read and was absent. Therefore no F5 host-baseline business mutation was entered:
no F5 APT install, Docker baseline install, F3 deployment, provisioning, product service start,
or reboot was reached by this run. The durable F5 production run/phase ledger itself was written
and the authorization is consumed.

The failed run is not replayable and must not be deleted or manually edited.

## 1. Confirmed source defect

Frozen failing product source:

~~~text
FAILING_SOURCE_HEAD=6e228a4b2c7c4ff78918571abb7b583e416615ee
FAILURE_CODE=remote_command_failed:2
~~~

The failure was closed to the target production-authority `phase_context()` CLI contract.
The function returned a valid context document without `status=PASS`, while the CLI main path
returns success only when `document.get("status") == "PASS"`. The runtime wrapper likewise
requires both remote exit code 0 and `status=PASS`.

This made a valid phase context exit with code 2 after `begin_phase()` had already durably moved
`HOST_BASELINE` to `APPLYING`.

## 2. Source repair

~~~text
SOURCE_REPAIR_HEAD=9048dd7c6b48c0620471919c0cf96c96bdab71f1
SOURCE_REPAIR_TREE=7b567c7140fd403049a6f7c2fa51887be08e8c8d
SOURCE_REPAIR_DELTA_FROM_FAILING_HEAD=2_COMMITS
SOURCE_REPAIR_CHANGED_FILES=2
SOURCE_REPAIR_CI=PASS_20_OF_20
~~~

Effective delta from the failing source is intentionally minimal:

1. `tools/n3w_t1_production_authority.py`: add `"status": "PASS"` to the successful
   `phase_context()` document.
2. `tests/tools/test_n3w_t1_production_authority.py`: assert the successful context carries
   `status == "PASS"`.

No production phase ordering, replay rule, target identity binding, reboot budget, board boundary,
or product mutation primitive was widened.

## 3. Replacement exact release

PR #613 rebuilt the exact production release from the repaired source and exact source-bound F3/F4
artifacts.

~~~text
BUILDER_HEAD=b2622cb7588d0224e1345abe84bd7aec307a2aae
WORKFLOW_RUN_ID=39195658088
EXACT_RELEASE_CI=PASS

SOURCE_HEAD=9048dd7c6b48c0620471919c0cf96c96bdab71f1
SOURCE_TREE=7b567c7140fd403049a6f7c2fa51887be08e8c8d

RELEASE_ID=31c8a8cd2d8424f93aaa7b4d0b78cfe2b73f1b035f4bdbce08a181ac56619420
RELEASE_SHA256=1bbcb81bd84ec899e4c1d37fffef99defbbcc40509c49ce41048f6a6d92039ad
FILE_INDEX_SHA256=be36b3cd3f5a20099f870c55dcb78586e2e507fddc47bf5f589d85fab8091c83

ARTIFACT_ID=12162160866
ARTIFACT_NAME=n3w-t1-f5-approved-release-9048dd7c6b48c0620471919c0cf96c96bdab71f1
ARTIFACT_ZIP_SHA256=1938ad3e4d7b87622a21968961b3fea4472907c4b31cc8db8c80acfd0fb149e8
ARTIFACT_SIZE_BYTES=2536415496
ARTIFACT_EXPIRES_AT=2026-11-18T03:39:43Z

F5_EXACT_RELEASE_POST_UPLOAD_BINDING=PASS
~~~

The previous release bound to source `6e228a4b...` remains historical evidence only and must not
be used for another production run.

## 4. Required next sequence

The replacement release is not yet eligible for another F5-9 run until its durable Mac archive is
accepted. Separately, the failed target run remains `IN_PROGRESS/HOST_BASELINE=APPLYING` and must
be closed by a bounded, evidence-preserving recovery path rather than ledger deletion or replay.

~~~text
NEXT_1=REPLACEMENT_RELEASE_DURABLE_MAC_ARCHIVE
NEXT_2=FAILED_RUN_CONTROLLED_TERMINALIZATION_DESIGN_AND_EXACT_RECOVERY_ARTIFACT
NEXT_3=SEPARATE_LIVE_RECOVERY_AUTHORIZATION
NEXT_4=FAILED_RUN_TARGET_TERMINALIZATION
NEXT_5=FRESH_F5_9_AUTHORIZATION_FOR_REPLACEMENT_RELEASE

DO_NOT_REPLAY_FAILED_RUN=true
DO_NOT_DELETE_TARGET_LEDGER=true
DO_NOT_REFLASH_T1B=true
DO_NOT_START_PRODUCT_SERVICES=true
~~~

A new live authorization is required before any target mutation that terminalizes the failed run
or starts a replacement production run.
