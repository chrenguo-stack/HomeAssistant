# N3-W T1 Golden Master R2A/R2B Final Closure Blockers Source Repair（2026-10-13）

TASK=
`N3W_T1_GOLDEN_MASTER_R2A_R2B_FINAL_CLOSURE_BLOCKERS_SOURCE_REPAIR_20261013_01`

## 0. Scope

```text
REPAIR_BASE=ef06c45ad1040a8221b68e1d22ec0abe363d7e42
SOURCE_MUTATION=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
R2C_ENTERED=false
```

This package repairs only the four blockers from the exact-head final closure review.

## 1. A1 source-root symlink authority

Seal public audit now validates the supplied source root before resolving it:

- absolute path required;
- root itself must not be a symlink;
- root must be a directory;
- resolved path must equal the supplied authority.

A source-root alias/symlink therefore fails before release or runtime evidence is trusted.

## 2. A2 positive product whitelist + forbidden inventory

The Seal public audit no longer treats a few absent instance directories as a complete
no-secret proof.

It now combines:

- exact `/opt/HomeAssistant` public tree binding;
- exact external public guard binary/unit hash + mode binding;
- exact three-image ID/platform/rootfs/config binding;
- default-only Docker network state;
- zero product containers/volumes/listeners;
- product firewall inactive;
- activation units absent;
- instance-owned paths absent;
- staging residue absent;
- positive product-owned namespace whitelist.

Any product-owned namespace entry outside the frozen allowlist is STOP.

## 3. A3 Golden Master authorization ledger classification

The durable Golden Master authorization ledger is intentionally retained in the sealed
image as **non-secret no-replay control provenance**.

The release manifest now freezes:

```text
build_authorization_id
authorization_ledger_policy=retained_nonsecret_no_replay_provenance
```

Seal audit requires the exact BUILD authorization record to match release/source/payload
binding, permits only an optional exact SEAL record with the same binding, and rejects
every unknown ledger entry.

The ledger is therefore not unclassified build-host residue and cannot silently grow
unknown state.

## 4. A4 focused fault injection

Added regressions for:

- source-root symlink;
- incomplete public commit cleanup;
- cleanup uncertainty → recovery required;
- Golden Master build wrapper durable one-shot authorization;
- unknown product namespace residue;
- unknown authorization-ledger residue;
- external public-file drift.

Existing tests continue to cover confirmation-before-claim, post-claim identity failure,
target-contract drift, image drift and tree drift.

## 5. Boundary after this repair

```text
R2A_R2B_SOURCE_REPAIR=IMPLEMENTED_CI_PENDING
R2C_TARGET_ARMBIAN_IDENTITY_ADAPTER=NOT_IMPLEMENTED
REAL_SEAL_MUTATION_EXECUTABLE=false
DISK_CAPTURE_READY=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

A fresh exact-head CI pass and focused closure review are still required before R2A/R2B
can be marked CLOSED_SOURCE.
