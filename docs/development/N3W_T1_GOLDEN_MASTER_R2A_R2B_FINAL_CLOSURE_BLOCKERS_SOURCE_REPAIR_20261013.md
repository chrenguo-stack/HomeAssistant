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


## 6. Focused closure-review follow-up

The first all-green exact head was reviewed immediately rather than promoted from CI
alone. Three additional fail-closed gaps were found and repaired inside the same
authorized source-repair gate:

1. authorization records now reject extra JSON keys, so the retained ledger cannot
   carry unclassified payload while still being called non-secret provenance;
2. an occupied/corrupt authorization slot is reported fail-closed as no-replay instead
   of being misreported as unconsumed after a partial durable claim;
3. the product namespace whitelist now covers unknown `/etc/n3wfc4*` residue, not only
   the exact `/etc/n3wfc4` path.

These are source-only repairs. R2C remains not entered and no live authorization is
implied.


## 7. Final focused closure review follow-up

The exact head `f9406235bff21a201c0a6bab465423340b8e83bb` reached 27/27 green
CI and was reviewed immediately. Three additional source blockers were found:

- A5: `exact_release_binding=true` was self-asserted because Seal did not require the
  external release-manifest SHA emitted by the Build result;
- A6: release/image/external-file schemas accepted unclassified extra fields and Seal
  did not require `board_access=false`;
- A7: external guard file mode was recorded from the candidate rather than checked
  against the frozen 0755/0644 policy.

This same authorized gate repairs A5-A7 and adds focused regression coverage. A fresh
exact-head CI pass plus one final focused review remain required before source closure.


## 8. Final design-contract review follow-up

After exact head `343112303a5cd14844ffdb66bc38353e2f414dcc` reached 27/27 PASS,
the final design/ADR comparison found two R2B contract gaps:

- A8: the pure Seal record did not include the source HEAD even though the frozen R2
  design requires the Seal record to bind it;
- A9: the reusable Seal audit executed public-release binding before the final
  instance/no-secret audit, while the frozen Seal order requires final no-secret audit
  before public-release binding and capture quiescence.

This same authorized source gate repairs A8-A9. The public-release adapter must supply a
valid 40-hex `source_head`; the audit result and final Seal record carry it. Audit
ordering is now `instance absence → public release binding → capture quiescence →
OS identity`, so the post-neutralization audit follows the frozen final ordering.

R2C remains not entered. Real OS-identity mutation, disk capture, T1 access, board
access, production service start and merge remain forbidden.

## 9. Pre/post Seal public-release continuity

The final closure review found A10: target-identity contract continuity was checked, but source HEAD, release-manifest SHA-256 and image-lock SHA-256 were not independently frozen across identity preparation.

A10 is repaired fail-closed before the Seal record can be written. public_audit_sha256 is not required to remain identical because the Seal authorization ledger may legitimately change after claim.

The R2 source-design authority is aligned with the accepted ledger, external-manifest, schema/mode, audit-order and continuity contracts.
