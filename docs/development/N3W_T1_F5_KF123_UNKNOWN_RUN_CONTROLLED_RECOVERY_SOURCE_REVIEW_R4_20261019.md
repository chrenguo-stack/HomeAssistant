# N3-W / T1 F5 — KF-123 UNKNOWN-run controlled recovery source review R4

Date: 2026-10-19

## Scope

~~~text
TASK=N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REVIEW_R4_20261019_01
RESULT=CLOSED_PASS

R4_REVIEW_BASE=cc4cc951790c5e83b43ed392e5067f64dd6ab566
R3_REPAIR_SOURCE_HEAD=4ab28033a6153cbe047849c8655d6a0ce06b667a
R3_REPAIR_SOURCE_TREE=dfa57d24f98c6db2cbd719073c894e8898d7fd3e
PR620_REVIEW_HEAD=cc4cc951790c5e83b43ed392e5067f64dd6ab566
PR620_REVIEW_TREE=145241e8edbb80f09665a1c012caed460675a5d6

ADJUDICATOR_BLOB=2c733a9d54160179eb456a83add7c489701ccc3b
TEST_BLOB=25e1435cdfa59168e21a0a916acada4a1323cf8b
CI_BLOB=6712e9ae837a232b5abfc7d9366abdbba0a4b35e

SOURCE_DRIFT_AFTER_R3_REPAIR=false
FOCUSED_TESTS=PASS_29
R3_REPAIR_SOURCE_HEAD_CI=PASS_12_OF_12
PR620_REVIEW_HEAD_CI=PASS_12_OF_12

ADJUDICATION_ARTIFACT_ID=12181787912
ADJUDICATION_ARTIFACT_DIGEST=e79645082567b71a63046c4857a91a2f8c13982e492a4fccd43a5d317b519725

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
SOURCE_MUTATION=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~

R4 independently rebound the exact R3 repair source, tests, workflow, design authority, production authority and current PR head. The four commits after source head `4ab28033...` are documentation-only; the adjudicator, tests and CI workflow are unchanged.

## R3 C1 — CLOSED

Existing recovery-root trust is now revalidated on every recovery-record read and before every recovery-ledger state transition.

The validator requires the root to remain:

~~~text
non-symlink
directory
owned by the executing root identity
mode 0700
~~~

Read-only verify reaches the recovery record only through this validating, non-creating path. A missing root, symlink root or metadata drift fails closed.

The focused recovery-root metadata-drift and symlink regressions pass.

~~~text
R3_C1_RECOVERY_ROOT_TRUST_REVALIDATION=CLOSED
~~~

## R3 C2 — CLOSED

Recovery JSON now uses the production-authority strict object parser. Duplicate keys therefore fail parsing before the authorization id, original record hashes, invariant hashes or recovery state can be trusted.

The focused duplicate-key recovery-record regression passes.

~~~text
R3_C2_RECOVERY_RECORD_DUPLICATE_KEY_REJECTION=CLOSED
~~~

## Inspect-to-claim hardening — CLOSED

The helper now acquires the production run lock after read-only inspect, reloads the run and F3 records, and rechecks both complete frozen SHA-256 values immediately before recovery-ledger creation.

A post-inspect record drift therefore stops before the recovery root is created and before the one-shot recovery authorization is durably consumed.

The focused race regression passes.

~~~text
INSPECT_TO_CLAIM_HASH_RECHECK=CLOSED
~~~

## Full focused re-review

R4 also rechecked the previously closed source contracts:

- the normal production authority UNKNOWN-run approval guard remains unchanged;
- no F3 replay, new production-run approval, product service start, reboot, package install or board-access path was introduced;
- historical run/source/release/target bindings remain exact;
- HOST_BASELINE remains exact and F3 remains bound to its exact plan artifact and predecessor;
- F3 production-execution evidence is strict, duplicate-key-free, filename/content bound and fail-closed;
- same-second same-target later-run ordering remains fail-closed;
- the recovery authorization is one-shot, consumed/no-replay and same-authorization-only;
- preserved historical run/phase invariants are rechecked across APPLYING and ADJUDICATED states;
- the only historical classification changes remain F3 `UNKNOWN -> FAILED` and run `failure_class UNKNOWN -> FAILED`, plus the permitted update timestamps;
- runtime/business evidence must remain clean before and after classification;
- independent postexecution read-only verification remains mandatory before the historical UNKNOWN blocker is considered operationally cleared.

No additional source blocker was found.

## Review result

~~~text
KF123_UNKNOWN_RUN_RECOVERY_SOURCE_REVIEW_R4=CLOSED_PASS

R1_A1=CLOSED
R1_A2=CLOSED
R1_A3=CLOSED
R2_B1=CLOSED
R2_B2=CLOSED
R2_B3=CLOSED
R3_C1=CLOSED
R3_C2=CLOSED
INSPECT_TO_CLAIM_HASH_RECHECK=CLOSED

TARGET_READONLY_PREAUTH_READY=true
LIVE_ADJUDICATION_READY=false
POSTEXECUTION_READONLY_VERIFY_REQUIRED=true

NEXT_ONE_GATE=
N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_ARTIFACT_AND_READONLY_PREAUTH_20261019_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~

This review did not access T1 and does not authorize the live UNKNOWN-run adjudication.
