# N3W KF089 Board B ID09 ROM Download Log Forensic — 2026-09-11

## Scope
Host-only adjudication of the 133-byte raw capture from ID09. No board access, reset, flash/NVS/otadata mutation, or new physical authorization.

## Raw capture

```text
Build:Sep 19 2022\r\nrst:0x15 (USB_UART_HPSYS),boot:0x4 (DOWNLOAD(USB/UART0/SDIO_FEI_FEO))\r\nSaved PC:0x40017604\r\nwaiting for download\r\n
```

SHA256: `6a05a17b4b0133469346312fcd60732aa9c667cc76e82f6eefbbffe600b85307`

Size: `133` bytes.

## Proven facts

- The ROM log explicitly contains `boot:0x4 (DOWNLOAD(...))`.
- The ROM log explicitly contains `waiting for download`.
- Therefore, at the moment this ROM message was emitted, the ESP32-C6 was in ROM download mode.
- No product-runtime log follows in this capture.
- `rst:0x15 (USB_UART_HPSYS)` is present.
- The capture does not contain proven port-open / first-byte / last-byte timestamps, so it does not prove whether these bytes were emitted before or after ID09 opened the serial port.
- Stale/buffered data remains possible.
- The observer/source audit reported that serial-open line-state side effects remain possible.

## Adjudication

`CURRENT_ROM_DOWNLOAD_MODE_PROVEN=PROVEN_AT_LOG_EMISSION` only.

The evidence is not yet sufficient to distinguish between:

1. Board B was already in ROM download mode before ID09 opened the serial port; or
2. The serial-open action / DTR-RTS handling caused a reset/boot-mode transition and the captured ROM log was generated as a consequence.

Because the observer had previously been classified as `DTR_RTS_SAFE=true`, but ID09 forensic still reports `SERIAL_OPEN_LINE_STATE_SIDE_EFFECT_POSSIBLE=true`, this contradiction must be reconciled host-only before another board access.

## Next safe action

Perform an exact host-only audit of the passive observer's serial-open sequence and the local serial library semantics. Determine:

- exact constructor/open order;
- default DTR and RTS states before and immediately after open;
- whether pyserial or the OS driver asserts/deasserts DTR/RTS on open even if later code sets them to a safe state;
- whether `exclusive`, `dsrdtr`, `rtscts`, or similar flags alter behavior;
- whether the implementation can open the USB Serial/JTAG endpoint without causing a reset/boot strap transition;
- whether the previous `DTR_RTS_SAFE=true` host test actually covered open-time transitions rather than only steady-state values.

No new passive capture should be performed until this contradiction is resolved.
