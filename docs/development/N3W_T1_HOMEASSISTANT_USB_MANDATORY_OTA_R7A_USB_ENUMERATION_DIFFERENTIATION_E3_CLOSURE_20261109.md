# N3-W T1 Home Assistant mandatory-USB OTA R7A
# USB enumeration differentiation E3 closure — second-device PASS — 2026-11-09

## 1. Gate result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_USB_ENUMERATION_DIFFERENTIATION_E3_SECOND_DEVICE_20261109_01
RESULT=CLOSED_PASS
PR=800
```

E3 replaced the original MXT USB device with one second known-good USB mass-storage device while
preserving the same T1 USB port, xHCI path, kernel and live U1 transaction.

## 2. Preserved live transaction

```text
TRANSACTION_PHASE=U1_PREPARE_REQUESTED
TRANSACTION_STATUS=ACTIVE
PUBLIC_PHASE=USB_REQUIRED_CONFIRMATION
USB_CONFIRMATION_REQUIRED=true
USB_CONFIRMATION_CONSUMED=false
PREPARE_ERROR_CODE=null
```

The live transaction remained intact. PREPARE was not replayed.

## 3. Second-device enumeration evidence

The second device enumerated successfully on T1:

```text
USB_CANDIDATE_PRESENT=true
USB_CANDIDATE_MODEL=Extreme
USB_CANDIDATE_CAPACITY_BYTES=32017047552

LSUSB_NON_ROOT_DEVICE_COUNT=1
USB_LIKE_BLOCK_DISK_COUNT=1
SCSI_DISK_COUNT=1
USB_BLOCK_DEVICE=/dev/sda
USB_TRAN=usb
USB_SERIAL_PRESENT=true
USB_WWN_PRESENT=false

NEW_USB_DESCRIPTOR_TIMEOUT=false
NEW_USB_UNABLE_TO_ENUMERATE=false
USB_MASS_STORAGE_DETECTED=true
SCSI_REMOVABLE_DISK_ATTACHED=true
```

Kernel evidence showed successful descriptor enumeration, USB Mass Storage binding, SCSI host creation,
and attachment of the removable block disk. The raw serial is intentionally not retained in this document.

## 4. Differentiation conclusion

The full evidence chain is now:

```text
ORIGINAL_MXT_T1_INSERTION_1=DESCRIPTOR_TIMEOUT_-110
ORIGINAL_MXT_MAC_ENUMERATION=PASS
ORIGINAL_MXT_T1_INSERTION_2=DESCRIPTOR_TIMEOUT_-110
SECOND_KNOWN_GOOD_USB_T1_ENUMERATION=PASS
SECOND_USB_R7A_CANDIDATE_DISCOVERY=PASS
```

Therefore:

```text
T1_USB_PATH_GENERAL_FAILURE=false
R7A_USB_CANDIDATE_DISCOVERY_PATH=PASS
ORIGINAL_MXT_DEVICE_SPECIFIC_COMPATIBILITY=CONFIRMED_AS_PRIMARY_DIRECTION
PRODUCT_SOURCE_BLOCKER_PROVEN=false
PERMANENT_T1_HARDWARE_FAULT_PROVEN=false
NEW_KF_REQUIRED=NO_SOURCE_KF_FROM_E3
```

This result does not claim that every USB mass-storage device is compatible. It proves that the T1 path and
R7A candidate logic function with the tested second device, and that the original MXT device is the isolated
compatibility outlier in this test chain.

## 5. Safety boundary

```text
SECOND_USB_CURRENTLY_INSERTED=true
PUBLIC_PHASE=USB_REQUIRED_CONFIRMATION
CONFIRM_USB_ERASE_AUTHORIZED=false
PREPARE_REPLAY_AUTHORIZED=false
U2_PLUS_AUTHORIZED=false
SERVICE_RESTART_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE=false
STOP=true
```

The next gate is the destructive USB confirmation boundary. It requires separate explicit authorization.
No erase, partitioning, mkfs, mount, target download or U2+ action occurred in E3.
