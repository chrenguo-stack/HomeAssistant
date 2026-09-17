# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current progress alignment: `docs/development/N3W_PROGRESS_ALIGNMENT_20260917.md`  
Current formal handoff: `docs/development/N3W_PR416_CONTROLLED_CHANNEL_TX_POSTFLASH_DIRECT_BASELINE_NEW_CHAT_HANDOFF_V1.0_20260917.md`  
Current local-development-environment authority: `docs/development/local-environment-records/2026-09-17-macos-x86_64.json`  
Current KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Repository authority at this alignment

```text
REPOSITORY=chrenguo-stack/HomeAssistant
ALIGNMENT_BASE_MAIN=416495ae9532d0d550cef25a949a62bd5242c434
ALIGNMENT_BASE_TREE=65a3075274a22924dde33879241ecdc87b992bdb
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
```

Always fresh-query `main` in a new conversation; the SHA above is the base used for this documentation alignment, not a permanent future-main claim.

## Recent merged route

```text
PR411=MERGED   # Relay MAC async delivery feedback
PR413=MERGED   # delivery feedback + reset diagnostics + harness reboot policy
PR414=MERGED   # Direct-to-Relay latency observability
PR415=MERGED   # Challenge raw-error observability
PR416=MERGED   # controlled-channel Challenge TX
PR417=MERGED   # local environment record
PR418=MERGED   # current-state alignment
PR419=MERGED   # handoff-template simplification / plain-language guidance
```

Historical PR #410/#412 remain superseded and must not be treated as current source authority.

## Frozen accepted baselines

```text
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF092_STATUS=CLOSED_PASS
SAME_BOOT_DIRECT_TO_RELAY_FUNCTIONAL_PATH=PASS
REBOOT_REQUIRED_FOR_RELAY=false
```

The older same-boot Direct -> Relay run had a 109.007 s Manager-visible blackout and 21 missing telemetry sequence numbers. Latency acceptance was therefore not closed.

## Challenge-delay root cause before PR #416

```text
relay_ad_seen_to_successful_challenge_tx_ms=70132
challenge_submit_failure_count=3
challenge_submit_first_error_raw=12397
challenge_submit_last_error_raw=12397
```

ESP-IDF 5.5.4 maps raw `12397` to `ESP_ERR_ESPNOW_CHAN`. At least the first and last failed Challenge submissions were rejected because the radio was on the wrong channel at send time.

## PR #416 deployment status

```text
CONTROLLED_CHANNEL_TX_SOURCE_INTEGRATION=PASS
PR416_IDF_SEMANTICS_REVIEW=PASS
PR416_BOARD_B_DEPLOYMENT=PASS
PR416_POSTFLASH_DIRECT_BASELINE=PASS
PR416_PHYSICAL_DIRECT_TO_RELAY_VALIDATION=PENDING
```

Frozen application artifact:

```text
FIRMWARE_SHA256=a701bf28d54a153f35bba6732c353dab97d3fe877aa75e35e5b57b4297258819
FIRMWARE_SIZE=1121952
TARGET=ESP32-C6
ESP_IDF=5.5.4
```

Board B deployment wrote only OTA state at `0x9000` and the application at `0x10000`; bootloader, partition table, product NVS, and full-flash erase were not touched.

## Post-flash Direct result

The real remote T1/Manager path accepted a fresh Board B Direct session continuously from sequence 0 through 85 at the normal cadence.

```text
BOARD_B_POSTFLASH_DIRECT_ACCEPTED_COUNT_AT_LEAST=86
BOARD_B_POSTFLASH_DIRECT_SEQ_FIRST=0
BOARD_B_POSTFLASH_DIRECT_SEQ_LAST=85
BOARD_B_POSTFLASH_INGRESS=direct
BOARD_B_MQTT_TLS_RECONNECT=PASS
```

No PR #416 Direct -> Relay movement test has been run yet, so the former ~70 s Challenge delay has not yet been re-measured.

## Current acceptance matrix

```text
DIRECT_BASELINE=PASS
SAME_BOOT_DIRECT_TO_RELAY_FUNCTIONAL_PATH=PASS   # historical/pre-PR416 physical proof
CONTROLLED_CHANNEL_TX_SOURCE_INTEGRATION=PASS
CONTROLLED_CHANNEL_TX_IDF_SEMANTICS=PASS
CONTROLLED_CHANNEL_TX_BOARD_B_DEPLOYMENT=PASS
CONTROLLED_CHANNEL_TX_POSTFLASH_DIRECT_BASELINE=PASS
CONTROLLED_CHANNEL_TX_PHYSICAL_DIRECT_TO_RELAY_VALIDATION=PENDING
TELEMETRY_CONTINUITY_ACCEPTANCE=PENDING_RETEST
LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
HOME_ASSISTANT_ENTITY_UPDATE=SEPARATE_OPEN_ITEM
```

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_PR416_CONTROLLED_CHANNEL_TX_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260917_01
PHYSICAL_AUTHORIZATION_REQUIRED=true
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

Next conversation: fresh-check only the minimum live prerequisites, obtain explicit physical-test authorization, establish a battery-powered Direct baseline, then move the same uninterrupted Board B boot to the Relay location and measure the transition. Do not flash again unless later evidence creates a separate explicitly authorized need.
