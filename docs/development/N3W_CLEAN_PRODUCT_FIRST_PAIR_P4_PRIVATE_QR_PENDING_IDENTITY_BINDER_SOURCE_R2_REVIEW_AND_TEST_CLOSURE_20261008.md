# N3-W P4 QR ↔ Manager Pending Identity Binder — Independent Source Repair and Synthetic Test Closure R2 (2026-10-08)

```text
GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_IDENTITY_BINDER_SOURCE_REPAIR_AND_TEST_20261008_01
STAGE=SOURCE_ONLY_INDEPENDENT_R2_REVIEW
RESULT=SOURCE_ONLY_CLOSED_PASS
BOARD_ACCESS=false
T1_ACCESS=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
SETUP_SECRET_IMPORT=false
PRODUCT_FIRST_NORMAL_BOOT=false
P4_FIRST_BOOT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
AUTO_P4=false
STOP=true
```

## 1. Authority and original baseline

The original implementation and source test closure were present in PR #522 before this R2:
`docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_IDENTITY_BINDER_SOURCE_TEST_CLOSURE_20261008.md`.

```text
PR=522
PR_STATE_REQUIRED=OPEN_DRAFT_UNMERGED
PRE_REVIEW_BRANCH_HEAD=ff1c92b3d2e9923ad9c4477ab12ba648b5b104e6

ORIGINAL_BINDER_BLOB=7d3d67944fb997eb7b9eea96c69a7d224557306e
ORIGINAL_TEST_BLOB=1dbd50bf9a58f6e316b6deda08faa448aa97a980
ORIGINAL_INDEPENDENT_SYNTHETIC_RECHECK=20_PASS
ORIGINAL_SOURCE_AND_TEST_GIT_HASH_RECONSTRUCTION=EXACT_MATCH
```

No live T1 host, board, product QR, Manager DB, private Setup Secret, or operator device identity was involved in this code-only review.

## 2. New independently reproduced gap

The original binder compared the full `hardware_id` union twice, but did not re-read the current pairing session state and lifecycle records after their earlier validation. A deterministic synthetic concurrent update was injected immediately before returning the final hardware union; it changed the single pending session from `pending` to `rejected`, without changing the identity union.

```text
DEFECT_CLASS=STALE_PAIRING_SESSION_AND_LIFECYCLE_READ_WITH_UNCHANGED_IDENTITY_UNION
ORIGINAL_PENDING_CHECK=pending
INJECTED_SESSION_STATE=rejected
ORIGINAL_BINDER_RETURN=BINDER_PASS_NO_IMPORT
SOURCE_REVIEW_RESULT=GAP_CONFIRMED
PRODUCT_FAILURE=false
MANAGER_RUNTIME_FAILURE_NOT_CLAIMED=true
```

A pairing state change, expiry change, credential assignment, or node lease addition can leave the hardware-ID union unchanged, making the original double-union read insufficient.

## 3. Exact repair, limited to local read-only validation

```text
REPAIRED_BINDER=tools/execution_packages/n3w/auto_safe_fallback/p4_private_qr_pending_identity_binder/validator.py
REPAIRED_BINDER_GIT_BLOB=3b7dc0d085dcda52fda0334840d75d5f8678bc1b

REPAIRED_TEST=tools/execution_packages/n3w/auto_safe_fallback/p4_private_qr_pending_identity_binder/test_validator.py
REPAIRED_TEST_GIT_BLOB=4f626fbacfd4a64e36d46e5e396a610df64526ee

REPAIR=FIRST_AND_SECOND_EXACT_PAIRING_AND_LIFECYCLE_READ
SECONDARY_CHECK=REJECT_IF_CRITICAL_ROWS_CHANGED_BETWEEN_READS
NEW_FAILURE_CODE=INVALID_BINDING_STATE_DRIFT
SECRET_IMPORT_CODE_ADDED=false
NETWORK_ACCESS_CODE_ADDED=false
MANAGER_DB_WRITE_CODE_ADDED=false
BOARD_ACCESS_CODE_ADDED=false
```

The binder now snapshots the current hardware's `registrations`, `pairing_sessions`, `registration_events`, `registration_node_history`, `node_id_leases`, `retirement_outbox` and `credential_assignments` selected nonsecret state. If any selected relevant row differs on the second read, it refuses a `BINDER_PASS_NO_IMPORT` result. It retains the original seven-table hashed identity union and the source-derived `hello_created` pending-transaction contract.

The first GitHub patch attempt briefly contained a source-only Python formatting error; it was corrected **before** the final test/version binding. The final Git blob SHA above is exact-matched to the independently compiled and tested local Python file. No code from the transient commit was deployed or run on T1 or board.

## 4. Synthetic test result and evidence

```text
LOCAL_PY_COMPILE=PASS
LOCAL_AST_AND_SCOPE_CHECK=PASS
REPAIRED_TEST_COUNT=24
REPAIRED_TEST_PASS=24
REPAIRED_TEST_FAIL=0
SOURCE_LOCAL_GIT_HASH_EQUALS_GITHUB_BLOB=true
TEST_LOCAL_GIT_HASH_EQUALS_GITHUB_BLOB=true

NEW_TEST_1=CONCURRENT_PAIRING_SESSION_REJECTED_FAIL_CLOSED
NEW_TEST_2=CONCURRENT_PAIRING_EXPIRY_SHRINK_FAIL_CLOSED
NEW_TEST_3=CONCURRENT_CREDENTIAL_ASSIGNMENT_FAIL_CLOSED
NEW_TEST_4=CONCURRENT_NODE_ID_LEASE_FAIL_CLOSED

SQLITE_READONLY_MODE=mode=ro
SQLITE_QUERY_ONLY=true
STATIC_NETWORK_IMPORT=false
STATIC_SUBPROCESS_IMPORT=false
STATIC_SETUP_SECRET_IMPORT=false
```

The original twenty tests still pass, and four new synthetic concurrency cases pass. A separate AST/source-scope inspection confirmed the validator contains no network or subprocess imports and does not invoke the Manager secret importer. This is local, synthetic verification **only**; no live Manager acceptance, secret intake, firmware first boot, physical QR or GitHub CI execution is implied.

## 5. Residual timing and provenance constraints

The new second read makes state changes *during these selected reads* detectable, but cannot prevent a race **after** validation returns. A future, separately authorized Manager-owned `greenhouse-manager-pairing import-payload --payload-stdin` step must revalidate that the exact pending transaction still exists and is valid at its own atomic import boundary. There is no end-to-end TOCTOU elimination in this standalone read-only core.

The `runtime_authority_pass` argument is an explicit synthetic-fixture hook, not trustworthy evidence of a live Manager, correct T1 DB mounts or expected T1/Broker/Manager continuity. Do not expose this function directly as a physical pairing gate without an exact-source runtime-bound read-only bridge. The current core never obtains a raw optical QR itself, and does not preserve or import a secret. The 60-second default minimum remaining lifetime is a provisional *source test* policy, not a field-approved safe transaction budget.

## 6. Project boundary / next one gate

```text
SOURCE_ONLY_GATE=CLOSED_PASS
LIVE_P4_C_BINDER_READY=false
P4_PRIVATE_QR_CAPTURE_READY=false
P4_T1_RUNTIME_BOUND_READONLY_BRIDGE_READY=false
P4_ONE_SHOT_MANAGER_STDIN_IMPORTER_READY=false
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
PRODUCT_FIRST_NORMAL_BOOT_EXECUTED=false
P4_PRIVATE_QR_SCANNED=false
P4_SETUP_SECRET_IMPORTED=false

NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_BINDER_LIVE_READONLY_BRIDGE_AND_IMPORTER_SOURCE_PREPARATION_20261008_01
NEXT_GATE_SCOPE=SOURCE_ONLY_NEW_TOOLS_AND_SYNTHETIC_FIXTURES
STOP=true
```

The current clean product board remains post-P3 written/readback-verified without a normal boot. Do not attempt a new pairing transaction, image write, chip erase, Manager restart or secret handoff under this source-only closure.
