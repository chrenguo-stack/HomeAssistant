# F1.0-RC2 + N3-W production-target integration

Updated: 2026-09-21  
Status: SOURCE_TARGET_CREATED

## Authority

```text
GATE=N3W_PRODUCTION_FIRMWARE_F1RC2_N3W_TARGET_20260921_01
BASE_PRODUCT_CORE_HEAD=e0275f20e6a40d82e9b745514387b81a788ee9d9
FROZEN_PR437_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
F1RC2_BASE=f1_0_rc2/f1_0_rc2.yml
PRODUCTION_TARGET=f1_0_rc2/f1_0_rc2_n3w_target.yml
N3W_TRANSPORT_PACKAGE=f1_0_rc2/packages/n3w_product_transport.yml
```

## Scope

This stage connects the existing F1.0-RC2 whole-device configuration to the
independent `greenhouse_n3w_product_core` successor.

The target inherits the existing F1.0-RC2 hardware, sensors, buses, display,
power protection, OTA, API, Wi-Fi and captive-portal behavior through the
existing `f1_0_rc2.yml` package. It then adds:

- the local `greenhouse_n3w_product_core` external component;
- `product_runtime: true`;
- one inert MQTT client with `enable_on_boot: false`, which is reserved for
  authenticated N3-W runtime configuration after Manager pairing.

## Explicit non-goals

This stage does **not**:

- include `packages/mqtt_n1.yml`;
- create or submit `gh.telemetry/1` business telemetry;
- call `take_telemetry_identity()`;
- call `submit_telemetry_json()`;
- duplicate or modify the frozen PR #437 Phase4 harness;
- flash a board or mutate T1;
- claim final production-firmware readiness.

The existing F1.0-RC2 sensor/quality/power schema will be reused by a separate
telemetry-bridge gate.
