# N3-W T1 F4 stack consolidation to main — merge decision

Date: 2026-10-17

```text
TASK=N3W_T1_F4_STACK_CONSOLIDATION_TO_MAIN_MERGE_DECISION_20261017_01
RESULT=READY_FOR_EXPLICIT_MERGE_EXECUTION_AUTHORIZATION

PR=608
PR_URL=https://github.com/chrenguo-stack/HomeAssistant/pull/608
PR_STATE=OPEN_DRAFT_NOT_MERGED
PR_MERGEABLE=true
PR_MERGEABLE_STATE=clean

MAIN_HEAD=b12c69be5c1d1d61887e9be4a776f575141d44c6
PR_BASE_SHA=b12c69be5c1d1d61887e9be4a776f575141d44c6
PR_HEAD_SHA=6b9d311c4055230fd758abe20b40d7d545b04d81
PR_COMMITS=2
PR_CHANGED_FILES=70

CI_RESULT=PASS:14/14
REQUIRED_RULESET=protect-main
REQUIRED_STATUS_CHECK_CONTEXTS=13
REQUIRED_STATUS_CHECKS_TERMINAL_ACCEPTABLE=PASS:13/13
REQUIRED_APPROVING_REVIEW_COUNT=0
UNRESOLVED_REVIEW_THREADS=0
ALLOWED_MERGE_METHOD=merge
SQUASH_ALLOWED=false
REBASE_ALLOWED=false

TREE_EQUIVALENCE_REVIEW=PASS
MAIN_PRESERVATION_REVIEW=PASS
PRODUCT_EQUIVALENCE=PASS:19/19
IMMUTABLE_EVIDENCE_BINDING=PASS:44/44
FROZEN_LEDGER_BINDING=PASS:3/3
CONSOLIDATION_METADATA_BINDING=PASS:4/4
UNLISTED_PATH_DRIFT=NONE

READY_FOR_REVIEW_TRANSITION_REQUIRED=true
MERGE_AUTHORIZATION_GRANTED=false
MERGE=false
MAIN_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false

POSTMERGE_STATE_ALIGNMENT_REQUIRED=true
OLD_STACK_CLEANUP_SEPARATE_DECISION=true

NEXT_ONE_GATE=N3W_T1_F4_STACK_CONSOLIDATION_TO_MAIN_MERGE_EXECUTION_20261017_01
AUTO_MERGE=false
STOP=true
```

## Decision

PR #608 is technically ready for an explicit merge-execution authorization.

Fresh binding proves that current main still equals the PR base, the PR head remains the exact two-commit clean
candidate, GitHub reports `mergeable=true` and `mergeable_state=clean`, all 14 observed PR workflows passed, and
all 13 status-check contexts required by the active `protect-main` ruleset are present in terminal acceptable states.

The active main ruleset requires no approving review, requires all review threads to be resolved, and permits only the
`merge` merge method. PR #608 currently has no submitted reviews and no review threads, so there is no review
blocker.

The PR is intentionally still Draft. This merge-decision gate does not mark it ready and does not merge it.

## Exact merge-execution contract

A separately authorized merge-execution gate must:

1. fresh-rebind `main`, PR #608 and the candidate branch;
2. require exact main/base `b12c69be5c1d1d61887e9be4a776f575141d44c6`;
3. require exact head `6b9d311c4055230fd758abe20b40d7d545b04d81`;
4. require the PR to remain open, Draft, clean and unmerged;
5. mark PR #608 ready for review;
6. fresh-rebind again and inspect required checks because `ready_for_review` may trigger new workflows;
7. if any required/new workflow is pending or failing, STOP without merge;
8. otherwise merge using GitHub merge method `merge` with exact expected head SHA;
9. fresh-rebind main and verify the merge result;
10. STOP for a separate post-merge state-alignment gate.

No squash or rebase merge is permitted by the active main ruleset.

## Post-merge boundary

The clean candidate intentionally froze the three project ledgers before PR construction. Therefore, after a future
successful merge, main will contain the frozen preparation-era ledger snapshot until a separate docs-only post-merge
state-alignment gate updates the authoritative current-state records.

F4 must not be declared fully repository-closed until that post-merge alignment is complete.

Closing or deleting historical draft PRs/branches is a later repository-cleanup decision and is not part of the merge
execution gate.
