# N3-W KF-089 Board A Durable Diagnostic Baseline PASS — 2026-09-07

Status: `PUBLIC_SAFE_PHYSICAL_EVIDENCE`

## Scope

This record freezes the public-safe outcome of the Board A serial-free durable-diagnostic closure. It does not change product source, firmware, T1, Broker, Manager, Home Assistant, provisioning state, credentials, or keys.

Stable product/source and artifact authority:

```text
PRODUCT_SOURCE_AUTHORITY=483ff1c662dc74d6e12529e27a69819e68160f9e
PRODUCT_SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
OBSERVABILITY_FIRMWARE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
DIAGNOSTIC_SCHEMA_VERSION=3
```

## Remote T1 canonical window

The fresh canonical Direct window used for durable-diagnostic attribution was:

```text
WINDOW_START=2026-09-07T12:57:03Z
WINDOW_END=2026-09-07T12:58:34Z
T1_DIRECT_ACCEPTED_COUNT=18
T1_DIRECT_REJECTED_COUNT=0
T1_DIRECT_DUPLICATE_COUNT=0
T1_SEQ_FIRST=435
T1_SEQ_LAST=452
T1_INGRESS_SOURCE=direct
BOARD_A_T1_ACCEPTANCE_BINDING=PASS
```

No live serial monitor was used.

## Direct ROM entry and read-only NVS capture

After the T1 window, Board A was fully powered off and entered ESP32-C6 ROM Download Mode directly with no intervening normal application boot.

```text
BOARD_A_OPERATOR_POWER_OFF_CONFIRMED=true
BOARD_A_DIRECT_ROM_ENTRY_CONFIRMED=true
NORMAL_APPLICATION_BOOT_AFTER_WINDOW=false
BOARD_A_ROM_IDENTITY_BINDING=PASS
DIRECT_ROM_ENTRY=PASS
NVS_CAPTURE_READ_ONLY=PASS
SERIAL_OPEN=false
FLASH_WRITE=false
PRODUCT_NVS_MUTATION=false
```

Only the lab diagnostic snapshot at `gh_n3w_diag/snapshot` was extracted from the read-only NVS capture. Raw NVS and private identity material remain private/local.

## Boot-session binding

```text
DIAG_MAGIC_VALID=true
DIAG_SCHEMA=3
DIAG_BOOT_SESSION=11540229135812002993
T1_BOOT_SESSION=11540229135812002993
BOARD_A_DIAG_SESSION_BINDING=PASS
SESSION_ATTRIBUTION=PASS
```

## Direct-path durable diagnostic result

```text
DIAG_PATH_STATE=DIRECT
DIAG_CURRENT_CHANNEL=11
DIAG_DIRECT_CHANNEL_HINT=11
DIAG_SCAN_ATTEMPTS=0
DIAG_SCAN_SUCCESSES=0
DIAG_SCAN_FAILURES=0
DIAG_ADVERTISEMENT_ATTEMPTS=1304
DIAG_ADVERTISEMENT_SUBMIT_SUCCESS=1304
DIAG_ADVERTISEMENT_SUBMIT_FAILURE=0
DIAG_BROADCAST_COMPLETION_COUNT=1304
DIAG_BROADCAST_COMPLETION_SUCCESS=1304
DIAG_BROADCAST_COMPLETION_FAILURE=0
DIAG_DISCOVERY_RX=0
DIAG_CHALLENGE_TX=0
DIAG_ACCEPT_RX=0
DIAG_RELAY_ACTIVE_COUNT=0
```

## Acceptance

```text
BOARD_A_T1_ACCEPTANCE_BINDING=PASS
BOARD_A_DURABLE_DIAG_BINDING=PASS
BOARD_A_DIRECT_BASELINE=PASS
PRODUCT_FAILURE=false
RESULT=PASS
LEAVE_BOARD_A_IN_ROM_DOWNLOAD_MODE=true
```

Board A app1 is already proven to contain the exact observability image. Board A app0 has not yet been normalized to that image in this route.

## Next gate

```text
NEXT_GATE=KF089_BOARD_A_APP0_NORMALIZATION_AND_POSTCHECK
```

The successor is a separately authorized application-partition mutation. It may write/erase only Board A app0, must preserve app1, NVS, bootloader, partition table, and OTA selection, and must prove the post-normalization Direct path through the remote T1 observer before proceeding to Board B.