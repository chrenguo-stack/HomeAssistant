# N3-W Auto Safe Fallback Gate F R2 Post-write OTADATA Reconciliation — 2026-10-04

Status: `POSTWRITE_HARNESS_FALSE_NEGATIVE_RECONCILIATION_IN_PROGRESS`

## Exact artifact and write

```text
SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
APPLICATION_EXPECTED_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
INITIAL_OTADATA_EXPECTED_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PARTITION_TABLE_EXPECTED_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

The minimal write targeted only:

```text
0x9000 ota_data_initial.bin
0x10000 firmware.bin
```

No bootloader, partition-table, product-NVS, full erase, or T1 mutation was performed.

The esptool write itself verified both written data ranges before the first hard reset.

## Post-write readback

```text
APPLICATION_POSTWRITE_MATCH=true
APPLICATION_POSTWRITE_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
PARTITION_TABLE_POSTWRITE_MATCH=true
PARTITION_TABLE_POSTWRITE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTADATA_POSTBOOT_EQUALS_INITIAL=false
OTADATA_POSTBOOT_SHA256=8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
```

The original harness labeled the whole minimal write FAIL because it required runtime otadata bytes to remain equal to the static `ota_data_initial.bin` file after multiple hard resets.

That condition is not a valid post-boot oracle. The previous Gate F evidence already used a `BOARD_B_RUNTIME_OTADATA_KNOWN_STATE_MATCH` criterion rather than requiring post-boot bytes to remain equal to the initial image.

## Current classification

```text
APPLICATION_WRITE_AND_READBACK=PASS
PARTITION_TABLE_PRESERVATION=PASS
OTADATA_INITIAL_WRITE_IMMEDIATE_VERIFY=PASS
OTADATA_POSTBOOT_INITIAL_IMAGE_EQUALITY=NON_GATING
POSTWRITE_HARNESS_FALSE_NEGATIVE=SUPPORTED
BOARD_B_R2_MINIMAL_WRITE_FINAL_DISPOSITION=PENDING_RUNTIME_OTADATA_RECONCILIATION
T1_MUTATION=false
MERGE=false
```

Do not repeat the flash write solely because the post-boot otadata hash differs from the static initial image. First reconcile runtime otadata and then continue with stale-Broker physical acceptance.
