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


## 6. Versioned executor binding

```text
EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p3_full_exact_flash_no_boot/executor.py
EXECUTOR_BLOB_SHA=660d367a65e5eecf78d20982f42ead5832d28ed7
EXECUTOR_COMMIT=135280d291b4830d506168ad18bc3ee6e59ad01c
REPOSITORY_BRANCH=fix/n3w-auto-safe-fallback-production-core-convergence-20261003
REPOSITORY_VERSIONED_EXECUTOR=true
```

The Mac bootstrap must fetch this exact GitHub Contents API blob and reject any
different blob SHA before Python compile/execute. The executor itself rebinds
the exact artifact and clean candidate before the P3 authorization claim.


## 7. First P3 execution stopped safely before claim

The first authorized P3 execution downloaded and verified the exact artifact,
then performed the board preclaim. It stopped before authorization claim and
before any flash mutation because the live board silicon binding did not match
the P1 R2 clean-candidate binding.

```text
STAGE=P3_FULL_EXACT_FLASH_NO_PRODUCT_BOOT
P3_PRECLAIM_RESULT=SILICON_BINDING_MISMATCH

ARTIFACT_BINDING_PASS=true
ARTIFACT_ID=11469977052
BUILD_RUN_ID=37594598870
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
ESPTOOL_VERSION=5.3.1

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

BOARD_PRECLAIM_PASS=false
FULL_CHIP_ERASE=false
FOUR_REGION_WRITE=false
READBACK_VERIFY_BOOTLOADER=false
READBACK_VERIFY_PARTITIONS=false
READBACK_VERIFY_OTADATA=false
READBACK_VERIFY_FIRMWARE=false
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
P3_PASS=false
READY_FOR_P4=false

T1_MUTATION=false
MANAGER_RESTART=false
BROKER_RESTART=false
STOP=true
```

Fresh source review confirms P1 and P3 use the same silicon-binding algorithm:
lowercase ROM MAC without separators, prefixed by `rom-c6-`, then SHA-256.
Therefore no algorithm drift is currently proven. The live connected board must
be classified read-only before P3 is resumed.

```text
P3_AUTHORIZATION_REMAINS_GRANTED=true
P3_AUTHORIZATION_CLAIMED=false
P3_AUTHORIZATION_CONSUMED=false
NEXT_ACTION=READONLY_CLASSIFY_CURRENT_CONNECTED_SILICON_BINDING
AUTO_RETRY=false
```


## 8. Read-only board classification after first P3 preclaim stop

A host-only/ROM read-only classification of the currently connected board
confirmed that the P3 silicon mismatch was real, not a binding-algorithm
difference.

```text
STAGE=P3_CURRENT_BOARD_READONLY_CLASSIFICATION
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_WRITE=false
FLASH_ERASE=false

P3_CONNECTED_OTHER_BOARD_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
P3_EXPECTED_CLEAN_CANDIDATE_SHA256=f9c00d136f84d1fdabb1e296608702539ed674271021b28cff2d4a23e4cd2bf7
BOARD_CLASSIFICATION=OTHER_BOARD
EXPECTED_P1_CANDIDATE_MATCH=false

FLASH_SIZE_8MB=true
SECURE_BOOT_DISABLED=true
FLASH_ENCRYPTION_DISABLED=true
PARTITION_WINDOW_BLANK=true
READY_TO_RESUME_P3=false
STOP=true
```

This proves the current USB-attached board is a different blank/security-open
ESP32-C6, but it is **not authorized as the P1 R2 clean candidate**. It must
not be adopted as a substitute P3 target without separately re-running the
clean-board eligibility route for that silicon.

```text
P3_AUTHORIZATION_REMAINS_GRANTED=true
P3_AUTHORIZATION_CLAIMED=false
P3_AUTHORIZATION_CONSUMED=false
NEXT_ACTION=RECONNECT_P1_R2_CLEAN_CANDIDATE_THEN_REPEAT_PRECLAIM
CURRENT_OTHER_BOARD_MUTATION_AUTHORIZED=false
```


## 9. Silicon-mismatch interpretation correction

The earlier wording that classified the connected silicon as a "wrong board"
was too strong and is superseded by this section.

The physical-acceptance authority requires **one genuinely clean candidate
before write**. It does not make the first successful P1 silicon digest a
permanent product-wide board identity. A different silicon may be used only
after that silicon independently passes a fresh P1 clean-board eligibility
gate.

```text
P3_SILICON_MISMATCH_INTERPRETATION_CORRECTION=true

OBSERVED_CURRENT_SILICON_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
PRIOR_P1_R2_SILICON_SHA256=f9c00d136f84d1fdabb1e296608702539ed674271021b28cff2d4a23e4cd2bf7

DIFFERENT_SILICON=true
CURRENT_BOARD_NOT_NEW=false
CURRENT_BOARD_DIRTY=false
CURRENT_BOARD_CLEAN_ELIGIBILITY=NOT_YET_FORMALLY_CLOSED
```

The operator explicitly states that the currently connected board is brand new
and unused. Existing read-only observations already show 8MB flash, Secure Boot
disabled, Flash Encryption disabled and a blank partition-table window. Those
facts are consistent with a clean successor candidate but do not replace the
formal P1 closure.

Correct successor route:

```text
NEXT_ONE_GATE=P1_FRESH_SUCCESSOR_CLEAN_BOARD_ELIGIBILITY_FOR_CURRENT_SILICON
AFTER_P1_PASS=P2_PREBOOT_RUNTIME_REFREEZE
AFTER_P2_REFREEZE_PASS=P3_FULL_EXACT_FLASH_NO_BOOT
```

P3 target selection must bind to the **latest successful P1 closure authority**
rather than a silicon digest permanently hard-coded into an executor.
