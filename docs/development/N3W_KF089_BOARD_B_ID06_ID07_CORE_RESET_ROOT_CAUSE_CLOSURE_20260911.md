# N3W KF-089 Board B ID06/ID07 Core Reset Root-Cause Closure — 2026-09-11

## Result

- ID06_RESET_TYPE=CORE_RESET_ONLY（esptool hard_reset → RTS）
- ID07_RESET_TYPE=CORE_RESET_ONLY（RTS-only HardReset）
- ID06_STRAP_RESAMPLED=false
- ID07_STRAP_RESAMPLED=false
- USB_SERIAL_JTAG_CORE_RESET_CHAIN_CONFIRMED=true
- BOARD_ALREADY_IN_DOWNLOAD_MODE_BEFORE_ID09=true
- FIRMWARE_FAILURE_PROVEN=false
- APP0_REWRITE_REQUIRED=false
- OTADATA_REWRITE_REQUIRED=false

## Adjudication

The prior ID06/ID07 resets did not constitute a true EN/CHIP_PU system reset and therefore did not resample the boot strap state. Board B could remain in ROM download mode across those core resets.

ID09 later captured explicit ROM evidence:

- boot:0x4 (DOWNLOAD(USB/UART0/SDIO_FEI_FEO))
- waiting for download

The passive observer open sequence was separately reviewed and did not prove an open-time DTR/RTS transition capable of causing the mode change.

## Next safe physical action

Under a fresh, single-use authorization:

1. Start the already host-tested passive/re-enumeration observer.
2. Confirm BOOT/GPIO9 is released/not externally held low.
3. Perform exactly one true system reset via EN/CHIP_PU, or one power-cycle if EN/CHIP_PU reset cannot be positively identified.
4. Observe boot/runtime evidence for up to 60 seconds.
5. Do not write Flash, app0, otadata, or NVS. Do not retry automatically.

The purpose is to force boot-strap resampling and verify app0/product/N3-W/Schema-v5 execution. No firmware rewrite is currently justified.
