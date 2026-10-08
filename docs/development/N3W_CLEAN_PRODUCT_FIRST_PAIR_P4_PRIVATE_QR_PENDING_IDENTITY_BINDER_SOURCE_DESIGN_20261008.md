# N3-W P4 Real LCD QR ↔ Unique Manager Pending Identity: Private Read-Only Binder Source Design — 2026-10-08

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_IDENTITY_BINDER_SOURCE_PREPARATION_20261008_01
STATUS=SOURCE_CONTRACT_PREPARED_EXECUTOR_NOT_YET_IMPLEMENTED
P3_RESULT=CLOSED_PASS
P4_PREBOOT_HOST_RESULT=CLOSED_PASS
P4_PRIVATE_PAIRING_IPC_PRESTAGE_RESULT=CLOSED_PASS

BOARD_NORMAL_BOOT=false
BOARD_ACCESS=false
T1_MUTATION=false
PENDING_FIRST_PAIR_CREATED=false
SETUP_SECRET_IMPORTED=false
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
STOP=true
```

## 1. Inputs are **two independently frozen authorities**

- **Preboot:** private Mac file `~/N3W_PRIVATE_EVIDENCE/N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_20261008_01/manager_preboot_identity_snapshot.json`; schema `n3w.kf050.runtime-identity-snapshot/1`, SHA256 `81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c`, exactly five sorted SHA256 hardware identities. Reject filename/path drift, symlinks, changed owner/mode, schema/count/hash mismatch.
- **Postboot:** one optically scanned *real product LCD page-5* `GHN3W2` payload (not product UART, log, fake QR or ROM/eFuse digest); a fresh Manager-controlled registration and credential history read-only snapshot from the same unchanged running Manager container, compared against the preboot snapshot.

The ESP32-C6 silicon binding digest `4b004ce3...` proves the board's physical candidate for P3; it is **not** the runtime `ghw-c6-...` hardware identity to be matched against the Manager. No product identity or pairing ID exists in this preboot work.

## 2. Source-derived exact schema / CLI review

All paths below were examined from product source commit `629f096a32e087087ea32d30707dcc3cd6295e5d`:

| Source file | Exact blob SHA | Contract |
| --- | --- | --- |
| `host/greenhouse-manager/src/greenhouse_manager/ops/n3w_pairing_cli.py` | `1dc70189873f4d33f3de1e5bb6524c434d73b5ef` | The single-line `GHN3W2:ghw-c6-<12 hex>:<UUID>:<43-char base64url>` grammar, exactly 32 decoded bytes; `import-payload --payload-stdin` is the eventual Manager-owned intake |
| `host/greenhouse-manager/src/greenhouse_manager/runtime/registration.py` | `230eeb45ce4aa2cf0a084d89eef901676500114d` | `registrations` stores `hardware_id`, `current_pairing_id`, optional `node_id`; pending state is in `pairing_sessions.state`, not `registrations.state`; `pairing_sessions.expires_at` is the deadline |
| `host/greenhouse-manager/src/greenhouse_manager/runtime/credential_lifecycle.py` | `e0499805e8f2d59a41d5b017e7ed35fb849686fd` | `credential_assignments` has `hardware_id`, `pairing_id`, `node_id`, `last_node_id`; all assignment rows including revoked are history |
| `host/greenhouse-manager/src/greenhouse_manager/runtime/replay_registry.py` | `babc2ee6898572cdbc68ba2c32ee90e060548f14` | `n3w_replay_state` is keyed by `node_id` and cannot be queried by a ROM hardware digest |
| `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_pairing_local_ipc.py` | `ca709cbe7d86b70055f88800de2b4d6751fd95ff` | Manager-owned local UDS, not lab file inbox or direct SQL mutation |

The existing frozen P2 identity snapshot is the distinct `hardware_id` union across exactly:
`registrations`, `pairing_sessions`, `registration_events`, `registration_node_history`, `node_id_leases`, `retirement_outbox`, and `credential_assignments`.

## 3. Required binder behavior before a single live first-pair attempt

1. Before physical boot, freeze and verify exact PR/source/artifact/silicon authority, current Manager/Broker container continuity, effective T1-A TLS, UDS security, private baseline snapshot and confirmed 120-second pending TTL. Prepare and **syntax-test all** Mac/remote scripts and synthetic no-secret test cases *before* causing Manager to create a pending transaction.
2. After P4-A/B normal boot and real LCD QR, the operator enters/pastes the **raw optical scan privately without terminal echo** into the Mac process (or an equivalent locally secured capture path). No raw QR or Setup Secret in command line/argv, shell history, stdout/stderr, GitHub, public log, chat or temporary files. Reject oversized, multiple lines, wrong prefix, malformed ID, incorrect base64url secret length. Redact on all exceptions.
3. Query Manager registration and credential DBs with `sqlite3 mode=ro` and `PRAGMA query_only=ON`, resolving current exact paths from the *same* running Manager mount contract; require exact table/column schemas and stable double-read where time permits. Do not open a writable SQLite connection and do not call `import-payload` during identity verification.
4. Derive sorted hashed product-hardware identity union using precisely the seven P2 tables. Require `POSTBOOT_HASH_SET - PREBOOT_HASH_SET` has **one** member, `PREBOOT_HASH_SET - POSTBOOT_HASH_SET` is empty, and the QR-derived `sha256(hardware_id)` equals that one new member. Reject zero, multiple new identities, missing old identities and ambiguous hashes.
5. For the new hardware identity, require exactly one current `registrations` row with `node_id IS NULL`; exactly one linked `pairing_sessions` row with `state='pending'`, matching `current_pairing_id` and matching QR-derived `sha256(pairing_id)`. Require pair session `hardware_id` equality, pending not expired, and a source-agreed minimum safe expiry margin.
6. Search all historical lifecycle tables: no prior node ID history, node ID lease, credential assignment (including revoked), retirement outbox or replay ownership that conflicts with a brand-new identity. `registration_events` generated by *this pending hello* may exist; all must be explainable by the same hardware/pairing transaction, never an older prior credential/identity.
7. Bind the two independent authorities: QR optical production identity and current Manager pending identity. Neither `SILICON_BINDING_SHA256` nor a guessed MAC-derived product ID substitutes for that match. Any ambiguity, concurrent pairing, changed Manager/Broker/TLS authority, missing expiry margin or schema drift is `STOP/INVALID`; do not import.
8. Publish only secret-free `PRODUCT_HARDWARE_ID_SHA256`, `PAIRING_ID_SHA256`, snapshot digest, counts, expiry-window classification and terminal PASS/INVALID/STOP. Retain the raw QR only in protected process memory for the separately authorized import, if operationally possible. A positive binder result must not itself cross the import STOP.

## 4. Separate import boundary

The corresponding eventual importer must be fully source-prepared, statically reviewed and tested without a real secret before product boot, with specific operator consent to Manager-side Setup Secret import independent of physical boot consent. It receives the optically captured payload only in memory and delivers the complete `GHN3W2` payload via `greenhouse-manager-pairing import-payload --payload-stdin` into the exact running Manager-owned `pairing.sock`, never argv or a lab compatibility path. The import result must be checked for `accepted=true` and correct response schema. **Import acceptance is not credential COMMIT.**

The operator STOP between P4-C and P4-D must remain explicit. Pre-authorization and prebuilt tooling are needed to avoid spending the 120-second pending TTL on interactive approvals or downloading new scripts.

## 5. Mandatory source-only test matrix (before physical P4)

| Case | Expected classification |
| --- | --- |
| Well-formed synthetic QR + exactly one synthetic new pending identity; no prior lifecycle history | `BINDER_PASS_NO_IMPORT` |
| Zero, two or more newly discovered hardware identities | `INVALID_UNIQUE_IDENTITY` |
| QR hardware-ID mismatch or QR pairing-ID mismatch | `INVALID_QR_PENDING_BINDING` |
| Existing old identity dropped/changed from baseline set | `INVALID_SNAPSHOT_DRIFT` |
| Pending expired, insufficient expiry margin, approved/rejected status | `INVALID_PENDING_LIFECYCLE` |
| Existing `node_id`, revoked credential, node-ID lease, retirement record or ambiguous replay linkage | `INVALID_PRIOR_HISTORY` |
| Malformed QR, multi-line input, invalid secret, very long input | `INVALID_QR_FORMAT` |
| T1/Manager/Broker container changes, DB path/mount changes, UDS/CA mismatch | `INVALID_RUNTIME_AUTHORITY` |
| Import command triggered during read-only identity check | `BLOCKER_SCOPE_VIOLATION` |
| Failure before Manager-side import authorization/claim | `STOP_NO_MANAGER_MUTATION` |

Tests must create private, synthetic SQLite fixtures locally and prove the read-only check leaves them unchanged. No real scanned QR, private identity values or live production secrets in test fixtures. Ensure main Python module, remote script, optional nested IPC helper and any subprocess scripting all pass local compile/AST checks; the previous P4 prep syntax error is now a mandatory regression gate.

## 6. Next exact boundary

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_IDENTITY_BINDER_SOURCE_REPAIR_AND_TEST_20261008_01
GATE_SCOPE=SOURCE_ONLY_SYNTHETIC_FIXTURES_NO_BOARD_NO_T1_MUTATION
CURRENT_SOURCE_DESIGN=PREPARED
BINDER_SOURCE_IMPLEMENTED=false
BINDER_SYNTHETIC_TESTS=NOT_YET_RUN
PRIVATE_IMPORTER_SOURCE_IMPLEMENTED=false
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
AUTO_P4=false
STOP=true
```

After the exact binder and importer are compiled, source-reviewed and tested, separately verify their live read-only preclaims; only then may the user authorize a bounded first product normal boot. All P4 pairing, COMMIT, interruption and recovery gates remain unexecuted.
