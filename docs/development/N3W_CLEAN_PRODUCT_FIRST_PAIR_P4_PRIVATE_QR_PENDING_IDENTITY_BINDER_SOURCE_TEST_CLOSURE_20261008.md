# N3-W P4 Real Optical QR ↔ Unique Pending Identity — Source-Only Binder Verification — 2026-10-08

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_IDENTITY_BINDER_SOURCE_REPAIR_AND_TEST_20261008_01
STATUS=SOURCE_ONLY_TEST_PASS
EXECUTION_SCOPE=SYNTHETIC_LOCAL_ONLY
PRODUCTION_PHYSICAL_ACCEPTANCE=NOT_RUN
P4_FIRST_BOOT_AUTHORIZATION_GRANTED=false
P4_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
STOP=true
```

## 1. Entry authority and frozen state

The exact product source authority is `629f096a32e087087ea32d30707dcc3cd6295e5d`; P3 exact-artifact four-region write/readback, P4 host continuity, and P4 private pairing CLI/socket preflight were each independently `CLOSED_PASS` before source work. The firmware has not booted normally since P3.

```text
P3_RESULT=CLOSED_PASS
P4_HOST_PREBOOT_RESULT=CLOSED_PASS
P4_PRIVATE_IPC_PRESTAGE_RESULT=CLOSED_PASS
FROZEN_PREBOOT_MANAGER_IDENTITY_COUNT=5
FROZEN_PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c
LIVE_MANAGER_PENDING_TTL_S=120
BOARD_STATE=FOUR_REGIONS_WRITTEN_AND_EXACT_READBACK_PASS_NO_PRODUCT_BOOT
```

## 2. Versioned source and exact tests

```text
BINDER_CORE=tools/execution_packages/n3w/auto_safe_fallback/p4_private_qr_pending_identity_binder/validator.py
BINDER_CORE_GIT_BLOB_SHA=7d3d67944fb997eb7b9eea96c69a7d224557306e

TEST_FILE=tools/execution_packages/n3w/auto_safe_fallback/p4_private_qr_pending_identity_binder/test_validator.py
TEST_FILE_GIT_BLOB_SHA=1dbd50bf9a58f6e316b6deda08faa448aa97a980

LOCAL_PY_COMPILE=PASS
LOCAL_PY_AST_PARSE=PASS
SYNTHETIC_TESTS_TOTAL=20
SYNTHETIC_TESTS_PASSED=20
SYNTHETIC_TESTS_FAILED=0
LOCAL_DATABASE_UNCHANGED_CHECK=PASS
STATIC_NO_SUBPROCESS=PASS
STATIC_NO_NETWORK=PASS
STATIC_NO_SECRET_IMPORT=PASS
SQLITE_READONLY_MODE_AND_QUERY_ONLY=PASS
GITHUB_EXACT_BLOB_MATCH_LOCAL_TESTED_FILES=true
```

The developer tested the exact files committed to GitHub using Python `unittest discover`. All 20 local synthetic scenarios passed. Both GitHub readback Git blob hashes match the independently calculated local `git hash-object` hashes after the 20-case final revision. This is **local synthetic evidence**, not GitHub CI, not live-T1 physical verification, and not an authority to begin first-pair transactions.

## 3. Covered correctness and safety

The binder accepts a real `GHN3W2` payload as an in-process string only, validates the frozen Manager CLI grammar and 32-byte base64url Setup Secret shape, and returns only SHA256 hashes of hardware and pairing IDs without printing, storing, or importing the Setup Secret. It checks:

- immutable, private, owner-only preboot snapshot, schema and expected SHA;
- exact identity union using all six registration-history tables and `credential_assignments`;
- exactly one newly appearing hardware identity and zero missing historical identities;
- QR hardware and pairing identifiers binding to a sole new `registrations` + `pairing_sessions` pending transaction;
- `pairing_epoch==1`, `node_id IS NULL`, `hello_created` event without old events;
- no prior node history, leases, retirement rows or credential assignment, including revoked;
- unexpired transaction with minimum remaining-time policy (default 60 seconds for this local test-only core);
- read-only SQLite `mode=ro` and `PRAGMA query_only=ON`; one additional union read catches some concurrent identity drift.

Negative scenarios cover zero/multiple new identities, missing old identities, QR mismatches, expiry/insufficient margin, pending-state changes, old sessions, node ownership, revoked and active credentials, leases, retirements, anomalous/duplicate hello events, malformed/long/multiline QR, missing SQL schema, missing runtime authority and unsafe private snapshot permissions.

**Critical replay qualification:** `n3w_replay_state` is keyed by `node_id`, **not** `hardware_id`. The validator requires the new pending registration has no assigned node ID and no historical node assignment in registration/credential tables. Old replay rows for unrelated existing nodes are permissible. It does not claim that examining a product hardware hash directly can prove absence of a replay record.

## 4. Precise limitation / stop

```text
BINDER_CORE_IMPLEMENTED=true
BINDER_CORE_SYNTHETIC_TESTED=true

LIVE_MANAGER_MOUNT_BOUND_READER_IMPLEMENTED=false
LIVE_T1_READONLY_SNAPSHOT_BRIDGE_IMPLEMENTED=false
PRIVATE_OPTICAL_NO_ECHO_MAC_CAPTURE_IMPLEMENTED=false
PRIVATE_ONE_SHOT_STDIN_ONLY_IMPORTER_IMPLEMENTED=false
SECRET_IMPORT_AUTHORIZATION_GRANTED=false

P4_FIRST_NORMAL_BOOT_EXECUTED=false
PRODUCT_RUNTIME_IDENTITY_VERIFIED=false
P4_PENDING_CREATED=false
SETUP_SECRET_IMPORTED=false
MANAGER_COMMIT=false
KF050_REBOOT_RECOVERY_VERIFIED=false

BINDER_SOURCE_ONLY_RESULT=PASS
P4_PHYSICAL_PRECLAIM_READY=false
AUTO_P4=false
STOP=true
```

The `runtime_authority_pass` boolean is only an API parameter for synthetic tests. It is not a secure attestation and **must not** be accepted as a live runtime identity or Manager provenance substitute. The binder is a verified local core, **not yet a runnable safe P4-C live executor**. Its current expiry margin policy is provisional and needs a source/runtime review before live use. This gate neither accesses the board/T1 nor mutates Manager.

## 5. Exact next gate

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_BINDER_LIVE_READONLY_BRIDGE_AND_IMPORTER_SOURCE_PREPARATION_20261008_01
NEXT_SCOPE=SOURCE_ONLY_DESIGN_IMPLEMENT_AND_SYNTHETIC_TEST
NEXT_AUTHORIZATION=SEPARATE_PHYSICAL_FIRST_BOOT_AND_SETUP_SECRET_IMPORT
BOARD_ACCESS=false
T1_MUTATION=false
SETUP_SECRET_IMPORT=false
MERGE=false
STOP=true
```

Build and test the secured Mac in-memory optical QR intake, fresh matching Manager/Broker/T1 runtime authority, read-only Manager database snapshot bridge, and a separate, operator-gated `greenhouse-manager-pairing import-payload --payload-stdin` one-shot importer before causing a short-lived Manager pending record. No product boot, repair state resets, high-water clearing, or normal provisioning is authorized in this stage.
