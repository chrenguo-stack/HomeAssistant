# N3-W production firmware DEHARNESS source repair

Updated: 2026-09-21  
Status: `SOURCE_REPAIR_IN_CI`

## Boundary

The already-validated PR #437 firmware lineage is frozen and is not rewritten by this work.

```text
PR437_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
PR437_MERGE_COMMIT=b9acaaad50b17c9cdb51c219330e612c383628f0
PR437_ARTIFACT_ROLE=ENGINEERING_PHYSICAL_VALIDATION
PR437_SOURCE_MUTATION=false

DEHARNESS_BASE_MAIN=8165cc441abd45f4d46f7439fa57edee1470c917
DEHARNESS_BRANCH=feature/n3w-production-firmware-deharness-20260921
DEHARNESS_PR=461
```

The DEHARNESS line is a new successor firmware target, not a rewrite of the physical-validation artifact.

## Product composition

The production target combines:

1. the existing F1.0-RC2 full-board product baseline:
   - SCD30 / SHT30 / BH1750;
   - RS485 soil temperature/moisture/EC;
   - battery and low-voltage protection;
   - LCD;
   - OTA and captive portal;
2. the merged PR #437 N3-W product transport:
   - authenticated pairing and persisted runtime material;
   - Direct MQTT;
   - ESP-NOW Relay;
   - Direct / Discovery / Relay path state machine;
   - Direct recovery scheduling;
   - Option-B bounded telemetry FIFO;
   - boot-session / sequence ownership.

The new build target is:

`firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_production.yml`

## DEHARNESS implementation

Phase-4 observation code is now opt-in behind:

`GREENHOUSE_N3W_ENABLE_PHASE4_LAB`

The existing Phase-4 target still enables its original source harness and diagnostics and therefore receives this build flag automatically.

The production target uses only:

```yaml
greenhouse_n3w_core:
  id: n3w_product_core
  product_runtime: true
```

It does not enable:
- `phase4_source_harness`;
- `phase4_lab_diagnostics`;
- `phase4_product_runtime`;
- synthetic telemetry;
- periodic pairing-PoP logging;
- RTC watchdog breadcrumb export.

When the lab build flag is absent:
- `n3w_lab_diagnostics.cpp` implementation is not compiled into the active binary;
- `n3w_phase4_physical_harness.cpp` implementation is not compiled into the active binary;
- `n3w_rtc_breadcrumb.cpp` implementation is not compiled into the active binary;
- the core holds no Phase4PhysicalHarness or RTC-breadcrumb state;
- extra ESP-NOW channel-context observation and bounded diagnostic callback logging are compiled out.

The existing lab source remains in the repository for regression and forensic builds.

## Real production telemetry

A separate component was added:

`firmware/esphome_rc/components/greenhouse_n3w_production_telemetry/`

It reads the real F1.0-RC2 ESPHome entities and builds `gh.telemetry/1` payloads.

The bridge obtains `boot_id` and `seq` only through the N3-W product runtime and submits only through `submit_telemetry_json()`; it does not bypass N3-W with a direct MQTT publisher.

The payload uses the schema-supported sensor fields and omits redundant `quality="ok"` entries. Missing measurements are omitted while a quality marker is emitted. This keeps the worst-case compact payload below the N3-W 1024-byte plaintext budget.

## Protected PR #437 behavior

This source repair intentionally does not redesign:
- Direct / Relay state transitions;
- 60/120/240/480 s recovery backoff;
- 30 s HEALTHY_RELAY ownership ceiling;
- 85 s NO_RELAY Wi-Fi budget;
- 120 s NO_RELAY absolute budget;
- Option-B 24-entry FIFO and 100 ms drain spacing;
- ESP-NOW MAC completion ownership;
- Relay restore and callback quiescence;
- pairing/NVS/boot-session/sequence semantics.

## Validation

Dedicated workflow:

`.github/workflows/n3w-production-firmware-ci.yml`

The workflow requires:
1. production source-contract PASS;
2. ESPHome 2026.4.3 production config PASS;
3. complete production firmware compile PASS;
4. binary string negative guard proving known Phase-4 fixture markers are absent;
5. preserved Phase-4 lab target recompilation PASS.

At document creation time, PR #461 CI is still running. No Board flash, serial open, or T1 runtime mutation is authorized or performed by this gate.
