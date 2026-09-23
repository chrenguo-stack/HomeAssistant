# N3-W Production Gateway Selection V1
## Board B Minimal ROM Identity Recheck Closure — 2026-09-23

Status: `CLOSED_PASS`

## Gate

```text
TASK=N3W_PRODUCTION_GWSEL_V1_BOARD_B_MINIMAL_ROM_IDENTITY_RECHECK_20260923_01
BOARD_LABEL=B
READ_ONLY=true
FLASH_READ=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_MUTATION=false
BOARD_C_ACCESS=false
```

## Repair authority used

```text
IDENTITY_PARSER_REPAIR_HEAD=
288accbc216176de0acab100233301c780571fb8

PARSER_SOURCE_REPAIR_CI=
35815218810

PARSER_SOURCE_REPAIR_RESULT=SUCCESS
```

The repaired parser follows the reusable authority:

```text
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md
```

## Physical identity recheck evidence

The operator confirmed Board B was the only intended USB target and had already
authorized temporary reset / ROM bootloader entry for this read-only recheck.

Observed result:

```text
BOARD_B_SINGLE_USB_TARGET=PASS
ESPTOOL_VERSION=5.3.1

BOARD_B_ROM_IDENTITY_PARSE=PASS

BOARD_B_HARDWARE_ID_SHA256=
cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0

EXPECTED_BOARD_B_HARDWARE_ID_SHA256=
cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0

BOARD_B_HISTORICAL_IDENTITY_MATCH=true

RAW_MAC_PUBLIC=false
FLASH_READ=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_MUTATION=false

N3W_PRODUCTION_GWSEL_V1_BOARD_B_MINIMAL_ROM_IDENTITY_RECHECK=PASS
BOARD_B_IDENTITY_RECHECK_EXIT_CODE=0
```

The raw ROM MAC was not published or committed.

## Adjudication

The corrected parser reproduces the independently frozen historical Board B
hardware-identity digest exactly.

Therefore:

```text
BOARD_B_DISTINCT_SILICON_IDENTITY=PROVEN
BOARD_B_HISTORICAL_IDENTITY_MATCH=PASS
BOARD_B_PREVIOUS_IDENTITY_CONFLICT=FALSE_POSITIVE_CLOSED
OPERATOR_BOARD_B_LABEL_DOUBT=WITHDRAWN
```

The earlier equal identity result was caused by the defective first-six-byte parser,
not by evidence that Board A had been connected twice.

## Composition with the earlier Board B full read-only preflight

The earlier full Board B preflight independently established:

```text
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false

PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

ARTIFACT_ID=
10693728323

ARTIFACT_BINDING=PASS

PERSISTENT_MUTATION=false
FLASH_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false
```

Those read paths were not affected by the identity-parser defect. Combining those
results with this repaired identity recheck closes Board B's static target
compatibility evidence:

```text
BOARD_B_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
BOARD_B_IDENTITY_BINDING=PASS
BOARD_B_PARTITION_BINDING=PASS
BOARD_B_SECURITY_COMPATIBILITY=PASS
BOARD_B_ARTIFACT_AUTHORITY_BINDING=PASS
```

This closure is not a write authorization.

The earlier preflight package had a bounded freshness window. A future firmware
mutation must perform whatever fresh pre-write revalidation is required by the
then-current execution gate; this closure must not be treated as a permanent
time-valid write token.

## Mutation boundary

```text
ROM_READ_ONLY_ACCESS_EXECUTED=true
TEMPORARY_RESET_ROM_ENTRY_AUTHORIZED=true

FLASH_READ=false
FLASH_WRITE=false
NVS_WRITE=false
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
FULL_FLASH_ERASE=false

PERSISTENT_MUTATION=false
WRITE_AUTHORIZATION_GRANTED=false
```

## Closure

```text
=== N3W GWSEL V1 BOARD B MINIMAL ROM IDENTITY RECHECK CLOSURE ===

BOARD_LABEL=B

BOARD_B_IDENTITY_RECHECK=PASS
BOARD_B_HISTORICAL_IDENTITY_MATCH=PASS
BOARD_B_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

PREVIOUS_BOARD_B_IDENTITY_CONFLICT=SUPERSEDED_FALSE_POSITIVE

BOARD_A_IDENTITY_RECHECK=PENDING
BOARD_C_ACCESS=false

FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false

STOP=true
=== END ===
```

## Proposed next ONE gate

The parser defect also invalidated the original Board A identity digest, even though
Board A's chip, flash-size, security, partition and artifact checks remain valid.

Proposed next gate:

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_A_MINIMAL_ROM_IDENTITY_RECHECK_20260923_01

BOARD_LABEL=A
BOARD_ACCESS_REQUIRED=true
READ_ONLY=true
TEMPORARY_RESET_ROM_ENTRY_REQUIRES_EXPLICIT_AUTHORIZATION=true
FLASH_READ=false
FLASH_WRITE=false
NVS_WRITE=false
BOARD_C_ACCESS=false
AUTO_EXECUTE=false
```
