# N3W T1 per-device fresh Armbian automated deployment — F1B focused closure

Date: 2026-10-14

```text
TASK=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F1B_FOCUSED_CLOSURE_REVIEW_20261014_01
PR=541
PR_STATE=OPEN_DRAFT_UNMERGED
REVIEW_BASE=fb2a0d0ef55980c83919b608633b060f656e8dcc
ORIGINAL_F1B_SOURCE_HEAD=f011bf389a0909383b9e485d089b89f9120e9173
REPAIRED_SOURCE_HEAD=f1306067667c1a58b172b543c452c1a388ec119e
SOURCE_EQUIVALENT_CI_HEAD=39bb520eab7bd9d2f9e565f0582fdd19da4c036c
SOURCE_EQUIVALENCE=f130606_TO_39bb520_IS_DOCS_ONLY_3_COMMITS
CI_RESULT=27_SUCCESS_0_FAILURE_0_PENDING
DEPLOYABLE_RUN_ID=38531162766
DEPLOYABLE_ARTIFACT_ID=11879005989
DEPLOYABLE_ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-39bb520eab7bd9d2f9e565f0582fdd19da4c036c
DEPLOYABLE_ARTIFACT_DIGEST=sha256:e10399bcc4a586b598a0e11cdfe2ebc88706b164a8d9eaa3f726ab0959d97b97
DEPLOYABLE_ARTIFACT_SIZE_BYTES=2535580469
A1=CLOSED_SOURCE
A2=CLOSED_SOURCE
A3=CLOSED_SOURCE
A4=CLOSED_SOURCE
A5=CLOSED_SOURCE
A6=CLOSED_SOURCE
A7=CLOSED_SOURCE
A8=CLOSED_SOURCE
A9=CLOSED_SOURCE
A10=CLOSED_SOURCE
KF_CLASSIFICATION=KF-108_RECURRENCE_NO_NEW_KF
NEW_SOURCE_BLOCKER_COUNT=0
F1B_SOURCE_STATUS=CLOSED_SOURCE
F1B_FOCUSED_CLOSURE_RESULT=CLOSED_PASS
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
F2_ENTERED=false
NEXT_ROUTE=F2_FRESH_T1_READONLY_PREFLIGHT_PREPARATION
AUTO_EXECUTE_NEXT_ROUTE=false
STOP=true
```

## Closure basis

The focused review independently rechecked A1-A10. Two same-gate host-wrapper blockers were found and repaired before closure:

- A3: a durable authorization claim could exist even when the SSH/result boundary lost the claim result. The repaired wrapper probes the durable claim ledger and treats present or unknown post-claim state as consumed/no-replay, closing the KF-108 recurrence.
- A10: a host-side event/transfer failure could leave the remote SSH apply child unreaped. The repaired wrapper now performs bounded terminate/wait/kill cleanup before returning failure.

The repaired source authority is `f1306067667c1a58b172b543c452c1a388ec119e`. The three commits from that source authority to `39bb520eab7bd9d2f9e565f0582fdd19da4c036c` modify only F1B progress/current-state documentation, so the latter is source-equivalent for the final CI and deployable-artifact proof.

The source-equivalent head completed all 27 pull-request workflows successfully. The deployable workflow initially encountered an external Docker HTTP 500 while materializing an external ARM64 image; a failed-job-only rerun succeeded and produced artifact ID `11879005989` with the digest recorded above. No source regression was established by the transient external pull failure.

F1B is therefore CLOSED_PASS. This document does not authorize F2 execution, T1 access, live mutation, board access, production service start, or merge.
