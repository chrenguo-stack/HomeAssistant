# N3-W T1 F4 stack consolidation to main — draft PR and CI progress

Date: 2026-10-17

```text
TASK=N3W_T1_F4_STACK_CONSOLIDATION_TO_MAIN_DRAFT_PR_AND_CI_20261017_01
STATUS=PR_CREATED_CI_PARTIAL_STOP_POLL_LIMIT

MAIN_BASE=b12c69be5c1d1d61887e9be4a776f575141d44c6
CONSOLIDATION_BRANCH=integrate/n3w-t1-f4-stack-consolidation-20261017
CONSOLIDATION_HEAD=6b9d311c4055230fd758abe20b40d7d545b04d81

PR=608
PR_URL=https://github.com/chrenguo-stack/HomeAssistant/pull/608
PR_STATE=OPEN_DRAFT_NOT_MERGED
PR_MERGEABLE=true
PR_BASE=main
PR_BASE_SHA=b12c69be5c1d1d61887e9be4a776f575141d44c6
PR_HEAD_SHA=6b9d311c4055230fd758abe20b40d7d545b04d81
PR_COMMITS=2
PR_CHANGED_FILES=70

CI_SUCCESS=13
CI_IN_PROGRESS=1
CI_TOTAL=14
CI_POLL_MAX_REACHED=true
IN_PROGRESS_WORKFLOW=N3W T1 F4 activation source CI
IN_PROGRESS_RUN_ID=38935594970

MERGE=false
MAIN_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false
STOP=true
```

## Progress

A new draft consolidation PR was created from the clean two-commit candidate directly to current main.

The PR currently contains exactly two commits and 70 changed files, matching the frozen construction contract. GitHub
reports the PR as mergeable, but no merge is authorized.

The candidate head triggered 14 observed PR workflows. After the allowed maximum of three polls, 13 are successful and
only `N3W T1 F4 activation source CI` remains in progress.

Per project CI rules, stop polling here. No tree-equivalence conclusion is advanced past CI while one required workflow
is still running.

Resume this same gate after the remaining workflow completes.
