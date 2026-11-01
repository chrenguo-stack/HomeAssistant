# H3/N2 Stage 2D-8 Dedicated-Board Authorization V60

## Operator confirmation

On 2026-07-22 the operator confirmed that the selected hardware is a dedicated spare test board and may be completely erased and overwritten across its full 8 MB SPI flash. No existing firmware or data needs to be retained.

## Hardware binding

- module: `ESP32-C6-WROOM-1-N8`
- board class: custom ESP32-C6-WROOM-1 product PCB
- flash capacity: 8 MB, confirmed by read-only ROM inspection
- chip: ESP32-C6 QFN40 revision v0.2
- transport: Espressif native USB-Serial/JTAG
- attached peripherals: USB only
- explicitly absent: battery, sensors, external loads

The raw MAC address, USB serial identifier and local serial-device path are retained only in the private operator session and are not stored in this public repository.

## Granted scope

This confirmation permits preparation of an immutable dedicated-board test firmware, an isolated test partition layout, deterministic build and recovery artifacts, and a still-LOCKED execution manifest.

It does not yet authorize any command that erases or writes flash. It also does not authorize opening writable NVS, connecting Wi-Fi or MQTT, starting a Broker, loading test credentials or keys, `PREPARE_CANDIDATE`, `ACTIVATE_PROFILE`, or `CLEANUP_TEST_STATE`.

A separate exact G2 authorization is required after the artifact digests, partition layout, recovery procedure and exact flash command have been reviewed.