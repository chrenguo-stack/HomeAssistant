# N3-W R3 temporary low-battery bypass source repair — 2026-11-03

## Purpose

During USB-powered R3 physical acceptance the production battery ADC path can report a voltage below the normal low-battery threshold and enter low-battery sleep. That makes the registration workflow require repeated manual resets and contaminates timing/evidence.

For the current development/acceptance cycle only, the formal N3-W target overrides the low-battery threshold to a negative value.

```text
TARGET=firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
DEVELOPMENT_BATTERY_LOW_THRESHOLD=-1.00V
BASE_PRODUCTION_BATTERY_LOW_THRESHOLD=3.00V
LOW_BATTERY_PROTECTION_BYPASSED_FOR_R3=true
PRODUCTION_ELIGIBLE=false
```

## Exact reuse of prior physical proof

The target change is not a new implementation. It exactly reproduces the previously proven Board D physical-acceptance target used by PR #663 / #726 / #731.

```text
CURRENT_BYPASS_TARGET_BLOB=6b37be9e3f281b8abcdf4443103ccb65f7920cd2
PR663_BYPASS_TARGET_BLOB=6b37be9e3f281b8abcdf4443103ccb65f7920cd2
BYTE_IDENTICAL=true
```

Only the N3-W target overrides the value. The reusable production base remains:

```text
firmware/esphome_rc/f1_0_rc2/f1_0_rc2.yml
battery_low_threshold="3.00"
```

The battery protection implementation in `packages/sensors.yml` is unchanged.

## Production restoration gate

This bypass is temporary and must be removed before production release.

Required production restoration:

1. remove the `battery_low_threshold: "-1.00"` override from `f1_0_rc2_n3w_target.yml`;
2. restore the regression contract so the formal target cannot contain the bench bypass;
3. prove the base/default threshold is still `3.00V`;
4. compile and package a new exact production firmware artifact;
5. do not reuse any R3 artifact built while the bypass is present.

```text
PRODUCTION_RESTORE_REQUIRED=true
PRODUCTION_RESTORE_DEFAULT=3.00V
R3_BYPASS_ARTIFACT_ALLOWED_FOR_PRODUCTION=false
```

## Physical execution boundary

The ESP32-C6 board already selected for R3 passed read-only USB identity binding:
- exactly one USB target;
- ESP32-C6 revision v0.2;
- 8 MB SPI Flash;
- no Flash/NVS mutation.

Because the previously bound R3 artifact was built before this bypass, it is superseded for the next physical write.

```text
PREVIOUS_R3_ARTIFACT_ID=13118775924
PREVIOUS_R3_ARTIFACT_FOR_NEXT_WRITE=SUPERSEDED
CURRENT_BOARD_REWRITE_REQUIRED=true
FLASH_WRITE_EXECUTED_IN_THIS_SOURCE_GATE=false
NVS_MUTATION=false
T1_MUTATION=false
FIRST_REGISTRATION_STARTED=false
```

A fresh exact artifact from the bypass source head must be bound before any erase/write command is issued.
