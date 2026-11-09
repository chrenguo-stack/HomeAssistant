# N3-W T1 Home Assistant mandatory-USB OTA R7A
# USB enumeration differentiation E2 stop — repeated descriptor timeout — 2026-11-09

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_USB_ENUMERATION_DIFFERENTIATION_E2_20261109_01
RESULT=STOP_REPEAT_DESCRIPTOR_TIMEOUT
PR=800
```

E2 moved the exact same USB device that had enumerated successfully on the Mac back to the T1
for one controlled reinsertion.

## 2. Preserved U1 state

```text
TRANSACTION_PHASE=U1_PREPARE_REQUESTED
TRANSACTION_STATUS=ACTIVE
PUBLIC_PHASE=USB_REQUIRED
USB_CONFIRMATION_REQUIRED=false
USB_CONFIRMATION_CONSUMED=false
USB_CANDIDATE_PRESENT=false
PREPARE_ERROR_CODE=null
```

The HA-USB transaction remains intact and active.

## 3. Repeated T1 enumeration failure

Fresh kernel evidence from the second T1 insertion:

```text
usb 1-2: new high-speed USB device number 6 using xhci-hcd
usb 1-2: device descriptor read/all, error -110
usb 1-2: new high-speed USB device number 7 using xhci-hcd
usb 1-2: device descriptor read/all, error -110
usb usb1-port2: attempt power cycle
usb 1-2: new high-speed USB device number 8 using xhci-hcd
usb 1-2: device descriptor read/8, error -110
usb 1-2: device descriptor read/8, error -110
usb 1-2: new high-speed USB device number 9 using xhci-hcd
usb 1-2: device descriptor read/8, error -110
usb 1-2: device descriptor read/8, error -110
usb usb1-port2: unable to enumerate USB device
```

Host projection remained:

```text
LSUSB_NON_ROOT_DEVICE_PRESENT=false
USB_LIKE_BLOCK_DISK_COUNT=0
SCSI_DISK_COUNT=0
NEW_USB_STORAGE_OR_SCSI_EVIDENCE=false
```

The second failure reproduces the first failure signature after the same USB was proven healthy enough
to enumerate as a 31.9 GB external physical mass-storage disk on the Mac.

## 4. Classification

```text
FIRST_T1_INSERTION_TIMEOUT=true
SAME_USB_MAC_ENUMERATION=PASS
SECOND_T1_INSERTION_TIMEOUT=true

TRANSIENT_SINGLE_INSERTION_EXPLANATION_WEAKENED=true
TEST_USB_COMPLETELY_DEAD=false
PRODUCT_CANDIDATE_LAYER_REACHED_ON_T1=false
PRODUCT_SOURCE_BLOCKER_PROVEN=false
PERMANENT_T1_HARDWARE_FAULT_PROVEN=false

REMAINING_FAULT_DOMAIN=T1_USB_PATH_OR_DEVICE_SPECIFIC_T1_COMPATIBILITY
NEXT_DIAGNOSTIC_CLASS=SECOND_KNOWN_GOOD_USB_SUBSTITUTION
NEW_KF_REQUIRED=NOT_YET_DETERMINED
```

The next discriminating test is a second known-good USB mass-storage device on the same T1 path.
If the second device also fails descriptor enumeration, the evidence shifts strongly toward a T1-side
port/controller/power/signal issue. If the second device enumerates normally, the evidence shifts toward
device-specific compatibility between the original MXT USB device and this T1/kernel/xHCI stack.

## 5. Safety boundary

```text
CURRENT_TEST_USB_INSERTED_ON_T1=true
SECOND_USB_AUTHORIZED=false
CURRENT_USB_UNPLUG_AUTHORIZED=false
PREPARE_REPLAY_AUTHORIZED=false
CONFIRM_USB_ERASE_AUTHORIZED=false
SERVICE_RESTART_AUTHORIZED=false
U2_PLUS_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE=false
STOP=true
```

E2 is stopped. No automatic retry or physical substitution is permitted without a separate E3 authorization.
