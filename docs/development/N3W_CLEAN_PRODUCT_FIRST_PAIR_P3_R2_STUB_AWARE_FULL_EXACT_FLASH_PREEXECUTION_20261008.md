# N3-W Clean Product First-Pair — P3 R2 Stub-Aware Full Exact Flash Preexecution — 2026-10-08

```text
STATUS=PREPARED_NOT_AUTHORIZED
P3_R1_RESULT=STOP_EXECUTOR_DEFECT
P3_R1_AUTHORIZATION_CONSUMED=true
P3_R1_REPLAY=false
P3_R2_AUTHORIZATION_GRANTED=false
```

## Proven R1 executor defect

```text
ARTIFACT_BINDING_PASS=true
BOARD_PRECLAIM_PASS=true
SILICON_BINDING_MATCH=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
FULL_CHIP_ERASE=false
FOUR_REGION_WRITE=false
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false

ROOT_CAUSE=P3_EXECUTOR_GLOBAL_NO_STUB_ON_ERASE_FLASH
ESPTOOL_VERSION=5.3.1
ERASE_FLASH_REQUIRES_STUB=true
PRODUCT_DEFECT=false
BOARD_DEFECT=false
ARTIFACT_DEFECT=false
```

The R1 executor forced `--no-stub` for every esptool command. In esptool
5.3.1, full-chip erase is stub-only. The failure therefore occurs before the
ROM loader can issue a chip erase. R1 did not modify flash through the failed
erase path.

## R2 repair

```text
CURRENT_CLEAN_CANDIDATE_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
P2_REFREEZE_PASS=true
READY_FOR_P3=true

EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p3_full_exact_flash_no_boot_r2/executor.py
EXECUTOR_COMMIT=00e7bceffe43f18b73c4c84849bc8a1554311318
EXECUTOR_BLOB_SHA=6c269d730d5bde72fc0e9a02b1babd408f6bd7da
```

R2 behavior:

```text
PRECLAIM_ROM_NO_STUB=true
PRECLAIM_PARTITION_WINDOW_MUST_BE_BLANK=true

FULL_CHIP_ERASE_USES_STUB=true
ERASE_AFTER_POLICY=no-reset
ERASE_RETURNS_TO_ROM_BOOTLOADER=true

POST_ERASE_PROBE_ROM_NO_STUB=true
WRITE_FLASH_ROM_NO_STUB=true
FINAL_READBACK_ROM_NO_STUB=true

PRODUCT_NORMAL_BOOT=false
RAW_MUTATION_STDOUT_STDERR_PRIVATE_CAPTURE=true
```

The only operation requiring the flasher stub is full-chip erase. esptool
`--after no-reset` exits the stub back to ROM bootloader without starting the
product firmware.

## Successor boundary

A new P3 R2 authorization is required because P3 R1 crossed its mutation claim
boundary and consumed its one-shot authorization.

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_R2_STUB_AWARE_FULL_EXACT_FLASH_20261008_01
P3_R2_AUTHORIZATION_GRANTED=false
AUTO_RETRY=false
AUTO_P4=false
STOP=true
```
