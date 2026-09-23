# N3-W Production Multi-Relay Gateway Selection V1
## Board A Write Target Preflight Closure — 2026-09-23

Status: `BOARD_A_PREFLIGHT_PASS`

## 1. Gate

```text
TASK=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_THREE_BOARD_WRITE_TARGET_PREFLIGHT_20260923_01

BOARD_STAGE=A
SEQUENTIAL_BOARD_PREFLIGHT=true

BOARD_B_ACCESS=false
BOARD_C_ACCESS=false
```

The operator explicitly confirmed that only physical Board A was connected and
explicitly authorized temporary reset / ROM bootloader entry for read-only inspection.

No persistent board mutation was authorized.

## 2. Exact executor authority

```text
EXECUTOR_BRANCH=
exec/n3w-production-gwsel-v1-board-a-readonly-preflight-20260923

EXECUTOR_HEAD=
4adfe7c252f2252ec95fb0742d20894aa7bbb376

CI_RUN_ID=
35806635245

CI_RESULT=SUCCESS
```

CI passed:

```text
Compile executor=PASS
Focused preflight tests=PASS
Read-only source contract=PASS
Public repository safety=PASS
```

## 3. Exact artifact authority

```text
ARTIFACT_ID=
10693728323

ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-8c445f2-exact-source

OUTER_ARTIFACT_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

RELEASE_BUNDLE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

FIRMWARE_BIN_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

PARTITIONS_BIN_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTA_DATA_INITIAL_BIN_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

The independently downloaded outer GitHub artifact matched the exact frozen
artifact size and SHA-256 before any board access.

## 4. Board A physical read-only evidence

Operator-visible execution result:

```text
BOARD_A_SINGLE_USB_TARGET=PASS

N3W_PRODUCTION_GWSEL_V1_BOARD_A_WRITE_TARGET_PREFLIGHT=PASS

BOARD_LABEL=A

HARDWARE_ID_SHA256=
3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee

CHIP=ESP32-C6
FLASH_SIZE=8MB

SECURE_BOOT=false
FLASH_ENCRYPTION=false

PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTADATA_READBACK_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3

CANDIDATE_ARTIFACT_ID=
10693728323

CANDIDATE_RELEASE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

HISTORICAL_IDENTITY_HASH_REUSED=false
HISTORICAL_IDENTITY_OVERRIDE_REUSED=false

PERSISTENT_MUTATION=false
FLASH_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false

BOARD_A_PREFLIGHT_EXIT_CODE=0
```

The raw ROM MAC, raw USB path, raw NVS and private local output were not committed.

## 5. Board A target compatibility adjudication

```text
BOARD_A_OPERATOR_LABEL_BINDING=PASS
BOARD_A_FRESH_ROM_IDENTITY_HASH=PASS
BOARD_A_CHIP_BINDING=PASS
BOARD_A_FLASH_SIZE_BINDING=PASS
BOARD_A_SECURE_BOOT_COMPATIBILITY=PASS
BOARD_A_FLASH_ENCRYPTION_COMPATIBILITY=PASS
BOARD_A_PARTITION_TABLE_BINDING=PASS
BOARD_A_ARTIFACT_AUTHORITY_BINDING=PASS

BOARD_A_WRITE_TARGET_COMPATIBILITY=PASS
```

The physical Board A partition-table hash exactly matches the corrected R2 production
artifact partition-table authority.

This supports the later minimal write route:

```text
0x9000  -> ota_data_initial.bin
0x10000 -> firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

No write is authorized by this closure.

## 6. OTA-data interpretation

The current Board A OTA-data region hash is intentionally different from the
artifact's pristine `ota_data_initial.bin` hash:

```text
CURRENT_BOARD_A_OTADATA_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3

ARTIFACT_INITIAL_OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

CURRENT_OTADATA_EQUALS_INITIAL=false
```

This is not an artifact mismatch. The artifact was validated independently before
board access; the Board A value is a readback of the mutable current OTA-selection
region.

The R2 physical-preparation document requested a current OTA-state read. This executor
reads and binds the complete physical OTA-data region but does not decode the
currently selected application slot.

```text
CURRENT_OTADATA_REGION_READ=PASS
CURRENT_OTA_SLOT_DECODE=NOT_EXECUTED
```

For the currently frozen later write method, this is nonblocking because that route
explicitly writes the exact `ota_data_initial.bin` to `0x9000` together with
`firmware.bin` to `0x10000`; the prior selected slot is not an input to that write.

If a later gate changes to an inactive-slot / otatool migration strategy:

```text
CURRENT_OTA_SLOT_DECODE_REQUIRED=true
THIS_PREFLIGHT_SLOT_RESULT_REUSABLE=false
```

That future route must perform its own slot-level read before mutation.

## 7. Mutation boundary

```text
TEMPORARY_RESET_ROM_ENTRY_AUTHORIZED=true
ROM_READ_ONLY_ACCESS_EXECUTED=true

PERSISTENT_MUTATION=false
FLASH_WRITE=false
NVS_WRITE=false
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
FULL_FLASH_ERASE=false

WRITE_AUTHORIZATION_GRANTED=false
```

The command path used `esptool v5.3.1` and the versioned executor's
`--no-stub` read-only ROM operations.

No claim is made here about the post-probe application runtime state; a later write
or runtime gate must establish its own fresh baseline.

## 8. Prior local execution defects

Two preparation defects were encountered and closed before this successful physical
preflight:

1. generated executor source contained literal `\n` text at two Python statement
   boundaries, causing CI compile failure before physical execution;
2. `ota_data_initial.bin` SHA-256 was inherited from old PR #469 as a truncated
   40-hex value, causing local artifact validation to stop before Board A access.

The final exact executor head adds a regression guard requiring artifact/member
SHA-256 values to be full 64-hex digests.

Neither failed attempt accessed Board A.

## 9. Board A closure

```text
=== N3W GWSEL V1 BOARD A WRITE TARGET PREFLIGHT CLOSURE ===

BOARD_LABEL=A

ARTIFACT_ID=
10693728323

EXECUTOR_HEAD=
4adfe7c252f2252ec95fb0742d20894aa7bbb376

CI_RUN_ID=
35806635245

BOARD_A_PREFLIGHT=PASS
BOARD_A_WRITE_TARGET_COMPATIBILITY=PASS

BOARD_A_PARTITION_TABLE_MATCH=PASS
BOARD_A_SECURITY_COMPATIBILITY=PASS

BOARD_A_CURRENT_OTADATA_REGION_READ=PASS
BOARD_A_CURRENT_OTA_SLOT_DECODE=NOT_EXECUTED_NONBLOCKING_FOR_FROZEN_WRITE_ROUTE

PERSISTENT_MUTATION=false
FLASH_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false

BOARD_B_ACCESS=false
BOARD_C_ACCESS=false

STOP=true
=== END ===
```

## 10. Proposed next ONE gate

Board A is complete. The user's required sequential rule remains:

```text
A -> STOP -> B -> STOP -> C -> STOP -> THREE_BOARD_SUMMARY
```

Proposed successor:

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_THREE_BOARD_WRITE_TARGET_PREFLIGHT_20260923_01_BOARD_B

BOARD_LABEL=B

BOARD_ACCESS_REQUIRED=true
PREFLIGHT_READ_ONLY=true
PERSISTENT_BOARD_MUTATION=false
FLASH_WRITE=false
NVS_WRITE=false
T1_ACCESS=false

TEMPORARY_RESET_ROM_ENTRY_REQUIRES_EXPLICIT_AUTHORIZATION=true
AUTO_EXECUTE=false
```


## 11. 2026-09-23 identity parser correction

The original Board A preflight used a parser that accepted only the first six bytes
after a generic `MAC:` label. On ESP32-C6, esptool may present the built-in address
as an eight-byte EUI-64 value with an inserted `ff:fe` extension. Truncating the
first six bytes discards the board-specific tail and can produce false identity
collisions.

Therefore the identity-only claims from this closure are superseded:

```text
BOARD_A_FRESH_ROM_IDENTITY_HASH=SUPERSEDED_BY_PARSER_REPAIR
ORIGINAL_BOARD_A_HARDWARE_ID_SHA256=INVALID_AS_SILICON_IDENTITY
```

The following independently observed results remain valid because their read paths
did not depend on the defective identity parser:

```text
BOARD_A_CHIP_BINDING=PASS
BOARD_A_FLASH_SIZE_BINDING=PASS
BOARD_A_SECURE_BOOT_COMPATIBILITY=PASS
BOARD_A_FLASH_ENCRYPTION_COMPATIBILITY=PASS
BOARD_A_PARTITION_TABLE_BINDING=PASS
BOARD_A_ARTIFACT_AUTHORITY_BINDING=PASS
PERSISTENT_MUTATION=false
FLASH_WRITE=false
```

The corrected reusable authority is:

```text
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md
```

A future identity recheck must use the repaired parser and the existing project
hardware-ID normalization contract.
