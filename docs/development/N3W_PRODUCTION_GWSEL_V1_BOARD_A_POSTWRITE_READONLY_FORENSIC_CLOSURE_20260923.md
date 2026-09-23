# N3-W Production Gateway Selection V1
## Board A Postwrite Readonly Forensic Closure — 2026-09-23

Status: `CLOSED_PASS`

## Gate

```text
TASK=
N3W_PRODUCTION_GWSEL_V1_BOARD_A_POSTWRITE_READONLY_FORENSIC_20260923_01

BOARD_LABEL=A
READ_ONLY=true
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_MUTATION_DURING_FORENSIC=false
```

## Trigger

The authorized Board A exact write had already completed the write command but the
old executor returned:

```text
STOP=post-write OTA-data readback SHA256 mismatch
BOARD_A_EXACT_WRITE_R3_EXIT_CODE=2
```

No retry, erase or reflash was permitted.

## Fresh readonly evidence

```text
BOARD_A_POSTWRITE_IDENTITY_BINDING=PASS
CHIP=ESP32-C6
SECURE_BOOT=false
FLASH_ENCRYPTION=false
FLASH_SIZE=8MB

BOARD_A_OTADATA_RUNTIME_STATE=PASS
OTADATA_OTA_SEQ=1
OTADATA_STATE=VALID
OTADATA_CRC=0x4743989a
OTADATA_RUNTIME_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3

BOARD_A_APPLICATION_READBACK_VERIFY=PASS
APPLICATION_READBACK_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

BOARD_A_PARTITION_TABLE_PRESERVED=PASS
PARTITION_TABLE_READBACK_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

BOARD_A_POSTWRITE_READONLY_FORENSIC=PASS
FLASH_READ=true
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_MUTATION_DURING_FORENSIC=false
```

## Adjudication

The application bytes are an exact match to the frozen production artifact and the
partition table is unchanged. The OTA-data region is the deterministic runtime OTA0
selection state produced after the write command's hard reset.

Therefore:

```text
BOARD_A_WRITE_FLASH_EXECUTED=true
BOARD_A_EXACT_ARTIFACT_APPLICATION_BINDING=PASS
BOARD_A_PARTITION_TABLE_PRESERVED=PASS
BOARD_A_BOOT_SELECTION_STATE=VALID_OTA0

BOARD_A_EXACT_WRITE_PHYSICAL_RESULT=PASS_AFTER_READONLY_FORENSIC
BOARD_A_REFLASH_REQUIRED=false
AUTO_REFLASH=false
AUTO_ERASE=false
```

This closes the physical write result only. Product runtime Direct/MQTT acceptance
remains a separate later gate.
