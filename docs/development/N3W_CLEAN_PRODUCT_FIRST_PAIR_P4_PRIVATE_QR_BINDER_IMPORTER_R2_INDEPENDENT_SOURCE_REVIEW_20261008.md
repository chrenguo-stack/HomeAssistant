# N3-W P4 QR Pending Identity Binder + Importer — R2 Independent Source Review (2026-10-08)

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_BINDER_AND_IMPORTER_R2_INDEPENDENT_SOURCE_REVIEW_AND_HOST_ONLY_PREFLIGHT_DESIGN_20261008_01
REVIEW_RESULT=BLOCKERS_FOUND
SOURCE_REVIEW=CLOSED_WITH_FINDINGS
HOST_ONLY_PREFLIGHT_DESIGN=PREPARED_NOT_EXECUTED
RUNTIME_PHYSICAL_ACCEPTANCE=NOT_GRANTED
STOP=true
```

## 1. Exact source authority

```text
REPO=chrenguo-stack/HomeAssistant
PR=522
REVIEW_HEAD=7ba2de68f629e34bf43d6e756824b5f24419b226
PR_STATE=OPEN_DRAFT_UNMERGED
PRODUCT_SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d

BRIDGE_HANDOFF_BLOB=70673b3fbfe4eb822e410c927139bac285dd2bbd
REMOTE_PROJECTION_BLOB=7b3ba146583b61271b41390736b67207c8d4c14e
HOST_READONLY_BLOB=bb54cfdbc867b3a776c951c622573accf2092dae
TEST_BRIDGE_BLOB=843bf0b16cb1d6947bc40cdd378b209f6172723e
TEST_HOST_BLOB=ad818a3b434df099e56dd80d4a40fd7feb184019
PREVIOUS_SYNTHETIC_RESULT=32_PASS
PREVIOUS_SYNTHETIC_RESULT_PROVENANCE=PREVIOUS_LOCAL_SOURCE_PREPARATION
INDEPENDENT_NEW_RUNTIME_TESTS=NOT_RUN
INDEPENDENT_LIVE_T1_TESTS=NOT_RUN
```

Input evidence includes five exact current GitHub files; prior R2 24-case identity core closure, prior 32-case bridge/importer source-only closure, and official Manager pairing CLI, pairing coordinator, pending registry and local IPC source.

**Preserve previous PASS as simulation-only evidence. Do not reinterpret 32 mocked tests as a safe production pairing authorization.**

## 2. Blockers requiring source repair before any live P4-C/P4-D execution

### A1 — Unforgeable provenance and authorization are not enforced (BLOCKER)

`bridge_handoff.py` defines caller-constructible `Binding(...,live_attested=True)` and `ImportPermission(...,separately_authorized=True,operator_continue=True)`. `OneShotImporter.import_once(...,transport=callable)` checks those booleans and hashes, not an execution-scope claim tied to a single fresh SSH Manager report and independently approved operator gate. `bind_qr` accepts a caller-provided dictionary containing three `*_pass=true` flags as proof of live origin. A fabricated dictionary can satisfy this API. The test suite intentionally does so for simulation; that confirms testing capability, not live authority.

**Required:** separate test seams from production path; produce a versioned one-shot operator-side orchestrator that itself performs exact current GitHub/source binding, private baseline verification, SSH host trust and live runtime verification, then issues an internal single-use authorized handoff. Treat any caller-supplied `live_attested`, imported permission booleans, or synthetic transport as untrusted. No import without distinct real human approval and an explicit at-time-of-use STOP.

### A2 — Read-only SSH source contains unused import-capable code (BLOCKER)

`host_readonly.build_remote_program` concatenates the **entire** `bridge_handoff.py`, a baseline assignment, and `remote_projection.py`, then sends the program to T1 via SSH/Python stdin. The full bridge module includes `OneShotImporter`, `ssh_manager_stdin_transport` and `subprocess.run(...docker exec -i...import-payload...)` even when `main_remote` does not call them. This contradicts the stricter source-level no-import-code promise for a read-only preflight.

**Required:** refactor a dedicated, minimal remote **read-only** module containing only SQLite projection and runtime attestation. The AST/static gate must reject executable Manager pairing/import/repair/erase/restart commands and code paths from this module, including inactive branches and callable helpers. No full Mac importer source shall be shipped to T1 in the read-only phase.

### A3 — P2 immutable snapshot is not bound to the host runner (BLOCKER)

`host_readonly.build_remote_program(...baseline: frozenset)` accepts any five strings with length 64, inserts them into SSH code, and does not check the private Mac owner/mode or exact frozen JSON SHA256. `remote_projection.main_remote` checks only shape and count, not the externally frozen artifact hash. A forged five-hash baseline could be accepted by the design without a source-verifiable link to the P2/P4 preboot snapshot.

**Required:** runner must read the **exact** Mac private `manager_preboot_identity_snapshot.json` through the previously source-reviewed owner-only, symlink-rejecting, digest-verified loader, frozen SHA256 `81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c`; never accept arbitrary baseline input for live use. The old five hashes must remain unchanged.

### A4 — Live runtime checks are only mocked; no proven real T1 compatibility (OPEN)

`remote_projection.py` intends to check Manager/Broker start times, container IDs, host network, DB/replay mounts, pairing UDS, 120s TTL and CA/leaf TLS fingerprint. `test_host_readonly.py::test_t1_remote_entry_with_simulated_source` patches both `_assert_runtime` and `project_readonly` (creating the latter when absent), so this path does not exercise live Docker mounts, real CA resolution, real UNIX socket or the actual SSH-combined integration. The earlier P4 private-IPC readiness was from a **different consumed executor**; it cannot substitute for verification of this new remote source.

**Required:** before first product boot, pass a separately authorized host-only **read-only** T1 preflight for the exact new instrument and its pinned runtime contract. Missing env defaults, container changes, shadow mounts, TLS mismatch, replay schema mismatch or uncertain persistence are STOP, not reasons to modify T1 automatically.

### A5 — Duplicated identity projection and post-check race (OPEN)

The new `bridge_handoff._project_once` duplicates the earlier, separately tested `validator.py` seven-table checks. They are not shared code paths; the remote script checks replay only as a table read, while source-only validator uses a different record comparison. Double-reading can catch a subset of changes **during** reads; it cannot stop a Manager session changing **after** the projection was produced. The isolated import routine allows a margin as low as one second, whereas source-only QR binder uses provisional 60s. This requires a consistent source-approved expiry policy before live use.

**Required:** converge identity semantics and negative regression tests, enforce authoritative time/margin at the last possible read-only check, and require Manager's own transaction state check at the import boundary. Do not assume an accepted secret proves credential COMMIT or KF-050 recovery.

### A6 — Production end-to-end STOP and secret handling are not yet demonstrated (OPEN)

`capture_private_qr` disables TTY echo and avoids writing the scan to a file, which is a positive source property. `ssh_manager_stdin_transport` sends the raw payload as process stdin rather than argv, also positive. But the fields `operator_continue`, `separately_authorized` are not integrated with a durable authorization claim, and `OneShotImporter._consumed` lives only in one Python object; a new object creates a new one-shot budget. The code is not yet a complete, audited field procedure for a 120-second pending TTL. A real unknown-response timeout must STOP instead of starting a new Python object/attempt.

**Required:** exact non-replayable gate ledger, no automatic retry even on timeout, local no-echo optical intake, sanitization under all failures, separate boot and secret-import authorizations, and deterministic short-run stopping points. Mac Terminal must not pass QR/secret as argv, shell history or GitHub text. Never substitute ROM silicon SHA for the runtime product `hardware_id`.

## 3. Positive source findings retained

- `n3w_simple_pairing_client.cpp` generates the real `GHN3W2:hardware_id:pairing_id:setup_secret` payload. The LCD's page-5 N3-W QR and Wi-Fi provisioning QR are separate values shown conditionally.
- Manager's official CLI supports `greenhouse-manager-pairing import-payload --payload-stdin`; UDS request/response schema is `gh.pair.setup-secret-import-result/1`.
- `n3w_simplified_pairing.py` checks Manager registry `record.pairing_id` and `RegistrationState.PENDING` before importing the secret. This is a useful Manager-side protection, **not** a demonstrated end-to-end race-free physical acceptance.
- Private TTY echo-off and secret-free hashed projection direction are reasonable; only their integration/provenance remains open.
- Prior P3 and P4 live host-readiness closures remain valid and are not reopened by these source-only tool blockers.

## 4. Review decision

```text
A1_UNFORGEABLE_AUTHORIZATION=BLOCKER_OPEN
A2_READONLY_SOURCE_SEPARATION=BLOCKER_OPEN
A3_IMMUTABLE_PREBOOT_SNAPSHOT=BLOCKER_OPEN
A4_NEW_T1_RUNTIME_COMPATIBILITY=OPEN_NOT_RUN
A5_IDENTITY_AND_TIME_BUDGET_CONVERGENCE=OPEN
A6_ONE_SHOT_OPERATOR_STOP=OPEN

R2_INDEPENDENT_REVIEW_RESULT=BLOCKERS_FOUND
R2_SOURCE_APPROVAL_FOR_PHYSICAL_BOOT=false
P4_HOST_ONLY_PREFLIGHT_DESIGN=PREPARED_NOT_EXECUTED
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED=false
AUTO_P4=false
BOARD_ACCESS=false
T1_ACCESS=false
SETUP_SECRET_IMPORTED=false
PR_MERGE=false
STOP=true
```

Next source gate is `N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_BINDER_IMPORTER_R3_SOURCE_REPAIR_AND_SYNTHETIC_REGRESSION_20261008_01`. Do not issue a runnable host-only executor or request P4 physical boot authorization until the three blockers close in source review and the host-only design is finalized.
