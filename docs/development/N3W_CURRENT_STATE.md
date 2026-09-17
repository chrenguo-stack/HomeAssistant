# N3-W Current State

Updated: 2026-09-17  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
ALIGNMENT_BASE_MAIN=416495ae9532d0d550cef25a949a62bd5242c434
ALIGNMENT_BASE_TREE=65a3075274a22924dde33879241ecdc87b992bdb
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

Recent integrated route:

```text
PR411=MERGED   # Relay MAC async delivery feedback into path hysteresis
PR413=MERGED   # delivery feedback + reset diagnostics + physical-harness reboot policy
PR414=MERGED   # Direct-to-Relay latency observability
PR415=MERGED   # Challenge submit raw-error observability
PR416=MERGED   # controlled-channel TX for Relay Challenge
PR417=MERGED   # redacted local development environment snapshot
PR418=MERGED   # current-state alignment
PR419=MERGED   # simplified handoff template / plain-language guidance

PR416_HEAD=d718f49fb05125c97c97c7525636da2246668142
PR416_MAIN_MERGE=11aa3ed3c1c727427e3a67f8764772c3a9fc3398
PR416_POSTMERGE_GREENHOUSE_MANAGER_CI=PASS
```

Historical PR #410/#412 are superseded stacked/documentation vehicles and are not current source authority.

## Frozen accepted baselines

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF092_STATUS=CLOSED_PASS
```

KF-092 remains closed and must not be reopened by the current PR #416 latency revalidation route.

## Pre-repair physical evidence

Board B previously proved same-boot Direct -> Relay through Board A without an uncommanded reboot, but Manager-visible telemetry had a long blackout:

```text
SAME_BOOT_DIRECT_TO_RELAY=PASS
UNCOMMANDED_REBOOT_DURING_TRANSITION=false
REBOOT_REQUIRED_FOR_RELAY=false
MANAGER_VISIBLE_GAP_MS=109007
MISSING_SEQUENCE_RANGE=50..70
MISSING_SEQUENCE_COUNT=21
TELEMETRY_CONTINUITY_ACCEPTANCE=FAIL
```

Per-boot observability localized most avoidable delay to Challenge submission after a Relay advertisement had already been accepted:

```text
relay_ad_seen_to_successful_challenge_tx_ms=70132
challenge_tx_to_accept_rx_ms=17
relay_active_to_first_relay_tx_ms=4100
challenge_submit_failure_count=3
challenge_submit_first_driver_error=11
challenge_submit_last_driver_error=11
challenge_submit_first_error_raw=12397
challenge_submit_last_error_raw=12397
```

For ESP-IDF 5.5.4, raw `12397` (`0x306D`) maps to `ESP_ERR_ESPNOW_CHAN`. At least the first and last failed Challenge submissions were therefore synchronous channel-mismatch rejection rather than over-air packet loss.

## PR #416 controlled-channel repair

PR #416 changes the Relay Challenge path to ESP-IDF `esp_now_switch_channel_tx()` while leaving Relay advertisements on the ordinary broadcast path and preserving Direct/Discovery/Relay policy thresholds.

```text
CONTROLLED_CHANNEL_TX_SOURCE_INTEGRATION=PASS
PR416_HOST_SOURCE_TESTS=45/45_PASS
PR416_ESP32C6_BUILD_ONLY=PASS
PR416_PR_CI=PASS
PR416_POSTMERGE_CI=PASS
```

### ESP-IDF semantics review

The required pre-deploy semantics review is complete.

Exact ESP-IDF 5.5.4 source plus the installed ESP32-C6 Wi-Fi/ESP-NOW libraries showed that the controlled-channel request and payload are copied during submission; the caller-owned request may therefore be freed after `esp_now_switch_channel_tx()` returns. `op_id` is generated internally and zero initialization is valid. The call does not block the application task for the full channel dwell; the Wi-Fi/channel manager continues the off-channel operation asynchronously.

```text
PR416_IDF_SEMANTICS_REVIEW=PASS
CONFIG_LIFETIME=SAFE
OP_ID_ZERO_INITIALIZATION=VALID
API_BLOCKS_FOR_FULL_1500MS=false
TARGET_CHANNEL_DWELL_MS=1500
SOURCE_REPAIR_REQUIRED=false
```

The official ESP-IDF off-channel tests also use dynamically allocated request objects that are released immediately after submission, consistent with the observed implementation semantics.

## Board B PR #416 deployment

Board B was freshly identified in ROM before write as the expected ESP32-C6 QFN40 revision v0.2 target. The deployment used the frozen PR #416 application artifact:

```text
FIRMWARE_SHA256=a701bf28d54a153f35bba6732c353dab97d3fe877aa75e35e5b57b4297258819
FIRMWARE_SIZE=1121952
IMAGE_TYPE=ESP32-C6
FLASH_SIZE=8MB
FLASH_MODE=DIO
FLASH_FREQ=80MHz
ESP_IDF=5.5.4
IMAGE_CHECKSUM=VALID
IMAGE_VALIDATION_HASH=VALID
```

Only the OTA state and application regions were written:

```text
OTADATA_OFFSET=0x9000
APPLICATION_OFFSET=0x10000
OTADATA_WRITE=PASS
APPLICATION_WRITE=PASS
OTADATA_HASH_VERIFY=PASS
APPLICATION_HASH_VERIFY=PASS
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

The one-shot Board B ROM-read and app+otadata flash authorizations were consumed and are not replayable.

## Post-flash Direct baseline

After the controlled-channel firmware deployment, the actual remote T1 path was reached directly and Manager accepted a new Board B Direct boot session continuously from sequence 0 through 85 at the normal ~5 s cadence.

```text
BOARD_B_POSTFLASH_FIRST_BOOT=PASS
BOARD_B_POSTFLASH_DIRECT_ACCEPTED_COUNT_AT_LEAST=86
BOARD_B_POSTFLASH_DIRECT_SEQ_FIRST=0
BOARD_B_POSTFLASH_DIRECT_SEQ_LAST=85
BOARD_B_POSTFLASH_INGRESS=direct
BOARD_B_PAIRING_IDENTITY_PRESERVED=true
BOARD_B_MQTT_TLS_RECONNECT=PASS
```

The observed Manager excerpt did not carry the device `reset_reason` field. Therefore the exact reset-reason value is not claimed by this evidence. The post-flash reboot itself was expected because the authorized esptool write ended with a hard reset.

No Direct -> Relay movement test using the PR #416 firmware has been executed yet. Therefore the former ~70 s Challenge delay has **not** yet been re-measured after the repair.

## Current live baseline

At the end of this conversation:

```text
T1_DIRECT_SSH_OBSERVATION=PASS
T1_MANAGER_CANONICAL_DIRECT_OBSERVATION=PASS
BOARD_B_LAST_OBSERVED_PATH=direct
BOARD_B_PR416_FIRMWARE_DEPLOYED=true
BOARD_A_MUTATION_THIS_ROUTE=false
T1_RUNTIME_MUTATION_THIS_ROUTE=false
BROKER_DYNSEC_MUTATION_THIS_ROUTE=false
```

Board A power/location and Board B physical power source/location are physical state and must be freshly confirmed in the next conversation before starting the movement test. Application serial must not be opened as a passive oracle because this project has already observed serial-open-triggered reset behavior.

## Current acceptance matrix

```text
DIRECT_BASELINE=PASS
SAME_BOOT_DIRECT_TO_RELAY_FUNCTIONAL_PATH=PASS   # pre-PR416 evidence
REBOOT_DEPENDENCY=false
LATENCY_OBSERVABILITY=PASS
CHALLENGE_CHANNEL_MISMATCH_ROOT_CAUSE=PROVEN_FOR_FIRST_AND_LAST_FAILED_SUBMISSIONS
CONTROLLED_CHANNEL_TX_SOURCE_INTEGRATION=PASS
CONTROLLED_CHANNEL_TX_IDF_SEMANTICS=PASS
CONTROLLED_CHANNEL_TX_BOARD_B_DEPLOYMENT=PASS
CONTROLLED_CHANNEL_TX_POSTFLASH_DIRECT_BASELINE=PASS
CONTROLLED_CHANNEL_TX_PHYSICAL_DIRECT_TO_RELAY_VALIDATION=PENDING
TELEMETRY_CONTINUITY_ACCEPTANCE=PENDING_RETEST
LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
HOME_ASSISTANT_ENTITY_UPDATE=SEPARATE_OPEN_ITEM
```

## Required guards

- USB port is only a locator; Board identity requires fresh silicon identity before a future board write.
- Application serial open is not a passive runtime oracle.
- Do not rewrite bootloader, partition table, or product NVS for the PR #416 latency revalidation.
- Do not normalize Board B identity during this route.
- Do not mutate Board A, T1 Manager/Broker, DynSec, credentials, or TLS configuration merely to run the PR #416 physical validation.
- Keep Board A stationary and powered as the Relay gateway during the movement test.
- The key acceptance question is same-boot Direct -> Relay latency/continuity after PR #416, not whether Relay can work at all; that functional path was already proven.
- Consumed one-shot authorizations are never replayable.
- Historical physical evidence is not a claim about live state in a new conversation; recheck only the facts needed for the next gate.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_PR416_CONTROLLED_CHANNEL_TX_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260917_01
PHYSICAL_AUTHORIZATION_REQUIRED=true
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

Purpose in plain language: start Board B on battery in good Wi-Fi, prove it is sending Direct telemetry, then move that same uninterrupted boot to the Relay test location and measure how long it takes to appear through Board A. The test must specifically show whether the previous ~70 s wait between Relay advertisement and successful Challenge has disappeared or materially changed.

The new conversation must fresh-check the minimum live prerequisites and obtain explicit physical-test authorization before moving/handling boards. It must not automatically flash again.

## Local development environment authority

Current redacted environment authority remains:

`docs/development/local-environment-records/2026-09-17-macos-x86_64.json`

Do not repeatedly rediscover unchanged Python/ESPHome tooling unless the environment changed or the next task needs it.

## Public/private evidence boundary

Public GitHub may store source, tests, artifact hashes, sanitized physical results, architecture decisions, and sanitized timing/acceptance results. Do not commit raw credentials, raw NVS, private keys, private host addresses, raw Manager/Broker logs, or private board identity material.
