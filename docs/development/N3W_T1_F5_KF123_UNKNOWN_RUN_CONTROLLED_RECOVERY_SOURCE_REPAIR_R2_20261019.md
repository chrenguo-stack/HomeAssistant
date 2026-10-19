# N3-W / T1 F5 — KF-123 UNKNOWN-run controlled recovery source repair R2

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REPAIR_R2_20261019_01
RESULT=SOURCE_REPAIR_CI_PASS_REVIEW_PENDING

REPAIR_BASE=2b532c040cac9b6643f4223278c5350be111f341
REPAIR_SOURCE_HEAD=2054d870758705c833acee24e9e734856fb43460
REPAIR_SOURCE_TREE=ac1f53ec0940ee9d9ea9d18497a1543cb6ef02a7

ADJUDICATOR_BLOB=6f521ee7ddf988b138ecbb70ec8ecf462928de2c
TEST_BLOB=8e43102ac8362e0c7019217e8ca45c95248c0c3f
SOURCE_DELTA_EXACT_2_FILES=true

FOCUSED_TESTS=PASS_25
PR620_SOURCE_HEAD_CI=PASS_12_OF_12
ADJUDICATION_ARTIFACT_ID=12180511596
ADJUDICATION_ARTIFACT_DIGEST=8ce92913fe9eb588a9ce42f72a603d5df71965ad75f13021ee77671d94dca8bb

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~

## B1 repair — execution-record filename/content binding

The execution-ledger scanner now recomputes every record filename from the same durable key used by the production bootstrap:

~~~text
sha256(run_id + "\n" + phase + "\n" + phase_claim_sha256 + "\n").json
~~~

After schema and field validation, the scanner requires the actual filename to equal the recomputed name exactly. A valid-shaped record stored under an unrelated SHA filename now fails closed.

A focused regression covers this wrong-filename case.

## B2 repair — exact preservation across split-state resume

The recovery record now freezes two additional invariant digests before historical mutation:

~~~text
original_run_invariant_sha256
original_phase_invariant_sha256
~~~

The run invariant excludes only the two fields that the recovery is allowed to change or refresh:

~~~text
failure_class
updated_at
~~~

The F3 phase invariant excludes only:

~~~text
state
updated_at
~~~

All other historical fields remain part of the invariant digest.

Every APPLYING and ADJUDICATED continuation now rechecks these invariant digests. In addition, while the run is still UNKNOWN its complete durable file SHA-256 must still equal the frozen preauthorization run hash, and while F3 is still UNKNOWN its complete durable phase SHA-256 must still equal the frozen preauthorization phase hash.

The helper also rechecks preserved invariants immediately after the phase write and after the run write.

Focused regressions now prove that a preserved run-field drift during the phase-FAILED/run-UNKNOWN split state and a preserved phase-field drift after ADJUDICATED both stop recovery.

## B3 repair — required negative regression coverage

The focused suite now explicitly covers:

- nonterminal run rejection;
- PASS run rejection;
- already-FAILED run rejection when no matching adjudication recovery record exists.

These are in addition to the previous wrong-hash, wrong-confirmation, changed failure code/binding, execution-ledger, product-material, split-state and different-authorization tests.

## Result

The R2 repair delta from the R2 failed-review head is exactly two files: adjudicator source and focused tests. No production authority source, product runtime source, T1 state or board state was modified.

The repaired source passes 25 focused tests. The exact source-head PR workflows pass 12/12, including Public repository safety. The exact adjudication package was rebuilt as artifact ID `12180511596` with digest `8ce92913fe9eb588a9ce42f72a603d5df71965ad75f13021ee77671d94dca8bb`.

The repair is not self-approved. A fresh independent source review is still required before target read-only preauthorization.

~~~text
NEXT_ONE_GATE=
N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REVIEW_R3_20261019_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
