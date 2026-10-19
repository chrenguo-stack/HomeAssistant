# N3-W / T1 F5 — KF-123 UNKNOWN-run controlled recovery source review R2

Date: 2026-10-19

## Scope

~~~text
TASK=N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REVIEW_R2_20261019_01
RESULT=FAIL_CLOSED_BLOCKERS_FOUND

REPAIR_SOURCE_HEAD=abda3c9f2ceb614b8b316ffdb32b5c86cd82678e
REPAIR_SOURCE_TREE=530bfd96231553771b101f3d7044e34cc51cc66d
PR620_REVIEW_HEAD=8a9bdc33941242919c3d9e8f2fa989c607e560fb
PR620_REVIEW_TREE=d9e5f8eefdf8ebad46fe5af5e1a5c9c9b69e460f

FOCUSED_TESTS=PASS_19
PR620_EXACT_HEAD_CI=PASS_12_OF_12

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
SOURCE_MUTATION=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~

The three R1 blockers were independently rechecked against the repaired source and are closed:

- R1 A1 CLOSED: execution-ledger root/file metadata, exact schema/fields and duplicate-key-free JSON are now validated before zero is accepted.
- R1 A2 CLOSED: HOST_BASELINE and F3 are rebound to plan artifact hashes and the exact HOST_BASELINE predecessor record SHA-256.
- R1 A3 CLOSED: same-second same-target runs now fail closed.

## R2 B1 — BLOCKER: execution-record filename/content binding

The production bootstrap keys an execution record by:

~~~text
sha256(run_id + "\n" + phase + "\n" + phase_claim_sha256 + "\n").json
~~~

The repaired scanner currently checks only that the filename has the shape of 64 hex characters plus `.json`. It does not recompute that key from the validated record contents.

A schema-valid record stored under the wrong SHA filename is therefore still accepted as a valid ledger record. For a forensic absence proof, record content and durable ledger key must agree.

Required repair:

- recompute the expected filename from `run_id`, `phase` and `phase_claim_sha256`;
- require an exact filename match;
- add a focused wrong-filename regression.

~~~text
R2_B1_EXECUTION_RECORD_FILENAME_BINDING=BLOCKER
~~~

## R2 B2 — BLOCKER: split-state exact preservation

The design allows only F3 `UNKNOWN -> FAILED`, run `failure_class UNKNOWN -> FAILED`, and the normal update timestamp. Every other historical field must remain unchanged.

The uninterrupted path preserves that contract. The resume path does not prove it exactly. In particular, the phase-FAILED/run-UNKNOWN split state can continue without rechecking that the run record still equals the frozen preauthorization run hash. Semantic checks can also accept drift in otherwise valid preserved fields such as `claimed_at`.

Required repair:

- persist stable invariant digests or equivalent exact preserved-field bindings before mutation;
- on every APPLYING/ADJUDICATED resume state, prove that the phase/run differ from preauthorization only by the permitted classification fields and `updated_at`;
- at minimum, while run.failure_class is still UNKNOWN, require the run record to remain at the frozen original run SHA-256;
- add regressions that alter a preserved historical field in split states and confirm a hard STOP.

~~~text
R2_B2_SPLIT_STATE_EXACT_PRESERVATION=BLOCKER
~~~

## R2 B3 — BLOCKER: required negative regressions missing

The design explicitly requires focused regressions for:

- rejecting a nonterminal or PASS run;
- rejecting an already FAILED run without a matching recovery record.

The source appears to reject these through the exact prestate guard, but the current 19-test focused suite does not contain those required cases.

~~~text
R2_B3_REQUIRED_NEGATIVE_REGRESSION_COVERAGE=BLOCKER
~~~

## Result

~~~text
KF123_UNKNOWN_RUN_RECOVERY_SOURCE_REVIEW_R2=FAIL_CLOSED

R1_A1=CLOSED
R1_A2=CLOSED
R1_A3=CLOSED

R2_B1_EXECUTION_RECORD_FILENAME_BINDING=BLOCKER
R2_B2_SPLIT_STATE_EXACT_PRESERVATION=BLOCKER
R2_B3_REQUIRED_NEGATIVE_REGRESSION_COVERAGE=BLOCKER

TARGET_READONLY_PREAUTH_READY=false
LIVE_ADJUDICATION_READY=false

NEXT_ONE_GATE=
N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REPAIR_R2_20261019_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~

No T1 access, target mutation, board access, merge or new production authorization occurred.
