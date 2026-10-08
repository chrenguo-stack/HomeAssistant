# N3-W Clean Product First-Pair — P3 Write-Only Offline Exact-Artifact R2 Physical Closure — 2026-10-08

```text
STATUS=CLOSED_PASS
GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_OFFLINE_ARTIFACT_R2_20261008_01
EXECUTED_STAGE=P3_WRITE_ONLY_SUCCESSOR_NO_PRODUCT_BOOT
EVIDENCE_PROVENANCE=OPERATOR_SUPPLIED_VERSIONED_EXECUTOR_JSON
HOST_PREFLIGHT_PASS=true
PR=522
PR_KEEP_OPEN_DRAFT_UNMERGED=true
STOP=true
```

## 1. Exact authority and successful preflight

The operator executed the authorized offline artifact R2 executor and supplied the complete public-safe terminal closure. The live result is sourced from that operator-provided JSON. Private raw esptool logs, downloaded binary bytes, raw board identity and local paths remain outside public GitHub.

```text
REPOSITORY=chrenguo-stack/HomeAssistant
EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p3_write_only_offline_artifact_r2/executor.py
EXECUTOR_BLOB_SHA=d6c8d63e20a53b3c8a626bd9d7d23f36b3fa24fc

EXPECTED_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
OBSERVED_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc
BOARD_PRECLAIM_PASS=true
PRECLAIM_PARTITION_WINDOW_BLANK=true
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
ESPTOOL_VERSION=5.3.1

PRODUCT_SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
PRODUCT_SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
ARTIFACT_ID=11469977052
BUILD_RUN_ID=37594598870
ARTIFACT_BINDING_PASS=true
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
```

The previously accepted P1 clean candidate and P2 preboot snapshot were preserved. P3 R3 previously proved the erased 0x8000/0x1000 partition window using the RAM stub. The present write-only successor independently rechecked the blank partition window before writing.

## 2. Actual physical write and four exact-length readbacks

```text
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_ALLOWED=false

FLASH_WRITE_ATTEMPTED=true
FOUR_REGION_WRITE=true
POTENTIAL_PARTIAL_WRITE=false
FULL_CHIP_ERASE=false

READBACK_VERIFY_BOOTLOADER=true
READBACK_VERIFY_PARTITIONS=true
READBACK_VERIFY_OTADATA=true
READBACK_VERIFY_FIRMWARE=true

P3_WRITE_ONLY_SUCCESSOR_PASS=true
READY_FOR_P4_AUTHORIZATION=true
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
AUTO_P4=false
P4_AUTHORIZATION_GRANTED=false
T1_MUTATION=false
BROKER_RESTART=false
MANAGER_RESTART=false
STOP=true
```

The executor requires every region to match both its exact source file length and its SHA256. The four frozen regions were:

| Offset | File | Exact bytes | Expected SHA256 | Readback |
| --- | --- | ---: | --- | --- |
| 0x0000 | bootloader.bin | 22576 | 985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5 | PASS |
| 0x8000 | partitions.bin | 3072 | 6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca | PASS |
| 0x9000 | ota_data_initial.bin | 8192 | 7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f | PASS |
| 0x10000 | firmware.bin | 1412672 | 4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65 | PASS |

The original no-stub SPI flash-access failure was bypassed using the flasher stub in RAM for flash access. The known `ARTIFACT_DOWNLOAD_FAILED` host-side failure was bypassed by strict local verification of the unmodified frozen GitHub artifact. Neither incident establishes a product-firmware defect.

## 3. Physical STOP state and authorization ledger

```text
P3_WRITE_ONLY_OFFLINE_R2_RESULT=CLOSED_PASS
P3_WRITE_ONLY_OFFLINE_R2_AUTHORIZATION_CLAIMED=true
P3_WRITE_ONLY_OFFLINE_R2_AUTHORIZATION_CONSUMED=true
P3_WRITE_ONLY_OFFLINE_R2_REPLAY=false

PRIOR_P3_WRITE_ONLY_ORIGINAL_AUTHORIZATION=SUPERSEDED_UNCLAIMED
PRIOR_P3_R2_AUTHORIZATION=CONSUMED_NO_REPLAY
PRIOR_P3_R3_AUTHORIZATION=CONSUMED_NO_REPLAY

CURRENT_BOARD_STATE=FOUR_REGIONS_WRITTEN_AND_EXACT_READBACK_PASS_NO_PRODUCT_BOOT
FULL_CHIP_ERASE_AGAIN=FORBIDDEN
FLASH_WRITE_AGAIN_WITH_THIS_AUTHORIZATION=FORBIDDEN
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
P4_AUTHORIZATION_GRANTED=false
P4_EXECUTED=false

AUTO_ERASE=false
AUTO_WRITE=false
AUTO_RETRY=false
AUTO_P4=false
STOP=true
```

P3 proves exact artifact/silicon binding, successful writes to the four designated regions, and independent exact-length readback verification. It does **not** prove a successful first normal boot, Wi-Fi provisioning, LCD pairing QR, Manager pending identity, Setup Secret handoff, Manager COMMIT, KF-050 reboot recovery, or A-to-B address relocation.

## 4. One next logical gate

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_FIRST_NORMAL_BOOT_PREEXECUTION_20261008_01
NEXT_GATE_SCOPE=READONLY_DESIGN_AND_FRESH_PREBOOT_AUTHORITY_REBIND
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_AUTO_EXECUTE=false
STOP=true
```

Before any normal product boot, use the existing clean-board physical-acceptance protocol as the authority: independently verify the current P2 Manager preboot identity snapshot and T1/Broker/Manager continuity as required by the P4 stage; preserve the exact written board/artifact lineage; define normal Wi-Fi provisioning and first-pair QR/Manager identity/Setup Secret/COMMIT/KF-050 STOP checkpoints. P4 remains a separate operator-approved physical gate; no board reset, power cycle, or normal boot is authorized by this closure.
