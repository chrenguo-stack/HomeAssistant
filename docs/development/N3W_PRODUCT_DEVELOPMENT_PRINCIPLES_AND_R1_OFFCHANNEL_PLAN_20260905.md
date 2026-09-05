# N3-W Product Development Principles and R1 Off-Channel Baseline

Date: 2026-09-05
Document class: `ARCHITECTURE_PRINCIPLE_AND_EXPERIMENT_PLAN`

## Frozen product-development principles

```text
N3W_PRIMARY_PATH_MODEL=SINGLE_ACTIVE_PRIMARY_DATA_PATH

PRODUCT_DEVELOPMENT_PRINCIPLE=
OFFICIAL_NATIVE_CAPABILITY_FIRST
THEN_EXPLICITLY_FEASIBLE_APPLICATION_LAYER_EXTENSION
THEN_ONLY_IF_PROVEN_NECESSARY_CUSTOM_LOW_LEVEL_ARCHITECTURE

PRODUCT_SEQUENCE=
SKELETON_FIRST
CORE_FUNCTIONS_FIRST
END_TO_END_FIRST
UX_OPTIMIZATION_LATER

ZERO_LOSS_SEAMLESS_FAILOVER_REQUIRED=false
FULL_RADIO_OWNERSHIP_STATE_MACHINE_REQUIRED=NOT_YET_PROVEN
```

At any instant the product has one primary data path. Short bounded control-plane probes are allowed while that primary path remains authoritative; they do not constitute a second active data path.

## Why this principle changed

R0 proved that the exact official ESP-NOW reference on ESP32-C6 can complete broadcast discovery and 100-frame unicast transfer on Board A and Board B. The product-level KF-089 failure therefore does not justify adding radio complexity before official framework capabilities are exhausted.

The current product implementation uses `esp_wifi_set_channel()` for radio movement. Espressif IDF 5.5.4 also exposes the official off-channel primitives:

```text
esp_now_switch_channel_tx(...)
esp_now_remain_on_channel(...)
```

R1 therefore tests those official primitives before any explicit Wi-Fi/ESP-NOW ownership state machine is promoted to product architecture.

## R1 scope

```text
R1=ESPRESSIF_OFFICIAL_OFF_CHANNEL_ESPNOW_API_BASELINE
```

R1 is diagnostic/reference only. It does not modify N3-W product source and does not test the full Relay protocol.

The minimum cases are:

```text
R1A=STA_CONNECTED_HOME_CHANNEL_BASELINE_ESPNOW
R1B=STA_CONNECTED_SWITCH_CHANNEL_TX_TO_TARGET
R1C=STA_CONNECTED_REMAIN_ON_CHANNEL_TARGET_RX
R1D=POST_OFFCHANNEL_HOME_CHANNEL_AND_STA_RECOVERY
```

R1 does not require zero latency, zero packet loss, or an uninterrupted Wi-Fi association. It requires bounded off-channel behavior and a usable return to the home channel without panic, reboot loop, or permanent Wi-Fi loss.

## Decision model

```text
R1B=PASS + R1C=PASS
  -> OFFICIAL_OFF_CHANNEL_PRIMITIVES_SUFFICIENT_FOR_NEXT_SIMPLIFICATION_REVIEW

R1B=PASS + R1C=FAIL
  -> OFFICIAL_ACTIVE_PROBE_SUPPORTED_BUT_ARBITRARY_OFFCHANNEL_RX_NOT_PROVEN

R1B=FAIL + R1C=FAIL
  -> OFFICIAL_OFF_CHANNEL_MODEL_INSUFFICIENT_FOR_CURRENT_PRODUCT_GOAL
  -> ONLY_THEN_CONSIDER_EXPLICIT_WIFI_SUSPEND_OR_RADIO_OWNERSHIP
```

No KF-089 implementation is authorized by this document.
