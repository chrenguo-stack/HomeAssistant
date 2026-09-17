# N3-W Progress Alignment — 2026-09-17

Status: `CURRENT_PROGRESS_ALIGNMENT`

This document aligns the live engineering conversation with repository state after PR #416 source integration, exact ESP-IDF semantics review, Board B deployment, and successful post-flash Direct baseline. Fresh exact repository/runtime/physical evidence takes precedence if later evidence proves drift.

## Alignment base

```text
REPOSITORY=chrenguo-stack/HomeAssistant
ALIGNMENT_BASE_MAIN=416495ae9532d0d550cef25a949a62bd5242c434
ALIGNMENT_BASE_TREE=65a3075274a22924dde33879241ecdc87b992bdb
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

## Route carried forward

```text
PR411=MERGED
PR413=MERGED
PR414=MERGED
PR415=MERGED
PR416=MERGED
PR417=MERGED
PR418=MERGED
PR419=MERGED
```

PR #416 remains the current source repair for the Relay Challenge channel-mismatch delay. PR #410/#412 remain superseded historical vehicles.

## Frozen historical physical result

The earlier same-boot Board B transition proved that Relay does not require a reboot, but continuity was poor:

```text
SAME_BOOT_DIRECT_TO_RELAY=PASS
REBOOT_REQUIRED_FOR_RELAY=false
MANAGER_VISIBLE_GAP_MS=109007
MISSING_SEQUENCE_COUNT=21
```

Per-boot timing localized the dominant avoidable delay to the Challenge step:

```text
relay_ad_seen_to_successful_challenge_tx_ms=70132
challenge_tx_to_accept_rx_ms=17
relay_active_to_first_relay_tx_ms=4100
challenge_submit_failure_count=3
challenge_submit_first_error_raw=12397
challenge_submit_last_error_raw=12397
```

ESP-IDF 5.5.4 maps `12397` to `ESP_ERR_ESPNOW_CHAN`. At least the first and last failed Challenge submissions were rejected synchronously because the current radio channel did not match the intended peer channel.

## PR #416 source repair

PR #416 changes Relay Challenge transmission to `esp_now_switch_channel_tx()` and leaves ordinary Relay advertisement transmission and existing path thresholds unchanged.

```text
PR416_HEAD=d718f49fb05125c97c97c7525636da2246668142
PR416_MAIN_MERGE=11aa3ed3c1c727427e3a67f8764772c3a9fc3398
PR416_HOST_SOURCE_TESTS=45/45_PASS
PR416_ESP32C6_BUILD_ONLY=PASS
PR416_PR_CI=PASS
PR416_POSTMERGE_CI=PASS
```

## Exact ESP-IDF semantics review completed

The previously required source-level review is no longer pending.

Evidence from exact ESP-IDF 5.5.4 headers/tests and the installed ESP32-C6 `libespnow.a` / `libnet80211.a` implementation established:

- caller request/payload are copied during submission;
- freeing the caller-owned request immediately after `esp_now_switch_channel_tx()` returns is valid;
- `op_id` is generated internally and zero initialization is valid;
- the application call returns after the Wi-Fi task has accepted/set up the off-channel operation; it does not sleep for the full `wait_time_ms`;
- the target-channel dwell continues through the Wi-Fi/channel-manager machinery;
- the configured 1500 ms controlled-channel window is not rejected by the API semantics reviewed here.

```text
PR416_IDF_SEMANTICS_REVIEW=PASS
CONFIG_LIFETIME=SAFE
OP_ID_ZERO_INITIALIZATION=VALID
API_BLOCKS_FOR_FULL_1500MS=false
TARGET_CHANNEL_DWELL_MS=1500
SOURCE_REPAIR_REQUIRED=false
```

This closes the pre-deploy source-semantics blocker. It does not by itself prove physical latency improvement.

## Board B deployment completed

Board B was freshly rebound by ROM silicon identity before mutation. The exact application image was parsed by esptool as a valid ESP32-C6 image:

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

Authorized deployment scope was kept minimal:

```text
0x9000  ota_data_initial.bin
0x10000 firmware.bin
```

Both writes passed esptool hash verification.

```text
OTADATA_WRITE=PASS
APPLICATION_WRITE=PASS
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

## Post-flash Direct baseline completed

After deployment and the expected hard reset, the real remote T1 was reached directly. Manager accepted a new Board B Direct session continuously from sequence 0 through 85 at roughly the normal 5-second cadence.

```text
BOARD_B_POSTFLASH_FIRST_BOOT=PASS
BOARD_B_POSTFLASH_DIRECT_ACCEPTED_COUNT_AT_LEAST=86
BOARD_B_POSTFLASH_DIRECT_SEQ_FIRST=0
BOARD_B_POSTFLASH_DIRECT_SEQ_LAST=85
BOARD_B_POSTFLASH_INGRESS=direct
BOARD_B_PAIRING_IDENTITY_PRESERVED=true
BOARD_B_MQTT_TLS_RECONNECT=PASS
```

The observed Manager log excerpt did not include the device `reset_reason`; no exact reset-reason value is claimed from that evidence.

The PR #416 firmware has **not yet** been tested by moving Board B from good Wi-Fi to the Relay location in the same battery-powered boot. Therefore the historical ~70 s Relay-advertisement-to-successful-Challenge delay remains the key measurement for the next conversation.

## Safety state at handoff

```text
BOARD_A_MUTATION_THIS_ROUTE=false
T1_RUNTIME_MUTATION_THIS_ROUTE=false
BROKER_DYNSEC_MUTATION_THIS_ROUTE=false
PRODUCT_CREDENTIAL_MUTATION_THIS_ROUTE=false
```

Board B did receive the explicitly authorized app+otadata deployment described above. Those one-shot authorizations are consumed and must not be replayed.

No further physical movement test is performed in this conversation.

## Current acceptance matrix

```text
DIRECT_BASELINE=PASS
SAME_BOOT_DIRECT_TO_RELAY_FUNCTIONAL_PATH=PASS   # historical/pre-PR416 evidence
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

## Next ONE gate

```text
NEXT_ONE_GATE=N3W_PR416_CONTROLLED_CHANNEL_TX_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260917_01
PHYSICAL_AUTHORIZATION_REQUIRED=true
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

Plain-language purpose: start Board B on battery where Wi-Fi is good, capture the fresh Direct baseline, then move that same uninterrupted boot to the Relay test location and measure when Manager first sees Relay telemetry through Board A. The result must directly compare the new Challenge timing with the prior ~70.132 s delay and the prior 109.007 s Manager-visible blackout.

Do not reflash Board B, change thresholds, mutate Board A, or alter T1/Broker/Manager/DynSec merely to run this test.
