# N3-W Production Gateway Selection V1
## Exact Write OTA-data Post-Reset Validator Source Repair Closure — 2026-09-23

Status: `CLOSED_PASS`

## Gate

```text
TASK=
N3W_PRODUCTION_GWSEL_V1_EXACT_WRITE_OTADATA_POSTRESET_VALIDATOR_SOURCE_REPAIR_20260923_01

BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
```

## Exact repair authority

```text
REPAIR_BRANCH=
fix/n3w-production-gwsel-v1-otadata-postreset-validator-20260923

REPAIR_BASE=
33e6658244146d890887876ba18f32dd61a879b5

REPAIR_HEAD=
9c83c66de9fb64609e27437e1b392c2dd6f2f37f

REPAIR_TREE=
65b6e3c1465c49b40098154695d92370741ef487
```

## CI

```text
CI_RUN_ID=35829956273
CI_RESULT=SUCCESS
CI_HEAD=
9c83c66de9fb64609e27437e1b392c2dd6f2f37f
```

CI URL:

https://github.com/chrenguo-stack/HomeAssistant/actions/runs/35829956273

## Defect

The old executor wrote the initial erased OTA-data image, then used
`--after hard-reset`, but required post-reset OTA-data to remain byte-identical to
the initial all-erased image.

For the frozen layout with OTA app slots and no factory app, ESP-IDF materializes a
valid OTA0 runtime record on that first boot. The old rule therefore created a
false-negative after a successful write.

```text
OLD_POSTRESET_RULE=INVALID
EXECUTOR_FALSE_NEGATIVE=PROVEN
```

## Repair contract

Write scope is unchanged:

```text
WRITE 0x9000  ota_data_initial.bin
WRITE 0x10000 firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FACTORY_IMAGE_WRITE=false
FULL_FLASH_ERASE=false
```

The repaired post-reset validator now requires:

```text
OTADATA_POSTRESET_OTA_SEQ=1
OTADATA_POSTRESET_STATE=VALID
OTADATA_POSTRESET_CRC=0x4743989a
OTADATA_POSTRESET_RUNTIME_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
```

Application and partition-table readback remain exact SHA-256 checks.

## Regression coverage

```text
POSTRESET_RUNTIME_OTADATA_CONTRACT=TESTED
INITIAL_ALL_FF_OTADATA_REJECTED_AS_POSTRESET_STATE=TESTED
WRITE_COMMAND_HARD_RESET=TESTED
APPLICATION_READBACK_EXACT_SHA=TESTED
PARTITION_TABLE_READBACK_EXACT_SHA=TESTED
NO_AUTOMATIC_DESTRUCTIVE_RECOVERY=TESTED
RUNBOOK_POSTRESET_GUARD=TESTED
```

## Diff scope

Relative to `33e665...`, the repair changes exactly six files:

```text
.github/workflows/n3w-production-gwsel-v1-three-board-exact-write-preparation-ci.yml
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md
docs/development/N3W_PRODUCTION_GWSEL_V1_EXACT_WRITE_OTADATA_POSTRESET_VALIDATOR_SOURCE_REPAIR_20260923.md
tests/execution_packages/n3w/production/gwsel_v1_three_board_write/test_executor.py
tests/execution_packages/n3w/production/test_board_write_target_preflight_runbook.py
tools/execution_packages/n3w/production/gwsel_v1_three_board_write/executor.py
```

No product firmware source file changed.

## Closure

```text
OTADATA_POSTRESET_VALIDATOR_SOURCE_REPAIR=CLOSED_PASS
GWSEL_V1_EXACT_WRITE_EXECUTOR_REPAIR_READY=true

BOARD_ACCESS_DURING_REPAIR=false
FLASH_WRITE_DURING_REPAIR=false
NVS_WRITE_DURING_REPAIR=false

BOARD_B_WRITE_ALLOWED_BY_THIS_CLOSURE=false
BOARD_C_WRITE_ALLOWED_BY_THIS_CLOSURE=false
STOP=true
```

The next board operation still requires a separate fresh preflight and explicit
board-specific authorization.
