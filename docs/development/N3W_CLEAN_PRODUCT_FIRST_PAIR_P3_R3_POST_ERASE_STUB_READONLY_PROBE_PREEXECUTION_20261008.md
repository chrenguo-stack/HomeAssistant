# N3-W Clean Product First-Pair — P3 R3 Post-Erase Stub Read-Only Probe Preexecution — 2026-10-08

```text
STATUS=PREPARED_NOT_AUTHORIZED
P3_R2_RESULT=STOP_POST_ERASE_ROM_READ_PATH
P3_R2_AUTHORIZATION_CONSUMED=true
P3_R2_REPLAY=false
P3_R3_AUTHORIZATION_GRANTED=false
FLASH_ERASE=false
FLASH_WRITE=false
PRODUCT_NORMAL_BOOT=false
```

## Current board state

```text
CURRENT_CLEAN_CANDIDATE_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
ARTIFACT_BINDING_PASS=true
BOARD_PRECLAIM_PASS=true
PRECLAIM_PARTITION_WINDOW_BLANK=true
FULL_CHIP_ERASE=true
FOUR_REGION_WRITE=false
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
```

The board is now formally classified as erased/unwritten.

## Proven post-erase failure

```text
LAST_COMPLETED_STEP=full_chip_erase
LAST_STARTED_STEP=post_erase_probe
LAST_STARTED_STEP_USES_STUB=false
LAST_STEP_RETURN_CODE=2
POST_ERASE_FAILURE_CLASS=ROM_NO_STUB_SPI_ATTACH_OR_FLASH_ACCESS
USB_RECONNECT_FAILURE=false
```

The ROM/no-stub read reconnected to the same ESP32-C6 and failed while enabling
the default SPI flash mode with a Bad data length result. No write occurred.

## R3 purpose

R3 is a new read-only recovery gate. It must not replay erase and must not write
flash.

```text
STEP_1=ROM_NO_STUB_GET_SECURITY_INFO
STEP_2=REQUIRE_EXPECTED_SILICON_BINDING
STEP_3=STUB_READ_FLASH_0x8000_0x1000
STEP_4=REQUIRE_ALL_FF
STEP_5=STOP
```

The flasher stub is uploaded only to RAM. The flash contents must not be
modified.

## PASS

```text
POST_ERASE_PARTITION_WINDOW_BLANK=true
FLASH_ERASE=false
FLASH_WRITE=false
PRODUCT_NORMAL_BOOT=false
READY_FOR_WRITE_ONLY_SUCCESSOR=true
STOP=true
```

## FAIL

Any silicon mismatch, serial ambiguity, stub upload/read failure, or non-FF byte
is STOP. No automatic retry and no erase.

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_R3_POST_ERASE_STUB_READONLY_PROBE_20261008_01
P3_R3_AUTHORIZATION_GRANTED=false
AUTO_RETRY=false
AUTO_WRITE=false
AUTO_P4=false
STOP=true
```
