# N3W KF-089 ID12 pre-board esptool wrapper permission STOP — 2026-09-12

```text
AUTHORIZATION_ID=N3W_KF089_ID11_AB_SCHEMA_V5_READONLY_RECOVERY_20260912_12
ID12_CLAIMED=true
BOARD_B_IDENTITY_PASS=NOT_EXECUTED
BOARD_B_NVS_READ_PASS=NOT_EXECUTED
BOARD_A_IDENTITY_PASS=NOT_EXECUTED
BOARD_A_NVS_READ_PASS=NOT_EXECUTED
FIRST_UNPROVEN_OR_FAILED_STAGE=BOARD_B_IDENTITY_COMMAND_START
RAW_EVIDENCE_PERSISTED=false
SECOND_RF_CAPTURE=false
APPLICATION_BOOT=false
FLASH_WRITE=false
NVS_WRITE=false
AUTO_RETRY=false
RESULT=STOP
STOP_REASON=esptool wrapper lacked executable permission; command failed before read-mac and before Board B access.
```

## Adjudication

- The ID11 RF capture remains the only RF capture and is not invalidated by this host-side failure.
- No Board B or Board A device access occurred under ID12.
- No application boot, flash write, NVS write, otadata write, pairing change, or T1 mutation occurred.
- The failure is host/tool invocation only. It is not evidence of an N3-W product-path failure.
- ID12 is retired because it was claimed. Do not replay it.

## Next gate

Host-only repair of the read-only recovery toolchain invocation. The exact ESP-IDF/esptool Python wrapper must be invoked through the exact bound Python interpreter rather than relying on the wrapper file executable bit. The repair must be shared durably, tested with a non-executable wrapper fixture, and must preserve the existing read-only contract (`read-mac` / `read-flash` only) before any new physical authorization is proposed.
