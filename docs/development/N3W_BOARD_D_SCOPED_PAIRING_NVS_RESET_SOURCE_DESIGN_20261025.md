# N3W Board D scoped pairing-NVS reset source design

Date: 2026-10-25

## Gate

```text
TASK=N3W_T1_BOARD_D_SCOPED_PAIRING_NVS_RESET_SOURCE_DESIGN_20261025_01
REPOSITORY=chrenguo-stack/HomeAssistant
BASE=03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
LIVE_BOARD_MUTATION=false
T1_MUTATION=false
```

This gate prepares a repository-owned one-shot executor for Board D only.
It does not authorize execution.

## Bound Board D authority

```text
HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
BOOTLOADER_SHA256=ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
NVS_OFFSET=0x790000
NVS_SIZE=0x70000
```

The exact Board D R4 release authority remains:
- artifact ID 12478974186
- artifact ZIP SHA-256 898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f
- release bundle SHA-256 b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5
- product source ec5f6d68e33db7757d91c807fff708ca81b075dc

## Reason

Board D still carries a durable pairing intent created against the predecessor T1.
The clean-reinstalled T1 has an empty pairing database.

Manager source behavior means an unknown pairing ID on an empty T1 is accepted as a new
`created` transaction. It does not produce terminal `expired` or
`replay_detected`, so firmware will not call `renew_pairing_intent_()`.

Reusing the old transaction ID would violate the ADR-0008 retry contract:
a retry must create a fresh random pairing ID and a terminal pairing ID must never be
reactivated.

## Scope

This reset is a Board D pairing-state reset only.

Allowed persistent mutation:
- erase exactly flash range `0x790000 + 0x70000`.

Forbidden:
- full flash erase;
- bootloader write;
- partition-table write;
- otadata write;
- app0/app1 write;
- phy_init write;
- T1 mutation;
- Manager database mutation;
- opening a pairing window;
- Setup Secret transfer;
- exposing raw pairing ID or Setup Secret.

The reset may also clear product-pairing Setup Secret and product-pairing state inside the
same NVS partition. That is expected. Firmware must regenerate fresh pairing material on
next product boot.

## Pre-execution requirements

Before claim:
1. exact repository/source authority is bound;
2. exact R4 release bundle is verified;
3. esptool major version is 5;
4. exactly one target serial port is supplied;
5. ROM reports ESP32-C6 and 8 MB flash;
6. Secure Boot and Flash Encryption are both disabled;
7. hardware ID SHA-256 equals the frozen Board D identity;
8. bootloader readback matches the frozen release;
9. partition-table readback matches the frozen release;
10. the partition table implies NVS offset/size `0x790000/0x70000`;
11. the supplied read-only preflight record is PASS and recent;
12. no mutation has happened under the reset authorization.

## One-shot authorization

Execution requires a new explicit authorization:

```text
N3W_T1_BOARD_D_SCOPED_PAIRING_NVS_RESET_20261025_01
```

The executor must durably claim that authorization before the first erase command.
The replay authority uses a fixed caller-independent local state namespace under the current UID's system-account Home directory; it is resolved from the OS account database rather than the `HOME` environment variable. The execution CLI does not accept an alternate evidence/claim root. Changing temporary work directories or overriding `HOME` therefore cannot create a second claim for the same authorization.
The claim directory entry is fsynced before erase, so authorization consumption is durable before the first destructive command. Once claimed, it is permanently consumed and may not be replayed even if later checks fail.

## Execution sequence

1. Re-run all Board D identity and release preconditions, including exact preflight artifact binding and `replay_permitted=false`.
2. Read the entire NVS range `0x790000/0x70000` to a private mode-0600 backup.
3. Freeze backup SHA-256, size and non-FF byte count.
4. Create a private one-shot claim record.
5. Run only `esptool erase-region 0x790000 0x70000` with a no-reset post action.
6. Without allowing the application to boot, read the same entire NVS range back.
7. Require:
   - size = 458752 bytes;
   - non-FF byte count = 0;
   - SHA-256 equals SHA-256 of 458752 bytes of `0xFF`.
8. Re-read bootloader and partition table before allowing application startup.
9. Require both protected hashes unchanged.
10. Only after all preboot postconditions PASS, hard-reset/start the application.
11. Close the one-shot record as `CLOSED_PASS`.

## KF-042 guard

The erased-region oracle must run before application startup.

Do not:
- hard-reset immediately after erase;
- reconnect after product boot and then require all-FF NVS.

The product application initializes NVS during boot, so a post-boot non-FF readback is not
evidence of erase failure.

## Post-reset boundary

This gate does not prove successful pairing.

After PASS:
- old Board D pairing intent is gone;
- application may generate a new Setup Secret and fresh random pairing ID;
- saved ESPHome Wi-Fi state may remain outside this product NVS partition, but continuity
  must be re-observed and never assumed;
- new T1 must still remain pairing-window CLOSED until a new first-pair authorization;
- any future pairing evidence must expose hashes only, never raw pairing ID or Setup Secret.

## Current classification

```text
BOARD_D_SCOPED_NVS_RESET_READONLY_PREFLIGHT=PASS
SCOPED_NVS_RANGE=0x790000+0x70000
LIVE_BOARD_MUTATION_AUTHORIZED=false
NVS_ERASE_EXECUTED=false
SOURCE_DESIGN=R1_REPLAY_BLOCKER_REPAIRED_PENDING_R2_REVIEW
```
