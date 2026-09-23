# N3-W Production Gateway Selection V1
## Board A Minimal ROM Identity Recheck Closure — 2026-09-23

Status: `CLOSED_PASS`

## Gate

```text
TASK=N3W_PRODUCTION_GWSEL_V1_BOARD_A_MINIMAL_ROM_IDENTITY_RECHECK_20260923_01
BOARD_LABEL=A
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

RUNBOOK=
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md
```

## Physical identity recheck evidence

Observed result:

```text
BOARD_A_SINGLE_USB_TARGET=PASS
ESPTOOL_VERSION=5.3.1

BOARD_A_ROM_IDENTITY_PARSE=PASS

BOARD_A_HARDWARE_ID_SHA256=
f1f1e36fe4784a26b936d6a2bc5d239ab531f5683aca91356a5e39f3f566b1eb

BOARD_A_DISTINCT_FROM_BOARD_B=true

RAW_MAC_PUBLIC=false
FLASH_READ=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_MUTATION=false

N3W_PRODUCTION_GWSEL_V1_BOARD_A_MINIMAL_ROM_IDENTITY_RECHECK=PASS
BOARD_A_IDENTITY_RECHECK_EXIT_CODE=0
```

The raw ROM MAC was not published or committed.

## Historical identity alignment

The fresh operator-confirmed Board A ROM identity digest is identical to the
historical archived hardware-identity digest:

```text
HISTORICAL_HARDWARE_ID_SHA256=
f1f1e36fe4784a26b936d6a2bc5d239ab531f5683aca91356a5e39f3f566b1eb

FRESH_BOARD_A_HARDWARE_ID_SHA256=
f1f1e36fe4784a26b936d6a2bc5d239ab531f5683aca91356a5e39f3f566b1eb

HISTORICAL_IDENTITY_MATCH=true
```

Because earlier project history contained role-label ambiguity, this closure does
not rely on the old role label alone. The current binding authority is the
combination of:

```text
OPERATOR_CONFIRMED_BOARD_LABEL=A
FRESH_ROM_SILICON_IDENTITY=PASS
DISTINCT_FROM_FROZEN_BOARD_B=true
HISTORICAL_HARDWARE_IDENTITY_MATCH=true
```

This re-establishes that archived hardware identity as the current Board A identity.

## Composition with the earlier Board A full read-only preflight

The earlier full Board A preflight independently established:

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
results with this repaired identity recheck closes Board A's static target
compatibility evidence:

```text
BOARD_A_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
BOARD_A_IDENTITY_BINDING=PASS
BOARD_A_PARTITION_BINDING=PASS
BOARD_A_SECURITY_COMPATIBILITY=PASS
BOARD_A_ARTIFACT_AUTHORITY_BINDING=PASS
```

This closure is not a write authorization. A future firmware mutation must perform
whatever fresh pre-write revalidation is required by the then-current execution
gate.

## Operator-command correction

The first Board A recheck command was rejected by interactive zsh before ROM access
because a paste-ready executable block contained a shell comment line beginning
with `#`.

The retry used a comment-free paste-ready block and completed successfully.

The reusable RUNBOOK now explicitly requires paste-ready interactive zsh command
blocks to contain no shell comment lines unless parsing is controlled by an
explicit non-interactive shell wrapper.

```text
FIRST_COMMAND_ROM_ACCESS=NOT_EXECUTED
FIRST_COMMAND_PERSISTENT_MUTATION=false
RUNBOOK_ZSH_PASTE_SAFE_RULE=ADDED
```

## Closure

```text
=== N3W GWSEL V1 BOARD A MINIMAL ROM IDENTITY RECHECK CLOSURE ===

BOARD_LABEL=A

BOARD_A_IDENTITY_RECHECK=PASS
BOARD_A_DISTINCT_FROM_BOARD_B=PASS
BOARD_A_HISTORICAL_IDENTITY_MATCH=PASS
BOARD_A_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

BOARD_B_IDENTITY_RECHECK=PASS
BOARD_B_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

BOARD_C_ACCESS=false

FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false

STOP=true
=== END ===
```

## Proposed next ONE gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_C_READONLY_PREFLIGHT_PREPARATION_20260923_01

BOARD_C_ACCESS=false
SOURCE_AND_EXECUTOR_PREPARATION_ONLY=true
AUTO_EXECUTE=false
```
