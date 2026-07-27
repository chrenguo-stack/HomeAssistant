# H3/N2 Stage 2D-9R G3R successor D2 execution package contract

- State: `REVIEWED_SOURCE_ONLY`
- D2 authorized: `false`
- Physical execution authorized: `false`

## Purpose

Freeze the exact host implementation that may later consume one independent exact
D2 authorization. The package itself is not an authorization and cannot run without
an exact authorization record whose source, package, script, launcher, toolchain,
board, serial, baseline, immutable firmware, private command and recovery bindings
all match.

## Pre-claim boundary

Before an authorization marker is atomically claimed, the launcher may only:

- verify package inventory and SHA-256 sums;
- verify the exact authorization record and its validity window;
- verify public Artifact bindings and regular-file modes;
- verify Python, OpenSSL, esptool and Mosquitto executable digests;
- verify private custody metadata without reading secret material content.

It must not enumerate USB or serial devices, open a serial port, invoke esptool,
start Mosquitto, read private command contents, access the target board, or perform
network, Flash or NVS operations before claim.

## Claimed one-shot path

A successful claim consumes D2 regardless of the later result. The normal path is:

1. enumerate exactly one authorized ESP32-C6 board and serial candidate;
2. verify the previously frozen read-only baseline;
3. erase Flash once;
4. write the exact immutable merged image once;
5. verify Flash once and use the automatic hard reset;
6. start one isolated loopback Mosquitto Broker with the exact private custody config;
7. wait for `stage2d9r_command_ready=PREPARE`;
8. send the exact frozen `GH2D9R_PREPARE_V1` once;
9. observe `stage2d9r_prepare=pass` and automatic firmware restart;
10. wait for `stage2d9r_command_ready=VERIFY`;
11. send the exact frozen read-only `GH2D9R_VERIFY_V1` once;
12. observe `stage2d9r_verify=pass`;
13. stop the isolated Broker and write one terminal consumed marker.

## Failure and recovery

Any failure after claim terminates as `CONSUMED_FAILED`; there is no automatic retry.
After the destructive boundary, and only when the same exact authorization explicitly
binds and permits it, the launcher may attempt locked recovery once by writing and
reading back the frozen 64 KiB all-`0xff` image at address `0x00400000`. Recovery does
not return to the normal path and does not change the terminal result to success.

## Permanently prohibited

The package never performs or authorizes a second PREPARE, second VERIFY, ACTIVATE,
CLEANUP, production service access, eFuse changes, Secure Boot changes, Flash
Encryption changes, manual BOOT-button handling, manual reset, Ready, merge, release,
tag or deployment.
