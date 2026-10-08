# N3-W Clean Product First-Pair Setup-Secret Handoff and Runtime Identity — P3 Full Exact Flash / No Product Boot Preexecution — 2026-10-08

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_FULL_EXACT_FLASH_NO_BOOT_20261008_01
STATUS=AUTHORIZED_NOT_EXECUTED
P3_AUTHORIZATION_GRANTED=true
P3_AUTHORIZATION_CLAIMED=false
P3_AUTHORIZATION_CONSUMED=false
BOARD_WRITE_AUTHORIZED=true
AUTO_P4=false
MERGE=false
```

## 1. Entry authorities

```text
P1_R2_CLEAN_BOARD_ELIGIBILITY=CLOSED_PASS
P2_STATUS=CLOSED_PASS

SILICON_BINDING_SHA256=f9c00d136f84d1fdabb1e296608702539ed674271021b28cff2d4a23e4cd2bf7
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
OLD_N3W_STATE_ABSENT=true

SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
BUILD_RUN_ID=37594598870
ARTIFACT_ID=11469977052
ARTIFACT_NAME=n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
```

P2 frozen preboot authority:

```text
MANAGER_CONTAINER_ID_SHA256=7b3c2a4de642e8a57da9d3f1652c9c35a27533c16f056736ecc89e289463bccc
MANAGER_STARTED_AT=2026-10-06T15:08:36.478286093Z
MANAGER_RESTART_COUNT=0
BROKER_CONTAINER_ID_SHA256=54a343cf903f5c73fd5b646c233e59cf0313b25d3f2caa55061fc64bc30741cd
BROKER_STARTED_AT=2026-10-06T05:01:47.110364692Z
BROKER_RESTART_COUNT=0
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c
```

## 2. Exact release binding

```text
BOOTLOADER_BIN_SIZE=22576
BOOTLOADER_BIN_SHA256=985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5

PARTITIONS_BIN_SIZE=3072
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OTA_DATA_INITIAL_BIN_SIZE=8192
OTA_DATA_INITIAL_BIN_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

FIRMWARE_BIN_SIZE=1412672
FIRMWARE_BIN_SHA256=4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65
```

Flash layout:

```text
FLASH_MODE=dio
FLASH_FREQ=80m
FLASH_SIZE=8MB
0x0000  bootloader.bin
0x8000  partitions.bin
0x9000  ota_data_initial.bin
0x10000 firmware.bin
```

## 3. Execution contract

All artifact download/hash/member checks, serial ownership checks, esptool
version checks and fresh ROM silicon/security/flash-size checks occur before
claim.

Immediately before `erase-flash`:

```text
P3_AUTHORIZATION_CLAIMED=true
P3_AUTHORIZATION_CONSUMED=true
```

After claim, any failure is fail-closed and the same P3 authorization is not
replayed.

Mutation sequence:

```text
FULL_CHIP_ERASE=true
WRITE_BOOTLOADER=true
WRITE_PARTITIONS=true
WRITE_OTADATA=true
WRITE_FIRMWARE=true
ESPTOOL_NO_STUB=true
BEFORE_RESET_POLICY=no-reset
AFTER_RESET_POLICY=no-reset
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
```

After write, independently read back the exact byte lengths at each flash
offset and compare SHA-256 to the frozen binaries. No normal reset is allowed.

```text
READBACK_VERIFY_BOOTLOADER=REQUIRED
READBACK_VERIFY_PARTITIONS=REQUIRED
READBACK_VERIFY_OTADATA=REQUIRED
READBACK_VERIFY_FIRMWARE=REQUIRED
```

## 4. Safety boundary

```text
MANAGER_RESTART=false
BROKER_RESTART=false
T1_MUTATION=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
NORMAL_PRODUCT_BOOT=false
P4_AUTO_EXECUTE=false
```

If P3 passes, leave the candidate in ROM Download Mode / no-reset state and
STOP. Stage P4 first normal product boot requires a later explicit authorization.

## 5. Incident guard incorporated before P3

The P2 executor incident is archived at:

`docs/development/N3W_P2_EXECUTOR_AUTHORITY_AND_RUNTIME_BINDING_INCIDENT_20261008.md`

P3 does not use an SSH alias, does not inspect T1 containers, and does not infer
negative runtime state from unexecuted default booleans.

```text
NEXT_ACTION=EXECUTE_P3_FULL_EXACT_FLASH_NO_BOOT
STOP=true
```
