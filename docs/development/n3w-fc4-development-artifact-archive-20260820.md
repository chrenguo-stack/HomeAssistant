# N3-W FC4 development artifact archive — 2026-08-20

This document closes the public-safe archive gap found before the KF-036 live
recovery boundary. The machine-readable companion is
`archive-manifests/n3w-fc4-archive-audit-20260820.json`.

## Authoritative source

```text
REMOTE_MAIN=3bd3f0736eb387dc76d53f472da59056e05a88e3
REMOTE_MAIN_TREE=b0d6fd40c196ba63f6aedec51a591b51bac68676
CLEAN_SUCCESSOR=933a1a00ef05c919d3809b96edb1c2dd459e0aca
PR=327
CI_SUCCESS=26
CI_SKIPPED=1
CI_FAILURE=0
```

PR #327 archives the KF-034, KF-035, and KF-036 source, tests, deployment gate,
operator documentation, and KNOWN_FAILURES entries. Older diagnostic commits,
the f38 detached worktree, and the old Manager settings worktree are not valid
exact-source bindings.

## Live-boundary chronology

The session included FC4 private-state/TLS/DynSec/runtime materialization,
Manager source rebinding, sequential board work, network diagnosis, and the
source implementation for expired-first-registration recovery. Historical
private evidence from the earlier S1A–S1D and P2B3A–P2B3C boundaries was not
given a complete public hash/size manifest at creation time. This is now a
durable legacy limitation: those chat transcripts and filenames alone are not
acceptance authority and must not be reconstructed or promoted by inference.

The latest authoritative runtime closure is P2B3D. Its public-safe binding is
captured in the companion JSON. It proves an ARM64 Manager image built from
main `3bd3f073`, host-network Manager health, Broker TLS continuity, one MQTT
connection, the expected UDP/HTTP listeners, zero critical log matches, and no
board access or KF-036 recovery during that boundary.

Raw claim and closure evidence remain mode `0600` in the private T1 evidence
root. Only their hashes, purpose, and path classes are public. Their sizes were
not captured before the archive rule became active, so the manifest records
`legacy-not-captured` rather than inventing a value.

## Quarantined board readbacks

Six local firmware/readback files were created with legacy A/B/C filenames.
Later in the session, board identity authority changed to MAC-tail identifiers.
No reliable MAC-tail-to-file binding exists for these six files.

They are therefore:

```text
CLASSIFICATION=PRIVATE_REQUIRED
IDENTITY_BINDING=QUARANTINED_UNBOUND
PUBLIC_RAW_EXPOSURE=false
ACCEPTANCE_AUTHORITY=false
```

Their hashes, sizes, and capture times are retained in the companion JSON so
future work can recognize them without opening or publishing raw firmware.
They must never be relabeled from an A/B/C filename by inference. A future
board readback is authoritative only if the same boundary binds the observed
chip MAC tail, serial/USB identity, flash range, file hash, and capture time.

## Reproducibility and temporary helpers

The ARM64 Python base transport is bound by digest, hash, and size. The FC4
firmware build package is privately retained and hash-bound, but is not bound
to a board identity. Two temporary runtime-edit helpers are hash-recorded but
superseded: their reusable network semantics are represented by KF-034/KF-035
and `tools/n3w_pairing_deployment_gate.py`. They are not deployment authority.

## Recovered terminal-only knowledge

- Host `install -o 999 -g 999` attempted NSS name resolution and failed when
  UID 999 had no passwd entry. Host directories must be created root-owned and
  then assigned with numeric `chown 999:999`; a container UID is not a host
  account name. This is KF-037.
- The final-product simplified pairing endpoint returns
  `gh.pair.simple-health/1`, while the legacy endpoint returns
  `gh.pair.health/1`. A preclaim must select the schema from the deployed
  endpoint composition, not from a generic pairing assumption. This is KF-038
  and now has a direct endpoint regression test.
- Valuable results were left across temporary files, private evidence, and
  conversation state after meaningful boundaries. Repository-level archive
  rules, an AGENTS entry point, and this sanitized manifest now guard that
  failure mode as KF-039.

## Physical authorization boundary

The archive-recovery work does not access T1 or boards and does not claim or
consume the approved KF-036 live authorization. Before live execution, the
executor must rebind authoritative main, exact Manager image, stopped Manager
state, registration and credential database bind mounts, target expired and
unapproved registration state, and absence of credential history.
