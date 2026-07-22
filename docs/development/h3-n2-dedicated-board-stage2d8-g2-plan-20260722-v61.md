# H3/N2 Stage 2D-8 Dedicated-Board G2 Plan V61

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

## V60 audit correction

The first locked artifact build was not approved for flashing. Review found that the shared ESP-IDF NVS backend opens a custom namespace but assumes its custom NVS partition has already been initialized. A fully erased test partition would therefore fail closed before the intended empty-namespace observation. Initializing a completely erased writable NVS partition can also activate its first page, which is inconsistent with a runtime zero-write gate.

V61 resolves the issue before any physical mutation:

1. CI uses Espressif's bundled NVS partition generator to create a deterministic 64 KiB seed image.
2. The seed contains only namespace `gh2d8_seed` and one non-secret format byte.
3. The target namespace `gh2d8_state` is deliberately absent.
4. The complete seed image is included in both merged full-flash packages at `0x400000`.
5. The partition table marks `gh2d8_nvs` as `readonly`.
6. The G2 runtime verifies the exact partition address, size and read-only flag before initializing the NVS reader.
7. It then performs only `INSPECT_READ_ONLY`, closes all handles and deinitializes the partition.

The read-only partition flag is a second, hardware-access-layer denial boundary: any accidental partition write or erase request is rejected by ESP-IDF.

## Two-image package

### G2 read-only probe

The G2 image creates one dedicated probe component. At startup it:

1. verifies `gh2d8_nvs` is an NVS partition at `0x400000`, size `0x10000`, marked read-only;
2. registers and scans the pre-generated NVS image;
3. creates the Stage 2D-8 driver and package in RAM;
4. proves that no volatile test key is loaded;
5. performs exactly one `INSPECT_READ_ONLY` operation against `gh2d8_state`;
6. accepts only the expected missing-target-namespace result;
7. requires active generation 0, candidate generation 0 and driver write count 0;
8. requires all MQTT session roles to remain false;
9. closes the persistence handle, deinitializes the partition, destroys volatile key state and stops.

It has no Wi-Fi, API, OTA, mDNS runtime, MQTT runtime, web server, credential, key, write authorization or operator command surface. The shared source directory's unused discovery adapter is linked only against the pinned ESP-IDF mDNS library and does not instantiate ESPHome network or mDNS components.

### Locked recovery image

The recovery image uses the same partition table and the same deterministic read-only NVS seed, but contains no Stage 2D-8 driver or persistence code. It only emits a serial `stage2d8_recovery=locked` marker and has no network or mutation surface.

## Fixed partition layout

| Name | Type | Offset | Size | Flags | Purpose |
|---|---|---:|---:|---|---|
| `nvs` | data/nvs | `0x9000` | `0x6000` | — | framework-local state |
| `phy_init` | data/phy | `0xF000` | `0x1000` | — | ESP-IDF PHY slot |
| `factory` | app/factory | `0x10000` | `0x3F0000` | — | G2 or locked recovery app |
| `gh2d8_nvs` | data/nvs | `0x400000` | `0x10000` | `readonly` | preseeded isolated G2 test partition |

The remaining flash is intentionally unused. No production partition, namespace or credentials are present.

## Artifact contract

CI compiles with ESPHome 2026.4.3 and packages, for both G2 and recovery:

- bootloader binary;
- binary partition table;
- application binary;
- deterministic `gh2d8_nvs` seed image;
- merged full image starting at flash offset `0x0`, with seed at `0x400000`;
- SHA-256 inventory;
- a redacted artifact manifest with `gate=LOCKED`.

The driver/probe source binding is `510566f7047a779b319daa87fb64cf64f292c224`. The final build commit and all binary digests are supplied by CI and must be copied into the private execution manifest before any live command is approved.

## Future G2 authorization boundary

After CI succeeds and the artifact is downloaded locally, the operator will be shown:

- exact artifact and manifest SHA-256 values;
- exact local serial path;
- exact erase-and-write command;
- exact recovery command;
- exact pre-boot and post-probe readback commands limited to the 64 KiB test partition;
- expected serial evidence;
- stop conditions.

A separate explicit G2 approval is then required. That approval may authorize only full erase, writing the reviewed G2 image, test-partition-only pre/post readback, booting it and collecting read-only serial evidence. It will not authorize a test key, writable NVS, Wi-Fi, MQTT, Broker startup, `PREPARE_CANDIDATE`, `ACTIVATE_PROFILE` or `CLEANUP_TEST_STATE`.
