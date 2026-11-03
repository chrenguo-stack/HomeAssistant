# N3-W R3 exact factory write/verify closure and Captive Portal preparation — 2026-11-03

## Physical write result

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_EXACT_FACTORY_WRITE_VERIFY_20261103_01
RESULT=PASS

BOARD_USB_TARGET_COUNT=1
BOARD_CHIP=ESP32-C6
BOARD_PACKAGE=QFN40
BOARD_REVISION=v0.2
BOARD_FLASH_SIZE=8MB

SOURCE_HEAD=414ff0290db37e89a0e137d30f491e6c17cba2b0
MERGED_MAIN=c93fc3561ecee6dda13306804a3168a9c12ffe3a
SOURCE_TREE=d4fadc4e036bcd01416ea9f7ade226fe2d20e5c7
MERGED_MAIN_TREE=d4fadc4e036bcd01416ea9f7ade226fe2d20e5c7
TREE_IDENTICAL=true

ARTIFACT_ID=13203682791
ARTIFACT_DIGEST=sha256:cbb227968c215e39c053151bf6946241cc44dbc230a6e5c4ceb0917f9f25c733
TARGET_BLOB=6b37be9e3f281b8abcdf4443103ccb65f7920cd2
BATTERY_LOW_THRESHOLD=-1.00V
PRODUCTION_ELIGIBLE=false

FACTORY_FILE=firmware.factory.bin
FACTORY_OFFSET=0x0
FACTORY_SIZE=1532256
FACTORY_SHA256=9ccc469898832bda612634aef64ca946631e81574076be504ef864aaee56d8f9

ERASE_FLASH=PASS
WRITE_FLASH=PASS
WRITE_HASH_VERIFY=PASS
VERIFY_FLASH=PASS
POSTWRITE_BOARD_IDENTITY=PASS

FLASH_MUTATION=true
NVS_ERASED=true
T1_MUTATION=false
FIRST_REGISTRATION_STARTED=false
```

The exact factory image was erased/written/verified successfully. The independent esptool verify step reported a matching digest. The board was hard-reset only after verification.

Raw MAC address and exact local USB locator are intentionally excluded from public GitHub.

## Temporary low-battery bypass

The R3 physical-acceptance target uses the previously proven development override:

```text
battery_low_threshold=-1.00V
```

The shared production base remains `3.00V`. This R3 artifact is not production eligible. Before production release the override must be removed and a new exact production artifact built.

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_R3_SENSORLESS_CAPTIVE_PORTAL_WIFI_SETUP_AND_IDLE_QR_20261103_01

ALLOWED=BOARD_BOOT;CAPTIVE_PORTAL_WIFI_SETUP;READONLY_SERIAL_OBSERVATION;LCD_IDLE_QR_OBSERVATION
FORBIDDEN=QR_CONFIRM;47110_REGISTRATION_CONFIRM;47112_PAIRING;DIRECT_DB_WRITE;DIRECT_CREDENTIAL_INJECTION;T1_MUTATION

FIRST_REGISTRATION_STARTED=false
```

The goal is to place the freshly erased/written board on the trusted product LAN through the normal product Captive Portal flow and prove the board reaches the idle unregistered QR state. Stop before the user confirms a T1 or starts first registration.
