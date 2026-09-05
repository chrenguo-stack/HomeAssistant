# N3-W R1 Board A Flash Read Transport Recovery — Closeout

Date: 2026-09-05
Document class: `READ_ONLY_RECOVERY_CLOSEOUT`
Repository branch: `diag/n3w-r1-offchannel-espnow-baseline-20260905`
Product source mutation: `false`

## Purpose

This document records the bounded read-only recovery performed after the first R1 two-board physical attempt stopped during Board A's fresh pre-flash full-flash backup.

The prior failure was:

```text
A fatal error occurred: Corrupt data, expected 0x1000 bytes but received 0xfd9 bytes.
```

No reference firmware had been written and no RF test had started before that stop.

## Frozen authorities

```text
CURRENT_MAIN=127c3f1e89baaaba7b7fd60d6d263632d30b2461
CURRENT_TREE=32135508818124e848bc895073b3cb6aaa6b9af3
PRODUCT_SOURCE_AUTHORITY=bff94bc4922d7a984eb1363cc24a163ad466a166
```

## Board A binding

```text
BOARD_A_PORT=/dev/cu.usbmodem14201
BOARD_A_USB_IDENTITY=98:A3:16:A9:F4:5C
BOARD_A_MAC=98:a3:16:a9:f4:5c
BOARD_A_CHIP=ESP32-C6
BOARD_A_REVISION=v0.2
BOARD_A_PHYSICAL_FLASH_SIZE=8MB

BOARD_A_PORT_OPEN_PROCESS_COUNT=0
BOARD_A_PORT_OPEN_PROCESSES=NONE
```

## Toolchain

```text
PYTHON_PATH=/Users/chenrenguo/.platformio/penv/bin/python
PYTHON_VERSION=3.11.9
ESPTOOL_PATH=/Users/chenrenguo/.platformio/penv/bin/esptool
ESPTOOL_VERSION=5.2.0
MACOS_VERSION=12.7.6
```

## Conservative full-flash read

One full 8 MB read was executed at fixed 115200 baud.

```text
READ_BAUD=115200
BOARD_A_RECOVERY_FULL_BACKUP=/private/tmp/n3w-r1-boarda-read-recovery-IPBEEk/board_a_recovery_full.bin
BOARD_A_RECOVERY_FULL_BACKUP_SIZE=8388608
BOARD_A_RECOVERY_FULL_BACKUP_SHA256=66027fd84b8e1d20c47e8abf198d772d71a65e09a18ad033e2d812b4dbbc59f0

BOARD_A_FULL_FLASH_READ_RECOVERY=PASS
BOARD_A_FLASH_READ_CAPABILITY=PROVEN
```

The earlier failed read stopped at approximately 2.3% and reported:

```text
READ_FAILURE_EXPECTED_BYTES=0x1000
READ_FAILURE_RECEIVED_BYTES=0xfd9
```

The successful conservative retry supports classifying the earlier failure as transient or transport-level rather than as evidence of Board A flash-content corruption.

## Scope integrity

```text
FLASH_WRITE=false
SERIAL_MONITOR_OPEN=false
RF_EXECUTION=false

BOARD_A_ACCESS=true
BOARD_B_ACCESS=false
BOARD_C_ACCESS=false

PRODUCT_SOURCE_CHANGED=false
HOMEASSISTANT_REPOSITORY_WRITE=false
```

## Closure

```text
READY_TO_RETRY_R1_PREFLASH_STAGE=true

FAILURE_CLASS=TRANSIENT_OR_TRANSPORT_LEVEL_PREVIOUS_READ_CORRUPTION
GATE_RESULT=PASS_BOARD_A_FLASH_READ_TRANSPORT_RECOVERED
NEXT_ROUTE=HIGH_LEVEL_AUTHORIZED_RETRY_OF_R1_PREFLASH_STAGE
STOP=true
```

The R1 RF experiment was not resumed automatically by this recovery gate.
