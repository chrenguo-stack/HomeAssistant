# N3-W R1R3 ROC Lifecycle Host Diagnostic Plan

Date: 2026-09-05
Document class: `HOST_ONLY_DIAGNOSTIC_HARNESS_REVISION`

## Frozen product principle

```text
N3W_PRIMARY_PATH_MODEL=SINGLE_ACTIVE_PRIMARY_DATA_PATH
OFFICIAL_NATIVE_CAPABILITY_FIRST=true
FULL_RADIO_OWNERSHIP_STATE_MACHINE_REQUIRED=NOT_YET_PROVEN
KF089_IMPLEMENTATION_AUTHORIZED=false
```

## Why R1R3 exists

R1-R2 established the following physical facts on Board A / Board B:

```text
R1A_HOME_CHANNEL_BASELINE=PASS
R1B_CONTROL_REMAIN_API=PASS
R1B_DUT_SWITCH_TX_API=PASS
R1B_PROBE_RX=PASS channel=6 seq=33
R1B=PASS

R1C_DUT_REMAIN_API=NOT_OBSERVED
R1C_PROBE_RX=FAIL_NOT_OBSERVED
CONTROL_HOME_CHANNEL_AFTER=6
DUT_STA_ASSOCIATED_AFTER=false
RESTORE_RESULT=PASS_BYTE_EXACT_PREBOOT
```

Therefore R1-R2 does not prove that the official off-channel API is insufficient. It proves one connected-STA off-channel TX path, while leaving the explicit lifecycle of `remain_on_channel` unresolved.

## Exact R1R3 question

R1R3 tests only this sequence:

```text
Board A CONTROL SoftAP on channel 1
Board B DUT STA associated on channel 1
        -> home-channel ESP-NOW baseline
        -> DUT sends ROC_ARMED on channel 1
        -> DUT calls esp_now_remain_on_channel(WIFI_ROC_REQ, channel 6)
        -> CONTROL calls esp_now_switch_channel_tx(channel 6)
        -> DUT receives one channel-6 probe if ROC is active
        -> DUT explicitly calls esp_now_remain_on_channel(WIFI_ROC_CANCEL, same op_id)
        -> DUT records channel / association immediately, +100 ms, +500 ms
        -> if disconnected, DUT issues bounded reconnect requests
        -> DUT must recover channel 1 + STA association
        -> DUT sends a normal channel-1 ESP-NOW HOME_ACK
```

This is intentionally one-directional. It does not chain the prior R1B and R1C scenarios.

## Official API authority used

Exact Espressif authority:

```text
ESPRESSIF_OFFICIAL_COMMIT=735507283d5b2f9fb363a1901172dbd9e847945d
```

The exact v5.5.4 headers define:

```text
WIFI_ROC_CANCEL
WIFI_ROC_REQ
esp_now_remain_on_channel(...)
esp_now_switch_channel_tx(...)
```

R1R3 uses only these public ESP-NOW/Wi-Fi primitives plus ordinary Wi-Fi STA/SoftAP and ESP-NOW peer/send APIs.

## Harness changes versus R1-R2

R1R3 adds:

```text
EXPLICIT_ROC_CANCEL=true
ROC_REQ_AND_CANCEL_SAME_OP_ID=true
CHANNEL_LOG_EVERY_BOUNDARY=true
STA_ASSOCIATION_LOG_EVERY_BOUNDARY=true
DISCONNECT_COUNT_LOGGING=true
RECONNECT_DURING_ROC=false
BOUNDED_RECONNECT_AFTER_CANCEL=true
HOME_CHANNEL_NORMAL_ESPNOW_ACK=true
```

The DUT suppresses reconnect attempts while the ROC window is active. Reconnect attempts begin only after explicit cancellation. This isolates the official ROC lifecycle from an uncontrolled reconnect loop.

## Host-only gate boundary

This gate may:

```text
create diagnostic source
create CI workflow
compile CONTROL image
compile DUT image
produce hash-bound artifact
```

It must not:

```text
access Board A/B/C
flash any board
open serial
execute RF
modify product source
implement KF089
modify T1 / Manager / Broker / DynSec
modify main
modify PR361
```

## Required CI result

The CI gate must verify exact official/pioarduino API-header authority, build both roles for ESP32-C6, bind the diagnostic source tree and generated artifacts, and upload one artifact suitable for a later separately-authorized short physical gate.

```text
R1R3_CONTROL_HOST_COMPILE=PASS
R1R3_DUT_HOST_COMPILE=PASS
R1R3_OFFICIAL_ROC_API_AUTHORITY=PASS
READY_FOR_R1R3_SHORT_PHYSICAL_GATE=true
```

A host compile PASS does not establish physical off-channel behavior.
