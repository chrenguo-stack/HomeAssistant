# N3-W Current State

Updated: 2026-09-07 18:36 +08:00  
Status: `CURRENT_STATE_AUTHORITY`

This file is the concise public-safe authority for the current N3-W development state. Historical detail and the 2026-09-07 local-chat/GitHub reconciliation are archived in:

`docs/development/N3W_KF089_LOCAL_CHAT_GITHUB_ALIGNMENT_ARCHIVE_20260907.md`

When this file conflicts with older handoffs or historical alignment documents, prefer fresh exact repository/CI/physical evidence, then the active product-direction decision, then this file.

## Repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
CURRENT_MAIN=483ff1c662dc74d6e12529e27a69819e68160f9e
CURRENT_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
PR_369=MERGED
PR_369_MERGE_COMMIT=d27c4aec59c75ebcc18b19cb2cc9d0562d0b7e08
PR_370=MERGED
PR_370_MERGE_COMMIT=483ff1c662dc74d6e12529e27a69819e68160f9e
```

Active architecture authority:

`docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

Current product direction remains:

- provisioned runtime startup must not require an already-established Wi-Fi association;
- Direct Wi-Fi remains preferred;
- when Direct is unavailable, the node must be able to enter node-local autonomous bounded Relay discovery;
- the full custom Wi-Fi/ESP-NOW radio-ownership state machine remains deferred unless later physical evidence proves it necessary.

## KF-089 status

KF-089 remains overall `OPEN` because end-to-end cold-boot Relay acquisition and later Direct recovery are not yet physically closed.

The original startup-gate sub-defect is now source-repaired and physically proven:

```text
KF089_ROOT_CAUSE_SOURCE_REPAIR=MERGED
KF089_STARTUP_GATE_REPAIR=PASS
TARGET_RUNTIME_READY_PHYSICAL=PASS
AUTONOMOUS_RELAY_DISCOVERY=NOT_PROVEN
AUTHENTICATED_RELAY_ACQUISITION=NOT_PROVEN
END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_PROVEN
```

PR #369 removed live Wi-Fi association as a hard startup prerequisite, added a 15 s Direct grace window, and permits legitimate `DISCOVERY` startup without a known Direct channel.

The clean physical retest on the repaired firmware proved that Board B created exactly one new durable boot session while battery powered in the target position, without an unexpected reboot:

```text
PRETEST_BOARD_B_SESSION=15870905187090026231
EXPECTED_TARGET_SESSION=15870905187090026232
POSTTEST_BOARD_B_BOOT_STATE=15870905187090026232
POSTTEST_SESSION_DELTA=1
TARGET_SESSION_ATTRIBUTION=PASS
TARGET_RUNTIME_READY_PHYSICAL=PASS
UNEXPECTED_TARGET_REBOOT=false
TARGET_SESSION_DIRECT_COUNT=0
TARGET_SESSION_RELAY_ACCEPTED_COUNT=0
ZONE_C_VALID=UNKNOWN
```

This proves the old `wifi_connected()` startup blocker is no longer preventing the runtime from becoming ready. It does not yet prove Relay discovery or RF reachability.

## Historical application-firmware interference eliminated

A possible interference source was identified from much older sensor/battery/LCD/EWM test application images that may have remained in an alternate OTA slot.

Both Board A and Board B application slots were therefore purged and normalized while preserving product NVS:

```text
BOARD_A_APP0_LEGACY_PURGED=PASS
BOARD_A_APP1_LEGACY_PURGED=PASS
BOARD_B_APP0_LEGACY_PURGED=PASS
BOARD_B_APP1_LEGACY_PURGED=PASS
OLD_APPLICATION_CODE_REMAINS_BOARD_A=false
OLD_APPLICATION_CODE_REMAINS_BOARD_B=false
PRODUCT_NVS_MUTATION=false
PAIRING_RETRIGGERED=false
```

At that boundary both application slots contained the same repaired KF-089 firmware:

```text
SOURCE=d27c4aec59c75ebcc18b19cb2cc9d0562d0b7e08
FIRMWARE_SHA256=11f21dc41cf91affb5a93bd0a302909b7694a00393b6636ac5f2c5f5a4b7bc05
```

Do not attribute later behavior to a historical YAML/application image unless new physical evidence contradicts that purge/normalization result.

## Relay-discovery observability

PR #370 added lab-only observability without changing the product path/protocol behavior.

Current diagnostic contract:

```text
DIAGNOSTIC_SCHEMA_VERSION=3
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
DIAGNOSTIC_KEY=snapshot
PRODUCT_TARGET_DIAGNOSTICS_ENABLED=false
PHASE4_GENERIC_DIAGNOSTICS_ENABLED=true
```

The Phase 4 physical target can now persist and/or summarize, among other fields:

- boot-session binding and snapshot uptime;
- actual working/scan channel and Direct channel hint;
- discovery scan attempts/success/failure and raw channel-set error;
- Relay discovery receive/reject;
- challenge/accept send, receive and verification stages;
- encrypted-peer installation;
- Relay-active transition and Relay telemetry send results;
- Relay advertisement attempt/submission outcome;
- asynchronous broadcast completion success/failure;
- bounded RX-drop count.

Diagnostic NVS writes to `gh_n3w_diag/snapshot` are expected for the lab target. They are separate from product provisioning state:

```text
LAB_DIAGNOSTIC_NVS_MUTATION=true
PRODUCT_NVS_MUTATION=false
```

## New exact-main physical artifact

The merged PR #370 exact-main physical target has been rebuilt successfully:

```text
SOURCE_COMMIT=483ff1c662dc74d6e12529e27a69819e68160f9e
SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
ESPRESSIF32_VERSION=55.03.38
TOOLCHAIN_VERSION=riscv32-esp-elf 14.2.0+20260121
FIRMWARE_IMAGE_SIZE=1114144
FIRMWARE_IMAGE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
FACTORY_IMAGE_SHA256=df63670dcf9b771fccda9e1881057d347d7b3c2adebc0ea2d5c8a70c6dace33a
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
PARTITION_COMPATIBILITY=PASS
LAB_DIAGNOSTICS_IN_BUILT_TARGET=PASS
```

The factory image is not authorized for the KF-089 physical refresh. Use application-partition-only update with exact readback verification and preserved product NVS.

## Current board/artifact boundary

The new observability artifact has been built but has not yet been proven flashed to Board A/B in the current route.

Therefore the next physical boundary must not assume either board is already running `efae17f4...`.

The last proven board application normalization used the older repaired firmware `11f21dc4...`. The next task must refresh the two boards to the new exact-main observability application image and establish a fresh Direct + diagnostic baseline before another battery-only Relay test.

## Current next gate

```text
NEXT_GATE=KF089_OBSERVABILITY_TWO_BOARD_APP_REFRESH_AND_DIRECT_DIAGNOSTIC_BASELINE
```

Required outcome before the next battery-only cold boot:

1. fresh Board A/B identity and partition rebind;
2. safe application-slot refresh to `efae17f4...` with exact readback SHA;
3. both OTA application slots normalized to the new exact-main image;
4. Direct telemetry accepted on both boards;
5. schema-v3 diagnostic serial summaries present;
6. Direct path has zero discovery scan attempts;
7. Board A/Board B advertisement submission and broadcast completion are observed healthy;
8. final Board B Direct boot session is rebound to the diagnostic `boot_session` field;
9. pairing, credentials, application-key epoch and peer-trust generation remain unchanged.

Only after that gate passes should the battery-only Relay diagnostic execution resume.

## Frozen acceptance boundaries

Do not collapse these separate claims:

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_STARTUP_GATE_REPAIR=PASS
KF089_AUTONOMOUS_RELAY_ACQUISITION=OPEN
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

The current work does not reopen FC4 and does not invalidate the three-board R2 Direct-runtime closeout.

## Evidence boundary

Public GitHub stores source, tests, hashes, sanitized closures and architecture decisions. Raw NVS, credentials, Setup Secrets, private identities and other sensitive physical-session evidence remain private/local and are not copied into this file.

The 2026-09-07 alignment archive records the public-safe test chronology and exact source/artifact bindings needed to continue the route without the local chat transcript.
