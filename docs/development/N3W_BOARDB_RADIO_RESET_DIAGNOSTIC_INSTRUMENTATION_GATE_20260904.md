# N3-W Board B Radio / Reset Diagnostic Instrumentation Gate

Date: 2026-09-04

## Authority

```text
GATE=N3W_BOARDB_RADIO_RESET_DIAGNOSTIC_INSTRUMENTATION
AUTHORIZATION=USER_APPROVED_20260904
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
```

## Exact repository binding

```text
BASE_MAIN=b683fc62a4126b6f6a0e945db8db68c2584e0e2d
BASE_MAIN_TREE=6acfee560dce268e1ca5f05fdebfe840ddc8bc20
FROZEN_BOARD_FIRMWARE_SOURCE=739d9af2bac78a3a59f92a4ae345d8f1b1dc15ab
DIAGNOSTIC_BRANCH=diag/n3w-boardb-radio-reset-observability-20260904
```

Compare of `FROZEN_BOARD_FIRMWARE_SOURCE..BASE_MAIN` contains no `firmware/` changes. Therefore the Board firmware product semantics at current main remain source-equivalent to the frozen deployed firmware baseline for this gate.

## Triggering observation

The preceding physical movement attempt closed as:

```text
WIFI_LOSS_STIMULUS_ACHIEVED=false
RELAY_TRANSITION_OBSERVED=false
BOARD_B_UNPLANNED_REBOOT=true
REBOOT_CAUSE=UNKNOWN
```

Observed evidence:

- Board B telemetry remained Direct / accepted during the sampled movement window.
- T1 continued receiving Board B Direct telemetry every 5 seconds.
- No Relay ingress was observed.
- Manager restart count remained zero.
- A new Board B boot session appeared during the window.

The new boot session proves a firmware/process restart boundary but does not, by itself, distinguish power loss, brownout/power glitch, watchdog, panic, software reset, USB/JTAG reset, or another reset source.

## Read-only source findings carried into this gate

1. The product adapter prevents `esp_wifi_set_channel()` while `wifi_connected()==true` unless the requested channel is already the connected STA channel.
2. Once `wifi_connected()==false`, Discovery may control the radio and scan the configured channels.
3. Default Discovery channels are `1, 6, 11` with `scan_dwell_ms=250`.
4. ESPHome Wi-Fi reconnection/scanning can still own the radio while `is_connected()==false`; therefore `wifi_connected()==false` is not a sufficient radio-ownership handoff oracle.
5. `esp_now_send()` synchronous submission status is consumed by the product state machine, while the asynchronous ESP-NOW send completion callback is delivered to `SimpleProductComponent::on_espnow_send_result()` and currently discarded.
6. Existing ESP-NOW driver diagnostic receive/broadcast-completion logs are capped at the first eight observations.
7. A failed Discovery channel switch returns `RADIO_FAILED`; the runtime tick result is currently discarded by the product component. The diagnostic build must observe this without changing it.

These findings justify instrumentation. They do NOT prove that the observed Board B reboot was caused by ESP-NOW Discovery or Wi-Fi/ESP-NOW radio contention.

## Diagnostic-only source scope

The diagnostic firmware may add observability only. It MUST NOT change transport behavior.

Required observability:

```text
A. RESET
- esp_reset_reason() on every firmware boot
- ESP-IDF version
- serial capture must preserve ROM boot / panic / WDT output if emitted

B. WIFI_MQTT_PATH
- Wi-Fi connected/disconnected state changes
- MQTT connected/disconnected state changes
- N3-W path state changes
- current Wi-Fi channel query result
- periodic bounded heartbeat while running

C. RADIO_CHANNEL
- every N3-W set_radio_channel request
- Wi-Fi-connected state at request time
- channel before/after the request when observable
- success/failure result
- monotonically increasing attempt/failure counters
- failure logging must be rate-limited so a failed tight loop is observable without the logger itself dominating timing

D. ESPNOW_TX_RX
- broadcast/unicast submission result
- asynchronous send-completion success/failure
- receive channel/RSSI/size
- RX-ring drop counter

E. HANDSHAKE
- classify observable control frames as RelayDiscovery / PeerChallenge / PeerAccept
- log TX/RX stage without logging keys, setup secrets, MQTT passwords, application keys, LMKs, or payload plaintext
```

## Strict non-goals

The diagnostic branch MUST NOT yet:

```text
- change Wi-Fi reconnect behavior
- pause or disable ESPHome Wi-Fi scanning/reconnect
- change scan_dwell_ms
- change allowed channel set
- change Direct failure thresholds
- add same-channel-first behavior
- add radio ownership arbitration
- change esp_now_send success semantics used by the state machine
- change peer/credential/application-key lifecycle
- erase or migrate NVS
- change Manager/Broker/T1 runtime
- change Board A or Board C
```

Those are separate product-repair gates after evidence collection.

## Preferred implementation boundary

Prefer diagnostic overrides / logging at the product adapter boundary so the underlying `SimpleProductRuntime`, `LocalPathController`, channel policy, and driver behavior remain unchanged.

The diagnostic implementation should make the minimum source delta necessary to expose:

```text
N3W_DIAG_BOOT
N3W_DIAG_STATE
N3W_DIAG_CHANNEL
N3W_DIAG_ESPNOW_TX_SUBMIT
N3W_DIAG_ESPNOW_TX_DONE
N3W_DIAG_ESPNOW_RX
N3W_DIAG_DIRECT_PUBLISH
```

Control-frame classification may use the existing public decoders for RelayDiscovery, PeerChallenge, PeerAccept, and compact telemetry. No secret-bearing decoded fields should be printed.

## Build / flash boundary

Only Board B may receive the diagnostic firmware in this gate.

Before flash:

```text
BOARD_A_ACCESS=false
BOARD_C_ACCESS=false
T1_MUTATION=false
BOARD_B_NVS_ERASE=false
BOARD_B_FACTORY_RESET=false
BOARD_B_CREDENTIAL_CHANGE=false
```

The build must use the current diagnostic branch and the same ESP32-C6 physical harness target/partition semantics as the frozen Board B firmware. Flashing must not erase NVS or intentionally rotate any durable identity/credential/key generation.

## First post-flash oracle

Before any RF movement test, hold Board B stationary in Wi-Fi Good and prove:

```text
DIAGNOSTIC_FIRMWARE_BOOTED=true
RESET_REASON_LOG_PRESENT=true
DIRECT_BASELINE_RESTORED=true
MQTT_CONNECTED=true
BOARD_B_CURRENT_IDENTITY_PRESERVED=true
BOARD_B_CREDENTIAL_GENERATION_UNCHANGED=true
BOARD_B_APPLICATION_KEY_EPOCH_UNCHANGED=true
BOARD_B_PEER_TRUST_GENERATION_UNCHANGED=true
UNPLANNED_REBOOT_DURING_BASELINE=false
```

If this baseline is not PASS, STOP. Do not perform another movement test.

## Next physical diagnostic, only after baseline PASS

The next physical attempt remains Board-B-only and must preserve continuous power/USB/diagnostic wiring. The primary purpose is now evidence capture, not proving Relay PASS in one attempt.

On any new boot session, immediately classify `esp_reset_reason()` and preserve the serial interval before/through/after the reset. On any Direct->Discovery transition, correlate Wi-Fi/MQTT state, `set_radio_channel` requests/results, ESP-NOW control traffic, and async send completion.

## Gate closure categories

```text
RESET_CAUSE_CLASSIFIED=true|false
RADIO_OWNERSHIP_CONFLICT_OBSERVED=true|false|UNKNOWN
CHANNEL_SWITCH_FAILURE_OBSERVED=true|false|UNKNOWN
ESPNOW_ASYNC_TX_FAILURE_OBSERVED=true|false|UNKNOWN
HANDSHAKE_STAGE_REACHED=NONE|DISCOVERY|CHALLENGE|ACCEPT|RELAY_ACTIVE
PRODUCT_REPAIR_REQUIRED=true|false|UNKNOWN
```

This gate is diagnostic. A product repair requires a separate authorization and must not be folded into this instrumentation branch.