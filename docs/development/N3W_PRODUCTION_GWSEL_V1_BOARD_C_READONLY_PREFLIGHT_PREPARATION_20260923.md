# N3-W Production Gateway Selection V1
## Board C Read-Only Preflight Preparation — 2026-09-23

Status: `PREPARED_AWAITING_CI_AND_PHYSICAL_AUTHORIZATION`

## Gate

```text
TASK=N3W_PRODUCTION_GWSEL_V1_BOARD_C_READONLY_PREFLIGHT_PREPARATION_20260923_01

BOARD_C_ACCESS=false
SOURCE_AND_EXECUTOR_PREPARATION_ONLY=true
AUTO_EXECUTE=false

FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_BOARD_MUTATION=false
```

## Preparation base

```text
BASE=
349639269b1733df6dc2ae0cf378d54e34893b8c

RUNBOOK=
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md
```

The base already contains:

```text
BOARD_A_IDENTITY_RECHECK=PASS
BOARD_B_IDENTITY_RECHECK=PASS
IDENTITY_PARSER_REPAIR=CLOSED_PASS
RUNBOOK_ZSH_PASTE_SAFE_RULE=ACTIVE
```

## Candidate artifact authority

The Board C preflight remains bound to the same exact production artifact:

```text
PRODUCT_SOURCE=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

PRODUCT_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

ARTIFACT_ID=
10693728323

ARTIFACT_OUTER_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

RELEASE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

## Board C frozen identity authority

The existing public-safe Board C R2 closeout records:

```text
BOARD_C_HARDWARE_ID_SHA256=
d6ef3f98a35f06a5a8b8e7716a015e17336242128b314a1b3244b114fc6f72e2

BOARD_C_CURRENT_IDENTITY_UNIQUE=true
BOARD_C_USB_BINDING=PASS
```

No raw MAC or other private identifier is copied into this preparation.

## Prepared executor

```text
tools/execution_packages/n3w/production/gwsel_v1_board_c_preflight/executor.py
```

The executor is derived from the repaired production preflight path and uses the
current RUNBOOK identity parser:

```text
EXPLICIT_BASE_MAC_PREFERRED=true
FULL_EUI64_PARSE=true
EUI64_FF_FE_RECOVERY=true
LEGACY_MAC48_FALLBACK=true
MALFORMED_EUI64_FAIL_CLOSED=true
```

Board C adds a stricter identity guard:

```text
FRESH_ROM_IDENTITY_REQUIRED=true
EXPECTED_BOARD_C_HARDWARE_ID_SHA256=
d6ef3f98a35f06a5a8b8e7716a015e17336242128b314a1b3244b114fc6f72e2

IDENTITY_MISMATCH_STOP_BEFORE_FLASH_ID=true
IDENTITY_MISMATCH_STOP_BEFORE_FLASH_READ=true
IDENTITY_OVERRIDE=false
```

Only after identity acceptance may the future physical preflight verify:

```text
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
PARTITION_TABLE_BINDING
OTADATA_READBACK
EXACT_ARTIFACT_BINDING
```

OTA-data remains boot-selection evidence only and is not used for physical identity.

## Mutation boundary

The prepared executor contains no write operation.

Forbidden recovery behavior remains:

```text
AUTO_REPAIR=false
AUTO_REFLASH=false
AUTO_NVS_ERASE=false
AUTO_PARTITION_MIGRATION=false
AUTO_BOOTLOADER_WRITE=false
AUTO_FULL_FLASH_ERASE=false
AUTO_IDENTITY_OVERRIDE=false
```

A later ROM/esptool execution may reset or enter the bootloader and therefore
requires a separate explicit Board C authorization.

## Prepared tests

```text
tests/execution_packages/n3w/production/gwsel_v1_board_c_preflight/test_executor.py
```

Coverage includes:

```text
EXACT_ARTIFACT_BINDING
FULL_LENGTH_AUTHORITY_HASHES
EUI64_NOT_TRUNCATED
EXPLICIT_BASE_MAC_PREFERRED
MALFORMED_EUI64_FAIL_CLOSED
WRONG_ARTIFACT_NOT_REFERENCED
OPERATOR_CONFIRMATION_BEFORE_BOARD_ACCESS
IDENTITY_MISMATCH_BEFORE_FLASH_ID_OR_READBACK
READ_ONLY_PARTITION_AND_OTADATA_READBACK
PARTITION_MISMATCH_FAIL_CLOSED
RAW_MAC_NOT_PUBLISHED
```

## Future physical execution boundary

This preparation does not authorize or execute the following proposed future gate:

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_C_WRITE_TARGET_PREFLIGHT_20260923_01

BOARD_C_CONNECTED_CONFIRMATION_REQUIRED=true
BOARD_C_TEMPORARY_RESET_READONLY_AUTHORIZATION_REQUIRED=true
AUTO_EXECUTE=false
```

The future operator command must obey the RUNBOOK zsh paste-safety rule: explanatory
comments stay outside the executable block.

## Current stop

```text
BOARD_C_ACCESS=false
ROM_ACCESS=false
FLASH_READ=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_BOARD_MUTATION=false
WRITE_AUTHORIZATION_GRANTED=false

STOP=true
```
