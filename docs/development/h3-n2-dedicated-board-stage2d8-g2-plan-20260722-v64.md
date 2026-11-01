# H3/N2 Stage 2D-8 Dedicated-Board G2 Plan V64

## 1. Purpose and execution gate

This document freezes the first physical Stage 2D-8 G2 acceptance package for a dedicated custom ESP32-C6-WROOM-1-N8 product PCB.

The execution gate remains `LOCKED`. Source preparation, CI compilation and artifact creation do not authorize a live erase, flash write, flash readback, writable NVS operation, Wi-Fi connection, MQTT connection, Broker startup, eFuse operation, `PREPARE_CANDIDATE`, `ACTIVATE_PROFILE` or `CLEANUP_TEST_STATE`.

A later exact, one-shot G2 approval must bind the selected board, local serial port, final source commit, artifact digest, G2 image digest, recovery image digest and complete commands.

## 2. Confirmed dedicated-board boundary

The operator confirmed:

- dedicated spare custom product PCB;
- ESP32-C6-WROOM-1-N8 module;
- complete 8 MB SPI flash may later be erased and replaced;
- no existing firmware or data requires preservation;
- native USB-Serial/JTAG only;
- no battery, sensor or external load;
- observed ESP32-C6 revision v0.2 and 8 MB flash;
- Secure Boot and Flash Encryption disabled during G1 read-only inspection.

Raw MAC addresses, USB serial numbers and local device paths are excluded from the public repository and CI artifacts.

## 3. G2 read-only contract

The G2 image performs exactly one startup inspection. It:

1. binds only partition `gh2d8_nvs` and namespace `gh2d8_state`;
2. verifies partition offset `0x400000`, size `0x10000` and ESP-IDF read-only flag;
3. initializes the preseeded test NVS partition without creating the target namespace;
4. proves that no volatile test key is loaded;
5. performs one `INSPECT_READ_ONLY` operation;
6. accepts only the absent target namespace as the empty state;
7. requires active generation 0, candidate generation 0 and persistent write count 0;
8. requires all MQTT session roles to remain false;
9. closes persistence state, destroys volatile key state and stops.

The concrete persistence port handles an absent namespace before enforcing the encrypted-record key requirement. Existing encrypted records still require a loaded test key; only the absent-namespace read-only result can succeed without one.

The image has no Wi-Fi, API, OTA, mDNS runtime, MQTT configuration, web server, credential, test key, write grant or operator command surface.

## 4. Locked recovery image

The recovery image uses the same chip target and partition table but contains no Stage 2D-8 driver or persistence package. It only emits `stage2d8_recovery=locked` over USB serial. Recovery flashing also requires explicit command-bound authorization.

## 5. Frozen partition layout

| Name | Type | Offset | Size | Binary flags | Purpose |
|---|---|---:|---:|---:|---|
| `nvs` | data/nvs | `0x9000` | `0x6000` | `0` | framework-local state |
| `phy_init` | data/phy | `0xF000` | `0x1000` | `0` | PHY slot |
| `factory` | app/factory | `0x10000` | `0x3F0000` | `0` | G2 or recovery app |
| `gh2d8_nvs` | data/nvs | `0x400000` | `0x10000` | `0x00000002` | isolated read-only test NVS |

ESP-IDF assigns the `readonly` flag to bit index 1, producing flag word `0x00000002`. CI decodes the binary partition table and rejects a missing flag, an offset or size drift, an extra partition, or unexpected flags on another partition.

## 6. Deterministic NVS seed

A 64 KiB NVS image is generated from a fixed CSV containing only:

- namespace `gh2d8_seed`;
- key `format_version` with value 1.

The target namespace `gh2d8_state` remains absent. CI generates the seed twice and requires byte identity. It rejects a wrong size, missing seed namespace or any occurrence of the target namespace.

The generator is pinned to `esp-idf-nvs-partition-gen==0.2.0` with wheel SHA-256 `7e128c81441fa406fe55b95f29a7d901098bcffc8cc464f993fdbecd074eb9a3`, installed using `--no-deps --require-hashes`.

## 7. Reproducible-build correction

V63 CI passed normal compilation and packaging, but independent comparison of two successful CI artifacts found that both application images differed only because ESPHome embedded the wall-clock build time. `CONFIG_APP_REPRODUCIBLE_BUILD=y` does not remove ESPHome's generated build-time string.

V64 therefore runs ESPHome 2026.4.3 through a reviewed wrapper that replaces only `writer.get_build_info()` with:

- fixed epoch `1784678400`;
- fixed timestamp `2026-07-22 00:00:00 +0000`;
- unchanged configuration hash and comment.

CI performs two clean builds of both G2 and recovery images. Bootloader, partition table and application binaries must be byte-identical across the two builds. The fixed timestamp must be present in each application image. Any mismatch fails closed and prevents packaging.

## 8. Host verification

V64 CI runs:

- the existing Stage 2D-8 C++ driver fault matrix;
- the eight-case G2 artifact matrix covering partition flags/layout and NVS seed faults;
- the two-clean-build byte-reproducibility gate;
- source-boundary and redaction gates.

## 9. Immutable V64 package

The final package contains, for both G2 and recovery:

- bootloader binary;
- binary partition table;
- application binary;
- deterministic NVS seed;
- merged image from flash offset `0x0` through the seed partition;
- SHA-256 for every file.

It also contains the partition CSV, seed CSV, generator pin, generator runtime evidence, source-boundary evidence, host fault-matrix evidence, reproducibility evidence, a redacted `gate=LOCKED` manifest and `SHA256SUMS`.

Every execution authorization remains false. The package must contain no raw board identifier, local serial path, Wi-Fi/MQTT credential or private key.

## 10. Future exact G2 authorization

After final V64 CI succeeds and the artifact is independently checked, the operator will receive:

- final source and artifact digests;
- exact G2 and recovery image digests;
- exact partition-table and NVS-seed digests;
- exact local serial path;
- exact erase, G2 write, recovery and permitted readback commands;
- expected serial evidence and stop conditions.

The later approval may authorize only the reviewed erase, G2 write, boot and read-only evidence collection. It will not authorize a test key, writable NVS, Wi-Fi, MQTT, Broker startup, profile preparation, activation or cleanup.
