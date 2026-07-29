# H3/N2 Stage 2D-9R G3R physical execution overlay binding repair

Decision: `D1-H3N2-STAGE2D9R-G3R-PHYSICAL-EXECUTION-OVERLAY-BINDING-REPAIR-20260729-01`.

## Disposition

Request `-05` is permanently invalid before physical authorization because its declared corrected-baseline overlay cannot be validated by the frozen policy-v1 request-04 wrapper. It was never authorized, claimed, consumed, or executed.

The successor request is `D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-06`.

## Overlay contract

The new execution package preserves every upstream physical implementation file and preserves the immutable and recovery payload TAR bytes exactly. It adds a new contract, wrapper, launcher, overlay binding, overlay manifest, and root checksum inventory.

The wrapper binds:

- request ID `-06`;
- corrected baseline `776517efcac0c6cf03cabe0572b773dedc89e9bb2793ccb0d9f9585ea6fa601f`;
- permanent rejection of `0735d98c7b4e2a698b42d39bdded1dd04f97b9441270e8bc03be347d369c8793`;
- truthful terminal states for requests `-03`, `-04`, and `-05`;
- exact H5 consumed-pass evidence;
- test-partition-only locked recovery with no recovery write-flash and no whole-chip recovery erase.

The launcher requires an explicit mode: `contract-check` or `execute`. `contract-check` performs only local request and authorization validation and cannot claim authorization or access a board. `execute` remains unavailable without a separately created exact physical authorization.

## Tests

CI must use the exact PR #198 Artifact, reconstruct the upstream execution package, preserve immutable/recovery bytes, build two byte-identical successor packages, and run a real shell integration test proving that a valid `-06` authorization contract passes while request `-04` and `-05` authorizations fail without board, USB, serial, esptool, Flash, or network activity.

This decision creates an unauthorized request `-06`; it does not create a physical authorization and does not execute the request.
