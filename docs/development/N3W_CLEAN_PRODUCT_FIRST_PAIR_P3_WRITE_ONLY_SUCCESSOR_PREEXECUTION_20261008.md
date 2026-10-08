# N3-W Clean Product First-Pair — P3 Write-Only Successor Preexecution — 2026-10-08

```text
STATUS=PREPARED_NOT_AUTHORIZED
STAGE=P3_WRITE_ONLY_SUCCESSOR_NO_PRODUCT_BOOT
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_SUCCESSOR_20261008_01
P3_WRITE_ONLY_SUCCESSOR_AUTHORIZATION_GRANTED=false
FLASH_ERASE=false
FLASH_WRITE=false
BOARD_ACCESS_FOR_SUCCESSOR=false
PRODUCT_NORMAL_BOOT=false
AUTO_WRITE=false
AUTO_P4=false
MERGE=false
STOP=true
```

This is a **design and executor-preparation record only**, not a grant to run the executor or to write flash.

## 1. Closed predecessor and current board

```text
P1_SUCCESSOR=CLOSED_PASS
P2_PREBOOT_RUNTIME_REFREEZE=PASS
P3_R1_AUTHORIZATION_CONSUMED=true
P3_R2_AUTHORIZATION_CONSUMED=true
P3_R3_RESULT=CLOSED_PASS
P3_R3_AUTHORIZATION_CONSUMED=true

P3_R3_CLOSURE=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_R3_POST_ERASE_STUB_READONLY_PROBE_CLOSURE_20261008.md
EXPECTED_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc

FULL_CHIP_ERASE_ALREADY_COMPLETED=true
CURRENT_BOARD_STATE=ERASED_UNWRITTEN
FOUR_REGION_WRITE=false
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false

R2_POST_ERASE_ROM_NO_STUB_READ=FAILED_AT_SPI_FLASH_CONFIG
R3_STUB_READ_OFFSET=0x8000
R3_STUB_READ_SIZE=4096
R3_STUB_READ_RETURN_CODE=0
R3_PARTITION_WINDOW_ALL_FF=true
```

The R3 probe proves the partition-table window only, not a full 8 MB blank read. The old R2 mutation authorization is permanently consumed, even though it erased successfully and stopped before writing.

## 2. Exact artifact and flash layout

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_MUST_REMAIN=OPEN_DRAFT_UNMERGED

PRODUCT_SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
PRODUCT_SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
BUILD_RUN_ID=37594598870
ARTIFACT_ID=11469977052
ARTIFACT_NAME=n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source
RELEASE_ZIP_SIZE=4340810
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c

FLASH_MODE=dio
FLASH_FREQ=80m
FLASH_SIZE=8MB

OFFSET_0x0000=bootloader.bin
BOOTLOADER_SIZE=22576
BOOTLOADER_SHA256=985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5

OFFSET_0x8000=partitions.bin
PARTITIONS_SIZE=3072
PARTITIONS_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

OFFSET_0x9000=ota_data_initial.bin
OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

OFFSET_0x10000=firmware.bin
FIRMWARE_SIZE=1412672
FIRMWARE_SHA256=4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65
```

All four files are exact frozen release members. Do not use firmware.factory.bin, firmware.ota.bin or a newly rebuilt application as a substitute. No full-chip erase or erase-region may be issued.

## 3. New exact executor authority (prepared only)

```text
EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p3_write_only_successor/executor.py
EXECUTOR_BLOB_SHA=481a368f1879e1e9f86bfc70ff36912128a8aaaa
EXECUTOR_REQUIRED_ESPTool_VERSION=5.3.1
EXECUTOR_SOURCE_STATIC_SCOPE_CHECK=PASS
EXECUTOR_LOCAL_PYTHON_COMPILE=REQUIRED_AT_NEXT_HOST_PREFLIGHT_NOT_YET_PERFORMED
EXECUTOR_PHYSICAL_EXECUTION=false
P3_WRITE_ONLY_SUCCESSOR_AUTHORIZATION_GRANTED=false
```

The executor reuses the bounded exact-release member verification, silicon-binding policy, fresh USB ownership checks, private evidence and per-region SHA256 readback from R2. It makes a narrowly scoped modification to avoid the proven ROM/no-stub SPI flash-access failure: only ROM `get-security-info` uses no-stub; flash-id, preclaim blank read, write-flash and each read-flash use the flasher stub in volatile RAM.

Static source inspection confirmed no `erase-flash` or `erase-region` invocation, one bounded `write-flash`, four exact SHA256 readback checks, `--before no-reset` and `--after no-reset`, and no automatic P4. This is **not** a claim that local Python compilation, stub write capability or post-write physical acceptance has already passed.

## 4. Preclaim before any write authorization consumption

All of the following must succeed before claiming the new one-shot write authorization:

1. Fresh repository / PR #522 / exact executor blob rebind; require OPEN, DRAFT, UNMERGED.
2. Obtain the exact frozen artifact, verify release ZIP length + SHA256, exact member set, each member's size/SHA256 and required manifest/source markers.
3. Mac Terminal: validate executor blob using `git hash-object`, then run `python3 -m py_compile`. No source change, no tool installation.
4. Require esptool 5.3.1, exactly one `/dev/cu.usbmodem*`, and no competing serial owner.
5. In the existing ROM Download Mode, `--no-stub get-security-info` and require the expected current silicon. Require Secure Boot disabled and Flash Encryption disabled.
6. Using stub in RAM, require exact 8 MB flash-id, then read `0x8000/0x1000` and require 4096 bytes all `0xFF`.
7. Require a fresh, non-existing private evidence directory; preserve prior P3/R2/R3 private records.

Any preclaim failure is immediate STOP **before** writing or consuming the new write authorization. The source does not need to re-erase the chip.

## 5. One-shot write and readback

Only after separate explicit operator authorization and all preclaims pass:

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
FLASH_WRITE_ATTEMPTED=true
POTENTIAL_PARTIAL_WRITE=true
```

Use stub-based esptool 5.3.1 `write-flash` once with four frozen offset/file pairs and exact flash parameters. The written bytes may be partial if the command fails; a return code of failure must **not** be recorded as zero writes.

Then use stub-based `read-flash` independently for **the exact file length** at each of the four offsets. For each region require actual size and SHA256 equal to its own preverified binary. On any mismatch, fail closed, do not retry, do not erase, and do not reset into product boot.

```text
PASS_REQUIRES=ARTIFACT_BINDING_PASS
PASS_REQUIRES=BOARD_PRECLAIM_PASS
PASS_REQUIRES=PRECLAIM_PARTITION_WINDOW_BLANK
PASS_REQUIRES=FOUR_REGION_WRITE
PASS_REQUIRES=READBACK_VERIFY_BOOTLOADER
PASS_REQUIRES=READBACK_VERIFY_PARTITIONS
PASS_REQUIRES=READBACK_VERIFY_OTADATA
PASS_REQUIRES=READBACK_VERIFY_FIRMWARE

PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
AFTER_RESET_POLICY=no-reset
P4_AUTHORIZATION_GRANTED=false
AUTO_P4=false
STOP=true
```

Successful four-region readback permits **requesting**, not executing, a separate P4 normal-product-boot authorization.

## 6. Failure / recovery / privacy

```text
FULL_CHIP_ERASE_AGAIN=FORBIDDEN
P3_R2_REPLAY=FORBIDDEN
P3_R3_REPLAY=FORBIDDEN
AUTO_RETRY=false
AUTO_ERASE=false
AUTO_WRITE=false
AUTO_P4=false
T1_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
MERGE=false
```

No automatic rollback can reconstruct the prior pre-erased firmware because the board has already been erased. A partial-write or failed-readback board must remain in the safest available bootloader/no-reset state; future flash recovery requires a separately reviewed successor and authorization, never a retry of this one-shot gate.

Raw command output, downloaded release, readback bytes, flash locator and any identity data stay in the private Mac evidence directory. Only public-safe SHA256 digests, structured flags, error code and STOP status may be returned to chat or GitHub.

## 7. Expected closure and authorization boundary

```text
STAGE=P3_WRITE_ONLY_SUCCESSOR_NO_PRODUCT_BOOT
AUTHORIZATION_GRANTED=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=
ARTIFACT_BINDING_PASS=
BOARD_PRECLAIM_PASS=
SILICON_BINDING_SHA256=
PRECLAIM_PARTITION_WINDOW_BLANK=
FLASH_WRITE_ATTEMPTED=
POTENTIAL_PARTIAL_WRITE=
FOUR_REGION_WRITE=
READBACK_VERIFY_BOOTLOADER=
READBACK_VERIFY_PARTITIONS=
READBACK_VERIFY_OTADATA=
READBACK_VERIFY_FIRMWARE=
P3_WRITE_ONLY_SUCCESSOR_PASS=
READY_FOR_P4_AUTHORIZATION=
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
FULL_CHIP_ERASE=false
P4_AUTHORIZATION_GRANTED=false
STOP=true
```

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_SUCCESSOR_20261008_01
CURRENT_STATUS=PREPARED_NOT_AUTHORIZED
REQUEST_NEW_PHYSICAL_WRITE_AUTHORIZATION=true
DO_NOT_EXECUTE_UNTIL_GRANTED=true
```
