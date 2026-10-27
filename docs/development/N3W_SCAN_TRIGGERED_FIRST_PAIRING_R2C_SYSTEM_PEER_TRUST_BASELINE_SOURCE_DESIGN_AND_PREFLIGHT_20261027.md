# N3-W scan-triggered first registration — R2C SYSTEM_PEER_KEY baseline source design and preflight

Date: 2026-10-27

## 1. Task and boundary

Task:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R2C_SYSTEM_PEER_TRUST_BASELINE_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01`

Fresh source authority:

- main: `44523f32531ebc76f93c02d484170f1d92eba627`
- frozen scan-triggered design: `docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md`
- frozen design blob in main: `92f72d913e5b89281e17be3e4651670b67bd5a9f`
- ADR-0011: scan-triggered first registration
- ADR-0007 / ADR-0008: long-lived peer trust and pairing recovery semantics
- R1 / R2A / R2B pre-R2C alignment review: PASS

This gate is source design / preflight only.

No product-source mutation, T1 access, board access, live runtime mutation, firmware change, flash/NVS action, R3 listener wiring or pending-ACK firmware work is authorized here.

## 2. Frozen R2C requirement

The frozen design requires:

```text
SYSTEM_PEER_TRUST_INITIALIZED_BEFORE_REGISTRATION_READY=true
SYSTEM_PEER_TRUST_MUTATED_BY_REGISTRATION=false
```

Exact semantics:

- SYSTEM_PEER_KEY is T1/system baseline authority, not per-node transaction state;
- product registration-service initialization creates or validates the canonical system peer-trust baseline before registration services become ready;
- first-registration bundle issuance uses existing-only lookup;
- adding/retrying a node cannot create or rotate peer trust;
- missing/corrupt peer trust at bundle issuance fails registration closed;
- first-registration rollback never deletes or rotates peer trust;
- R2A/R2B ledger and reconciliation never persist peer-trust key material.

## 3. Current-source findings

### 3.1 Peer-trust store already has the required stable lifecycle primitives

`SystemPeerTrustStore` already provides:

- `get_or_create(system_id)`: create generation 1 when absent, otherwise return the same credential;
- `get(system_id)`: existing-only lookup;
- `snapshot(system_id)`: secret-free metadata;
- `rotate(system_id)`: explicit security operation only;
- `audit()`: secret-free SQLite health metadata.

The store validates:
- system ID shape;
- 32-byte key material;
- non-zero newly generated key;
- positive generation through the credential contract;
- snapshot timestamp metadata;
- SQLite integrity through `audit()`.

Ordinary `get()` does not rotate.

### 3.2 Current first-registration issuer still mutates peer-trust lifecycle

Current `SimplifiedCredentialBundleIssuer.issue()` calls:

`peer_trust.get_or_create(base.system_id)`

while composing the bundle.

That means the first bundle can create SYSTEM_PEER_KEY as a transaction-side effect. This is the exact R2C gap frozen by section 6.7.

Current `issue_existing()` is conceptually existing-only, but it contains a compatibility fallback that may call `get_or_create()` when the injected store does not expose `get()`. That fallback is incompatible with the new exact lifecycle boundary and must be removed.

### 3.3 Existing credential recovery already has the correct target semantics

Existing credential-recovery tests prove:
- missing peer trust blocks recovery;
- recovery reuses the existing key/generation;
- recovery does not rotate peer trust.

R2C must preserve these semantics exactly.

### 3.4 Current product pairing composition is the correct present-stage readiness boundary

Current dynamic pairing flow constructs `SimplifiedProductPairingComposition` before:
- `pairing_runtime.start()`;
- `pairing_socket.start()`;
- the dynamic pairing window is reported OPEN.

Therefore peer-trust baseline initialization/validation can occur during composition construction, before the registration/pairing listener becomes ready.

This is preferable to initializing peer trust in global Manager/MQTT startup:
- peer-trust failure must fail registration readiness closed;
- it must not unnecessarily stop ordinary Manager MQTT/telemetry service;
- the existing clean product image may legitimately have no peer-trust DB before registration service initialization.

R3 will later reuse the same baseline-initialization primitive before always-on 47110/47111 registration readiness.

## 4. Clean-product / factory boundary

R2C does **not** change the factory/golden clean-state contract.

Before registration-service initialization:

```text
system-peer-trust.sqlite3 may be absent
peer_trust_records = 0
```

This remains valid.

R2C does not require:
- SYSTEM_PEER_KEY in the golden image;
- SYSTEM_PEER_KEY in an exact release artifact;
- SYSTEM_PEER_KEY in manager-state.sqlite3;
- SYSTEM_PEER_KEY in first_registration_attempts;
- T1 firstboot to expose key material;
- changes to clean-product database business-table emptiness.

The key is generated on the target T1 at registration-service product initialization, using the existing cryptographic random source.

## 5. R2C source design

### 5.1 Explicit baseline initialization API

Add one lifecycle-explicit API on `SystemPeerTrustStore`, conceptually:

```python
initialize_baseline(system_id, now=None) -> PeerTrustSnapshot
```

Required behavior:
1. validate `system_id`;
2. create generation 1 only when the canonical record is absent;
3. if present, never modify key/generation/timestamps;
4. validate the exact existing credential;
5. validate secret-free metadata and SQLite health;
6. return secret-free `PeerTrustSnapshot`, not key bytes;
7. never rotate.

The existing `get_or_create()` may remain as a lower-level/backward-compatible primitive, but registration/bundle code must not use it.

### 5.2 Registration-service initialization ordering

In `build_simplified_product_pairing_composition()`, after the private peer-trust database is opened and before any pairing runtime/listener factory can become ready:

```text
open/validate private peer-trust DB
-> initialize_baseline(settings.system_id)
-> obtain/validate secret-free snapshot
-> construct issuer/stager/coordinator
-> construct pairing runtime
-> later worker.start() may expose listener
```

If baseline initialization/validation fails:
- composition construction fails;
- pairing runtime does not start;
- pairing window never becomes OPEN;
- ordinary Manager MQTT/telemetry service remains outside this failure scope.

If baseline creation succeeds and a later composition/open step fails:
- baseline is **not rolled back**;
- the next attempt reuses the same generation/key;
- this is intentional because peer trust is system baseline, not transaction-owned state.

### 5.3 Existing-only bundle issuance

Change `SimplifiedCredentialBundleIssuer.issue()` to use only:

`peer_trust.get(base.system_id)`

It must not create or rotate.

`issue_existing()` also uses exact `get()`; remove the compatibility fallback to `get_or_create()`.

Consequences:
- missing peer trust during bundle issuance raises/fails closed;
- first-registration retry cannot create peer trust;
- credential recovery retains the same existing-only semantics;
- no bundle path is a peer-trust lifecycle writer.

### 5.4 Rotation remains out of scope

`SystemPeerTrustStore.rotate()` remains unchanged and is not called by:
- first registration;
- retry;
- ordinary repair;
- credential recovery;
- R2B reconciliation;
- rollback.

Rotation remains a separately authorized security operation.

## 6. Expected implementation scope

Expected product-source files:

1. `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_peer_trust_store.py`
2. `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_credentials.py`
3. `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_product_runtime.py`

Expected focused tests:

1. `host/greenhouse-manager/tests/runtime/test_n3w_peer_trust_store.py`
2. `host/greenhouse-manager/tests/runtime/test_n3w_simplified_credentials.py`
3. `host/greenhouse-manager/tests/runtime/test_n3w_credential_recovery_peer_trust_guard.py`
4. `host/greenhouse-manager/tests/runtime/test_n3w_simplified_product_runtime.py`
5. dynamic pairing/final product wiring tests only where required to prove baseline-before-listener ordering.

Not expected in R2C:
- firmware changes;
- R2A ledger schema changes;
- R2B reconciler changes;
- registration.py changes;
- DynSec/application-key changes;
- 47110/47111/47112 product wiring changes;
- first-registration 1800-second deadline work;
- pending-ACK record changes;
- clean-product staging/golden-image semantic changes.

Any such expansion requires a separate design justification.

## 7. Required tests

### A. Baseline creation

Prove:
- absent store/record -> service initialization creates exactly generation 1;
- key is 32 bytes and non-zero through existing store invariants;
- returned initialization result is secret-free;
- reopen sees the same key/generation.

### B. Baseline stability

Prove:
- repeated service initialization does not rotate;
- generation remains unchanged;
- existing record timestamps remain unchanged;
- adding a second node/retrying registration does not mutate peer trust.

### C. Ordering

Instrument product pairing composition so the pairing-runtime factory can prove:
- baseline record already exists before runtime construction;
- baseline therefore exists before `pairing_runtime.start()` / listener readiness.

### D. Fail closed

Prove:
- corrupt peer-trust metadata/key/store causes composition construction to fail;
- runtime factory/listener start is not reached;
- ordinary Manager service need not be terminated by this registration-readiness failure.

### E. Issuer existing-only

Prove:
- `issue()` with missing baseline raises and leaves store count at zero;
- `issue_existing()` with missing baseline raises and leaves store count at zero;
- neither method references/calls `get_or_create()`;
- with initialized baseline, both methods return the same peer-trust generation/key.

### F. Failure after baseline initialization

Prove:
- baseline initialization succeeds;
- later composition/runtime construction fails;
- peer trust remains present;
- next initialization reuses it without rotation.

### G. Recovery regression

Retain existing recovery guarantees:
- missing peer trust is not initialized by recovery;
- existing peer trust is reused unchanged;
- no credential-recovery test observes peer-trust generation/key rotation.

### H. Security/public evidence

Prove:
- no SYSTEM_PEER_KEY bytes enter logs, repr, audit, snapshot, CI output or public diagnostics;
- ledger remains free of SYSTEM_PEER_KEY;
- baseline initializer returns only secret-free metadata.

## 8. R3 handoff contract

R2C does not wire always-on registration services.

R3 must consume the same baseline-initialization contract before it makes 47110/47111 registration readiness true.

Required R3 ordering:

```text
Manager normal runtime alive
-> initialize/validate peer-trust baseline
-> R2B startup reconciliation
-> only if both PASS: registration readiness
-> 47110/47111 available
-> 47112 remains idle-closed
```

A peer-trust baseline failure therefore blocks registration readiness but does not authorize stopping unrelated normal telemetry.

## 9. Preflight decision

No design blocker was found.

The current gap is expected R2C implementation work, not an R1/R2A/R2B regression.

```text
R2C_DESIGN_RESULT=PASS
R2C_DESIGN_BLOCKER_COUNT=0
R2C_IMPLEMENTATION_REQUIRED=true
R2C_IMPLEMENTATION_READY=true

SYSTEM_PEER_TRUST_BASELINE_OWNER=REGISTRATION_SERVICE_INITIALIZATION
SYSTEM_PEER_TRUST_FACTORY_IMAGE_EMBEDDED=false
SYSTEM_PEER_TRUST_CLEAN_BASELINE_MAY_BE_ABSENT=true
SYSTEM_PEER_TRUST_INITIALIZER_RETURNS_SECRET=false
SYSTEM_PEER_TRUST_INITIALIZED_BEFORE_LISTENER_READY=true
FIRST_REGISTRATION_ISSUER_EXISTING_ONLY=true
RECOVERY_ISSUER_EXISTING_ONLY=true
REGISTRATION_ROLLBACK_MUTATES_PEER_TRUST=false
GLOBAL_MANAGER_TELEMETRY_GATED_BY_PEER_TRUST=false

R3_LISTENER_WIRING_IN_R2C=false
FIRMWARE_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
```

## 10. Next gate

After this design/preflight is reviewed and merged, the next source gate is:

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R2C_SYSTEM_PEER_TRUST_BASELINE_SOURCE_IMPLEMENTATION_20261027_01`

That gate may implement only the bounded source/test scope above, then run focused and repository CI before any R3 work.
