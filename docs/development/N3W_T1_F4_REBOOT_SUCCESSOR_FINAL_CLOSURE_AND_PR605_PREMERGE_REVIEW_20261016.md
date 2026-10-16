# N3-W T1 F4 reboot successor final closure and PR #605 pre-merge review

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_SUCCESSOR_FINAL_CLOSURE_AND_PR605_PREMERGE_REVIEW_20261016_01
RESULT=STOP_BLOCKED_SOURCE_REPAIR_REQUIRED

PR=605
REVIEW_HEAD=e2a38fa2d7c5c9996a57327e6f03dae5991e8123
PR_BASE_SHA=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
PR_STATE=OPEN_DRAFT_NOT_MERGED
PR_MERGEABLE=true
REVIEW_HEAD_CI=PASS:13/13

PRIOR_SOURCE_REVIEW_HEAD=da64d1cdfbe7e198abc1d536014769f56471d0cb
SOURCE_DRIFT_SINCE_PRIOR_REVIEW=DOCS_ONLY
LIVE_REBOOT_ACCEPTANCE=PASS
POST_REBOOT_STATE=REBOOT_ACCEPTED

A1_DURABLE_REBOOT_TRANSACTION_CLOSURE=OPEN_BLOCKER
A1_DURABLE_CLAIM_STAGE=REBOOT_PENDING
A1_DURABLE_REBOOT_ACCEPTANCE_PASSED=false
A1_READONLY_VERIFIER_RETURNS_REBOOT_ACCEPTED=true
A1_READONLY_VERIFIER_PERSISTS_ACCEPTANCE=false
A1_FINALIZE_COMMAND_PRESENT=false
A1_SUCCESSOR_REBOOT_CLAIM_BLOCKED_BY_PREEXISTING_CLAIM=true

STACK_PARENT_PR_600=OPEN_DRAFT_NOT_MERGED
STACK_PARENT_PR_599=OPEN_DRAFT_NOT_MERGED
STACK_PARENT_PR_598=OPEN_DRAFT_NOT_MERGED
MAIN_HEAD=b12c69be5c1d1d61887e9be4a776f575141d44c6

PR605_MERGE_READY=false
MAIN_INTEGRATION_READY=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
REBOOT_EXECUTED_IN_THIS_REVIEW=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_F4_REBOOT_ACCEPTANCE_DURABLE_CLOSURE_SOURCE_REPAIR_20261016_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

## Review conclusion

The real-T1 reboot acceptance remains valid. A changed boot identity proved that the authorized reboot occurred, and
the post-reboot verifier passed provisioning resume, Broker/Services persistence, certificate timer/lifecycle
behavior, certificate identity continuity, Manager stability/business state, and Home Assistant MQTT integration
uniqueness.

PR #605 is nevertheless not ready to merge.

The source-preparation authority explicitly required the post-reboot read-only verifier to prove the persisted
recovery contract and close the reboot transaction without replaying the consumed authorization. Current source does
the proof portion but has no durable close transition:

1. `claim-reboot` persists the one-shot record as `REBOOT_PENDING` with
   `reboot_acceptance_passed=false`;
2. the post-reboot verifier intentionally performs no writes and only returns `REBOOT_ACCEPTED` on stdout;
3. no repository-owned finalize command persists the accepted post-boot identity or transitions the durable record
   to an accepted terminal state;
4. the reboot claim creator rejects any pre-existing reboot-claim path.

Therefore a successfully accepted production T1 remains durably indistinguishable from a still-pending reboot if
only target-local control state is inspected, and the existing claim permanently occupies the path used by the
one-shot authority. GitHub evidence correctly records the observed acceptance, but external archive evidence is not
a replacement for the target-local transaction terminal state required by the source-preparation contract.

This is a source-state-machine blocker, not a failure of the completed live reboot acceptance. The repair must keep
the verifier itself read-only, add a fail-closed repository-owned acceptance-finalization path after verifier PASS,
persist the post-boot identity/acceptance linkage atomically, preserve consumed/no-replay semantics, and provide a
read-only terminal-state verifier.

## Stack integration finding

PR #605 is a stacked PR whose current base is PR #600's head. PR #600 is itself based on PR #599, and PR #599 is
based on PR #598. All four are currently open drafts and unmerged. Even after A1 is repaired and reviewed, main
integration must preserve parent-before-child ordering or use a separately reviewed stack-consolidation route.

No source, T1, runtime, board, or merge mutation occurred in this review.
