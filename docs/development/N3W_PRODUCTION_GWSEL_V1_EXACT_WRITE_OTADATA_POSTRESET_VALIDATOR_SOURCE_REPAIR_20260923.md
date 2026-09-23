# N3-W Production Gateway Selection V1
## Exact Write OTA-data Post-Reset Validator Source Repair — 2026-09-23

Status: `SOURCE_REPAIR_PRE_CI`

## Gate

```text
TASK=
N3W_PRODUCTION_GWSEL_V1_EXACT_WRITE_OTADATA_POSTRESET_VALIDATOR_SOURCE_REPAIR_20260923_01

BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
PHYSICAL_AUTO_EXECUTE=false
```

## Repair base

```text
BASE_EXECUTOR_HEAD=
33e6658244146d890887876ba18f32dd61a879b5
```

## Physical evidence that triggered this repair

Board A's authorized exact write returned a false-negative after the write command:

```text
STOP=post-write OTA-data readback SHA256 mismatch
```

A separate read-only forensic gate then proved:

```text
BOARD_A_APPLICATION_READBACK_VERIFY=PASS
APPLICATION_READBACK_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

BOARD_A_PARTITION_TABLE_PRESERVED=PASS
PARTITION_TABLE_READBACK_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

BOARD_A_OTADATA_RUNTIME_STATE=PASS
OTADATA_OTA_SEQ=1
OTADATA_STATE=VALID
OTADATA_CRC=0x4743989a
OTADATA_RUNTIME_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
```

Therefore Board A does not require a reflash.

## Source defect

The exact artifact writes `ota_data_initial.bin` at `0x9000`. Its SHA-256 is:

```text
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Those bytes represent the initial erased OTA-data state.

The executor's write command uses `--after hard-reset`. The frozen partition
layout has OTA application slots and no factory app. On that first boot ESP-IDF
materializes the valid OTA0 selection record. The previous validator incorrectly
required the post-reset readback to remain byte-identical to the initial image.

```text
OLD_RULE=
POSTRESET_OTADATA_SHA256 == OTADATA_INITIAL_IMAGE_SHA256

OLD_RULE_RESULT=FALSE_NEGATIVE
```

## Repair

The write route is unchanged:

```text
WRITE 0x9000  ota_data_initial.bin
WRITE 0x10000 firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FACTORY_IMAGE_WRITE=false
FULL_FLASH_ERASE=false
```

Only post-reset acceptance changes.

The repaired executor validates:

```text
OTADATA_POSTRESET_OTA_SEQ=1
OTADATA_POSTRESET_STATE=VALID
OTADATA_POSTRESET_CRC=0x4743989a
OTADATA_POSTRESET_RUNTIME_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
```

It also requires the remaining bytes in the first OTA-data sector and the entire
second sector to retain their expected erased state.

Application and partition-table post-write verification remain exact SHA-256
checks.

## Regression coverage

Focused tests now cover:

```text
POSTRESET_RUNTIME_OTADATA_CONTRACT
INITIAL_ALL_FF_OTADATA_REJECTED_AS_POSTRESET_STATE
WRITE_COMMAND_STILL_USES_HARD_RESET
APPLICATION_READBACK_EXACT_SHA
PARTITION_TABLE_READBACK_EXACT_SHA
NO_DESTRUCTIVE_RECOVERY
```

The reusable write-target RUNBOOK now records the same initial-image versus
post-reset-runtime distinction.

## Mutation boundary

```text
BOARD_ACCESS=false
ROM_ACCESS=false
FLASH_READ=false
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_BOARD_MUTATION=false
```

## Current status

```text
SOURCE_REPAIR_WRITTEN=true
CI_RESULT=PENDING
BOARD_B_WRITE_ALLOWED=false
BOARD_C_WRITE_ALLOWED=false
STOP_PENDING_CI=true
```
