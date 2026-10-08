# N3-W P4 QR Binder / Importer — R2 Host-Only Read-Only Preflight Design (2026-10-08)

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_BINDER_AND_IMPORTER_R2_INDEPENDENT_SOURCE_REVIEW_AND_HOST_ONLY_PREFLIGHT_DESIGN_20261008_01
DESIGN_RESULT=PREPARED_NOT_EXECUTED
SOURCE_REVIEW=BLOCKERS_FOUND
HOST_ONLY_EXECUTOR=NOT_AUTHORIZED
BOARD_ACCESS=false
T1_ACCESSED_IN_THIS_GATE=false
MANAGER_OR_BROKER_MUTATION=false
REAL_QR_CAPTURE=false
SETUP_SECRET_IMPORT=false
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
STOP=true
```

## 1. Intent and STOP boundaries

The forthcoming host-only preflight may verify that the **same** T1-A, Manager, Broker, protected pairing IPC, TLS certificate, data mount and original five identities are ready for later P4 physical pairing. **It cannot verify a new pending identity before the board first boots**; no such record should exist yet. The first new pending pairing record must only be created under a separately authorized future P4-A/B product-normal-boot gate.

The previous consumed P4-preboot and P4-private IPC authorizations are evidence, **not reusable execution tickets**. No automatic T1 SSH or physical progression on the strength of this design.

## 2. Stage H0 — Source repair gate (no T1)

```text
REQUIRED_R3_SOURCE_REPAIR=true
A1_AUTHORIZATION_PROVENANCE=CLOSED_REQUIRED
A2_READONLY_IMPORT_CODE_SEPARATION=CLOSED_REQUIRED
A3_PRIVATE_SNAPSHOT_HASH_OWNER_MODE_BINDING=CLOSED_REQUIRED
A4_NEW_SCRIPT_INTEGRATION_TESTS=PASS_REQUIRED
A5_TIME_AND_HISTORY_POLICY_CONVERGENCE=PASS_REQUIRED
A6_IMPORT_REPLAY_AND_OPERATOR_CONTINUATION=PASS_REQUIRED
```

The read-only remote program must be a separate versioned file with no Manager-mutating command, import helper or Setup Secret handling. An exact artifact/source manifest should pin all locally executed files. The Mac orchestrator must verify exact Git SHA and PR OPEN/DRAFT/unmerged before any SSH. Previous R2 code is *not* an approved read-only executor.

## 3. Stage H1 — Mac-local static preflight (no SSH)

1. Verify PR #522/commit, expected source blobs, frozen product artifact and P3 silicon digest, never infer runtime hardware_id from eFuse or MAC.
2. Verify private snapshot is a regular owner-only mode-0600 Mac file, not symlink; exact SHA256 `81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c`; exact schema and five unique sorted SHA256 identities, no private values in public output.
3. Parse/compile Mac runner, remote read-only script, and every nested Python string. Inspect Python AST for forbidden import/call/command tokens and verify no executable secret import, write-mode SQLite connection, replay clear, reset, service restart, flash, pairing creation or shell command interpolation.
4. Verify SSH target binding to the prior authorized T1-A privately and confirm SSH host key from the existing trusted local known-hosts policy. Use `BatchMode=yes`, `StrictHostKeyChecking=yes`; never use permissive known-host replacement. Reject ambiguous target, drift or missing private preflight.
5. Prepare private evidence output directory with owner-only permissions; record only safe metadata, digests and booleans. No raw QR, secret, pairing-ID, raw device identity, host address or container inspect dumps in GitHub/chat/log.

```text
H1_EXPECTED=MAC_SOURCE_AND_PRIVATE_BASELINE_PASS
H1_SIDE_EFFECTS=NONE
H1_ERROR=STOP_BEFORE_SSH
```

## 4. Stage H2 — Individually authorized host-only T1 readonly run

Obtain a **new exact one-shot host-only** authorization before SSH; no P4 physical or Setup Secret import authorization is implied.

Remote read-only scope:

- Recheck current Manager/Broker container IDs, creation/start times, running, restart counters, fixed n3wfc4 broker selector, Manager host network/empty ports and image provenance.
- Recheck private T1-A address and Manager `GH_N3W_PAIRING_ADVERTISED_HOST=auto` without disclosing the address.
- Recheck Manager-owned Unix socket is a socket with exact `0600` permissions and safe parent directory; installed `greenhouse-manager-pairing` command is present, **not invoked**. Effective Manager pending TTL must still equal the authorized current value (observed 120s).
- Recheck broker TLS IPv4 port 8883, CA certificate digest, TLS server hostname and leaf certificate SHA256; verify full live TLS hostname trust and both container continuity identifiers.
- Resolve registration, credential and replay SQLite files through **current** Manager mount mappings with symlink/directory controls. Open only SQLite URI `mode=ro`, require `PRAGMA query_only=ON`; require exact documented schemas. Read identity union twice, then require still **exactly five** unchanged preboot identities. No current newly pending product identity should be created by this gate.
- Reject inconsistent double reads, mount relocation, permission changes, missing tables, unknown CA or network path, container drift, or extra identities. No Manager pairing `hello`, TCP pairing post, API mutation, import-payload, reboot, configuration repair, replay reset or high-water clear.

Output solely:

```text
STAGE=P4_QR_BINDER_IMPORTER_R3_HOST_ONLY_READONLY_PREFLIGHT
SOURCE_PROVENANCE_PASS=<bool>
PRIVATE_PREBOOT_SNAPSHOT_PASS=<bool>
T1_MANAGER_BROKER_CONTINUITY_PASS=<bool>
TLS_CA_LEAF_SNI_REPROBE_PASS=<bool>
PAIRING_UDS_AND_CLI_READINESS_PASS=<bool>
REGISTRATION_CREDENTIAL_REPLAY_READONLY_PASS=<bool>
PREBOOT_IDENTITY_COUNT=5
PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c
MANAGER_RESTART=false
BROKER_RESTART=false
MANAGER_DB_WRITE=false
SETUP_SECRET_IMPORT=false
BOARD_ACCESS=false
P4_FIRST_NORMAL_BOOT_EXECUTED=false
AUTHORIZATION_CLAIMED=<bool>
AUTHORIZATION_CONSUMED=<bool>
AUTO_RETRY=false
STOP=true
```

Capture return code and a safe digest of remote stderr, never raw traceback or records with identity/private values. Unknown runtime failure returns `STOP/INVALID`, not `PASS`. A consumed authorization must not be retried.

## 5. Stage H3 — future physically authorized transaction (out of scope)

Only **after** H2 closure, R3 source repair and a separately bounded P4-first-normal-boot permission may an operator start the clean board. Physical P4-A/B must produce a real page-5 `GHN3W2` QR and the one pending Manager identity. A later separately authorized P4-C optical binder obtains a fresh runtime snapshot and applies exact current time/expiry tests before explicit P4-D secret import permission.

The 120-second Manager pending TTL starts with Manager hello, not at H2 preflight. Avoid prompts, GitHub downloads, coding or manual lengthy checks after pending starts. Validate operator readiness and time margin **before** first physical normal boot. At the distinct P4-C→P4-D STOP, a pre-authorized but unconsumed import permission plus at-time-of-use operator continuation is needed; never automatically cross the STOP.

Manager's own pending transaction check at the exact import step remains required. An import-`accepted=true` response does not prove credential COMMIT, canonical telemetry zero-window or KF-050 physical cold/warm boot criteria.

## 6. R3 source regression matrix prior to host preflight

| Case | Expected |
| --- | --- |
| Caller forges `live_attested=True` or all three projection booleans | Block all import before authenticated runtime path |
| Caller forges separate import booleans / starts a fresh `OneShotImporter` | No second import; require real operator and one-shot durable gate state |
| Remote read-only assembled script contains import call/function, Manager repair/reset, writing SQLite | Static gate FAIL before SSH |
| Preboot hash set syntactically valid but not exact private SHA file | FAIL before SSH |
| Manager/Broker ID, lifecycle, UDS, mount, SNI/CA/leaf drift | STOP without mutation |
| Wrong current host, host key or private address binding | STOP before remote execution |
| Fresh QR identity mismatches unique Manager pending, has old credentials, or expires | STOP before import |
| Snapshot changed mid-read with same hardware set | STOP; do not rely on identity union alone |
| Mock importer accepts payload but no Manager COMMIT | Mark import accepted only, no physical PASS |
| Network timeout/unknown import response | Consume one-shot claim, STOP, no automatic retry |
| Source Python compiles but assembled remote script fails | STOP local AST check before SSH |

All tests must run entirely with synthetic identities and synthetic secrets. No real pairing QR or actual Manager secret in fixtures.

## 7. Final decision

```text
H0_SOURCE_REPAIR=OPEN_BLOCKERS
H1_MAC_STATIC_PREFLIGHT=DESIGNED_NOT_EXECUTED
H2_T1_HOST_ONLY_READONLY=DESIGNED_NOT_AUTHORIZED_NOT_EXECUTED
H3_P4_PHYSICAL_FIRST_BOOT=NOT_AUTHORIZED
IMPORT=NOT_AUTHORIZED

NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_QR_PENDING_BINDER_IMPORTER_R3_SOURCE_REPAIR_AND_SYNTHETIC_REGRESSION_20261008_01
STOP=true
```
