# N3-W / T1 F5 — KF-123 UNKNOWN-run controlled recovery source review

Date: 2026-10-19

## Scope

~~~text
TASK=N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REVIEW_20261019_01
RESULT=FAIL_CLOSED_BLOCKERS_FOUND

REVIEW_BASE=223e79b4dfb4f1f17501fcf244352e468d17dd27
SOURCE_IMPLEMENTATION_HEAD=a4f5bfa9ea0cd75511f8a562c14a6b99f0640d9a
SOURCE_IMPLEMENTATION_TREE=629a6fb39ba3e9645bb11713481b57c29d15738c
PR620_REVIEW_HEAD=6dd2076af9f555aec5e7b054050915faaf6dad36
PR620_REVIEW_TREE=f58dda31eeabc68e285a52377e7a738462595f30

ADJUDICATOR_BLOB=957597637e958808cf24f95248de5ca354ed354d
TEST_BLOB=7ad940b735b84416f489e7faf3b551b6c0f3fb55
CI_BLOB=6712e9ae837a232b5abfc7d9366abdbba0a4b35e

PR620_CI=PASS_12_OF_12
FOCUSED_TESTS=PASS_12

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
SOURCE_MUTATION=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~

CI success is accepted as execution evidence for the implemented tests and package build, but it does not close the source review. Independent review found fail-closed gaps that must be repaired before any target read-only preauthorization or live adjudication.

## What is correct

The implementation correctly keeps the normal production UNKNOWN-run approval guard unchanged and adds no F3 replay or new-production-run path. It binds the helper to the exact historical run/source/release, requires consumed/no-replay TERMINAL/FAIL + UNKNOWN state, requires HOST_BASELINE SUCCEEDED, requires F3 UNKNOWN with the preserved failure code, and requires fresh run/phase SHA-256 values before the first recovery claim.

The dedicated recovery ledger is one-shot and durable, uses CLAIMED -> APPLYING -> ADJUDICATED, and permits bounded continuation only under the same authorization. The source has explicit split-state handling for phase reclassification, run reclassification, and recovery-ledger finalization. The CLI reports conservative mutation state after recovery or historical-ledger writes.

The runtime guard is conservative: Docker must remain active and the current implementation requires zero containers, images, volumes, non-default networks, known product paths, product units and F3 staging roots. The helper also provides a separate read-only verify command.

## A1 — BLOCKER: F3 business-execution ledger zero proof is not fail-closed

`_execution_record_count()` treats every syntactically valid JSON object that does not expose the exact
`run_id` + `phase` pair as unrelated and silently ignores it.

That is weaker than the design requirement "F3 production business-execution ledger count is exactly zero". A corrupt or schema-invalid record can therefore be present while the helper still returns count 0. Examples include a JSON object with missing fields, a wrong schema, or duplicate keys resolved by ordinary `json.loads`.

The function also does not validate the execution-ledger root/file ownership and mode contract used by the production bootstrap.

Required repair:

- validate the execution-ledger root as an authority-owned ledger;
- parse records with duplicate-key rejection;
- validate every record against the production execution schema/required fields before using it as evidence;
- fail closed on any malformed or ambiguous record;
- add regression tests proving malformed/schema-invalid/duplicate-key records cannot be reported as zero.

~~~text
A1_F3_EXECUTION_LEDGER_ZERO_PROOF=BLOCKER
~~~

## A2 — BLOCKER: historical phase binding is not exact enough

`_host_baseline_exact()`, `_phase_unknown_exact()` and `_phase_failed_exact()` verify source head, release ID and target binding, but they do not re-prove the complete phase-chain bindings originally enforced by `n3w_t1_production_authority.claim_phase()`.

Missing checks include:

- HOST_BASELINE `artifact_sha256` equals the plan's HOST_BASELINE artifact;
- HOST_BASELINE predecessor is exactly null;
- F3 `artifact_sha256` equals the plan's F3 artifact;
- F3 `predecessor_sha256` equals the current durable HOST_BASELINE phase-record SHA-256.

As written, a drifted phase binding can still be accepted and reclassified if source/release/target remain the same.

Required repair:

- re-prove the complete HOST_BASELINE and F3 binding chain from the durable plan and phase records;
- keep `binding_sha256` validation supplied by the authority loader;
- add focused tests for artifact and predecessor drift.

~~~text
A2_PHASE_CHAIN_BINDING_EXACTNESS=BLOCKER
~~~

## A3 — BLOCKER: later-run exclusion has a same-second ambiguity

`_later_target_run_absent()` compares integer-second `created_at` values and rejects only:

~~~text
other.created_at > incident.created_at
~~~

A later same-target run created in the same second is therefore not rejected. This is a narrow edge case, but the recovery contract requires a fail-closed proof that no later production run has been approved for this target.

Required repair:

- treat same-second same-target ordering as ambiguous and STOP, or
- bind to another durable ordering fact that can unambiguously prove the other run predates the incident.

~~~text
A3_LATER_RUN_ORDERING=BLOCKER
~~~

## Non-blocking note — post-adjudication process gate

The normal production authority blocks a new approval while this run remains `failure_class=UNKNOWN`. Once the controlled recovery eventually changes that field to FAILED, the repository process must still preserve the existing rule that a separate fresh read-only postexecution verification closes recovery before any new F5-9 authorization is granted.

This review does not require widening the normal production authority in the current repair unless the repair design chooses to encode that process gate in source. It does require the handoff/current-state chain to keep the postverify gate explicit.

## Review result

~~~text
KF123_UNKNOWN_RUN_RECOVERY_SOURCE_REVIEW=FAIL_CLOSED

A1_F3_EXECUTION_LEDGER_ZERO_PROOF=BLOCKER
A2_PHASE_CHAIN_BINDING_EXACTNESS=BLOCKER
A3_LATER_RUN_ORDERING=BLOCKER

TARGET_READONLY_PREAUTH_READY=false
LIVE_ADJUDICATION_READY=false

NEXT_ONE_GATE=
N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REPAIR_20261019_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~

No T1 access or target mutation was performed. PR #620 remains OPEN/DRAFT and unmerged.
