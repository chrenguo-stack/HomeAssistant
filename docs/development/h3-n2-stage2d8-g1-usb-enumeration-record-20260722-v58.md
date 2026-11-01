# H3/N2 Stage 2D-8 G1 USB Enumeration Record V58

## Status

The operator selected the dedicated spare-board route for Stage 2D-8 physical acceptance.

A macOS USB inventory on 2026-07-22 identified exactly one Espressif native USB JTAG/serial device and one matching modem-style serial port.

## Redacted binding

- device class: `Espressif USB JTAG/serial debug unit`
- USB vendor ID: `0x303a`
- USB product ID: `0x1001`
- transport: native USB JTAG/serial
- observed serial-port class: `/dev/cu.usbmodem*`
- exact port value: retained only in the private operator session
- USB serial identifier SHA-256: `a70a575ffe8f766a1017972f842aa894f10542e05eb710e419f724933ceb977f`
- serial-port path SHA-256: `3dbd58fb2a751780ce45dab2216fc0ffbcb9e70e8ff0a6fe00c85bd0055420b5`

The raw USB serial identifier and exact local device path are deliberately not stored in the public repository.

## Interpretation

The board is visible to macOS through Espressif's native USB JTAG/serial interface. No third-party USB-UART driver is required for this interface.

This record authorizes only the next read-only chip-identification step already covered by the Stage 2D-8 stage-level authorization. It does not authorize:

- reading flash contents;
- erasing or writing flash;
- opening a writable NVS namespace;
- starting Wi-Fi or MQTT;
- starting a temporary Broker;
- loading test credentials or test key material;
- `PREPARE_CANDIDATE`;
- `ACTIVATE_PROFILE`;
- `CLEANUP_TEST_STATE`.

The execution manifest remains `LOCKED` until the chip identity, security state, flash size, exact partition plan, firmware artifacts, and recovery procedure are reviewed.