# N3-W Auto Safe Fallback Gate F — Stale Broker Host Runtime Failure — 2026-10-04

Status: `GATE_F_STALE_BROKER_HOST_RUNTIME_ACCEPTANCE_FAIL`

## Scope

This document records the first physical Gate F runtime failure after Board B existing-identity credential recovery succeeded.

No T1 address mutation was performed during this diagnostic sequence. The observed stale Broker address pre-existed the Gate F runtime check and was preserved intentionally as the physical oracle for auto safe fallback.

## Durable recovery state

Existing-identity credential recovery completed successfully:

```text
NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
NODE_ID_PRESERVED=true
CURRENT_PAIRING_ID_SHA256=470bb405ee9bca1db201be35802cfa8b0cdcbf093ddfb3d436856ece71da10ae
CURRENT_PAIRING_IS_NEW=true
PAIRING_EPOCH=9
PAIRING_SESSION_STATE=approved
PAIRING_SESSION_REASON=operator_approved
REGISTRATION_ACTIVE=true
ACTIVE_GENERATION=3
PENDING_GENERATION=None
CREDENTIAL_STATE=active
RECOVERY_DURABLE_STATE_PASS=true
```

Manager restart count remained unchanged:

```text
MANAGER_RESTART_COUNT=1
MANAGER_STARTED_AT=2026-10-01T11:49:58.671855407Z
```

## Runtime failure evidence

The recovered Board B still did not reconnect to Broker TLS or resume canonical telemetry:

```text
CURRENT_BOOT_SESSION=dc40c82e1467cf88
CURRENT_SEQ=112
CURRENT_SOURCE=direct
CURRENT_UPDATED_AT=2026-09-24T13:28:35.713Z
BOARD_B_8883_ESTABLISHED_COUNT=0
POST_RECOVERY_TELEMETRY_PASS=false
```

The current T1 LAN endpoint is reachable on Broker TLS:

```text
T1_CURRENT_LAN_IP=REDACTED_PRIVATE_ADDRESS
BROKER_TCP_8883_CURRENT_T1_IP=PASS
```

The running Manager configuration still advertises the historical Broker host to node credentials:

```text
GH_N3W_NODE_BROKER_HOST=HISTORICAL_PRIVATE_ADDRESS
GH_N3W_NODE_BROKER_PORT=8883
GH_N3W_NODE_BROKER_TLS_SERVER_NAME=armbian
GH_N3W_PAIRING_ADVERTISED_HOST=auto
GH_N3W_PAIRING_BIND_HOST=0.0.0.0
```

Therefore the exact physical fault condition is:

```text
PERSISTED_OR_ISSUED_BROKER_HOST=HISTORICAL_PRIVATE_ADDRESS
CURRENT_REACHABLE_BROKER_HOST=CURRENT_T1_PRIVATE_ADDRESS
STALE_BROKER_HOST_PRESERVED=true
BOARD_B_MQTT_RECOVERY_OBSERVED=false
BOARD_B_TELEMETRY_RECOVERY_OBSERVED=false
```

## Source oracle

Validated production source head:

```text
b2419d17c198a85b7b50d9c1771544c2e3a0ab6b
```

The production core contains a Broker relocation path which:

- keeps the durable Broker host as the stable baseline;
- waits for persistent MQTT failure;
- performs local Manager/Broker discovery;
- temporarily retargets only the runtime MQTT endpoint;
- preserves TLS server name, CA, account identity, and durable pairing data;
- promotes a verified discovered Broker host only for the current boot.

Relevant policy constants are:

```text
MQTT_FAILURE_TRIGGER_MS=10000
DISCOVERY_BUDGET_MS=1000
CANDIDATE_BUDGET_MS=6000
CLEANUP_RESERVE_MS=2000
DISCOVERY_MIN_INTERVAL_MS=60000
```

The logical Direct path also requires three business-sample failures before transitioning from `DIRECT` to `DISCOVERY`. The exact target business telemetry cadence is 60 seconds.

## Acceptance result

Observation continued far beyond both the initial 90-second post-recovery check and the approximate three-sample Direct failure window. The canonical cursor remained unchanged and no Board B TCP/8883 connection appeared.

Therefore:

```text
PAIRING_RECOVERY=PASS
CREDENTIAL_RECOVERY=PASS
BROKER_SERVICE_CURRENT_IP=PASS
STALE_BROKER_HOST_FAULT_CONDITION=CONFIRMED
AUTO_FALLBACK_RECOVERY_OBSERVED=false
GATE_F_STALE_BROKER_HOST_RUNTIME_ACCEPTANCE=FAIL
FAILURE_IS_NOT_INSUFFICIENT_WAIT=true
T1_ADDRESS_MUTATION_NOT_STARTED=true
MERGE=false
```

This result does not yet identify the exact internal failing sub-state. The next step is read-only runtime forensics to distinguish among:

1. Direct path never leaving `DIRECT` despite repeated MQTT-unavailable business samples;
2. transition to `DISCOVERY` without reaching a Direct recovery probe;
3. Broker relocation discovery not starting;
4. discovery starting but retaining no valid candidate;
5. candidate runtime retarget occurring but MQTT/TLS verification failing.

Do not repair `GH_N3W_NODE_BROKER_HOST` before this forensic split is captured, because doing so would erase the current physical failure oracle.
