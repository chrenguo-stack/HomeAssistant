# N3W CI execution convergence V1

Date: 2026-10-14

```text
TASK=N3W_CI_EXECUTION_CONVERGENCE_V1_20261014_01
BASE_HEAD=39bb520eab7bd9d2f9e565f0582fdd19da4c036c
PR=541
PR_CHANGED_FILES_AT_ENTRY=261
F1B_CLOSURE=CLOSED_PASS
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
MERGE=false
F2_ENTERED=false
```

## Problem

PR #541 has accumulated 261 changed files. Pull-request path filtering is therefore evaluated against a broad cumulative PR diff, so small later commits can still launch the full 27-workflow set.

Three particularly expensive workflows did not have PR-level concurrency cancellation:

- `N3W T1 fresh bootstrap deployable payload CI`
- `N3W T1 fresh install exact ARM64 CI`
- `N3W T1 production stack staging payload CI`

These workflows perform ARM64/QEMU/image or artifact work and can overlap with obsolete runs after a newer PR commit arrives.

## V1 source repair

Add the same bounded PR-level concurrency policy already used by several lighter workflows:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

The policy cancels an older in-progress run of the same workflow for the same pull request when a newer PR head is available. Push-to-main runs are not configured to cancel each other.

This V1 deliberately does not rewrite path filters, remove required checks, change test contents, change artifact contracts, or change product source/runtime behavior.

## Remaining structural issue

Concurrency cancellation reduces wasted heavy-run time but does not solve the root cause that PR #541 is a long-lived 261-file umbrella PR. The preferred next structural measure is to stop extending the same umbrella indefinitely and move the next development phase to a small/stacked phase PR with a narrow diff, after this CI-convergence change is verified.

```text
CI_CONVERGENCE_V1_SOURCE_STATUS=PENDING_CI
PR_SPLIT_EXECUTION=NOT_STARTED
NEXT_PHASE_SOURCE_WORK=NOT_STARTED
STOP_AFTER_THIS_CHANGE_UNTIL_CI=true
```
