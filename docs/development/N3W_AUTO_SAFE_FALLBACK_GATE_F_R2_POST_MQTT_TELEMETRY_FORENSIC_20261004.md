# N3-W Auto Safe Fallback Gate F R2 Post-MQTT Telemetry Forensic

Date: 2026-10-04

## Status

R2 stale-Broker recovery is physically proven through Broker discovery, runtime Broker retarget, MQTT reconnect, candidate promotion, production telemetry generation, queue admission, and Direct MQTT publish submission.

The end-to-end acceptance is not closed because the Manager canonical cursor does not advance. Live T1 evidence now proves the Direct ingress messages reach Manager but are rejected as `stale_boot_session` once per production telemetry interval.

## Exact-source review

Exact source authority:

- SOURCE_HEAD: `67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1`

Production telemetry bridge:

- `firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml`
- interval: `${n3w_telemetry_interval}`; production value is 60 seconds
- bridge exits only when N3-W runtime is not ready or telemetry identity/payload construction fails
- accepted telemetry is passed to `submit_telemetry_json()`

N3-W transport source:

- `firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp`
- admission first enqueues telemetry and emits a `telemetry held` log
- Direct + MQTT transport invokes runtime Direct publish and emits `telemetry Direct single attempt submitted` on local MQTT publish acceptance

Runtime Direct topic:

- `gh/v1/<system_id>/ingress/node/<node_id>/telemetry`

Boot-session source:

- `GreenhouseN3wCore` owns telemetry identity through `NvsBootSessionStore` + `BootSessionManager`
- normal boot-session start loads the durable counter, increments it, saves and verifies before issuing the session
- Manager replay/canonical high-water remains fail-closed: a lower session is rejected as `stale_boot_session`

## Physical evidence

One controlled 90-second boot showed:

- stale Broker connection failure
- Broker relocation discovery
- retained discovery candidate
- standalone Direct Broker candidate attempt
- MQTT connected
- candidate promoted for this boot
- production telemetry generated at the normal interval
- `N3-W telemetry held seq=0`
- `N3-W telemetry Direct single attempt submitted seq=0`

The Manager canonical cursor still remained on the historical Direct cursor.

Subsequent T1 read-only evidence proved the missing canonical update is not a Broker/ACL/subscription loss:

- Manager Direct subscription is active on `gh/v1/greenhouse/ingress/node/+/telemetry`
- Manager receives the target node's Direct ingress every production telemetry interval
- each received message is rejected with `code=stale_boot_session`
- Broker accepts the Board client on TLS MQTT 8883 using the expected node client ID and username
- no Board/T1 mutation occurred during the forensic read

## Current failure classification

The current open failure domain is no longer Broker relocation or MQTT transport.

```text
BROKER_RELOCATION=PASS
MQTT_RECONNECT=PASS
PRODUCTION_TELEMETRY_GENERATION=PASS
DIRECT_MQTT_LOCAL_SUBMISSION=PASS
BROKER_TO_MANAGER_DELIVERY=PASS
MANAGER_DIRECT_SUBSCRIPTION=PASS
MANAGER_INGRESS_RESULT=REJECTED_STALE_BOOT_SESSION
CANONICAL_ADVANCE=FAIL
```

This matches the safety semantics of the historical KF-050 boot-session contract: Manager must reject a candidate boot session lower than its durable high-water. Do not relax Manager replay protection and do not clear replay/canonical high-water as a shortcut.

The next forensic action is read-only comparison of:

1. Manager durable highest boot-session for this node; and
2. Board B durable `gh_n3w/boot_state` counter.

Only after that comparison should a recovery-floor or source-repair decision be made.

## Boundary

MERGE=false
GATE_F=CANNOT_CLOSE
R3_MUTATION=false
MANAGER_REPLAY_RELAXATION=false
MANAGER_HIGH_WATER_CLEAR=false
