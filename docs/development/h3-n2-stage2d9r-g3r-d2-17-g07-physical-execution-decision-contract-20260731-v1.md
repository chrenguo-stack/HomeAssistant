# D2-17 G07 physical-execution decision contract

`D1-H3N2-STAGE2D9R-G3R-D2-17-G07-PHYSICAL-EXECUTION-20260731-01` authorizes exactly one claim, one consume and one frozen D2-17 physical execution using the existing G07 authorization.

The decision separately binds private source `662406f97a023c4edc71d6bc17841828d0cc7c36` and acceptance source `fa85d0f335f47d60e2b2b1c6d43946246b246fe3`, acceptance Artifact `8767063701`, authorization record `37fa9803c4ce96083f2b58d4b973c8373326c179d609645f35af1ec72076a601`, private-delivery binding `b1b213b82f8e7b3b954fc2c37eeb0e1d0da22d1c4c54731f9014555f32c329d7`, and expiry `2026-07-30T18:19:45.410516Z`.

Before inherited claim, the driver validates the decision-package root manifest, acceptance Artifact contents, G07 private-package root manifest, canonical terminal semantics, target tools, authorization state and expiry, execution identity, and board/serial/baseline.

Both frozen shell hops remain content-bound at mode `0600`. The driver independently verifies the canonical outer and inner launcher, rebuilds the outer environment contract, and invokes the verified inner launcher through `/bin/sh`; it does not chmod or mutate the payload.

After the driver writes or updates the separate physical-decision marker, the no-argument entry point runs a content-bound finalizer that removes the old `marker_sha256`, recomputes the canonical JSON digest over the terminal marker fields, and atomically replaces only that decision marker. It does not modify the inherited authorization marker, authorization record, runtime payload or board state. The driver's original exit code is preserved.

Any drift closes the run. Replay, automatic retry, ACTIVATE, CLEANUP, Ready, merge, release, tag and deployment are forbidden.
