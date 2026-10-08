# N3-W Auto Safe Fallback Gate F — R2 Board B Write Preflight — 2026-10-04

Status: `PASS`

## Exact artifact binding

```text
WORKFLOW_RUN_ID=37204582611
ARTIFACT_ID=11303803442
ARTIFACT_NAME=n3w-auto-safe-fallback-f1rc2-67a0460-r2-exact-source
ARTIFACT_OUTER_SHA256=be604ae4bba09d1a675017518a8847fdd655f2f5bb64dca200bb6e8d49378582
ARTIFACT_INNER_SHA256=ae80eeb6a36d250ecdd3123f8ac084e40d7f4a47f7331b91a1d8b91818c74e7c
SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
APPLICATION_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
FACTORY_SHA256=ab47b2604eb2af6000e3bea05a88c791dcda84bcfd7eeb56619172d75576a295
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
BINARY_DEHARNESS_PROOF=PASS
DIRECT_MQTT_RELOCATION_R2_MARKERS=PASS
```

## Board B read-only preflight

Exact private board identifiers are intentionally omitted from the public repository.

```text
R2_ARTIFACT_BINDING=PASS
CHIP_MATCH=true
BOARD_B_ROM_IDENTITY_MATCH=true
FLASH_SIZE_MATCH=true
SECURE_BOOT=false
FLASH_ENCRYPTION=false
BOARD_PARTITION_TABLE_MATCH=true
BOARD_B_R2_WRITE_PREFLIGHT=PASS
FLASH_WRITE=false
T1_MUTATION=false
```

The board partition table matches the frozen artifact. Secure Boot and Flash Encryption are disabled. The expected Board B ROM identity and 8 MiB flash geometry were confirmed read-only before any R2 write.

## Authorized minimal write boundary

The next mutation is restricted to:

```text
0x9000  ota_data_initial.bin
0x10000 firmware.bin
```

The following remain prohibited in this gate:

```text
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
T1_MUTATION=false
MERGE=false
```

This preserves the existing durable pairing / credential / stale-Broker NVS state so the repaired exact artifact can be tested against the same physical stale-Broker oracle.
