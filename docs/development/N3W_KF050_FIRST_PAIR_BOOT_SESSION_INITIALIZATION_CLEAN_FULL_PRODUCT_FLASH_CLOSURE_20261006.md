# N3-W KF-050 First-Pair Boot-Session Initialization — Clean Full Product Flash Closure — 2026-10-06

```text
TASK=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_CLEAN_FULL_PRODUCT_FLASH_20261006_01
STATUS=CLOSED_PASS
CLEAN_FULL_PRODUCT_FLASH=PASS
FULL_FLASH_ERASE=true
FOUR_REGION_WRITE=true
READBACK_VERIFY=PASS
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
AFTER_OPERATION=no-reset
T1_MUTATION=false
MANAGER_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MERGE=false
```

## 1. Entry authority

Stage P1 clean-board eligibility and Stage P2 healthy Broker-A preparation were both already CLOSED_PASS before this board mutation gate began.

The exact product artifact authority remained:

```text
SOURCE_HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
SOURCE_TREE=f45ca257de0b6e41f0458346711bb4e105ba1fcc
WORKFLOW_RUN_ID=37249933019
ARTIFACT_ID=11320812037
ARTIFACT_NAME=n3w-kf050-first-pair-f1rc2-157448b-exact-source
RELEASE_ZIP_SHA256=44610382a0e7d9c04e4445e873b9d99fd9a781d18fd497f39cb382d3fce3b3ff
```

The P3-A read-only rebind immediately before mutation reconfirmed the same qualified clean board:

```text
HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
PARTITION_TABLE_STATE=BLANK
NVS_PARTITION_COUNT=0
OLD_N3W_STATE_ABSENT=true
```

No erase or write had occurred before that rebind.

## 2. Exact write layout

The exact artifact `flash_args` contract was used:

```text
FLASH_MODE=dio
FLASH_FREQ=80m
FLASH_SIZE=8MB
0x0000  bootloader.bin
0x8000  partitions.bin
0x9000  ota_data_initial.bin
0x10000 firmware.bin
```

The board was then formally initialized with one full-chip erase followed by one four-region write from the same release ZIP.

## 3. Readback verification

Every written region was read back from the board and SHA-256 checked against the bound artifact.

```text
BOOTLOADER_OFFSET=0x0000
BOOTLOADER_SIZE=22576
BOOTLOADER_EXPECTED_SHA256=e36ee1eaa32780c74612ea512164fa56770744fbefa1e34df2fab36de76b4b97
BOOTLOADER_READBACK_SHA256=e36ee1eaa32780c74612ea512164fa56770744fbefa1e34df2fab36de76b4b97
BOOTLOADER_READBACK=PASS

PARTITIONS_OFFSET=0x8000
PARTITIONS_SIZE=3072
PARTITIONS_EXPECTED_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
PARTITIONS_READBACK_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
PARTITIONS_READBACK=PASS

OTADATA_OFFSET=0x9000
OTADATA_SIZE=8192
OTADATA_EXPECTED_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
OTADATA_READBACK_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
OTADATA_READBACK=PASS

FIRMWARE_OFFSET=0x10000
FIRMWARE_SIZE=1410080
FIRMWARE_EXPECTED_SHA256=4595edea29c93b3618435035bd87e3740f3c8afd0b663dc0b21ef65de343cd6b
FIRMWARE_READBACK_SHA256=4595edea29c93b3618435035bd87e3740f3c8afd0b663dc0b21ef65de343cd6b
FIRMWARE_READBACK=PASS
```

Therefore the board contains the exact frozen production image in all four required regions.

## 4. P4 clean-start preservation

All esptool operations used `--after no-reset`.

Final execution evidence:

```text
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED=false
AFTER_OPERATION=no-reset
```

The product firmware therefore was not intentionally allowed to enter its normal runtime after the write/readback sequence. This preserves the P4 first-pair interruption acceptance starting condition.

The board must remain connected and must not be manually reset, power-cycled, unplugged, or otherwise allowed to perform an uncontrolled first normal boot before the P4 procedure begins.

## 5. Non-actions

```text
T1_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
PAIRING_REPAIR=false
RECOVERY_FLOOR_EXECUTION=false
LEGACY_RECOVERY_HELPER=false
```

## 6. Gate decision

Stage P3 requirements are satisfied.

```text
CLEAN_FULL_PRODUCT_FLASH=PASS
EXACT_FOUR_REGION_IMAGE=PASS
READBACK_VERIFY=PASS
FORMAL_PAIRING_STARTED=false
RESULT=CLOSED_PASS
```

The next stage is the first normal product boot, ordinary pairing, and the KF-050 controlled interruption acceptance. It requires separate authorization because it deliberately starts product runtime and includes one controlled power interruption/reboot in the narrow post-COMMIT/pre-first-canonical window.

```text
NEXT_ONE_GATE=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_FIRST_PAIR_INTERRUPTION_ACCEPTANCE_20261006_01
BOARD_ERASE=false
BOARD_REFLASH=false
PAIRING_REPAIR=false
MANAGER_REPLAY_CLEAR=false
MANAGER_HIGH_WATER_CLEAR=false
T1_MUTATION=false
MERGE=false
STOP=true
```