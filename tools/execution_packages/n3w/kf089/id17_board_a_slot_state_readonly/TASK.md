# N3W KF-089 ID17 Board A dual-slot read-only preclaim

## Goal

Determine the smallest safe mutation needed to put Board A on the exact Schema-v5 diagnostic firmware before a new independent Relay validation session.

ID17 performs **read-only** inspection only. It does not deploy firmware and does not switch OTA slots.

The reason for this gate is the ID16 result:

```text
BOARD_B_SCHEMA_VERSION=5
BOARD_B_UNICAST_TX_COMPLETION=PROVEN
BOARD_A_SCHEMA_VERSION=3
A_COMPACT_RX=NOT_PROVEN
FIRST_UNPROVEN_STAGE=BETWEEN_B_UNICAST_COMPLETION_AND_A_COMPACT_RX
```

The historical ID11 session cannot be replayed to manufacture missing A-side Schema-v5 counters. A later experiment must be independent.

## OTA Guard disposition

PR #385 remains open/unmerged and currently records:

```text
GUARD_PREMUTATION_AND_MUTATION_DATA_PATH=PASS
GUARD_IDENTITY_CONTRACT_REPAIR=PASS
GUARD_POSTMUTATION_FLASH_FINISH_HANDLING=REPAIR_REQUIRED
GUARD_FAILURE_STATE_RECONNECT_PATH=REVIEW_REQUIRED
N3W_OTA_GUARD_FULLY_READY=false
```

Therefore ID17 does not use OTA Guard mutation code. It first asks a simpler question: is the exact Schema-v5 firmware already present in Board A's inactive slot?

If yes, the later mutation can be reduced to a slot-selection operation. If no, a separate inactive-slot deployment package is required.

## Exact Schema-v5 firmware authority

```text
SOURCE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
FIRMWARE_BIN_SIZE=1115648
FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
SAME_BINARY_VALID_FOR_A_AND_B=true
```

## Frozen dual-slot geometry

```text
PARTITION_TABLE_OFFSET=0x8000
PARTITION_TABLE_SIZE=0x1000
OTADATA_OFFSET=0x9000
OTADATA_SIZE=0x2000
APP0_OFFSET=0x10000
APP0_SIZE=0x3C0000
APP1_OFFSET=0x3D0000
APP1_SIZE=0x3C0000
```

The executor verifies the physical partition table before classifying slot state.

## Physical scope

Only Board A may be physically accessed. Board B, RF, T1, pairing state, NVS state, and product runtime are outside this gate.

After a fresh explicit ID17 authorization, Board A must begin fully unpowered with all non-USB power removed. Hold BOOT/GPIO9 low before applying USB power, keep it low through power-on/reset and enumeration, and release only after enumeration. The intended state is ROM Download Boot.

After preparation there is no RESET, power-cycle, reconnect, or retry under the same authorization.

## Exact operation sequence

1. Host-only exact-head and clean-worktree checks.
2. Host-only Python 3.11 / esptool 5.3.1 binding.
3. Verify Board A serial locator exists without opening it.
4. Claim/consume physical authorization immediately before the first Board A target command.
5. `read-mac` and require exactly one canonical `BASE MAC:` with public-safe suffix `F3:50`.
6. Read partition table at `0x8000`, size `0x1000`.
7. Read otadata at `0x9000`, size `0x2000`.
8. Read exactly `1115648` bytes from app0 starting at `0x10000`.
9. Read exactly `1115648` bytes from app1 starting at `0x3D0000`.
10. Host-only parse partition geometry and OTA selection.
11. SHA256 both slot payload windows against the exact Schema-v5 firmware hash.
12. Persist private raw evidence, sanitized summaries, closure, and evidence manifest.

All ROM commands use:

```text
--chip esp32c6
--before no-reset
--after no-reset
--no-stub
ESPTOOL_OPEN_PORT_ATTEMPTS=1
```

## Classification

```text
inactive slot exact Schema-v5 == true
  -> PREPARE_BOARD_A_SLOT_SWITCH_ONLY_PACKAGE

inactive slot exact Schema-v5 == false
  -> PREPARE_BOARD_A_INACTIVE_SLOT_SCHEMA5_DEPLOYMENT_PACKAGE

active slot exact Schema-v5 == true
  -> HOST_ADJUDICATE_ACTIVE_SCHEMA5_SELECTION_VS_SCHEMA3_RUNTIME_HISTORY
```

No mutation is permitted from the ID17 result itself.

## Forbidden

```text
BOARD_B_PHYSICAL_ACCESS=false
RF_EXECUTION=false
T1_ACCESS=false
APPLICATION_BOOT=false
RESET_RETRY=false
AUTO_RETRY=false
FLASH_WRITE=false
NVS_WRITE=false
OTADATA_WRITE=false
OTA_SLOT_SWITCH=false
PAIRING_CHANGE=false
FIRMWARE_REFLASH=false
```

## Evidence boundary

Raw partition table, raw otadata, raw slot payload windows, and full BASE MAC remain private/local. Public GitHub may contain only sanitized geometry, hashes, selected slot number, pass/stop status, and next-route classification.
