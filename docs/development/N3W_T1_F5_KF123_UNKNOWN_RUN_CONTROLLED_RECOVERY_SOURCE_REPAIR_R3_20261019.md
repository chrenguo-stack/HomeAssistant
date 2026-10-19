# N3-W / T1 F5 — KF-123 UNKNOWN-run controlled recovery source repair R3

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REPAIR_R3_20261019_01
RESULT=SOURCE_REPAIR_CI_PASS_REVIEW_PENDING

REPAIR_BASE=7d4b3c118d4d57a729555b925cbd86eefb0b8dd0
REPAIR_SOURCE_HEAD=4ab28033a6153cbe047849c8655d6a0ce06b667a
REPAIR_SOURCE_TREE=dfa57d24f98c6db2cbd719073c894e8898d7fd3e

ADJUDICATOR_BLOB=2c733a9d54160179eb456a83add7c489701ccc3b
TEST_BLOB=25e1435cdfa59168e21a0a916acada4a1323cf8b
SOURCE_DELTA_EXACT_2_FILES=true

FOCUSED_TESTS=PASS_29
PR620_SOURCE_HEAD_CI=PASS_12_OF_12
ADJUDICATION_ARTIFACT_ID=12181787912
ADJUDICATION_ARTIFACT_DIGEST=e79645082567b71a63046c4857a91a2f8c13982e492a4fccd43a5d317b519725

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~

## C1 repair — recovery-root trust is revalidated

The recovery root now has an explicit read-only validator. Any existing recovery root must be:

~~~text
non-symlink
directory
owned by the executing root identity
mode 0700
~~~

Creation and validation are now separate behaviors:

- `_ensure_recovery_root()` creates a missing root only for a new recovery claim, then validates it;
- `_read_recovery()` validates the existing parent root before trusting the authorization-bearing recovery file;
- `_set_recovery_state()` validates the root again before every recovery-ledger state transition;
- `verify_adjudicated_run()` reaches recovery records only through the non-creating read path.

A missing or drifted recovery root is therefore not silently recreated during read-only verify.

Focused regressions cover:

- recovery-root metadata drift before resume;
- a recovery-root symlink before independent verify.

## C2 repair — duplicate recovery JSON keys are rejected

Recovery records now use the production authority strict JSON object hook. Duplicate keys therefore stop parsing before any authorization field, original hash, invariant digest or recovery state can be trusted.

A focused regression rewrites an otherwise valid recovery record with a duplicate `authorization_id` and confirms read-only verify fails closed.

## Non-blocking hardening completed — inspect-to-claim hash recheck

After the read-only inspector returns the authorized run/phase hashes, the helper now acquires the production run exclusive lock, reloads the exact run and F3 phase, and immediately rechecks both complete file SHA-256 values before creating the recovery ledger record.

If either record changed after inspect, the helper stops before recovery-root creation and does not consume the recovery authorization.

A focused regression simulates a post-inspect run-record drift and proves the recovery root remains absent.

## Result

The R3 repair delta from the R3 failed-review head is exactly two files: adjudicator source and focused tests. No production-authority source, product runtime source, T1 state or board state was modified.

The repaired source passes 29 focused tests. Exact source-head PR workflows pass 12/12, including Public repository safety. The exact adjudication package was rebuilt as artifact ID `12181787912` with digest `e79645082567b71a63046c4857a91a2f8c13982e492a4fccd43a5d317b519725`.

The repair is not self-approved. A fresh independent source review is required before target read-only preauthorization.

~~~text
NEXT_ONE_GATE=
N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REVIEW_R4_20261019_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
