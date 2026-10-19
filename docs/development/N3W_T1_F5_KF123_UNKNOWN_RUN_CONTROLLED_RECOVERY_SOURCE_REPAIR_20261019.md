# N3-W / T1 F5 — KF-123 UNKNOWN-run controlled recovery source repair

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REPAIR_20261019_01
RESULT=SOURCE_REPAIR_CI_PASS_REVIEW_PENDING

REPAIR_BASE=479cb6ca26111d14346f6ab8b6800e7edad97d32
REPAIR_SOURCE_HEAD=abda3c9f2ceb614b8b316ffdb32b5c86cd82678e
REPAIR_SOURCE_TREE=530bfd96231553771b101f3d7044e34cc51cc66d

ADJUDICATOR_BLOB=cebe8cbad039d7565139f735acaa010c3bf34140
TEST_BLOB=5add1a3a9eaec56a4efafe0f3c6ea569630b059d
SOURCE_DELTA_EXACT_2_FILES=true

FOCUSED_TESTS=PASS_19
PR620_SOURCE_HEAD_CI=PASS_12_OF_12
ADJUDICATION_ARTIFACT_ID=12172839778
ADJUDICATION_ARTIFACT_DIGEST=3d8691be96f6db449c79802cbd600ba4dc74beddae4b9f1808a8614c923d1ffc

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~

## A1 repair — F3 execution-ledger zero proof

The adjudicator now validates the production execution ledger as evidence instead of merely scanning JSON objects.

It now fails closed unless the ledger root is an owned 0700 directory, every entry is a regular 0600 single-link SHA-named JSON file, duplicate JSON keys are rejected, every record has the exact production execution schema and field set, hash-shaped fields are valid, state/result semantics are valid, and consumed/no-replay is preserved.

Only after all records validate does the helper count records for the historical run. Malformed, schema-invalid, duplicate-key, metadata-drifted or ambiguous records can no longer be silently treated as "zero".

Focused tests cover valid historical execution presence, invalid schema, duplicate keys and ledger metadata drift.

## A2 repair — exact historical phase-chain binding

The HOST_BASELINE proof now additionally requires the exact plan-bound HOST_BASELINE artifact SHA-256 and a null predecessor.

The F3 UNKNOWN/FAILED proofs now additionally require the exact plan-bound F3 artifact SHA-256 and the exact durable HOST_BASELINE phase-record SHA-256 as predecessor.

The existing authority loader still validates the phase record field set and binding_sha256, so the recovery helper now re-proves both the record integrity and the original phase chain.

Focused tests cover HOST_BASELINE artifact drift, F3 artifact drift and F3 predecessor drift.

## A3 repair — later-run same-second ambiguity

Later same-target exclusion now fails closed on:

~~~text
other.created_at >= incident.created_at
~~~

A same-target run with the same integer-second created_at is therefore treated as ambiguous and blocks adjudication instead of being accepted as older.

A focused regression proves same-second same-target presence stops the inspector.

## Result

The repair delta from the failed review head is exactly two files: adjudicator source and focused tests. No production authority source, product runtime source, T1 state or board state was modified.

The repaired source passes 19 focused tests and the source-head PR workflows pass 12/12. The exact recovery package was rebuilt and bound to artifact ID `12172839778`, digest `3d8691be96f6db449c79802cbd600ba4dc74beddae4b9f1808a8614c923d1ffc`.

The source repair is not self-approved. A separate source review is required before any target read-only preauthorization.

~~~text
NEXT_ONE_GATE=
N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REVIEW_R2_20261019_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
