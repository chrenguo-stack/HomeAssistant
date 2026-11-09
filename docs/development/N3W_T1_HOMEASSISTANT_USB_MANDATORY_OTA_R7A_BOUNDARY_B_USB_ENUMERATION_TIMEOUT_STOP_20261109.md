# N3-W T1 Home Assistant mandatory-USB OTA R7A
# Boundary B USB insertion discovery STOP — USB enumeration timeout — 2026-11-09

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_BOUNDARY_B_USB_INSERTION_DISCOVERY_20261109_01
RESULT=STOP_USB_ENUMERATION_TIMEOUT
PR=800

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
ONE_SHOT_PHYSICAL_INSERTION=true
```

The dedicated removable test USB was physically inserted once under the bounded authorization.
The existing U1 transaction remained ACTIVE, but Linux never completed USB enumeration and no
block device appeared.

## 2. Preserved U1 state

```text
TRANSACTION_PRESENT=true
TRANSACTION_PHASE=U1_PREPARE_REQUESTED
TRANSACTION_STATUS=ACTIVE
PREPARE_STATE_PRESENT=true
CONFIRMATION_REQUIRED=false
CONFIRMATION_CONSUMED=false
CANDIDATE_PRESENT=false
PREPARE_ERROR_CODE=None

PREPARE_REPLAYED=false
CONFIRM_USB_ERASE_INVOKED=false
WIPEFS=false
PARTITION_WRITE=false
MKFS=false
MOUNT=false
TARGET_DOWNLOAD=false
U2_PLUS=false
```

The live U1 transaction remains intact and must not be cleared or replaced by another PREPARE.

## 3. Host enumeration evidence

```text
LSUSB_VISIBLE_DEVICES=ROOT_HUB_ONLY
USB_SYSFS_DEVICE_COUNT=1
USB_SYSFS_NON_ROOT_DEVICE_PRESENT=false
USB_LIKE_BLOCK_DISK_COUNT=0
SCSI_DISK_COUNT=0
OTA_MEDIA_MOUNT_COUNT=0
HOST_DAEMON_ACTIVE=true
HOST_DAEMON_NRESTARTS=0
```

Relevant kernel evidence:

```text
usb 1-2: new high-speed USB device number 2 using xhci-hcd
usb 1-2: device descriptor read/all, error -110
usb 1-2: new high-speed USB device number 3 using xhci-hcd
usb 1-2: device descriptor read/all, error -110
usb usb1-port2: attempt power cycle
usb 1-2: new high-speed USB device number 4 using xhci-hcd
usb 1-2: device descriptor read/8, error -110
usb 1-2: device descriptor read/8, error -110
usb 1-2: new high-speed USB device number 5 using xhci-hcd
usb 1-2: device descriptor read/8, error -110
usb 1-2: device descriptor read/8, error -110
usb usb1-port2: unable to enumerate USB device
```

## 4. Failure classification

```text
DISCOVERY_WORKER_TIMEOUT=false
CANDIDATE_FILTER_REJECTION=false
STABLE_IDENTITY_FAILURE_NOT_REACHED=true
BLOCK_DEVICE_ENUMERATION_NOT_REACHED=true
USB_DESCRIPTOR_ENUMERATION_FAILED=true
FAILURE_LAYER=LINUX_USB_BUS_ENUMERATION
CURRENT_PRODUCT_SOURCE_BLOCKER_PROVEN=false
CURRENT_HARDWARE_FAULT_PROVEN=false
NEW_KF_REQUIRED=NOT_YET_DETERMINED
```

The R7A discovery worker polls every second while the transaction remains U1. The host backend
can only classify a candidate after Linux exposes a block disk. That prerequisite never occurred.
The observed -110 descriptor timeout is therefore below the product candidate-selection layer.

This evidence does not yet distinguish among:
- the specific test USB device;
- connector/adapter/cable/contact behavior;
- T1 USB-port power or signal integrity;
- host USB-controller/driver behavior for this specific device.

No product-source repair is justified from this evidence alone.

## 5. Frozen safety boundary

```text
USB_CURRENTLY_INSERTED=true
USB_UNPLUG_AUTHORIZED=false
USB_REINSERT_AUTHORIZED=false
SECOND_USB_INSERTION_AUTHORIZED=false
PREPARE_REPLAY_AUTHORIZED=false
CONFIRM_USB_ERASE_AUTHORIZED=false
U2_PLUS_AUTHORIZED=false
SERVICE_RESTART_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE=false
STOP=true
```

The failed one-shot insertion authorization is consumed. The device remains physically inserted
at the observation stop point.

## 6. Recommended next gate

The next gate should be a separate controlled physical enumeration-differentiation gate. It should
preserve the live U1 transaction and use only bounded physical substitution plus read-only host
observation.

Recommended sequence:

1. fresh read-only verify U1 remains ACTIVE / USB_REQUIRED and no candidate exists;
2. authorize one unplug of the failed test USB;
3. verify host returns to zero external USB devices;
4. test the same USB on a separate known-good computer only to establish whether it enumerates;
5. if the same device is known-good, authorize one controlled reinsertion into T1 and capture
   immediate kernel/lsusb/lsblk evidence;
6. if it fails again, use a second known-good USB only under a separate bounded substitution step;
7. stop as soon as the fault class is isolated;
8. do not invoke CONFIRM_USB_ERASE or any U2+ operation.

```text
NEXT_STAGE=USB_ENUMERATION_DIFFERENTIATION
NEXT_GATE_AUTHORIZED=false
AUTO_RETRY=false
AUTO_REPAIR=false
AUTO_RESTART=false
```
