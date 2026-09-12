# N3W KF-089 ID19 Board A slot-switch-only

ID18 proved that Board A app0 contains the exact Schema-v5 image while app1 remains the selected rollback slot. ID19 is intentionally narrower than a firmware deployment: it changes only OTA selection metadata so that app0 becomes the next boot slot. It does not boot the application.

Frozen predecessor:

```text
ID18_RESULT=PASS
ID18_EXECUTION_PACKAGE_COMMIT=b796acc305a06610b34c1d0d0e35fcf2b37336ff
APP0_SCHEMA5_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
APP1_ROLLBACK_SHA256=5a3004647de0ef71e7be5664863a62b76a47c0cfdb32e38b07a296ca379f7562
SELECTED_SLOT=1
ACTIVE_OTA_SEQ=4
ACTIVE_OTA_STATE=2
```

Before mutation the executor must fresh-read identity, partition geometry, full otadata, app0 and app1. The frozen prestate above must still match exactly. The target OTA-copy index is derived from the fresh otadata snapshot. The planned target entry preserves its existing label/state and changes only sequence and CRC. Unsupported target states stop before mutation.

The mutation uses one direct ESP32-C6 ROM connection. It does not use the stock high-level esptool write path and does not call flash-finish. The target otadata sector is updated once, then the full otadata region is verified on the same ROM connection and again through an independent readback. App0 and app1 are read back and must retain their frozen hashes.

A successful ID19 result means only that app0 is selected for the next boot. The board remains in ROM Download state. A later separately authorized gate must boot and prove that Schema-v5 actually runs before any new RF experiment.

Safety boundary:

```text
APP0_WRITE=false
APP1_WRITE=false
APPLICATION_BOOT=false
RESET_AFTER_SWITCH=false
BOARD_B_PHYSICAL_ACCESS=false
T1_ACCESS=false
RF_EXECUTION=false
AUTO_RETRY=false
AUTO_ROLLBACK=false
```

This package does not authorize physical access. A fresh explicit ID19 authorization is required after exact-head CI acceptance.
