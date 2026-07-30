# D2-17 G06 nested-launcher permission-independent handoff repair

## Failure boundary

G06 reached the verified canonical outer through `/bin/sh`, but that outer directly executed its inner launcher. Both files were regular, content-verified files with mode `0600`. The inner direct `exec` therefore returned 126 (`Permission denied`) before execution-identity freeze, authorization creation, claim, consume, or any physical operation.

## Accepted repair

A successor must treat the canonical outer and inner launcher as a two-hop verified handoff:

1. resolve the package root without following a package-root symlink;
2. require the canonical outer and inner launcher to be regular non-symlink files;
3. verify both exact content SHA-256 values;
4. reproduce the outer environment contract (`PYTHONDONTWRITEBYTECODE=1`, `GH_D2_17_OUTER_PACKAGE_ROOT`, and the requested delivery profile);
5. invoke the verified inner launcher as `/bin/sh <inner> <arguments>`;
6. preserve argument boundaries, including spaces and empty strings;
7. perform no chmod, rewrite, rename, replacement, or other package mutation.

The frozen outer remains independently verified even though direct execution is bypassed. The inner launcher sets `GH_D2_17_LAUNCHER_PACKAGE_ROOT` and invokes the frozen Python wrapper. Any outer or inner digest drift, symlink substitution, path escape, or shell unavailability fails closed.

## Regression boundary

Tests must reproduce the original 126 failure with both scripts at mode `0600`, then prove the repaired handoff succeeds without changing either mode. Tests must also cover argument fidelity, outer tampering, inner tampering, symlink rejection, and absence of package-mutation primitives.

## Safety

This repair is public and host-only. It does not create G07 private material or authorization and does not enumerate USB, access a board or serial port, run esptool, modify NVS/Flash, start a Broker, or execute PREPARE, VERIFY, recovery, ACTIVATE, or CLEANUP.
