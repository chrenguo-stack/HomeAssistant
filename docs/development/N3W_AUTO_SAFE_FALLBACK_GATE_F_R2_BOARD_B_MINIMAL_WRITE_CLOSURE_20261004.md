# N3-W Auto Safe Fallback Gate F R2 — Board B Minimal Write Closure — 2026-10-04

Status: `CLOSED_PASS`

## Frozen artifact

```text
SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
APPLICATION_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
OTADATA_INITIAL_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

## Minimal write

Only the OTA data initial image and application image were written.

```text
OTADATA_WRITE_OFFSET=0x9000
APPLICATION_WRITE_OFFSET=0x10000
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
T1_MUTATION=false
```

Esptool reported hash verification PASS for both written images.

Post-write readback established:

```text
APPLICATION_POSTWRITE_MATCH=true
APPLICATION_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
PARTITION_TABLE_POSTWRITE_MATCH=true
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

The first harness incorrectly required post-boot OTA metadata to remain byte-identical to `ota_data_initial.bin`. That is not a valid post-boot oracle because boot/OTA selection updates runtime OTA metadata.

A read-only reconciliation then read the full runtime OTA-data region twice after boot:

```text
RUNTIME_OTADATA_SHA256_1=8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
RUNTIME_OTADATA_SHA256_2=8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
RUNTIME_OTADATA_STABLE=true
```

Therefore:

```text
BOARD_B_R2_MINIMAL_WRITE=PASS
POSTWRITE_OTADATA_INITIAL_EQUALITY_FALSE_NEGATIVE=CLOSED
APPLICATION_READBACK=PASS
PARTITION_TABLE_PRESERVATION=PASS
RUNTIME_OTADATA_KNOWN_STABLE_STATE=PASS
PRODUCT_NVS_PRESERVED_BY_WRITE_PLAN=true
```

## Next gate

Proceed to the stale-Broker runtime-recovery physical acceptance without mutating the persisted Broker configuration or T1. Use a controlled reboot as the timing origin so RAM-only relocation state is discarded, then require rediscovery/reconnect within the frozen recovery budget.

```text
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_F_R2_STALE_BROKER_RUNTIME_RECOVERY_ACCEPTANCE_20261004_01
MERGE=false
```
