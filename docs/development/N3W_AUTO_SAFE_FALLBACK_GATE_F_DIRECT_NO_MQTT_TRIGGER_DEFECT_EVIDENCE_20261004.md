# N3-W Auto Safe Fallback Gate F — Direct/no-MQTT trigger defect evidence — 2026-10-04

Status: `PHYSICAL_FAIL_SOURCE_TRIGGER_DEFECT_SUPPORTED`

## Physical state

Board B successfully completed existing-identity credential recovery while preserving stable node identity:

```text
NODE_ID_PRESERVED=true
PAIRING_EPOCH=9
PAIRING_SESSION_STATE=approved
ACTIVE_GENERATION=3
PENDING_GENERATION=None
CREDENTIAL_STATE=active
RECOVERY_DURABLE_STATE_PASS=true
```

T1 current LAN address and deployment configuration:

```text
T1_CURRENT_LAN_IP=REDACTED_PRIVATE_ADDRESS
GH_N3W_NODE_BROKER_HOST=HISTORICAL_PRIVATE_ADDRESS
GH_N3W_NODE_BROKER_PORT=8883
GH_N3W_NODE_BROKER_TLS_SERVER_NAME=armbian
GH_N3W_PAIRING_ADVERTISED_HOST=auto
GH_N3W_PAIRING_BIND_HOST=0.0.0.0
BROKER_TCP_8883_CURRENT_T1_IP=PASS
```

Manager-visible runtime remained stale:

```text
CURRENT_BOOT_SESSION=dc40c82e1467cf88
CURRENT_SEQ=112
CURRENT_SOURCE=direct
CURRENT_UPDATED_AT=2026-09-24T13:28:35.713Z
BOARD_B_8883_ESTABLISHED_COUNT=0
```

## Board serial evidence

A passive serial capture after the credential recovery showed the product runtime loading provisioned state and starting in Direct mode, then repeatedly timing out against the stale broker address:

```text
Provisioned N3-W runtime state loaded
Simplified N3-W product runtime active ... mode=direct direct_channel=6
MQTT_EVENT_ERROR
esp-tls: select() timeout
esp-tls: Failed to open new connection
mqtt_client: Error transport connect
Disconnected: TCP disconnected
```

The first real N3-W telemetry sample was admitted into the hold FIFO:

```text
N3-W telemetry held seq=0 depth=1 path=0 ownership=0
```

After that, the same held sample was repeatedly polled while MQTT remained unavailable:

```text
N3-W telemetry held without Direct MQTT opportunity seq=0 depth=1 state_result=0
```

No serial evidence was observed for:

```text
N3-W Broker relocation discovery started
N3-W Broker relocation discovery retained=...
N3-W Broker relocation candidate attempt started
N3-W Broker relocation candidate promoted for this boot
N3-W opened phased Direct recovery
```

## Exact-source trigger analysis

Validated product source:

```text
b2419d17c198a85b7b50d9c1771544c2e3a0ab6b
```

`submit_telemetry_json()` records Direct path-health failure only when a new business telemetry sample is generated. Backlog polling intentionally passes `TelemetryPathAccounting::TRANSPORT_ONLY`, so repeated polling of one held sample does not increment Direct-failure hysteresis.

The production target sets:

```text
n3w_telemetry_interval=60s
```

The LocalPath policy requires:

```text
direct_failures_to_discovery=3
```

Therefore the Direct/no-MQTT path can require approximately three business-sample intervals before transitioning out of Direct. With the production 60-second telemetry cadence this is approximately 180 seconds in the worst alignment case, before later Direct-recovery/MQTT-recovery/Broker-relocation logic can become eligible.

This conflicts with the intended no-Relay recovery budget of 120 seconds and also defeats the broker relocation policy's own 10-second persistent MQTT failure trigger as an end-to-end trigger from the initial stale-broker condition.

## Current classification

```text
PAIRING_RECOVERY=PASS
CREDENTIAL_RECOVERY=PASS
STALE_BROKER_HOST_CONDITION=CONFIRMED
BROKER_RELOCATION_RECOVERY_OBSERVED=false
GATE_F_STALE_BROKER_HOST_RUNTIME_ACCEPTANCE=FAIL
DIRECT_NO_MQTT_RECOVERY_TRIGGER_DEPENDS_ON_BUSINESS_SAMPLE_CADENCE=true
SOURCE_TRIGGER_DEFECT=SUPPORTED
MERGE=false
```

## Safety boundary

Do not update `GH_N3W_NODE_BROKER_HOST` yet. The stale value is the current physical failure oracle. Do not merge PR #522. Preserve the Board/T1 state while the trigger defect is reviewed and repaired.
