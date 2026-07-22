# H3/N2 Stage 2D-8 Dedicated-Board G2 Plan V60

## Purpose

Prepare an immutable, still-LOCKED package for the first physical Stage 2D-8 run on a dedicated custom ESP32-C6-WROOM-1-N8 product PCB. This plan does not authorize a live flash operation.

## Confirmed board boundary

- dedicated spare board;
- full 8 MB flash may later be erased and replaced;
- no existing firmware or data needs preservation;
- USB only;
- no battery, sensor or external load attached;
- ESP32-C6 revision v0.2;
- 8 MB external SPI flash;
- native USB-Serial/JTAG transport;
- Secure Boot and Flash Encryption disabled at the read-only inspection point.

Raw MAC, USB serial and local device path are excluded from the public repository.

## Two-image package

### G2 read-only probe

The G2 image creates one dedicated probe component. At startup it:

1. creates the Stage 2D-8 driver and package in RAM;
2. binds only `gh2d8_nvs` and `gh2d8_state`;
3. proves that no volatile test key is loaded;
4. performs exactly one `INSPECT_READ_ONLY` operation;
5. accepts only the expected empty-namespace result;
6. requires active generation 0, candidate generation 0 and write count 0;
7. requires all MQTT session roles to remain false;
8. closes the persistence handle, destroys volatile key state and stops.

It has no Wi-Fi, API, OTA, mDNS runtime, MQTT, web server, credential, key, write authorization or operator command surface. The shared source directory's unused discovery adapter is linked only against the pinned ESP-IDF mDNS library and does not instantiate ESPHome network or mDNS components.

### Locked recovery image

The recovery image uses the same chip and partition table but contains no Stage 2D-8 driver or persistence code. It only emits a serial `stage2d8_recovery=locked` marker and has no network or mutation surface.

## Fixed partition layout

| Name | Type | Offset | Size | Purpose |
|---|---|---:|---:|---|
| `nvs` | data/nvs | `0x9000` | `0x6000` | framework-local state |
| `phy_init` | data/phy | `0xF000` | `0x1000` | ESP-IDF PHY slot |
| `factory` | app/factory | `0x10000` | `0x3F0000` | G2 or locked recovery app |
| `gh2d8_nvs` | data/nvs | `0x400000` | `0x10000` | isolated Stage 2D-8 test partition |

The remaining flash is intentionally unused. No production partition or namespace is present.

## Artifact contract

CI compiles with ESPHome 2026.4.3 and packages, for both G2 and recovery:

- bootloader binary;
- binary partition table;
- application binary;
- merged full image starting at flash offset `0x0`;
- SHA-256 inventory;
- a redacted artifact manifest with `gate=LOCKED`.

The driver/probe source binding is `941becd5b670496fbea9e26f47d9d02ed0633526`. The final build commit and all binary digests are supplied by CI and must be copied into the private execution manifest before any live command is approved.

## Future G2 authorization boundary

After CI succeeds and the artifact is downloaded locally, the operator will be shown:

- exact artifact and manifest SHA-256 values;
- exact local serial path;
- exact erase-and-write command;
- exact recovery command;
- expected serial evidence;
- stop conditions.

A separate explicit G2 approval is then required. That approval may authorize only full erase, writing the reviewed G2 image, booting it and collecting read-only serial evidence. It will not authorize a test key, writable NVS, Wi-Fi, MQTT, Broker startup, `PREPARE_CANDIDATE`, `ACTIVATE_PROFILE` or `CLEANUP_TEST_STATE`.
