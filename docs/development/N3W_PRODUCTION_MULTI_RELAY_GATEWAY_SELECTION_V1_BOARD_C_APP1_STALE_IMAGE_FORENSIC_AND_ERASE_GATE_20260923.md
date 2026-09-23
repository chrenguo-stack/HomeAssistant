# N3-W Production Multi-Relay Gateway Selection V1 — Board C APP1 stale image forensic and erase gate

Status: `ERASE_AUTHORIZED`

## Read-only forensic result

Board C APP1 was read from the exact partition range:

```text
APP1_OFFSET=0x3D0000
APP1_SIZE=0x3C0000
APP1_SLOT_SIZE=3932160
APP1_ALL_FF=false
APP1_VALID_ESP_IMAGE_HEADER=true
APP1_PREFIX_SHA256=28e408354742384e713d07dde1984f3b6e08b8dd7010052acab34519e3c78207
APP1_MATCHES_CURRENT_EXACT_FIRMWARE=false
APP1_DIFFERENT_VALID_IMAGE_PRESENT=true
APP1_NONIMAGE_RESIDUAL_DATA_PRESENT=false
FLASH_WRITE=false
NVS_WRITE=false
RESULT=COMPLETE
```

This proves that APP1 contains a valid ESP application image different from the current exact
production image. The readback does not by itself identify that stale image as the operator's
historical battery/sleep YAML test firmware.

The currently running application was independently observed booting from APP0 at
`0x10000`, so the stale APP1 image is not the application currently executing.

## Authorized mutation

The operator previously authorized erasing the stale test image if present. This gate therefore
authorizes only the APP1 partition erase:

```text
ERASE_START=0x3D0000
ERASE_LENGTH=0x3C0000
ERASE_END_EXCLUSIVE=0x790000
APP0_MUTATION=false
OTADATA_MUTATION=false
NVS_MUTATION=false
PARTITION_TABLE_MUTATION=false
FULL_FLASH_ERASE=false
```

The erase range ends exactly at the start of NVS.

## Acceptance

PASS requires a full readback of APP1 after erase to contain only `0xFF`, and the current APP0
exact firmware prefix to retain SHA-256:

`c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a`

After PASS, execution returns to Board C Wi-Fi/N3-W reprovisioning. No automatic successor is
executed from this gate.
