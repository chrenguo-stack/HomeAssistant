# N3-W T1 F4 PR #605 final/pre-merge and stack integration review

Date: 2026-10-17

```text
TASK=N3W_T1_F4_PR605_FINAL_PREMERGE_AND_STACK_INTEGRATION_REVIEW_20261017_01
RESULT=PR605_RELATIVE_BASE_PASS_MAIN_INTEGRATION_STOP_STACK_CONSOLIDATION_REQUIRED

MAIN=b12c69be5c1d1d61887e9be4a776f575141d44c6
PR=605
PR_HEAD=0acf1c6e5dca0b103e3c3aaceb26c847bfad65d3
PR_BASE=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
PR_STATE=OPEN_DRAFT_NOT_MERGED
PR_MERGEABLE=true

PRODUCT_SOURCE_REVIEW_HEAD=19bd98386c4828c0768f2f3936429db8c7a59adf
SOURCE_DRIFT_AFTER_REVIEW=DOCS_ONLY
PR605_HEAD_CI=PASS:13/13

LIVE_REBOOT_ACCEPTANCE=PASS
POST_REBOOT_ACCEPTANCE=PASS
DURABLE_REBOOT_LEDGER=REBOOT_ACCEPTED
TERMINAL_VERIFY=PASS
KF_121_DURABLE_LEDGER_BLOCKER=CLOSED_PASS

PR605_RELATIVE_TO_PR600_PREMERGE_REVIEW=PASS
PR605_DIRECT_MAIN_MERGE_READY=false

DECLARED_CHAIN_598_599_600_605=VALID_DIRECT_ANCESTRY
DECLARED_CHAIN_ROOTED_AT_MAIN=false
UPSTREAM_PARENT_597_DISCOVERED=true
UPSTREAM_PARENT_596_DISCOVERED=true
UPSTREAM_PARENT_595_DISCOVERED=true
PR601_604=SIDE_BRANCH_FROM_PR600_NOT_ANCESTOR_OF_PR605

MAIN_TO_PR605_HEAD_AHEAD_BY=272
MAIN_TO_PR605_HEAD_FILE_COUNT=65

RECOMMENDED_INTEGRATION_ROUTE=DESIGN_EXPLICIT_F4_STACK_CONSOLIDATION_TO_MAIN
AUTO_MERGE=false
BOARD_ACCESS=false
T1_MUTATION=false
MERGE=false
STOP=true
```

## 1. PR #605 final/pre-merge review

The durable-ledger blocker that stopped the previous final review is now closed on the real T1. The target-local
reboot ledger is durably `REBOOT_ACCEPTED`, the independent terminal verifier passed, and the consumed reboot
authorization remains non-replayable.

The exact reviewed product source remains
`19bd98386c4828c0768f2f3936429db8c7a59adf`. Every commit after that source head in PR #605 is documentation-only.
The current PR #605 head has 13/13 successful observed workflows.

Therefore PR #605 is source/runtime ready relative to its current base PR #600 head. No open KF-121 runtime or
durable-ledger blocker remains.

## 2. Why PR #605 must not be merged directly to main

PR #605 is still a stacked PR. Its base is PR #600 head, not main.

The previously stated direct ancestry is correct:

```text
#598 -> #599 -> #600 -> #605
```

However fresh repository binding shows that this is not the full path back to main. PR #598 itself is based on PR
#597 head; PR #597 is based on PR #596 head; PR #596 is based on PR #595 head; and PR #595 is itself not based on
current main.

The current PR #605 head is 272 commits ahead of current main and the cumulative main-to-head delta spans 65 files.
Therefore treating only #598/#599/#600/#605 as the complete integration stack would be incomplete.

## 3. Side branches

PRs #601-#604 form a separate historical/documentation path from PR #600 and are not ancestors of the current PR
#605 head. They must not be blindly inserted into the #605 parent chain merely because they share earlier F4
history.

Any consolidation design must classify these side branches as either already superseded by content present on the
current #605 head, still carrying unique durable evidence, or separately retainable without changing product source.

## 4. Integration conclusion

There is no justification for a direct PR #605 -> main merge.

The safer next step is a dedicated read-only stack-consolidation design that starts from current main and the current
PR #605 head, reconstructs the exact ancestor/side-branch graph, identifies the minimal authoritative F4 source and
required durable documentation, and defines one reviewable integration route.

No merge is authorized by this review.
