# N3-W Auto Safe Fallback Gate F — Progress Alignment — 2026-10-04

Status: `SOURCE_REPAIR_GATE_ENTERED`

## Repository authority

```text
PR=522
PR_STATE=OPEN_DRAFT
PR_MERGED=false
PR_HEAD_BRANCH=fix/n3w-auto-safe-fallback-production-core-convergence-20261003
PR_HEAD_BEFORE_SOURCE_REPAIR=7716dfd816436f6bc92c247c6779f807810f9f2e
VALIDATED_PRODUCT_SOURCE_BEFORE_GATE_F=b2419d17c198a85b7b50d9c1771544c2e3a0ab6b
MERGE=false
```

## Gate F prerequisite restoration

Board B exact-artifact write and post-write readback passed. The initial healthy paired baseline failed because Board B entered Gate F carrying the deliberately-unrepaired KF-099 repair-wait condition.

The existing-identity recovery path was completed using the exact live pairing transaction and the Board's existing Setup Secret. Durable identity was preserved:

```text
NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
NODE_ID_PRESERVED=true
PAIRING_EPOCH=9
PAIRING_SESSION_STATE=approved
PAIRING_SESSION_REASON=operator_approved
ACTIVE_GENERATION=3
PENDING_GENERATION=None
CREDENTIAL_STATE=active
RECOVERY_DURABLE_STATE_PASS=true
```

No registration delete, database reset, durable node replacement, or T1-address test mutation was used.

## Current T1 / Board runtime condition

T1 moved from the historical LAN address to the current LAN address while the Manager deployment still carries the historical node Broker host:

```text
T1_CURRENT_IP=192.168.68.195
BOARD_B_IP=192.168.68.180
GH_N3W_NODE_BROKER_HOST=10.168.1.194
GH_N3W_NODE_BROKER_PORT=8883
GH_N3W_NODE_BROKER_TLS_SERVER_NAME=armbian
GH_N3W_PAIRING_ADVERTISED_HOST=auto
GH_N3W_PAIRING_BIND_HOST=0.0.0.0
BROKER_TCP_8883_192.168.68.195=PASS
```

This stale Broker host is intentionally preserved as the Gate F physical oracle. Do not update it before the source repair is validated.

## Physical runtime failure

After credential recovery, Board B still did not reconnect to MQTT or advance canonical telemetry:

```text
CURRENT_BOOT_SESSION=dc40c82e1467cf88
CURRENT_SEQ=112
CURRENT_SOURCE=direct
CURRENT_UPDATED_AT=2026-09-24T13:28:35.713Z
BOARD_B_8883_ESTABLISHED_COUNT=0
POST_RECOVERY_TELEMETRY_PASS=false
GATE_F_STALE_BROKER_HOST_RUNTIME_ACCEPTANCE=FAIL
```

A serial capture showed the product runtime loading the provisioned state and starting in Direct mode, followed by repeated TCP/TLS connection timeouts against the stale Broker address:

```text
Provisioned N3-W runtime state loaded
Simplified N3-W product runtime active ... mode=direct direct_channel=6
MQTT_EVENT_ERROR
esp-tls: select() timeout
esp-tls: Failed to open new connection
mqtt_client: Error transport connect
Disconnected: TCP disconnected
```

The N3-W telemetry queue showed:

```text
N3-W telemetry held seq=0 depth=1 path=0 ownership=0
N3-W telemetry held without Direct MQTT opportunity seq=0 depth=1 state_result=0
```

No Broker-relocation or phased Direct-recovery log was observed.

The serial capture itself showed a reboot signature, so it is not used as a same-boot elapsed-time oracle for the pre-capture runtime. It remains valid for the post-boot state-machine observations above.

## Source defect classification

The exact product target uses:

```text
n3w_telemetry_interval=60s
```

The LocalPath policy uses:

```text
direct_failures_to_discovery=3
```

The current source intentionally records one Direct path-health failure only when a new business telemetry sample is generated. Polling an already-held FIFO item uses `TelemetryPathAccounting::TRANSPORT_ONLY` and therefore does not increment Direct-failure hysteresis.

Consequently a Direct node with healthy Wi-Fi but a dead/stale MQTT Broker address may need approximately three 60-second business-sample intervals before the logical path can leave Direct. Only later can the existing Direct-recovery MQTT phase drive Broker relocation.

This creates a source-level budget contradiction:

```text
BUSINESS_TELEMETRY_INTERVAL=60s
DIRECT_FAILURES_TO_DISCOVERY=3
FAILOVER_TRIGGER_WORST_ALIGNMENT_APPROX=180s
NO_RELAY_ABSOLUTE_BUDGET=120s
BROKER_RELOCATION_MQTT_FAILURE_TRIGGER=10s
```

The 10-second Broker relocation trigger is therefore not an end-to-end trigger from the initial `Wi-Fi connected + MQTT disconnected` condition in the production integration.

Current classification:

```text
PAIRING_RECOVERY=PASS
CREDENTIAL_RECOVERY=PASS
STALE_BROKER_HOST_CONDITION=CONFIRMED
BROKER_RELOCATION_RECOVERY_OBSERVED=false
DIRECT_NO_MQTT_RECOVERY_TRIGGER_DEPENDS_ON_BUSINESS_SAMPLE_CADENCE=true
SOURCE_TRIGGER_DEFECT=CONFIRMED_FOR_REPAIR
GATE_F_PHYSICAL_ACCEPTANCE_COMPLETE=false
MERGE=false
```

## Source repair gate

```text
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_DIRECT_MQTT_BROKER_RELOCATION_TRIGGER_SOURCE_REPAIR_20261004_01
```

Repair intent:

1. Preserve `direct_failures_to_discovery=3` and the existing Direct/Relay hysteresis.
2. Preserve the existing nonblocking Manager discovery, RAM-only Broker retarget, TLS server name, CA, MQTT identity, and durable pairing state.
3. Do not create a second Direct/Relay state machine.
4. While the runtime is still `DIRECT`, Wi-Fi is connected, and MQTT remains disconnected, drive the existing Broker relocation path from an independent monotonic MQTT-failure timer.
5. After `kBrokerRelocationMqttFailureTriggerMs=10000`, allow bounded Manager discovery and candidate verification without waiting for a new business telemetry sample.
6. Bound the standalone Direct relocation attempt using the existing discovery/candidate/cleanup budgets.
7. If the candidate succeeds, promote only the boot-local runtime Broker host.
8. If the candidate fails, rollback to the stable runtime host and retain existing failover behavior.
9. Keep the current physical stale-Broker oracle unchanged until a repaired exact artifact is ready for physical revalidation.

## Safety boundary

```text
BOARD_MUTATION=false
T1_LIVE_MUTATION=false
GH_N3W_NODE_BROKER_HOST_MUTATION=false
MERGE=false
```
