# N3-W PR #437 177468e Board B read-only write-target preflight

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Authority

```text
TASK=N3W_PR437_BOARD_B_WRITE_TARGET_PREFLIGHT_20260920_01
PRODUCT_SOURCE_HEAD=177468e290a207f2fb7f6c554aedf60b61373b4d
PRODUCT_SOURCE_TREE=a50ff98887b14b70cf9d278c6f8b7edf536eae88
ARTIFACT_ID=10607030747
ARTIFACT_NAME=n3w-pr437-boardb-exact-source
ARTIFACT_ZIP_SHA256=371d4369b791df527c595bc43ac203487f18a000b47ec73692d728ce58483dd8
APPLICATION_SHA256=74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

## Scope

This package performs only bounded ROM/esptool reads against the operator-selected Board B target.

It may reset the board into the ROM loader as part of esptool access, but it contains no flash-write command, no erase command, no application-serial observation, no product-NVS mutation, and no T1 access.

The checks are:
- esptool major version 5;
- ESP32-C6 target;
- public-safe hardware identity hash against the repository-frozen Board B reference;
- Secure Boot disabled;
- Flash Encryption disabled;
- 8MB flash;
- read-only partition-table readback at 0x8000 / 0xC00;
- partition-table SHA-256 match.

The 2026-09-19 operator identity override is explicitly non-reusable. If the automated identity comparison fails, this preflight stops before partition inspection and before any write. A later write requires a separate explicit authorization.

## Frozen compatibility binding

```text
REFERENCE_HARDWARE_ID_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
PARTITION_TABLE_OFFSET=0x8000
PARTITION_TABLE_SIZE=0xC00
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

The Phase4 target remains ESP32-C6 / 8MB / ESP-IDF. No partition-layout setting changed between the prior artifact target and 177468e; the fresh readback is still required and fail-closed.

## Execution

Example operator command:

```bash
python tools/execution_packages/n3w/kf096/pr437_177468e_board_b_preflight/executor.py \
  --port /dev/cu.usbmodem14101 \
  --output /tmp/n3w-pr437-177468e-boardb-preflight.json
```

The JSON output is private-local evidence because it binds the local port locator by SHA-256. Only public-safe results should be copied into GitHub.

## Boundary

```text
BOARD_ACCESS_REQUIRED=true
PREFLIGHT_READ_ONLY=true
ROM_ESPTOOL_ACCESS=true
APPLICATION_SERIAL_OPEN=false
FLASH_WRITE=false
PRODUCT_NVS_WRITE=false
T1_MUTATION=false
WRITE_AUTHORIZATION=false
```
