# N3-W Production Multi-Relay Gateway Selection V1 — Board C APP1 stale-image erase closure

Status: `CLOSED_PASS`

## Exact bounded erase result

```text
APP1_OFFSET=0x3D0000
APP1_SIZE=0x3C0000
APP1_READBACK_SIZE=3932160
APP1_ALL_FF_AFTER_ERASE=true

APP0_READBACK_SIZE=1392960
APP0_SHA256=c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a
APP0_EXACT_FIRMWARE_PRESERVED=true

APP1_STALE_IMAGE_ERASE=PASS
APP0_MUTATION=false
OTADATA_MUTATION=false
NVS_MUTATION=false
PARTITION_TABLE_MUTATION=false
FULL_FLASH_ERASE=false
RESULT=PASS
STOP=true
```

The stale valid ESP image previously present in APP1 was successfully erased. Full APP1
readback is all `0xFF`. The current exact production image in APP0 is unchanged and still
matches the frozen exact firmware SHA-256.

This closure does not identify the erased stale image's historical source. It only proves that
the alternate OTA slot no longer contains an executable image.

## Next route

Board C remains in the previously observed post-factory-reset state where Wi-Fi STA
configuration and N3-W provisioning must be restored. No product reflashing is required.

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_WIFI_REPROVISION_20260923_01
AUTO_EXECUTE_NEXT_GATE=false
```
