# N3-W R2B Verification-Harness Known-Failure Disposition

Date: 2026-09-04

## Scope

This public-safe document closes the deferred known-failure disposition identified
during Board B R2 runtime-liveness verification. It does not reopen Board B, FC4, or
the completed three-board R2 regression/retest, and it makes no product-source or
runtime change.

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
BOARD_B_R2=FROZEN_PASS
N3W_THREE_BOARD_REGRESSION_RETEST=PASS
PRODUCT_REGRESSION_PROVEN=false
BOARD_B_FIRMWARE_FAILURE_PROVEN=false
MANAGER_PRODUCT_FAILURE_PROVEN=false
BROKER_PRODUCT_FAILURE_PROVEN=false
CURRENT_DISCOVERED_FAILURE_DOMAIN=PHYSICAL_HARNESS
```

Raw Board identities, MQTT identities, credentials, private locators, private paths,
Setup Secret, private keys and raw logs are intentionally excluded.

## Why this disposition is required

During the R2B verification work two composite `PHYSICAL_HARNESS` records were
proposed provisionally before Board B closeout. Their numbers were explicitly not
frozen; final allocation was required to be rechecked against the current central KF
index before repository commit.

By the final R2B closeout, one later Broker-observability issue had legitimately taken
`KF-085`, while the earlier Manager-state/schema oracle issue had not yet received an
explicit central disposition. The central index also had not yet folded in the final
KF-085 addendum.

This document resolves both archive gaps without changing any prior product result.

## Disposition A — original provisional “KF-085” composite

The earlier provisional composite covered several harness assumptions:

- treating a runtime/DynSec object as if one guessed exact-file/container-path form
  were authoritative;
- hard-coded or incomplete mount/path classification;
- over-requiring host-source provenance during read-only validation;
- allowing incomplete/UNKNOWN authority to behave like a negative fact.

This composite does **not** receive a second new KF number because its root causes are
already separated by the final evidence into existing guards:

```text
DB/container/host path-domain confusion        -> KF-045
current-runtime/current-endpoint classification -> KF-071
UNKNOWN/unobserved-fact propagation             -> KF-072
single-file live bind-mount authority/write     -> KF-085
```

The final allocated `KF-085` is therefore retained exactly as already archived in the
R2B incident ledger/addendum:

```text
KF-085
DOMAIN=PHYSICAL_HARNESS
SUBJECT=running Broker single-file bind-mount live authority / writeability oracle
STATUS=RESOLVED
```

No duplicate KF is created for the earlier composite because the central rules require
same-root-cause incidents to be merged rather than mechanically renumbered.

## KF-086 — Manager state authority / schema / public-safe identity oracle

```text
ID=KF-086
DOMAIN=PHYSICAL_HARNESS
STATUS=RESOLVED
```

### Phenomenon

R2B read-only verification repeatedly stopped before product evidence could be
classified because the harness attempted to infer Manager state authority by broad
SQLite enumeration or an incorrect database/schema assumption. In particular, the
harness could require `credential_assignments` from the pairing/registration database,
although the deployed Manager has a separately configured N3-W credential-lifecycle
database. Some intermediate logic also treated recovery of raw private Board identity
as necessary even though the frozen public-safe identity hashes plus unique current
registration/credential bindings were sufficient for the validation purpose.

These failures were harness/oracle failures. They did not prove a malformed Manager
schema, missing product data, Board failure, Broker failure, or firmware regression.

### Root cause

The verifier failed to bind state queries to the **live Manager Settings and the
owner-specific database authority** before checking schema and identity. It conflated
three independent questions:

1. where the current Manager says a database lives;
2. which lifecycle owns a table;
3. how the target Board may be identified safely and uniquely for a read-only audit.

The product uses separate authorities. The runtime configuration exposes the pairing
DB and `GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH` independently, and credential lifecycle
code owns/validates `credential_assignments` independently from registration/pairing
state.

### Resolution / regression guard

Future A/B/C validation must follow this order:

1. **Bind the exact running Manager first.** Resolve state paths from current live
   Settings/environment of that Manager; do not enumerate arbitrary SQLite files and
   promote a candidate by filename heuristics.
2. **Keep database lifecycle authority separate.** Registration/pairing/lease/history
   queries use the configured pairing/registration DB; `credential_assignments` and
   credential-generation state use the configured credential-lifecycle DB. Validate
   each schema against its owning component independently.
3. **Do not require a table in the wrong database.** Absence of
   `credential_assignments` from the pairing DB is not a product/schema failure.
4. **Use the correct path domain.** Running-container read-only SQLite should use the
   exact Manager container authority with URI `mode=ro` and `PRAGMA query_only=ON`, or
   a separately proven unique host/container translation under KF-045.
5. **Prefer public-safe frozen identity authority for public validation.** When the
   gate only needs to prove continuity/uniqueness and frozen SHA-256 values exist,
   compare the live current registration/credential records to those hashes. Do not
   branch into searching for raw private identity merely because an oracle was
   designed around raw literals.
6. **Fail closed on ambiguity, not on an oracle assumption.** Zero/multiple target
   matches, conflicting live Settings, wrong schema ownership, or hash mismatch remain
   `UNKNOWN_NOT_PASS`/FAIL as appropriate; they must not be repaired by widening the
   query or scanning private material.
7. **Keep product and harness classification separate.** A verifier that queried the
   wrong database or demanded unnecessary raw identity proves a harness defect, not a
   Manager/Board product defect.

### Existing guard relationship

KF-086 is distinct from, but composes with:

```text
KF-045  container/host Manager DB path-domain authority
KF-071  current runtime/current endpoint discriminator
KF-072  UNKNOWN propagation / unobserved-fact serialization
KF-049  public-repository identity redaction policy
```

KF-086 owns the additional **schema/lifecycle ownership + public-safe identity oracle**
contract, which is not fully represented by those records individually.

## Product-source evidence relationship

The deployed Manager source independently exposes the credential-lifecycle database
through `GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH`; `credential_lifecycle.py` owns the
`credential_assignments` schema. Existing Manager tests also bind the credential
lifecycle database independently. This disposition does not add a product fix because
the product structure already behaved as designed; the R2B problem was the verifier's
model of that structure.

## Board B closeout relationship

The final Board B public-safe closeout already proved the operational outcome needed
by the corrected oracle:

```text
BOARD_B_PAIRING_STATE=approved
BOARD_B_CREDENTIAL_STATE=active
BOARD_B_ACTIVE_CREDENTIAL_GENERATION=2
BOARD_B_PENDING_CREDENTIAL_GENERATION=NONE
BOARD_B_APPLICATION_KEY_EPOCH=1
BOARD_B_PEER_TRUST_GENERATION=1
BOARD_B_SECURITY_LIFECYCLE_SEPARATION_PRESERVED=true
BOARD_B_RUNTIME_LIVENESS=PASS
R2_BOARD_B_RUNTIME_LIVENESS=PASS
PRODUCT_REGRESSION_PROVEN=false
```

Board identity continuity was archived using public-safe SHA-256 authority; raw
identity is not required in the public closeout.

## Final archive disposition

```text
ORIGINAL_PROVISIONAL_KF085_COMPOSITE=
MERGED_INTO_KF045_KF071_KF072_AND_FINAL_KF085

KF085_FINAL_ALLOCATION=CONFIRMED
KF085_CENTRAL_FOLD_IN_REQUIRED=true

KF086_FINAL_ALLOCATION=CONFIRMED
KF086_DOMAIN=PHYSICAL_HARNESS
KF086_STATUS=RESOLVED

NEW_PRODUCT_FAILURE_COUNT=0
PRODUCT_SOURCE_CHANGE_REQUIRED=false
RUNTIME_MUTATION_REQUIRED=false
BOARD_ACCESS_REQUIRED=false
```

The companion change to `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` makes the central
index the primary authority for both final KF-085 and KF-086.