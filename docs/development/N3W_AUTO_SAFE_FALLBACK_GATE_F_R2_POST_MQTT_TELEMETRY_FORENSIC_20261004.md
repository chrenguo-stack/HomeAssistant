# N3-W Auto Safe Fallback Gate F R2 Post-MQTT Telemetry Forensic

Date: 2026-10-04

## Status

R2 stale-Broker recovery is physically proven through Broker discovery, runtime Broker retarget, MQTT reconnect, and candidate promotion for the current boot.

The end-to-end acceptance is not closed because the Manager canonical cursor did not advance during a subsequent 90-second read-only observation. The canonical cursor remained at the historical boot/session record while Manager restart count remained unchanged and the stale deployment oracle remained preserved.

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
- Direct + MQTT transport invokes runtime Direct publish and emits `telemetry Direct single attempt submitted` on success

Runtime Direct topic:

- `gh/v1/<system_id>/ingress/node/<node_id>/telemetry`

## Current forensic split

The current open failure domain is post-MQTT telemetry delivery, not Broker relocation:

1. production telemetry script does not generate/admit a sample after recovery; or
2. Board submits Direct MQTT telemetry but Broker/Manager ingestion does not advance canonical state.

No R3 source mutation is authorized from this evidence alone.

## Next gate

Use one controlled reset with a bounded 90-second serial capture. Preserve the stale Broker oracle. Confirm, in one boot:

- stale Broker connection failure;
- relocation discovery;
- MQTT candidate connection and promotion;
- first 60-second production telemetry generation/admission;
- `telemetry held` and, if Direct MQTT is usable, `telemetry Direct single attempt submitted`.

Then compare the Manager canonical cursor before/after the same observation. This physically separates Board-side generation/publish from Broker/Manager ingestion without relying on missing logs.

MERGE=false
GATE_F=CANNOT_CLOSE
R3_MUTATION=false
