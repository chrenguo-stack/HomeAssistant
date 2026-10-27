# N3-W scan-triggered first registration — pre-R2C R1/R2A/R2B frozen-design alignment review

Date: 2026-10-27

## 1. Task and boundary

This document records the independent frozen-design alignment review performed after PR #683 merged and before any R2C implementation begins.

Review task:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_PRE_R2C_R1_R2A_R2B_FROZEN_DESIGN_ALIGNMENT_REVIEW_20261027_01`

Current product/source authority at review start:

- main: `4f21695cf7e17465f91a6a881adf3888dd9cfc61`
- PR #679 frozen design head: `81dbf9de789232df7dadf21f4bd37bb5c9fc67d5`
- PR #680 R1 merge commit: `f7a5c924242c74b5aa9e7f6cb5f0e96a8d54f30f`
- PR #681 R2A merge commit: `13847caa82c79c662f084dd38e6fc28823495954`
- PR #682 R2B design-precision head: `f9448a99c61085ba09a8b54198421ec208e8dc4c`
- PR #683 R2B merge commit: `4f21695cf7e17465f91a6a881adf3888dd9cfc61`
- PR #683 reviewed/merged tree: `4889ceccfd998af7fe185d5e22353fc71b929592`

This review is source/docs only. No T1 access, board access, live runtime mutation, firmware mutation, flash/NVS operation or R2C source implementation is authorized by this document.

## 2. Review method

The review was performed from the frozen design and current merged source/tests, not from PR comments alone.

Primary design authority:
- ADR-0011 at PR #679 frozen design authority;
- `N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md` at the PR #679 frozen design head;
- the accepted R2B precision delta at PR #682 head.

The review checked:
1. whether R1 implements only the trusted-product-LAN/discovery/bootstrap foundation frozen for R1;
2. whether R2A implements the durable first-registration attempt ledger and preserves its transactional invariants;
3. whether R2B implements the exact three-valued cross-store reconciliation and exact-owned cleanup contract;
4. whether any R2C SYSTEM_PEER_KEY or R3 identity-bound 47112 wiring was entered early;
5. whether a new false-PASS path or source blocker appeared after the bottom-up stack merge.

## 3. R1 result — PASS

R1 remains aligned with the frozen design.

Verified properties:
- trusted product LAN authority is derived from the current NetworkManager `eth0` IPv4 subnet rather than generic RFC1918/private-address classification;
- unavailable, malformed, disconnected, zero-subnet or ambiguous authority fails closed;
- the host atomically publishes non-secret trusted-LAN state and Manager consumes the directory through a read-only directory bind;
- registration ingress guard covers exactly 47110/tcp, 47111/udp and 47112/tcp, admits only the trusted product subnet and has no loopback/private-network fallback;
- 47111 UDP discovery and registration mDNS are constrained by the exact trusted product LAN/interface authority;
- 47110 uses TLS, bounded JSON, strict confirm identity shape and trusted-source admission;
- a valid R1 confirm still returns `first_registration_transaction_not_implemented` and does not create a first-registration transaction;
- R1 registration runtime remains isolated from ordinary Manager application startup;
- no durable first-registration transaction, identity-bound 47112 product window, 1800-second live transaction wiring or R3 product flow was introduced by R1.

Result: **R1_SOURCE_ALIGNMENT=PASS**.

## 4. R2A result — PASS

R2A remains aligned with the frozen durable-ledger contract.

Verified properties:
- `first_registration_attempts` resides in the same RegistrationRegistry SQLite database;
- ledger operations use the same sqlite3 connection and RLock;
- ledger writes participate in an already-open RegistrationRegistry transaction and do not commit early;
- persisted attempt state is secret-free: no Setup Secret, source IP, MQTT password, application-key material or SYSTEM_PEER_KEY is stored;
- canonical pairing ID is permanent replay authority;
- at most one ACTIVE first-registration attempt is permitted;
- a predecessor with unresolved cleanup blocks a successor;
- ownership prestate recording is allowed only after `HELLO_OBSERVED`;
- `BUNDLE_STAGED` requires node binding, DynSec prestate absence, application-key prestate absence, exact initial key epoch and delivery digest;
- `COMMITTED` requires a prior durable `COMMITTING` claim;
- terminal state/reason mapping is exact: expiry -> `expired`; restart invalidation -> `replay_detected`;
- SQL constraints and direct reader validation reject corrupt/contradictory state;
- the staged ownership tuple remains preserved across terminalization and therefore remains available to later R2B reconciliation.

Result: **R2A_SOURCE_ALIGNMENT=PASS**.

## 5. R2B result — PASS

R2B remains aligned with the accepted PR #682 precision contract.

Verified read-only oracles:
- RegistrationRegistry exposes exact-pairing state including current pointer, node binding and lease owner/state;
- CredentialLifecycle reads exact pairing assignments and the classifier treats multiple matches as contradictory;
- application-key reconciliation snapshot is secret-free, validates existing material binding, exposes exact node/epoch state and detects conflicting ACTIVE/GRACE epochs;
- reconciliation can open the key store without running ordinary recovery/schema-repair mutation;
- DynSec inspection uses deterministic plan structure and exact `getClient` / `getRole` evidence rather than name presence alone.

Verified classifier and recovery semantics:
- only `COMMITTED`, `DEFINITELY_NOT_COMMITTED` and `UNKNOWN` classifications exist;
- `COMMITTED` requires prior durable `COMMITTING` plus exact cross-store evidence;
- a consistent-looking store state without `COMMITTING` cannot invent success;
- `UNKNOWN` never authorizes destructive cleanup;
- only `DEFINITELY_NOT_COMMITTED` can create terminal `cleanup_state=REQUIRED`;
- `REQUIRED` is the durable prior-classification receipt and re-entry resumes exact-owned cleanup without re-running classification;
- terminal `FAILED` remains fail closed and cannot auto-promote;
- destructive DynSec/application-key cleanup requires durable prestate absence plus durable stage-completion ownership proof;
- a drifted DynSec target is not deleted;
- application-key cleanup is restartable/idempotent, including the DB-revoked/file-still-present crash window;
- RegistrationRegistry first-registration terminal cleanup is one same-SQLite atomic transition, verifies exact pairing/history/lease ownership and preserves NODE_ID non-reuse;
- restart-before-/hello becomes a durable replay tombstone without inventing a pairing-session row;
- deadline and restart terminal reasons remain exact;
- startup reconciliation fails closed when any terminal FAILED/UNKNOWN condition remains.

Result: **R2B_SOURCE_ALIGNMENT=PASS**.

## 6. Scope boundary check

The merged source has not entered the next implementation layers.

- R2C SYSTEM_PEER_KEY lifecycle implementation: **not entered**.
- R3 identity-bound 47112 product wiring: **not entered**.
- 47110 valid confirm starting a real first-registration transaction: **not entered**.
- normal Manager startup wiring of the full registration runtime: **not entered**.
- node scan/browser/LCD product implementation: **not entered**.

These omissions are intentional stage boundaries, not R1/R2A/R2B defects.

## 7. New blockers / false-PASS review

No new R1/R2A/R2B product-source blocker was found.

No new source false-PASS route was found in the reviewed boundaries.

```text
R1_SOURCE_ALIGNMENT=PASS
R2A_SOURCE_ALIGNMENT=PASS
R2B_SOURCE_ALIGNMENT=PASS
NEW_SOURCE_BLOCKER_COUNT=0
NEW_FALSE_PASS_PATH_COUNT=0
PRODUCT_SOURCE_REPAIR_REQUIRED=false
```

## 8. Repository-authority convergence required before R2C

The implementation is aligned, but repository documentation authority was not yet aligned when this review started.

Two documentation/state drifts were identified:
1. PR #682 remained an open Draft on the historical PR #679 design branch. Its accepted precision delta was implemented by R2B but its exact design file was not yet present in main.
2. `N3W_CURRENT_STATE.md` and `N3W_CURRENT_STATE_INDEX.md` still described PR #681 and PR #683 as unmerged.

This docs-only convergence carries the exact accepted PR #682 design blob into current main and updates current-state authorities. It does not reinterpret or expand the design.

After this docs-only change merges:
- the main design file will contain the accepted PR #682 R2B precision rules;
- current state/index will reflect PR #681 and PR #683 merged status;
- this review becomes the formal pre-R2C source-alignment evidence;
- the historical stacked PR #682 route may be closed as superseded by current-main convergence;
- R2C may then begin from a fresh main rebind, under a separate gate.

## 9. Stop point

This review does not authorize R2C implementation.

```text
PRE_R2C_FROZEN_DESIGN_ALIGNMENT=PASS
PRE_R2C_DOC_AUTHORITY_CONVERGENCE_REQUIRED=true
R2C_ENTRY_READY=false_until_docs_convergence_merges
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
R2C_SOURCE_MUTATION=false
```
