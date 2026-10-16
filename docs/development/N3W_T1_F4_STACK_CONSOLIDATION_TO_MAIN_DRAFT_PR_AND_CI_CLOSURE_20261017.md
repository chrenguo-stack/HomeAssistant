# N3-W T1 F4 stack consolidation to main — draft PR, CI and focused equivalence closure

Date: 2026-10-17

```text
TASK=N3W_T1_F4_STACK_CONSOLIDATION_TO_MAIN_DRAFT_PR_AND_CI_20261017_01
RESULT=CLOSED_PASS_READY_FOR_SEPARATE_MERGE_DECISION

PR=608
PR_URL=https://github.com/chrenguo-stack/HomeAssistant/pull/608
PR_STATE=OPEN_DRAFT_NOT_MERGED
PR_MERGEABLE=true

MAIN_BASE=b12c69be5c1d1d61887e9be4a776f575141d44c6
MAIN_TREE=ae55875aedcde8dbdd8ac537784a908bd10a05a5

CONSOLIDATION_HEAD=6b9d311c4055230fd758abe20b40d7d545b04d81
CONSOLIDATION_TREE=29951e55ab800f77a2d5b3012adcd94e874bbd8d
CONSOLIDATION_COMMITS=2
CONSOLIDATION_CHANGED_FILES=70

COMMIT_A=f1fd9a679a32e43dd57dc96147823b36bfb674ae
COMMIT_A_TREE=a98ed5c105f55849d6f416fa46f05fb309c54d54
COMMIT_A_PARENT=b12c69be5c1d1d61887e9be4a776f575141d44c6

COMMIT_B=6b9d311c4055230fd758abe20b40d7d545b04d81
COMMIT_B_PARENT=f1fd9a679a32e43dd57dc96147823b36bfb674ae

PRODUCT_SOURCE_AUTHORITY=19bd98386c4828c0768f2f3936429db8c7a59adf
PRODUCT_SOURCE_AUTHORITY_TREE=f5b66faf690c88d655e01ffc0a5d5ef122b589af
IMMUTABLE_EVIDENCE_AUTHORITY=62f2a107d834b31b498e230ee68f66833580f4c5
IMMUTABLE_EVIDENCE_AUTHORITY_TREE=1a2cb562a75d295e3e3296ba3ea5cfbb0dd1ca4a

CI_RESULT=PASS:14/14
TREE_EQUIVALENCE_REVIEW=PASS
MAIN_PRESERVATION_REVIEW=PASS
PRODUCT_EQUIVALENCE=PASS:19/19
IMMUTABLE_EVIDENCE_BINDING=PASS:44/44
FROZEN_LEDGER_BINDING=PASS:3/3
CONSOLIDATION_METADATA_BINDING=PASS:4/4
ALLOWLIST_PATHS=70
CHANGED_PATHS=70
UNLISTED_PATH_DRIFT=NONE
MAIN_PRESERVATION_CHECKED_PATHS=1666

LIVE_REBOOT_ACCEPTANCE=PASS
POST_REBOOT_ACCEPTANCE=PASS
DURABLE_REBOOT_LEDGER=REBOOT_ACCEPTED
TERMINAL_VERIFY=PASS
KF_121_DURABLE_LEDGER_BLOCKER=CLOSED_PASS

MERGE=false
MAIN_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false

NEXT_ONE_GATE=N3W_T1_F4_STACK_CONSOLIDATION_TO_MAIN_MERGE_DECISION_20261017_01
AUTO_MERGE=false
STOP=true
```

## Final focused review

PR #608 completed all 14 observed workflows successfully.

The clean candidate was then re-bound against current main, the exact reviewed product source authority, the immutable
evidence authority, the frozen ledger record and the consolidation metadata.

The two-commit history is exact:

1. commit A is a single child of exact current main and contains the exact reviewed product snapshot;
2. commit B is a single child of commit A and adds the frozen durable evidence / ledger / consolidation metadata.

The main-to-candidate diff contains exactly 70 changed paths, equal to the complete allowlist. There are no changed
paths outside the allowlist.

All 19 product paths are byte/mode-equivalent to the source-reviewed authority. All 44 immutable evidence paths match
their frozen evidence authority. All three mutable ledgers and all four consolidation metadata files match the
preparation freeze.

All repository blob paths outside the allowlist were independently compared between exact main and the candidate;
1666 non-allowlisted blob paths are unchanged.

## Merge boundary

This closure establishes that PR #608 is technically ready for a separate merge decision. It does not authorize or
perform a merge.

The PR remains Draft and unmerged until the separate merge gate is explicitly authorized.
