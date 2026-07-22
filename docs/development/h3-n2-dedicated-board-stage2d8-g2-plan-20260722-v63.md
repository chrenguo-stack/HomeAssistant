# H3/N2 Stage 2D-8 Dedicated-Board G2 Plan V63

## 1. Purpose and gate

This document freezes the first physical Stage 2D-8 G2 acceptance package for a dedicated custom ESP32-C6-WROOM-1-N8 product PCB.

The execution gate remains `LOCKED`. This plan and its CI artifacts do not authorize a live erase, flash write, flash readback, writable NVS operation, Wi-Fi connection, MQTT connection, Broker startup, eFuse operation, `PREPARE_CANDIDATE`, `ACTIVATE_PROFILE` or `CLEANUP_TEST_STATE`.

A later, exact and one-shot G2 approval must bind the selected board, serial port, final artifact digest, merged-image digest, recovery-image digest and the complete commands.

## 2. Confirmed dedicated-board boundary

The operator confirmed all of the following:

- the selected board is a dedicated spare custom product PCB;
- the installed module is ESP32-C6-WROOM-1-N8;
- the complete 8 MB SPI flash may later be erased and replaced;
- no existing firmware or data requires preservation;
- only native USB-Serial/JTAG is connected;
- no battery, sensor or external load is connected;
- the observed chip is ESP32-C6 revision v0.2;
- the observed flash capacity is 8 MB;
- Secure Boot and Flash Encryption were disabled during the G1 read-only inspection.

Raw MAC addresses, USB serial numbers and local device paths are excluded from the public repository and CI artifacts.

## 3. G2 read-only probe contract

The G2 image creates one dedicated probe component. At startup it:

1. verifies the fixed test partition label `gh2d8_nvs`;
2. verifies the fixed test partition offset `0x400000` and size `0x10000`;
3. verifies that the partition is marked read-only by ESP-IDF;
4. initializes the NVS partition without creating the target namespace;
5. proves that no volatile test key is loaded;
6. performs exactly one `INSPECT_READ_ONLY` operation;
7. accepts only an absent `gh2d8_state` namespace as the expected empty state;
8. requires active generation 0 and candidate generation 0;
9. requires persistent write count 0;
10. requires active, candidate and probe MQTT session states to remain false;
11. closes persistence state, destroys volatile key state and stops.

The probe has no Wi-Fi, API, OTA, mDNS runtime, MQTT configuration, web server, credential, test key, write authorization or operator command surface.

The concrete ESP32 persistence port handles an absent namespace before enforcing the encryption-key requirement. Existing encrypted records still require a valid loaded test key; only the absent-namespace read-only result can succeed without one.

## 4. Locked recovery image

The recovery image uses the same chip target and partition table but contains no Stage 2D-8 driver, persistence package or network configuration. It emits only the serial marker `stage2d8_recovery=locked`.

The recovery image is prepared before the first board write so the operator has a reviewed, credential-free fallback image. Recovery flashing also requires an explicit command-bound authorization.

## 5. Fixed partition layout

| Name | Type | Offset | Size | Flags | Purpose |
|---|---|---:|---:|---|---|
| `nvs` | data/nvs | `0x9000` | `0x6000` | none | framework-local state |
| `phy_init` | data/phy | `0xF000` | `0x1000` | none | ESP-IDF PHY slot |
| `factory` | app/factory | `0x10000` | `0x3F0000` | none | G2 or recovery application |
| `gh2d8_nvs` | data/nvs | `0x400000` | `0x10000` | `readonly` | isolated Stage 2D-8 test partition |

ESP-IDF stores the `readonly` flag as bit index 1, so the binary flag word must contain `0x00000002`. CI decodes the partition binary and rejects a missing flag, an offset or size drift, an extra partition or any unexpected flag on another entry.

The remaining flash is intentionally unused. No production partition or namespace is present.

## 6. Deterministic NVS seed

A completely erased NVS partition cannot be treated as a portable, already initialized read-only NVS store. CI therefore generates a deterministic 64 KiB seed image containing only:

- namespace `gh2d8_seed`;
- key `format_version` with value 1.

The target namespace `gh2d8_state` is deliberately absent.

The seed is generated twice and the two binaries must be byte-identical. CI rejects an incorrect size, a missing seed namespace or any occurrence of the target namespace.

The generator is fixed to:

- package: `esp-idf-nvs-partition-gen`;
- version: `0.2.0`;
- wheel SHA-256: `7e128c81441fa406fe55b95f29a7d901098bcffc8cc464f993fdbecd074eb9a3`;
- installation mode: `--no-deps --require-hashes` into the pinned host Python environment;
- runtime evidence: Python and `cryptography` versions are recorded in the artifact manifest.

## 7. Host verification

The V63 CI pipeline must pass both host suites.

### 7.1 Stage 2D-8 driver fault matrix

The existing C++ driver matrix covers default-off behavior, mirrored one-shot authorization, prepare/validate/activate sequencing, stale authorization, rollback, marker ambiguity, promotion failure, cleanup failure and volatile key destruction.

### 7.2 G2 artifact fault matrix

The dedicated G2 artifact matrix contains eight cases:

- valid frozen partition table;
- missing read-only flag rejected;
- test partition offset drift rejected;
- unexpected partition rejected;
- valid seed image accepted;
- wrong seed size rejected;
- missing seed namespace rejected;
- pre-created target namespace rejected.

## 8. Immutable artifact package

CI compiles with ESPHome 2026.4.3 and packages with esptool 5.3.1. For both G2 and recovery it retains:

- bootloader binary;
- binary partition table;
- application binary;
- deterministic NVS seed binary;
- merged image beginning at flash offset `0x0` and ending after the seed partition;
- individual file SHA-256 values.

The package also contains:

- the partition CSV;
- the seed CSV;
- the hash-pinned generator requirement;
- generator runtime evidence;
- source-boundary evidence;
- host artifact fault-matrix evidence;
- a redacted manifest with `gate=LOCKED`;
- `SHA256SUMS`.

The manifest must keep every execution authorization false. The artifact must contain no raw board identifier, local serial path, Wi-Fi credential, MQTT credential or private key.

## 9. Future exact G2 authorization

After final CI succeeds and the final artifact is downloaded and independently checked, the operator will be shown:

- final source commit;
- GitHub artifact digest and locally calculated ZIP digest;
- exact G2 merged-image digest;
- exact recovery merged-image digest;
- exact partition-table and NVS-seed digests;
- exact local serial port;
- exact full-flash erase command;
- exact G2 write command;
- exact recovery command;
- exact permitted 64 KiB test-partition pre/post readback commands;
- serial evidence markers and stop conditions.

The separate G2 approval may authorize only the reviewed erase, G2 write, boot and read-only evidence collection. It will not authorize a test key, writable NVS, Wi-Fi, MQTT, Broker startup, profile preparation, activation or cleanup.
