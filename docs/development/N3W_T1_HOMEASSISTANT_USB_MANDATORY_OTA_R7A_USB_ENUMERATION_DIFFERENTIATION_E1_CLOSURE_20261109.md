# N3-W T1 Home Assistant mandatory-USB OTA R7A
# USB enumeration differentiation E1 closure — 2026-11-09

## 1. Result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_USB_ENUMERATION_DIFFERENTIATION_E1_20261109_01
RESULT=CLOSED_PASS
```

E1 differentiated the failed T1 USB enumeration from a completely failed test USB by moving
the same device to a known-good Mac after a bounded single unplug.

## 2. T1 post-unplug state

```text
TRANSACTION_PHASE=U1_PREPARE_REQUESTED
TRANSACTION_STATUS=ACTIVE
USB_CONFIRMATION_REQUIRED=false
USB_CANDIDATE=null
PREPARE_ERROR_CODE=null
LSUSB_NON_ROOT_DEVICE_COUNT=0
USB_LIKE_BLOCK_DISK_COUNT=0
SCSI_DISK_COUNT=0
HOST_DAEMON_ACTIVE=true
E1_T1_POST_UNPLUG=PASS
```

The live U1 transaction remained intact and healthy.

## 3. Same-device Mac enumeration

The same physical test USB enumerated successfully on the Mac:

```text
PRODUCT=MXT USB Device
VID=aaaa
PID=8816
USB_SPEED=Up to 480 Mb/s
CURRENT_REQUIRED=100 mA
CAPACITY=31,914,983,424 bytes
BSD_NAME=disk2
EXTERNAL_PHYSICAL=true
PARTITION_MAP=MBR
FILESYSTEM=MS-DOS FAT32
REMOVABLE_MEDIA=true
SMART=Verified
```

This proves the device can complete descriptor enumeration, expose a mass-storage logical unit,
and present a block disk on another known-good host.

## 4. Classification

```text
TEST_USB_COMPLETELY_DEAD=false
T1_DESCRIPTOR_TIMEOUT_WAS_REAL=true
PRODUCT_CANDIDATE_LAYER_REACHED_ON_T1=false
PRODUCT_SOURCE_BLOCKER_PROVEN=false
T1_HARDWARE_FAULT_PROVEN=false
REMAINING_FAULT_DOMAIN=T1_USB_PATH_OR_DEVICE_SPECIFIC_T1_COMPATIBILITY
NEW_KF_REQUIRED=NOT_YET_DETERMINED
```

The evidence does not yet distinguish:
- a transient/contact event on the first T1 insertion;
- T1 USB-port power or signal-integrity behavior;
- T1 xHCI/kernel compatibility with this device;
- a T1-specific issue affecting all USB mass-storage devices.

## 5. Safety boundary

```text
T1_REINSERT_AUTHORIZED=false
SECOND_USB_AUTHORIZED=false
PREPARE_REPLAY_AUTHORIZED=false
CONFIRM_USB_ERASE_AUTHORIZED=false
SERVICE_RESTART_AUTHORIZED=false
U2_PLUS_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE=false
```

E1 is complete. The next physical diagnostic gate requires separate authorization.
