# N3-W Auto Safe Fallback Gate F R2 Post-MQTT Telemetry Forensic

Date: 2026-10-04

## Status

R2 stale-Broker recovery is physically proven through Broker discovery, runtime Broker retarget, MQTT reconnect, and candidate promotion for the current boot.

The first production telemetry sample after recovery was also physically observed on Board B. The Board admitted seq=0 into the N3-W queue and the Direct MQTT path accepted the publish call, while the Manager canonical cursor remained unchanged.

Therefore the earlier Board-side generation versus downstream-ingress split is now closed on the Board side. The remaining failure domain begins after the local ESPHome MQTT publish submission and includes Broker receipt/authorization, Broker delivery to the Manager subscription, and Manager ingress validation/canonical commit.

## Exact-source authority

- SOURCE_HEAD: `67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1`
- production telemetry bridge: `firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml`
- production telemetry interval: 60 seconds
- transport source: `firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp`
- Direct topic: `gh/v1/<system_id>/ingress/node/<node_id>/telemetry`

The production bridge executes every 60 seconds and passes accepted payloads to `submit_telemetry_json()`. The N3-W transport logs queue admission and successful local Direct publish submission separately.

## Physical evidence

Pre-reset canonical cursor:

```text
CURSOR_FOUND=true
BOOT_SESSION=dc40c82e1467cf88
SEQ=112
SOURCE=direct
UPDATED_AT=2026-09-24T13:28:35.713Z
```

Same controlled-reset boot Broker relocation evidence:

```text
N3-W Broker relocation discovery started
MQTT_EVENT_ERROR
esp-tls: select() timeout
Disconnected: TCP disconnected
N3-W Broker relocation discovery retained=1
N3-W standalone Direct Broker candidate attempt started
Connected
N3-W standalone Direct Broker candidate promoted for this boot
```

Same boot production telemetry evidence:

```text
N3-W telemetry held seq=0 depth=1 path=0 ownership=0
N3-W telemetry Direct single attempt submitted seq=0 depth_after=0
```

Runtime evidence:

```text
Startup low-battery grace period: 300 seconds
Simplified N3-W product runtime active node=node_39c9c9c308eac09b5cbb00ac9780f6bc mode=direct direct_channel=6
```

Post-90-second canonical cursor:

```text
CURSOR_FOUND=true
BOOT_SESSION=dc40c82e1467cf88
SEQ=112
SOURCE=direct
UPDATED_AT=2026-09-24T13:28:35.713Z
```

Manager/deployment invariants:

```text
MANAGER_RESTART_COUNT=1
GH_N3W_NODE_BROKER_HOST=10.168.1.194
BOARD_FLASH_WRITE=false
BOARD_NVS_MUTATION=false
T1_MUTATION=false
```

## Interpretation

The following are now physically proven in one bounded boot:

- stale Broker connection fails;
- discovery finds the current Broker endpoint;
- runtime Broker retarget succeeds;
- MQTT reconnect succeeds;
- candidate is promoted for the current boot;
- the 60-second production telemetry script reaches N3-W admission;
- telemetry seq=0 enters the hold queue;
- the Direct MQTT publish call is locally accepted.

The unchanged Manager canonical cursor proves that end-to-end delivery is still not complete.

`N3-W telemetry Direct single attempt submitted` must not be interpreted as Broker acknowledgement. It proves only that the local Direct MQTT publish call returned success to the N3-W transport. Broker receipt and downstream Manager processing remain unproven.

## Source-contract alignment

The Manager contract subscribes to:

```text
gh/v1/<system_id>/ingress/node/+/telemetry
```

which matches the Board Direct topic shape. Historical KF-089 repair contracts also require the corresponding Manager Direct-ingress Dynamic Security ACL.

## Current forensic boundary

```text
BROKER_RELOCATION_PHYSICAL=PASS
MQTT_RECONNECT_PHYSICAL=PASS
PRODUCTION_TELEMETRY_GENERATION=PASS
N3W_QUEUE_ADMISSION=PASS
LOCAL_DIRECT_MQTT_PUBLISH_SUBMISSION=PASS
BROKER_RECEIPT=NOT_PROVEN
MANAGER_DIRECT_SUBSCRIPTION_RUNTIME=NOT_PROVEN
MANAGER_INGRESS_ACCEPTANCE=NOT_PROVEN
CANONICAL_ADVANCE=FAIL
```

No R3 firmware source mutation is justified from this evidence.

## Next gate

Perform T1-side read-only ingress forensics before changing either firmware or Manager deployment:

1. verify the running Manager has the expected Direct-ingress subscription;
2. inspect Broker/Dynamic Security evidence for the active node credential and Direct publish ACL;
3. observe whether the Broker receives/forwards a fresh Board telemetry publication;
4. if Broker delivery is proven, inspect Manager rejection/validation evidence and replay/canonical state.

Preserve the stale deployment oracle and do not mutate Board NVS, Broker Dynamic Security state, Manager configuration, or T1 deployment during this forensic gate.

MERGE=false
GATE_F=CANNOT_CLOSE
R3_MUTATION=false
NEXT_FAILURE_DOMAIN=BROKER_OR_MANAGER_INGRESS
