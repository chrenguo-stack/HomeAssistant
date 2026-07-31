# G09 outer PRECLAIM evidence-root binding repair

## Frozen result

The G09 physical decision terminal is bound by `f48c08cba7bbe10f4a769dc838c4fdd6571470c7c93d1b24fa02acf3b820ba85` and reports `BLOCKED_BEFORE_INHERITED_CLAIM`. Authorization remained unclaimed and unconsumed, and every physical-operation flag remained false.

The G09 package and authorization are retired without replay.

## Exact root cause

The public G09 outer driver installed the execution-identity adapter and then called `d2_11.configure_core()` inside `validate_host`. The frozen D2-11 configured core requires prepare, delivery and terminalization evidence roots to have already been bound by `prepare_payload_handoff`.

The exact frozen execution package deterministically raises:

```text
ExecutionError: PREPARE_EVIDENCE_ROOT_NOT_BOUND
```

This occurs before outer board-baseline verification and before inherited claim.

## Repair

The successor outer preclaim validator must not call `configure_core`. It validates:

1. execution identity with the D2-17 contract;
2. authorization with the D2-17 identity-aware contract;
3. private custody metadata;
4. the frozen D2-11 base authorization validator.

The inherited executor remains unchanged and still performs `prepare_payload_handoff` before `configure_core`.

## Safety

This repair is public, add-only and host-only. It does not create private material, claim or consume authorization, enumerate USB, access serial, invoke esptool, read or write NVS, start a Broker, run PREPARE or VERIFY, or perform recovery.

The next explicit gate is:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G10-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01`
