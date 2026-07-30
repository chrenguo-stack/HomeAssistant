# D2-17 G05 canonical outer permission-independent invocation repair contract

## Status

Accepted public host-only repair under `D1-H3N2-STAGE2D9R-G3R-D2-17-G05-CANONICAL-OUTER-PERMISSION-INDEPENDENT-INVOKE-REPAIR-20260730-01`.

## Terminal disposition

G05 is permanently retired after `PermissionError` before authorization creation. Its terminal record is bound by
`7c55a1c6f7973bbacab2c6132480060374eee5406703f4a002a9efde5eaebb3a` and the secret-free failure disposition binding is
`93365d68ad0ec7428a2d60642403d300239f6a36516f364768618457d5bc1659`. G05 may not be replayed, modified, repacked or reused.

## Root cause

The frozen canonical outer is a content-verified POSIX shell script with SHA-256
`2083652dfeedb93c71ac589300b155c1102fd6354dbeb31ecd588669a97b7994`. The G05 private package preserved the extracted file mode as `0600`.
The controller called the script path directly with `subprocess.run`. POSIX direct
execution requires an execute bit, so Python raised `PermissionError` before
execution identity freeze or authorization creation.

The script's first line is `#!/bin/sh`; lack of an execute bit does not invalidate
its content. The fault is the invocation method, not the immutable execution payload.

## Repair

A successor controller shall:

1. verify the launcher is a regular non-symlink file;
2. verify its exact content SHA-256 before invocation;
3. verify `/bin/sh` exists and is executable;
4. invoke `["/bin/sh", launcher, *arguments]`;
5. preserve the exact argument vector and environment;
6. never `chmod`, rewrite, copy over, or otherwise mutate the verified package;
7. reject content tampering, symlinks, directories and missing shell interpreters;
8. keep authorization creation, board, USB, serial, esptool, Flash/NVS and network
   operations outside public CI.

Executable mode is not a security binding. Exact launcher content, path type, shell
interpreter availability and argument preservation are the bindings.

## Regression requirements

The test suite must prove that:

- a verified mode-`0600` POSIX script executes successfully through `/bin/sh`;
- the same script's mode is unchanged after execution;
- arguments containing spaces and empty strings are preserved;
- a changed byte is rejected before invocation;
- a symlink is rejected;
- no authorization, marker, board or physical operation is performed.

## Next gate

`D1-H3N2-STAGE2D9R-G3R-D2-17-G06-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260730-01`
