# D2-17 G04 private-source dual-binding repair contract

Decision: `D1-H3N2-STAGE2D9R-G3R-D2-17-G04-PRIVATE-SOURCE-DUAL-BINDING-REPAIR-20260730-01`

## Retired attempt

The G04 physical attempt is permanently retired after
`TERMINAL_PRIVATE_SOURCE_SHA_DRIFT` before inherited claim.

- authorization created/claimed/consumed: `true/false/false`;
- board, USB, serial, esptool, Flash/NVS, Broker, PREPARE, VERIFY and recovery: not started;
- automatic retry and replay: forbidden;
- G04 private package, authorization, physical package and runtime: may not be reused.

Failure-disposition binding:

`e3d08da72f8ebab41aded95fe215ef030e99151bf9fbaee1af7c7b722525f6fb`

## Root cause

Three different source commits describe three different layers:

1. G04 private-package build source:
   `0691b3c85cf3ee018cd07cf038138cbf4dcd1f34`;
2. secret-free G04 static-check acceptance source:
   `e58b934c7e00125bf7d7c5a75f6ee338dd5dbdd7`;
3. G04 physical-decision source:
   `2acda017ba287c36718fda1031d55acf4101697d`.

The retired driver incorrectly required `terminal.private_source_sha` to equal the
second value. The terminal correctly reports the first value, so the check always
blocked before board access.

## Repaired contract

A successor must validate each layer against its own frozen field:

```text
terminal.private_source_sha == G04_PRIVATE_SOURCE_SHA
acceptance artifact head_sha == G04_ACCEPTANCE_SOURCE_SHA
physical decision package source_sha == G04_PHYSICAL_DECISION_SOURCE_SHA
```

The values must not be substituted for one another merely because all three belong
to the same stacked evidence chain. A mismatch remains fail-closed with a
layer-specific error code.

This public repair creates no private package or authorization and performs no
physical operation. The next private generation is G05 and requires explicit
approval of:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G05-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260730-01`
