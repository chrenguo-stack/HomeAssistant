# N3-W P4 Private QR / Pinned T1 Read-Only Bridge / Separately Authorized Manager Importer — Source Preparation Closure (2026-10-08)

```text
GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_BINDER_LIVE_READONLY_BRIDGE_AND_IMPORTER_SOURCE_PREPARATION_20261008_01
RESULT=SOURCE_PREPARED_SYNTHETIC_PASS
PHYSICAL_GATE=NOT_AUTHORIZED
LIVE_T1_GATE=NOT_EXECUTED
SETUP_SECRET_IMPORT=NOT_EXECUTED
P3_CLEAN_BOARD_NORMAL_BOOT=NOT_STARTED
STOP=true
```

## 1. Entry authority and prior state

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_REQUIRED_STATE=OPEN_DRAFT_UNMERGED
SOURCE_START_HEAD=ddf481107f5f76e9c89d5f4adf4a9c25846acce6
EXACT_PRODUCT_SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d

P3_EXACT_FOUR_REGION_WRITE_READBACK=CLOSED_PASS
P4_PREBOOT_MANAGER_BROKER_CONTINUITY=CLOSED_PASS
P4_PRIVATE_PAIRING_CLI_SOCKET_READONLY_PRESTAGE=CLOSED_PASS
P4_QR_PENDING_BINDER_R2_SOURCE_REPAIR_AND_TEST=SOURCE_ONLY_CLOSED_PASS

MANAGER_PREBOOT_IDENTITY_COUNT=5
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c
LIVE_PRESTAGE_MANAGER_PENDING_TTL_S=120
CURRENT_BOARD_STATE=EXACT_FIRMWARE_FOUR_REGION_VERIFIED_NO_PRODUCT_NORMAL_BOOT
```

The R2 source-only binder is frozen at `validator.py` blob `3b7dc0d085dcda52fda0334840d75d5f8678bc1b`, 24 synthetic tests PASS. It remains a standalone, no-import validation core; its `runtime_authority_pass` boolean is **not** sufficient by itself as production attestation.

## 2. Source package committed and exact local/GitHub binding

All five files belong to:

`tools/execution_packages/n3w/auto_safe_fallback/p4_private_qr_pending_identity_binder/`

| File | Git blob SHA256-style object ID (Git SHA-1) | Purpose |
| --- | --- | --- |
| `bridge_handoff.py` | `70673b3fbfe4eb822e410c927139bac285dd2bbd` | Private no-echo optical scan; source-derived QR syntax; local seven-table read-only projection; 60-second provisional expiry margin; separate one-shot import authorization and stdin-only transport |
| `remote_projection.py` | `7b3ba146583b61271b41390736b67207c8d4c14e` | Script intended to run on pinned T1 via standard input; rebind fixed Manager/Broker container continuity, exact mounts, pairing UDS, current 120s TTL, broker TLS/CA/leaf, then output sanitized hashed identity/pairing projection |
| `host_readonly.py` | `bb54cfdbc867b3a776c951c622573accf2092dae` | Compose AST-checked inline remote Python program, pin root/private T1 target, strict host-key SSH read-only transport; reject unexpected response schema or missing live TLS/UDS/container proof |
| `test_bridge_handoff.py` | `843bf0b16cb1d6947bc40cdd378b209f6172723e` | Synthetic SQLite and no-secret importer/optical binding failures |
| `test_host_readonly.py` | `ad818a3b434df099e56dd80d4a40fd7feb184019` | Remote code concatenation AST, strict target/SSH boundary and mocked Manager runtime/TLS response |

Exact Git blob SHAs were independently obtained from tested local files and verified by reading the committed files back from PR #522. Test fixtures are entirely synthetic; no actual product identities or secrets were written to GitHub.

## 3. Source-only local test evidence

```text
LOCAL_PYTHON_COMPILE=PASS
LOCAL_AST_BRIDGE_REMOTE_ASSEMBLY=PASS
SOURCE_AND_TEST_GITHUB_BLOB_MATCH=5_OF_5
SYNTHETIC_TEST_COUNT=32
SYNTHETIC_TEST_PASS=32
SYNTHETIC_TEST_FAIL=0
SYNTHETIC_TEST_EXECUTION_ENV=ISOLATED_LOCAL_CONTAINER
GITHUB_ACTIONS_CI_RESULT=NOT_CLAIMED
T1_REAL_EXECUTION=NONE
BOARD_ACCESS=NONE
MANAGER_DB_WRITE=NONE
SETUP_SECRET_CAPTURE=NONE
SETUP_SECRET_IMPORT=NONE
```

Negative tests check unavailable/changed/historical identities, expired or mismatched pairing ID, changed pairing state, revoked credential history, stale projection, incorrect T1 identity, missing TLS attestation, missing separate import authorization, replay of a consumed import action, response schema rejection, and Setup Secret exclusion from process argv. Synthetic database hash equality checked no mutation. The mock importer deliberately simulates Manager import responses: `import_accepted=true` is *not* proof of real Manager COMMIT.

## 4. Exact no-secret bridge and conditional import flow

The intended future P4-C path, **not executed in this gate**, is:

1. Mac reads the private original five-identity snapshot (owner-only mode 0600) and verifies its exact frozen digest; this must be wired into the final orchestrator, not replaced by a caller-provided preboot hash set.
2. The operator optically scans the real LCD page-5 `GHN3W2` barcode into Mac TTY, with terminal echo off; raw optical payload stays in process memory and must not reach argv, logs, GitHub or terminal output.
3. Mac sends an AST-checked remote **code + five hashed preboot IDs only** to one strictly SSH-pinned T1. The full QR/Setup Secret does not cross to T1 in this read-only phase.
4. The remote code checks the same Manager/Broker container IDs/start times, host network, broker service identity, matching DB mount paths, Manager pairing UDS mode, effective 120-second pending TTL, TLS CA certificate and TLS leaf certificate. It opens configured SQLite files only `mode=ro` with `PRAGMA query_only=ON`. It reports hashed new hardware and pairing IDs, expiry, the original five hash set and a read timestamp.
5. Mac compares that projection with the private actual LCD scan. An accepted **live-attested** view must be under 10 seconds old, match exactly one new pending transaction, and satisfy a provisional minimum 60 seconds remaining. Synthetic-only identity matching is deliberately **not sufficient to import**.
6. P4-D is a **separate operator authorization and separate continuation**. A bounded one-shot importer, only after binding and authorization, sends the complete optically scanned payload by stdin over SSH to `docker exec -i greenhouse-manager greenhouse-manager-pairing import-payload --payload-stdin` inside the pinned running Manager container. No Setup Secret is passed as shell argv or logged. The importer will not retry after any attempt, and accepts only the published `gh.pair.setup-secret-import-result/1` result schema.
7. An `accepted` import result proves only intake; later Manager COMMIT, zero canonical telemetry window and KF-050 single controlled interruption require separate evidence and authorization.

## 5. Important remaining blockers

```text
NO_LIVE_T1_READONLY_REBIND_YET=true
NO_REAL_OPTICAL_LCD_SCAN_YET=true
NO_REAL_MANAGER_PENDING_RECORD_YET=true
NO_MANAGER_IMPORT_YET=true
NO_FIRST_PRODUCT_BOOT_YET=true

OPERATOR_MAC_END_TO_END_ONE_SHOT_ORCHESTRATOR=NOT_YET_IMPLEMENTED
PINNED_SSH_PLUS_MANAGER_DB_LIVE_ACCEPTANCE=NOT_YET_TESTED
REAL_TLS_CA_AND_LEAF_PROBE=NOT_YET_RUN
AUTHORITATIVE_P4_C_TO_P4_D_PERMISSION_HANDOFF=NOT_YET_VALIDATED
RECHECK_AT_MANAGER_ATOMIC_IMPORT_BOUNDARY=REQUIRED
120_SECOND_WINDOW_OPERATOR_PACING=REQUIRES_PREEXECUTION_REVIEW
P4_PRODUCT_BOOT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
AUTO_P4=false
STOP=true
```

The source files are preparation artifacts, **not an approved runnable physical acceptance executor**. In particular, the pure source package exposes import primitives but no authorized field-side orchestrator. A caller-supplied boolean or forged projection is not an independent Manager attestation; any final orchestrator must bind exact SSH, pinned runtime, private snapshot, read timestamp and operator approval together. Python strings cannot guarantee forensic memory zeroization; the private optical scan process should remain bounded and short-lived.

Double-reading read-only SQLite records reduces, but cannot remove, the time-of-check/time-of-use race: the Manager's own atomic transaction check is mandatory during final import. The 60-second remaining-time and 10-second projection-age source policies are provisional, not live-approved. Real T1 read-only validation might STOP if TLS file path/fingerprint format or runtime changed; do not repair host state to satisfy a test without separate authority.

## 6. Next gate

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_BINDER_AND_IMPORTER_R2_INDEPENDENT_SOURCE_REVIEW_AND_HOST_ONLY_PREFLIGHT_DESIGN_20261008_01
NEXT_SCOPE=INDEPENDENT_SOURCE_REVIEW_PLUS_PREPARE_VERSIONED_READONLY_HOST_PREFLIGHT_NO_BOARD
BOARD_ACCESS=false
T1_MUTATION=false
IMPORT_EXECUTED=false
FIRST_NORMAL_BOOT=false
MERGE=false
STOP=true
```

Before any real first normal boot, review source safety and write/version a single-use, fail-closed Mac orchestrator that validates the preboot snapshot, makes a fresh SSH-bound Manager read-only check, privately captures the QR, validates pending uniqueness and time budget, requires a separately authorized import gate, and stops before the final Manager COMMIT observation. No previous P4 authorization is reusable for first boot or Setup Secret import.
