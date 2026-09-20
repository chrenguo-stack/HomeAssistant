# PR437 Board B USB enumeration and local-owner read-only forensic

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Trigger

The Board B prior LAN address produced no response across a 150-second Direct-recovery observation window, while Manager and Broker stayed healthy and no MQTT reconnect appeared.

Before attributing the failure to the Wi-Fi/Direct recovery state machine, rule out two local confounders without opening serial:

1. the previously bound Board B native USB path is no longer enumerated;
2. another local process currently owns the serial device and may have interacted with it.

## Scope

This package does not open the serial device. It only:
- checks whether the previously bound device node exists;
- counts current /dev/cu.usbmodem* entries;
- runs lsof against the expected path and emits only owner count;
- reads macOS IOUSB registry text and emits only a coarse Espressif/USB-JTAG match count.

No raw process IDs or USB path names beyond the already-frozen expected path are emitted.

## Execution

    python3 /tmp/n3w-pr437-177468e-boardb-usb-enum-readonly.py       --output /tmp/n3w-pr437-177468e-boardb-usb-enum-readonly.json

## Boundary

    BOARD_RESET=false
    APPLICATION_SERIAL_OPEN=false
    FLASH_WRITE=false
    PRODUCT_NVS_WRITE=false
    T1_ACCESS=false
    T1_MUTATION=false
