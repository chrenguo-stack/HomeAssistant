# N3-W Auto Safe Fallback — Gate F Board B Write Evidence

Date: 2026-10-04

## Scope

This record captures the successful Board B write and post-write readback for Gate F physical acceptance preparation.

## Frozen production source and artifact

```text
PRODUCT_SOURCE_HEAD=b2419d17c198a85b7b50d9c1771544c2e3a0ab6b
PRODUCT_SOURCE_TREE=c138ac3efa9b23b4d083f0cb5248089fef493416
WORKFLOW_RUN_ID=37123365844
ARTIFACT_ID=11273613346
ARTIFACT_ZIP_SHA256=57465f56362404b269f80adb21994a22ec0d1acdcc724f9a163c84b6df3eea4d
RELEASE_BUNDLE_SHA256=7bf9980e50d2baa26459ca020002e8947d8038409dcb564a0101131be1799a6a
APPLICATION_SHA256=474e738068fc894b20cfe5f647a6112b66c141aa86c873d414d8ed183679e43c
OTADATA_INITIAL_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

## Preflight evidence

```text
PREFLIGHT=PASS
HARDWARE_ID_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
FLASH_WRITE=false
```

Preflight executor focused CI:

```text
RUN_ID=37176041943
RESULT=PASS
```

## Write evidence

```text
BOARD_B_WRITE=PASS
HARDWARE_ID_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
OTADATA_INITIAL_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
APPLICATION_SHA256=474e738068fc894b20cfe5f647a6112b66c141aa86c873d414d8ed183679e43c
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

Write executor focused CI:

```text
RUN_ID=37180482741
RESULT=PASS
```

## Post-write readback

The board was allowed to boot after the write, then both OTA-data and application regions were read back through ROM/esptool.

```text
OTADATA_READBACK_SIZE=8192
OTADATA_READBACK_SHA256=8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
APPLICATION_READBACK_SIZE=1408416
APPLICATION_READBACK_SHA256=474e738068fc894b20cfe5f647a6112b66c141aa86c873d414d8ed183679e43c
```

Interpretation:

- application readback is an exact match to the frozen artifact: PASS;
- OTA-data readback is intentionally evaluated as runtime boot state, not as an immutable copy of `ota_data_initial.bin` after the board has booted;
- the observed runtime OTA-data SHA256 exactly matches the previously recorded final N3-W otadata SHA256 from the F350 physical-acceptance archive: `8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3`;
- ESP-IDF OTA semantics permit the OTA-data partition to change as boot/OTA state is selected or confirmed.

```text
BOARD_B_APPLICATION_POSTWRITE_READBACK=PASS
BOARD_B_RUNTIME_OTADATA_KNOWN_STATE_MATCH=PASS
BOARD_B_POSTWRITE_READBACK=PASS
```

## Boundary after post-write readback

```text
BOARD_B_WRITE_COMPLETE=true
BOARD_B_POSTWRITE_READBACK_COMPLETE=true
USB_DIRECT_BASELINE_COMPLETE=false
T1_LIVE_MUTATION=false
PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
MERGE=false
```

The next required step is USB Direct baseline before any T1 address-change experiment.
