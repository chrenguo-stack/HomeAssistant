# D2-10 PREPARE timeout root-cause and successor repair contract

## Frozen observation

D2-10 sent exactly one PREPARE command after the watchdog-repaired firmware
booted.  From the send time until the late-result window ended, the device kept
emitting the same PREPARE-ready line once per second.  There was no
`stage2d9r_prepare=pass`, no `stage2d9r_executor=fail`, no reboot, and no VERIFY.
The terminal result is therefore `PREPARE_RESULT_TIMEOUT`, not an executor
validation failure and not another watchdog reset.

## Root cause

The repaired firmware configures stdin as nonblocking and calls the inherited
console reader once per ESPHome loop.  That reader requests at most 128 bytes
and parses only after it receives the terminating newline.  The host capture
session wrote the complete private PREPARE command in one call.

The command is necessarily larger than the USB Serial/JTAG default 256-byte RX
buffer.  Even the minimum valid command is 695 bytes:

- schema: 17 bytes;
- minimum suffix: 8 bytes;
- five 64-character hexadecimal fields: 320 bytes;
- minimum 256-byte CA in unpadded base64url: 342 bytes;
- seven separators and one newline: 8 bytes.

The combined evidence closes the remaining frozen-path mechanism as
`USB_SERIAL_JTAG_RX_BURST_OVERRUN_AFTER_NONBLOCKING_REPAIR`: the tail containing
the only newline was lost before the 128-byte-per-loop consumer assembled a
complete line.  It explains continued readiness with no parser success/failure
marker and no reset, while the competing reset, validation-failure, and
executor-success hypotheses are directly contradicted by the captured output.

References:

- ESP-IDF USB Serial/JTAG VFS source:
  <https://github.com/espressif/esp-idf/blob/master/components/esp_driver_usb_serial_jtag/src/usb_serial_jtag_vfs.c>
- ESP-IDF buffer-size issue documenting the default 256-byte console buffer:
  <https://github.com/espressif/esp-idf/issues/14823>

## Source repair

The successor transport preserves the exact command bytes and exactly one
command opportunity.  It writes at most 64 bytes, flushes, waits 100 ms, and
then writes the next chunk.  The final chunk retains the sole newline.  A short
write is terminal and is never retried.  The normal result timeout begins only
after delivery returns; the timeout value itself is unchanged.

Public delivery evidence contains only schema, SHA-256, byte and chunk counts,
delay, flush count, and exact-write status.  It never stores raw private command
material.

## Safety boundary

This repair is source-only and inert on import.  It creates no physical request
or authorization.  It cannot enumerate USB, open a serial device, start a
Broker, invoke esptool, flash firmware, send PREPARE/VERIFY, or run recovery.
A later independent gate must create an exact execution binding and tests that
explicitly install the repair on the realtime capture session.

D2-10 and every D2-10 package remain permanently non-replayable.
