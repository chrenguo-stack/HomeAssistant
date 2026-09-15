# KF-092 — Relay MAC Delivery Feedback Does Not Drive Path Hysteresis

Date: 2026-09-15  
Status: `OPEN`  
Primary domain: `FIRMWARE_RUNTIME`

## Symptom

Board B was proven Relay-only in bounded fresh windows, then later produced a bounded interval with no Manager-accepted Direct or Relay telemetry, and subsequently resumed Manager-accepted Relay telemetry without operator intervention.

Observed sequence:

```text
RELAY_ONLY_WINDOW_DIRECT=0
RELAY_ONLY_WINDOW_RELAY=27

LATER_180S_DIRECT=0
LATER_180S_RELAY=0

LOOKBACK_ACCEPTED_RELAY=56
LOOKBACK_REJECTED=0

LATER_RELAY_RUN_COUNT=16
LATER_RELAY_RUN_START=2026-09-15T03:06:35Z
LATER_RELAY_RUN_END_AT_CAPTURE=2026-09-15T03:08:00Z
```

This disproves permanent Board B loss and does not prove a fixed Relay-session lifetime.

Board C was separately operator-confirmed associated with the AP, so its Direct path is real and it is not a valid Relay-only oracle for this symptom.

## Source authority

Current deployed board source authority:

```text
BOARD_FIRMWARE_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
```

Relevant source paths:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_espnow_driver.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.cpp
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.h
```

## Proven source defect

`SimpleProductRuntime::send_telemetry()` currently treats the return value of `send_encrypted_peer()` as Relay success/failure and immediately feeds that result into `LocalPathController::note_relay_result()`.

`SimpleProductComponent::send_encrypted_peer()` delegates to `EspNowDriver::send()`, whose return value is based on synchronous `esp_now_send(...) == ESP_OK` submit acceptance.

The actual asynchronous ESP-NOW unicast MAC result arrives later through `EspNowDriver::send_cb_()`. That callback reaches `SimpleProductComponent::on_espnow_send_result()`, but non-broadcast completions currently go only to diagnostics through `diagnostics_.on_unicast_completion(...)`.

Therefore:

```text
SOURCE_DEFECT_PROVEN=true
ROOT_CLASS=ASYNC_ESPNOW_DELIVERY_RESULT_NOT_FEEDING_RELAY_PATH_CONTROLLER
SYNC_SUBMIT_ACCEPTANCE_USED_AS_DELIVERY_RESULT=true
ACTUAL_UNICAST_COMPLETION_REACHES_DIAGNOSTICS_ONLY=true
```

Current path policy defaults:

```text
DIRECT_FAILURES_TO_DISCOVERY=3
DIRECT_RECOVERIES_TO_DIRECT=2
RELAY_FAILURES_TO_DISCOVERY=2
```

Because actual MAC failures do not reach `note_relay_result(false)`, `relay_failures_` may never increment even while real delivery fails.

## Field-causation classification

```text
FIELD_INCIDENT_CAUSATION=STRONGLY_INDICATED_NOT_YET_PHYSICALLY_PROVEN
```

The source defect is directly proven. The observed Board B intermittent Relay symptom is consistent with it, but post-fix physical validation is required before claiming exact field causation.

## Minimum repair design

The Wi-Fi callback task must not directly mutate runtime/path state.

Required architecture:

```text
ESP-NOW unicast send callback
-> enqueue bounded completion record {destination, success}
-> return quickly from Wi-Fi task

normal component loop
-> drain completion records
-> match destination to current active Relay
-> feed actual MAC completion into Relay hysteresis
```

Rules:

```text
IMMEDIATE_SUBMIT_FAILURE=COUNT_AS_RELAY_FAILURE
ESP_NOW_SUBMIT_OK=NOT_DELIVERY_SUCCESS
BROADCAST_COMPLETION_AFFECTS_RELAY_PATH=false
STALE_OLD_RELAY_COMPLETION=IGNORE
CALLBACK_DIRECT_PATH_MUTATION=false
CURRENT_ACTIVE_RELAY_DESTINATION_MATCH_REQUIRED=true
```

When the second consecutive actual Relay failure reaches the existing hysteresis threshold, the runtime must leave `RELAY_ACTIVE`, remove the old Relay peer, re-enter `DISCOVERY`, scan, and reacquire an authenticated Relay.

A successful actual completion after one failure must reset the existing Relay-failure hysteresis.

## Required tests

At minimum:

1. submit succeeds + completion succeeds → remain `RELAY_ACTIVE`;
2. submit succeeds + first completion fails → remain `RELAY_ACTIVE`;
3. submit succeeds + second consecutive completion fails → `DISCOVERY`;
4. immediate submit failure → counts as failure without waiting for callback;
5. broadcast completion → no child Relay path effect;
6. completion for stale/old Relay destination → ignored;
7. callback task only enqueues/updates bounded callback-safe state and does not mutate `LocalPathController` directly;
8. completion success after one failure resets Relay failure hysteresis;
9. existing Direct→DISCOVERY and Relay→Direct recovery semantics remain unchanged.

## Authorization

```text
AUTHORIZATION=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
GRANTED=true
CLAIMED=false
CONSUMED=false
RESULT=PENDING
REPLAY_PERMITTED=true
SCOPE=SOURCE_HOST_TEST_CI_DOCUMENTATION_ONLY
```

No board/T1 live mutation is authorized.

## Next gate

```text
NEXT_ONE_GATE=N3W_KF092_RELAY_MAC_DELIVERY_FEEDBACK_SOURCE_REPAIR_20260915_01
```

The next chat must fresh-rebind repository authority, then may directly execute the authorized source/host-test/CI repair. It must STOP after source/CI closure and must not deploy firmware or run physical validation automatically.
