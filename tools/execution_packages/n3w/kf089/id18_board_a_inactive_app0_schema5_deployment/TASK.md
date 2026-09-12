# N3W KF-089 ID18 Board A inactive-app0 Schema-v5 deployment

## Goal

Materialize the smallest mutation implied by ID17: write the exact frozen Schema-v5 firmware payload to Board A's **inactive app0 slot only**, verify exact readback, and leave OTA boot selection unchanged on app1.

ID18 does **not** switch OTA slots and does **not** boot the application. A later separately authorized gate must perform slot selection only after ID18 proves the app0 payload and unchanged rollback/otadata state.

## Predecessor evidence

```text
ID17_RESULT=PASS
ID17_SELECTED_SLOT=1
ID17_INACTIVE_SLOT=0
ID17_ACTIVE_OTA_SEQ=4
ID17_ACTIVE_OTA_STATE=2
ID17_ACTIVE_SLOT_EXACT_SCHEMA5=false
ID17_INACTIVE_SLOT_EXACT_SCHEMA5=false
ID17_NEXT_ROUTE=PREPARE_BOARD_A_INACTIVE_SLOT_SCHEMA5_DEPLOYMENT_PACKAGE
```

## Exact Schema-v5 authority

```text
SOURCE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
FIRMWARE_BIN_SIZE=1115648
FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
TARGET_SLOT=app0
TARGET_OFFSET=0x10000
TARGET_PARTITION_SIZE=0x3C0000
ROLLBACK_SLOT=app1
ROLLBACK_OFFSET=0x3D0000
```

The project method authority records ESP-IDF 5.5.4 OTA deployment as: verify physical partition/OTA state, write the exact image only to the inactive OTA slot, perform exact-size readback and SHA-256 verification, then switch OTA selection in a later step. ID18 intentionally stops before that final slot-selection mutation.

## Mutation primitive review

The first host-only ID18 revision used stock esptool `write-flash`. A source review of esptool v5.3.1 found that the high-level write path has an independent `ESPLoader.WRITE_FLASH_ATTEMPTS=2` whole-image reconnect/retry loop. That conflicts with this gate's `AUTO_RETRY=false` contract even when `write_block_attempts=1` is configured.

Therefore the physical-ready revision **does not invoke stock `write-flash` at all**. It binds esptool v5.3.1 in-process after loading the private retry config, requires `loader.WRITE_BLOCK_ATTEMPTS == 1`, connects once to the ESP32-C6 ROM loader, verifies identity and same-connection flash freshness, then performs one low-level ROM sequence:

```text
flash_begin(exact firmware size, 0x10000)
flash_block(seq=0..N-1) exactly once each
flash_md5sum(0x10000, exact firmware size)
```

No `cmds.write_flash`, no whole-image retry loop, and no `flash_finish` are used. The ROM high-level esptool implementation itself skips `flash_finish` because it can exit the loader and run user code; ID18 preserves ROM Download state for the later readback verification.

## Why slot switch is separated

PR #385 OTA Guard remains `BOARD_B_RECOVERY_ONLY` and still records post-mutation completion/reconnect repair work. ID18 avoids otadata mutation entirely. The currently selected app1 rollback path remains boot-authoritative throughout this gate.

## Physical preparation

A fresh explicit ID18 physical authorization is required before any Board A access.

Board A must begin fully unpowered with all non-USB power removed. Hold BOOT/GPIO9 low before applying USB power, keep it low through power-on/reset and enumeration, and release only after enumeration. The intended state is ROM Download Boot.

After preparation there is no RESET, power-cycle, USB reconnect, or mutation retry under the same authorization.

## Execution sequence

1. Host-only exact-head, clean-worktree, Python 3.11, esptool 5.3.1 checks.
2. Host-only exact firmware size/SHA-256 verification.
3. Verify Board A locator exists without opening it.
4. Claim/consume authorization immediately before first Board A target command.
5. `read-mac`; require exactly one canonical `BASE MAC:` with public-safe suffix `F3:50`.
6. Read partition table `0x8000 / 0x1000`; verify exact dual-slot geometry.
7. Read otadata `0x9000 / 0x2000`; require selected slot 1, active seq 4, active state VALID(2).
8. Read exact Schema-v5-sized payload windows from app0 and app1.
9. If app0 has unexpectedly become exact Schema-v5 already, stop without mutation and route to slot-switch preparation.
10. Bind the esptool v5.3.1 direct-ROM runtime only after the retry config is active.
11. Open exactly one mutation connection; re-verify canonical BASE MAC and same-connection MD5 freshness of app0, app1, and otadata.
12. Enter `flash_begin` once at `0x10000`, then send each app0 firmware block exactly once. Persist mutation progress before and after each block.
13. Verify exact-size app0 MD5 on the same ROM connection. Do not call `flash_finish`.
14. After closing that connection, read back exactly 1115648 bytes from app0 and require exact SHA-256 match.
15. Re-read otadata and require byte-for-byte equality with pre-mutation otadata.
16. Re-read the app1 payload window and require pre/post SHA-256 equality.
17. Persist private evidence and route to `PREPARE_BOARD_A_SLOT_SWITCH_ONLY_PACKAGE` only if every verification passes.

## Retry contract

A private `esptool.cfg` is created in the evidence root and selected through `ESPTOOL_CFGFILE` before the esptool mutation runtime is imported:

```text
connect_attempts=1
write_block_attempts=1
open_port_attempts=1
```

The executor additionally requires at runtime:

```text
ESPTOOL_VERSION=5.3.1
ESP32C6ROM.FLASH_WRITE_SIZE=0x400
loader.WRITE_BLOCK_ATTEMPTS=1
STOCK_HIGH_LEVEL_WRITE_FLASH_USED=false
```

If a low-level mutation call fails after `flash_begin` is entered, persistent app0 state is uncertain and the executor STOPs. It performs no mutation retry and no automatic rollback. Any recovery inspection requires a separate later authorization.

## Mutation boundary

Allowed mutation:

```text
BOARD_A_APP0_INACTIVE_SLOT_WRITE=true
TARGET_OFFSET=0x10000
INPUT_SIZE=1115648
DIRECT_ROM_SINGLE_CONNECTION=true
```

Forbidden:

```text
BOARD_B_PHYSICAL_ACCESS=false
T1_ACCESS=false
RF_EXECUTION=false
APPLICATION_BOOT=false
OTA_SLOT_SWITCH=false
OTADATA_WRITE=false
NVS_WRITE=false
APP1_WRITE=false
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PAIRING_CHANGE=false
STOCK_ESPTOOL_WRITE_FLASH=false
WHOLE_IMAGE_MUTATION_RETRY=false
AUTO_RETRY=false
RESET_RETRY=false
AUTO_ROLLBACK=false
FLASH_FINISH=false
```

## Evidence boundary

Full BASE MAC, raw partition table, raw otadata, raw app payload windows, local firmware paths, and block-level mutation progress remain private. Public-safe closure may contain only suffixes, hashes, geometry, selected/inactive slot numbers, result, and route.
