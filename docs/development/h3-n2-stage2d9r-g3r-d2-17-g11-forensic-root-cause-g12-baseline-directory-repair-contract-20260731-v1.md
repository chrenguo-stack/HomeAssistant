# D2-17 G11 forensic root-cause acceptance and G12 repair contract

## Accepted evidence

The G11 R2 read-only forensic export passed without board, USB, serial, esptool,
NVS/Flash, network, Broker, PREPARE, VERIFY or recovery activity. It found the
existing physical runtime, but no `preclaim-baseline` directory, no baseline
partition output, no physical result, no stdout/stderr capture and no claim or
consume marker.

The frozen inherited execution source builds the partition output path under the
supplied baseline work directory and invokes `read_flash` without first creating
that directory. This is the deterministic root cause of the G11 preclaim block:

`BASELINE_OUTPUT_PARENT_DIRECTORY_NOT_CREATED_BEFORE_READ_FLASH`.

The public terminal reported only `ExecutionError` because its outer exception
normalizer retained the inherited exception class rather than the inherited
exception's first string argument.

## G12 repair

A G12 successor must be new material. It must not replay G11, reuse the G11
authorization, modify the G11 runtime or reuse G11 claim/consume state.

Before invoking the inherited baseline function, the G12 adapter must create the
unique baseline work directory with mode `0700`, fail closed if it already exists,
and verify it is a real directory rather than a symlink. The terminal normalizer
must preserve a non-empty inherited string subcode from `exc.args[0]`; it may use
the exception class only when no such subcode exists.

Host-only tests must prove directory creation, exclusive reuse rejection,
subcode preservation, fallback behavior and zero physical-operation flags.

## Current boundary

This public add-only repair authorizes no private package, authorization creation,
board operation, USB/serial enumeration, esptool, NVS/Flash, network, Broker,
PREPARE, VERIFY, recovery, ACTIVATE or CLEANUP. Ready, merge, release, tag and
deployment remain forbidden.

The next explicit gate is:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G12-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01`.
