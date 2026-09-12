# N3W KF-089 Board B ID06 USB observation-chain forensic result — 2026-09-11

Observed host-only forensic result after the single normal-boot attempt:

```text
NORMAL_BOOT_MECHANISM=ESPTOOL_HARD_RESET_RTS_WITH_USB_DELAY
ROM_STRAP_RELEASED_BEFORE_RESET=NOT_PROVEN
USB_REENUMERATION_OBSERVED=NOT_PROVEN
PRE_RESET_PORT=/dev/cu.usbmodem14101
POST_RESET_PORT=NOT_OBSERVED
OBSERVER_FOLLOWED_REENUMERATION=false
OBSERVED_BYTE_COUNT=0
OBSERVED_DATA_CLASS=EMPTY
USB_SERIAL_JTAG_EXPECTED=PASS
BOOT_FAILURE_PROVEN=false
OBSERVATION_PATH_FAILURE_PROVEN=false
MOST_LIKELY_CLASS=B_USB_SERIAL_JTAG_OBSERVATION_CHAIN_LOSS
```

Adjudication:

- ID06 does not prove Board B failed to boot.
- The observation path also was not formally proven failed because USB disappearance/reappearance was not captured.
- The strongest current hypothesis is that the reset caused a USB Serial/JTAG observation-chain loss and the observer remained bound to the pre-reset port.
- No additional physical reset or Board B access should occur until the observer is redesigned to follow USB re-enumeration.

Required host-only observer design:

1. Before the next reset, snapshot the target USB interface metadata and all candidate serial devices.
2. Treat `/dev/cu.*` only as a locator, not identity authority.
3. Start the observer before the reset event and keep a separate device-enumeration watcher active continuously.
4. Record disappearance and reappearance timestamps and every candidate port transition.
5. Rebind only to a uniquely matching USB device/interface using stable metadata available on the host (for example VID/PID plus serial number/location/interface metadata), and fail closed on ambiguity.
6. Opening the serial stream must not intentionally assert a reset or boot strap; DTR/RTS must be controlled/deasserted as appropriate for the selected serial API.
7. After rebind, capture raw bytes continuously for a bounded window and preserve the exact raw stream plus decoded text.
8. Classify evidence as ROM_BOOT_LOG, PRODUCT_LOG, SCHEMA_V5_EVIDENCE, MALFORMED_OR_OTHER, or EMPTY.
9. No Flash, otadata, NVS, Board A, or T1 mutation is part of this observer design.

Current state:

```text
ID06_REPLAY_PERMITTED=false
BOOT_FAILURE_PROVEN=false
APP0_PERSISTENT_SELECTION_PREVIOUSLY_PROVEN=true
NEXT_GATE=HOST_ONLY_USB_REENUMERATION_OBSERVER_DESIGN_AND_TEST
```
