# N3-W R1 Off-Channel ESP-NOW — Preflash Backup Failure Closeout

Date: 2026-09-05  
Document class: `PHYSICAL_GATE_STOP_CLOSEOUT`  
Parent experiment: `ESPRESSIF_OFFICIAL_OFF_CHANNEL_ESPNOW_API_BASELINE`  
Execution: `N3W-R1-OFFICIAL-OFFCHANNEL-ESPNOW-TWO-BOARD-PHYSICAL-BASELINE-20260905-01`

## 1. Result

The R1 physical gate stopped during the fresh preflash backup stage before any diagnostic firmware was written.

```text
GATE_RESULT=STOP_PREFLASH_BACKUP_FAILED
OFFICIAL_OFFCHANNEL_ESPNOW_API_BASELINE=NOT_ESTABLISHED
FLASH_WRITE=false
RF_EXECUTION=false
```

No R1A/R1B/R1C/R1D radio case was executed and no restore write was required.

## 2. Frozen authorities

```text
CURRENT_MAIN=127c3f1e89baaaba7b7fd60d6d263632d30b2461
CURRENT_TREE=32135508818124e848bc895073b3cb6aaa6b9af3
PRODUCT_SOURCE_AUTHORITY=bff94bc4922d7a984eb1363cc24a163ad466a166

LOCAL_ARTIFACT_ZIP_SHA256=a2e9308786dfae83d0f2c386362073e6fbf95a61c7f631987085507324c638ce
REFERENCE_ARTIFACT_AUTHORITY=PASS

R1_DIAGNOSTIC_COMMIT=44b166c0a3c1565937363381d0ed274a50b9d6bf
R1_DIAGNOSTIC_SOURCE_TREE_HASH=79142f0792a5e295dc8733d93332835a2e456d91
DIAGNOSTIC_MAIN_SHA256=cd50b8b75465cbc5a7bd2bf811781b5b469e741c3748967c2890667061530618
```

## 3. Board identity and security preflight

```text
CONTROL=BOARD_A
CONTROL_PORT=/dev/cu.usbmodem14201
CONTROL_BASE_MAC=98:a3:16:a9:f4:5c
CONTROL_CHIP=ESP32-C6
CONTROL_REVISION=v0.2
CONTROL_PHYSICAL_FLASH_SIZE=8MB
CONTROL_SECURE_BOOT_ENABLED=false
CONTROL_FLASH_ENCRYPTION_ENABLED=false

DUT=BOARD_B
DUT_PORT=/dev/cu.usbmodem14101
DUT_BASE_MAC=98:a3:16:a9:f3:50
DUT_CHIP=ESP32-C6
DUT_REVISION=v0.2
DUT_PHYSICAL_FLASH_SIZE=8MB
DUT_SECURE_BOOT_ENABLED=false
DUT_FLASH_ENCRYPTION_ENABLED=false
```

Board C was not accessed.

## 4. Failure evidence

Board A full 8 MB preflash read failed at approximately 2.3% progress with:

```text
A fatal error occurred: Corrupt data, expected 0x1000 bytes but received 0xfd9 bytes.
```

The backup was incomplete and no canonical SHA-256 was computed.

```text
CONTROL_PREFLASH_SIZE=FAILED_INCOMPLETE
CONTROL_PREFLASH_SHA256=NOT_COMPUTED
DUT_PREFLASH_SIZE=NOT_EXECUTED
DUT_PREFLASH_SHA256=NOT_EXECUTED
```

This failure occurred in the host↔board flash-read transport stage. It does not establish an R1 API failure, an ESP-NOW failure, a product-source failure, or a Board A flash-content defect.

## 5. Scope integrity

```text
BOARD_A_ACCESS=true
BOARD_B_ACCESS=true
BOARD_C_ACCESS=false
USB_ACCESS=true
FLASH_READ=true
FLASH_WRITE=false
SERIAL_OPEN=false
RF_EXECUTION=false

HOMEASSISTANT_MAIN_WRITE=false
PRODUCT_SOURCE_CHANGED=false
PR361_CHANGED=false
T1_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
DYNSEC_MUTATION=false
EFUSE_WRITE=false
```

## 6. High-level disposition

The R1 build/source/artifact authority remains valid and unchanged. The physical R1 result remains `NOT_ESTABLISHED` because the gate never reached reference flashing or RF execution.

The next action is a separate bounded, read-only classifier for the Board A USB/flash-read transport. The classifier should first exclude competing serial access and then attempt a conservative full-flash read without any flash write. Only after a complete current-state backup is proven should the R1 physical gate be re-authorized.

```text
R1_BUILD_AUTHORITY=FROZEN_PASS
R1_PHYSICAL_BASELINE=NOT_ESTABLISHED
FAILURE_CLASS=HOST_BOARD_FLASH_READ_TRANSPORT_CORRUPTION
PRODUCT_FAILURE=false
ESPNOW_API_FAILURE=false
RF_FAILURE=false
NEXT_ROUTE=BOARD_A_USB_FLASH_READ_TRANSPORT_RECOVERY
```
