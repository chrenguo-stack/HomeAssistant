# N3W KF-089 Board B USB Serial/JTAG Download-Mode Root-Cause Direction — 2026-09-11

## Current evidence

- ID09 passive capture recovered 133 bytes of ROM output:
  - `rst:0x15 (USB_UART_HPSYS)`
  - `boot:0x4 (DOWNLOAD(USB/UART0/SDIO_FEI_FEO))`
  - `waiting for download`
- Therefore Board B was in ROM download mode when that ROM log was emitted.
- ID09 passive observer safe-open forensic found pyserial 3.5 configured with `dtr=false` and `rts=false` before `open()`, with no proven open-time control-line transition.
- This weakens the hypothesis that the passive observer itself forced download mode.

## Official Espressif behavior relevant to the next gate

For ESP32-C6 USB Serial/JTAG, the default USB Serial/JTAG reset can perform only a core reset and does not necessarily re-sample boot strapping pins. If the device is already in ROM download mode, a default/hard reset may therefore leave it in download mode even after the physical BOOT strap is released. Espressif documentation recommends a true system reset (for example manual EN reset or power cycle) to re-sample boot strapping pins. The esptool watchdog-reset mechanism is documented as disabled on ESP32-C6 because it can cause a full system freeze requiring a power cycle.

## Adjudication

- `SERIAL_OPEN_CAUSED_DOWNLOAD_MODE=NOT_PROVEN`
- `BOARD_ALREADY_IN_DOWNLOAD_MODE_BEFORE_ID09=LIKELY`
- `ID06_OR_ID07_RESET_LEFT_DOWNLOAD_MODE=PLAUSIBLE`
- `EXACT_FIRST_ENTRY_INTO_DOWNLOAD_MODE=NOT_PROVEN`
- `FIRMWARE_FAILURE=NOT_PROVEN`
- `APP0_CONTENT_REWRITE_REQUIRED=false`
- `OTADATA_REWRITE_REQUIRED=false`

## Next safe gate

Host-only first: reconstruct the exact ID06/ID07 reset path and verify that it used USB Serial/JTAG core-reset semantics rather than a full system reset that re-samples GPIO9. Do not access Board B during this forensic.

If confirmed, the next physical recovery should be a single true system reset with BOOT/GPIO9 physically released, with the already-fixed observer running before reset, followed by bounded product/Schema-v5 observation. No flash, otadata, NVS, rollback, or second reset.
