# N3-W Auto Safe Fallback Gate F R2 Post-MQTT Telemetry Forensic

Date: 2026-10-04

## Status

R2 stale-Broker recovery is physically proven through Broker discovery, runtime Broker retarget, MQTT reconnect, candidate promotion, production telemetry generation, queue admission, Direct MQTT publish submission, Broker delivery, and Manager Direct ingress receipt.

The end-to-end canonical acceptance is blocked by a pre-existing boot-session compatibility gap, not by the R2 Broker fallback implementation.

## Exact-source review

Exact source authority:

- SOURCE_HEAD: `67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1`

Production telemetry bridge:

- `firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml`
- interval: `${n3w_telemetry_interval}`; production value is 60 seconds
- accepted telemetry is passed to `submit_telemetry_json()`

N3-W transport source:

- `firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp`
- Direct path publishes to `gh/v1/<system_id>/ingress/node/<node_id>/telemetry`
- `N3-W telemetry Direct single attempt submitted` means the local MQTT publish call accepted the message

Boot-session source:

- `GreenhouseN3wCore` owns telemetry identity through `NvsBootSessionStore` + `BootSessionManager`
- normal boot-session start loads the durable counter, increments it, persists it, verifies it, then issues the new session
- NVS namespace/key remain `gh_n3w/boot_state`
- Manager replay/canonical high-water remains fail-closed: a lower session is rejected as `stale_boot_session`

## Physical evidence

A controlled boot proved:

- stale Broker connection failure
- Broker relocation discovery
- retained discovery candidate
- standalone Direct Broker candidate attempt
- MQTT connected
- candidate promoted for this boot
- production telemetry generated at the normal interval
- `N3-W telemetry held seq=0`
- `N3-W telemetry Direct single attempt submitted seq=0`

T1 evidence then proved:

- Manager Direct subscription active on `gh/v1/greenhouse/ingress/node/+/telemetry`
- Broker accepted the Board client on TLS MQTT 8883 using the expected node identity
- Manager received Direct ingress once per production telemetry interval
- every received message was rejected with `code=stale_boot_session`
- Manager/Broker remained running

## Root-cause comparison

Read-only Manager replay state:

```text
MANAGER_HIGHEST_SESSION_HEX=dc40c82e1467cf88
MANAGER_HIGHEST_SESSION_DECIMAL=15870905187090026376
```

Read-only Board B NVS dump of the exact `gh_n3w/boot_state` record format found a monotonic historical sequence from 0 through 17. The highest valid persisted record in the dump was:

```text
BOARD_BOOT_STATE_MAX_HEX=0000000000000011
BOARD_BOOT_STATE_MAX_DECIMAL=17
```

The esptool read itself reset the Board after the dump, so the normal firmware may advance the counter again on the next telemetry identity allocation. That does not affect the classification because the Board counter remains many orders of magnitude below the Manager durable high-water.

The relation is therefore proven:

```text
BOARD_DURABLE_BOOT_COUNTER << MANAGER_DURABLE_BOOT_HIGH_WATER
```

This is the historical KF-050 compatibility-migration condition: a legacy/random historical boot-session high-water remains on Manager while the repaired product now uses a small monotonic durable counter on the Board.

## Root-cause classification

```text
R2_BROKER_FALLBACK=PASS
R2_MQTT_RECOVERY=PASS
R2_TELEMETRY_GENERATION=PASS
R2_DIRECT_PUBLISH_PATH=PASS
BROKER_TO_MANAGER_DELIVERY=PASS
MANAGER_DIRECT_SUBSCRIPTION=PASS
MANAGER_REPLAY_REJECTION=EXPECTED_SAFE_BEHAVIOR
KF050_COMPATIBILITY_MIGRATION_GAP=CONFIRMED
R2_SOURCE_DEFECT=false
MANAGER_DEFECT=false
BOOT_SESSION_RECOVERY_FLOOR_REQUIRED=true
CANONICAL_ADVANCE=BLOCKED_BY_STALE_BOOT_SESSION
```

## Safety boundary

Do not repair this by deleting or lowering Manager replay/canonical high-water. Do not relax `stale_boot_session` rejection semantics.

The safe repair direction is the existing KF-050 recovery-floor path: establish a Board durable boot-session floor at or above the Manager high-water through the guarded migration flow, with the required successor pairing/credential lifecycle, then return to normal product firmware and prove the next boot session is strictly greater than the Manager high-water.

No recovery-floor mutation was executed by this forensic step.

## Boundary

MERGE=false
GATE_F=CANNOT_CLOSE
R3_MUTATION=false
MANAGER_REPLAY_RELAXATION=false
MANAGER_HIGH_WATER_CLEAR=false
KF050_COMPATIBILITY_MIGRATION_GAP=CONFIRMED
BOOT_SESSION_RECOVERY_FLOOR_REQUIRED=true
