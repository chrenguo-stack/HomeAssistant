# N3-W / T1 F5 — KF-123 UNKNOWN-run controlled recovery source review R3

Date: 2026-10-19

## Scope

~~~text
TASK=N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REVIEW_R3_20261019_01
RESULT=FAIL_CLOSED_BLOCKERS_FOUND

R3_REVIEW_BASE=bf30a9fe81217d677ec079821701f37efd5a0889
R2_REPAIR_SOURCE_HEAD=2054d870758705c833acee24e9e734856fb43460
R2_REPAIR_SOURCE_TREE=ac1f53ec0940ee9d9ea9d18497a1543cb6ef02a7
R3_REVIEW_HEAD=bf30a9fe81217d677ec079821701f37efd5a0889
R3_REVIEW_TREE=76698b92b48dc83952081d3e601ba2e03eee2f1b

ADJUDICATOR_BLOB=6f521ee7ddf988b138ecbb70ec8ecf462928de2c
TEST_BLOB=8e43102ac8362e0c7019217e8ca45c95248c0c3f
CI_BLOB=6712e9ae837a232b5abfc7d9366abdbba0a4b35e

SOURCE_DRIFT_AFTER_R2_REPAIR=false
FOCUSED_TESTS=PASS_25
PR620_EXACT_HEAD_CI=PASS_12_OF_12

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
SOURCE_MUTATION=false
MERGE=false
NEW_PRODUCTION_AUTHORIZATION=false
~~~

The R2 repair delta was independently rebound. The exact adjudicator and focused-test blobs at the docs-aligned PR head are unchanged from source head `2054d870758705c833acee24e9e734856fb43460`. The later four commits are docs-only.

## R2 B1 — CLOSED

Execution-record filenames are now recomputed from the same durable key used by the production bootstrap:

~~~text
sha256(run_id + "\n" + phase + "\n" + phase_claim_sha256 + "\n").json
~~~

A valid-shaped record under an unrelated SHA filename fails closed. The dedicated regression passes.

~~~text
R2_B1_EXECUTION_RECORD_FILENAME_BINDING=CLOSED
~~~

## R2 B2 — CLOSED

The recovery record now freezes preserved-field invariant digests for the historical run and F3 phase. APPLYING and ADJUDICATED continuation paths recheck those invariants, while an UNKNOWN run/phase must still match the complete frozen preauthorization record SHA-256.

The R3 review confirms that the invariant sets exclude only the fields explicitly permitted by the design:

~~~text
run: failure_class, updated_at
phase: state, updated_at
~~~

All other durable historical fields remain covered. The new split-state drift regressions pass.

~~~text
R2_B2_SPLIT_STATE_EXACT_PRESERVATION=CLOSED
~~~

## R2 B3 — CLOSED

The focused suite now explicitly rejects:

- nonterminal runs;
- PASS runs;
- already-FAILED runs without a matching recovery record.

~~~text
R2_B3_REQUIRED_NEGATIVE_REGRESSION_COVERAGE=CLOSED
~~~

## R3 C1 — BLOCKER: existing recovery-root trust is not revalidated on resume or verify

The helper validates the recovery root only when creating a new recovery record through `_claim_recovery()` -> `_ensure_recovery_root()`.

When a recovery record already exists, `adjudicate_unknown_run()` goes directly to `_read_recovery(recovery_path)`. The independent `verify_adjudicated_run()` path does the same.

`_read_recovery()` validates the file itself, but it does not validate that the parent recovery root is still:

~~~text
non-symlink
directory
owned by the executing root identity
mode 0700
~~~

This leaves the resume/verify path weaker than the design's "separate durable root-owned recovery ledger" contract. A recovery-root symlink or metadata drift after the initial claim is not rejected before the authorization-bearing record is trusted or rewritten.

Required repair:

- separate "ensure/create recovery root" from "validate existing recovery root";
- on every existing-record read, resume, state transition and postexecution verify, require the recovery root itself to be an exact owned 0700 non-symlink directory;
- do not create a missing root during read-only verify;
- add focused regressions for recovery-root symlink and metadata drift on resume/verify.

~~~text
R3_C1_RECOVERY_ROOT_TRUST_REVALIDATION=BLOCKER
~~~

## R3 C2 — BLOCKER: recovery authorization record does not reject duplicate JSON keys

Production run/phase authority records use strict duplicate-key rejection, and the repaired F3 execution-ledger scanner now does the same.

The recovery record parser still uses ordinary:

~~~text
json.loads(...)
~~~

without a strict object hook.

Because the recovery record carries the one-shot `authorization_id`, original record hashes, preserved-field invariant hashes and terminal recovery state, duplicate-key ambiguity is not acceptable for a fail-closed authorization ledger. A duplicate field collapses to one value before the required-field set is checked.

Required repair:

- parse recovery records with duplicate-key rejection, preferably the same strict object hook used by the production authority;
- treat duplicate-key recovery JSON as invalid;
- add a focused duplicate-key recovery-record regression.

~~~text
R3_C2_RECOVERY_RECORD_DUPLICATE_KEY_REJECTION=BLOCKER
~~~

## Non-blocking hardening note

There is a small inspect-to-claim race window: after the fresh inspector hashes are compared with the authorized expected hashes, the helper reloads run/phase and derives invariant digests for the recovery record without first rechecking those reloaded files against the expected hashes.

The later CLAIMED prestate check still fails closed before APPLYING, so this does not currently permit historical mutation on drift. However, it can consume/create a recovery record whose invariant snapshot came from a drifted intermediate state and make the one-shot recovery unrecoverable without manual intervention.

Recommended hardening in the same repair: immediately recheck the loaded run/phase file hashes against the expected authorized hashes before writing the recovery record.

## Review result

~~~text
KF123_UNKNOWN_RUN_RECOVERY_SOURCE_REVIEW_R3=FAIL_CLOSED

R2_B1=CLOSED
R2_B2=CLOSED
R2_B3=CLOSED

R3_C1_RECOVERY_ROOT_TRUST_REVALIDATION=BLOCKER
R3_C2_RECOVERY_RECORD_DUPLICATE_KEY_REJECTION=BLOCKER

TARGET_READONLY_PREAUTH_READY=false
LIVE_ADJUDICATION_READY=false

NEXT_ONE_GATE=
N3W_T1_F5_KF123_UNKNOWN_RUN_CONTROLLED_RECOVERY_SOURCE_REPAIR_R3_20261019_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~

No T1 access, target mutation, board access, merge or new production authorization occurred.
