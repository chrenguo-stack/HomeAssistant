# N3-W Auto Safe Fallback Gate F — Progress Alignment — 2026-10-04

Status: `SOURCE_REPAIR_GATE_ENTERED`

## Repository authority

```text
PR=522
PR_STATE=OPEN_DRAFT
PR_MERGED=false
PR_HEAD_BRANCH=fix/n3w-auto-safe-fallback-production-core-convergence-20261003
PR_HEAD_BEFORE_SOURCE_REPAIR=7716dfd816436f6bc92c247c6779f807810f9f2e
MERGE=false
```

## Gate F prerequisite restoration

Board B exact-artifact write and readback passed. Existing-identity credential recovery also completed successfully while preserving the existing logical node identity.

```text
PAIRING_RECOVERY=PASS
CREDENTIAL_RECOVERY=PASS
PAIRING_SESSION_STATE=approved
CREDENTIAL_STATE=active
PENDING_GENERATION=None
RECOVERY_DURABLE_STATE_PASS=true
```

No registration deletion, database reset, durable node replacement, or T1-address mutation was used.

## Current physical failure oracle

The current T1 Broker service is reachable on its present LAN address, while the node's durable/issued Broker host still points to the historical LAN address. Exact private addresses are intentionally omitted from the public repository.

```text
CURRENT_T1_BROKER_8883=PASS
NODE_BROKER_HOST=HISTORICAL_PRIVATE_ADDRESS
STALE_BROKER_HOST_PRESERVED=true
BOARD_B_8883_ESTABLISHED_COUNT=0
POST_RECOVERY_TELEMETRY_PASS=false
GATE_F_STALE_BROKER_HOST_RUNTIME_ACCEPTANCE=FAIL
```

## Serial evidence

Board B loaded provisioned runtime state, started in Direct mode, and repeatedly failed MQTT transport connection to the stale Broker endpoint. One new telemetry sample was held, then the same queued sample was repeatedly polled without a Direct MQTT opportunity.

No Broker-relocation discovery, Broker candidate attempt, Broker candidate promotion, or phased Direct-recovery log was observed during the captured window.

The serial capture showed a reboot signature, so it is not used as a pre-capture same-boot elapsed-time oracle.

## Source defect classification

Production integration uses:

```text
BUSINESS_TELEMETRY_INTERVAL=60s
DIRECT_FAILURES_TO_DISCOVERY=3
FAILOVER_TRIGGER_WORST_ALIGNMENT_APPROX=180s
NO_RELAY_ABSOLUTE_BUDGET=120s
BROKER_RELOCATION_MQTT_FAILURE_TRIGGER=10s
```

The current implementation records Direct path-health failure when a new business telemetry sample is generated. Polling a held FIFO item uses transport-only accounting and does not advance Direct-failure hysteresis.

Therefore the effective Direct/no-MQTT recovery trigger is coupled to business telemetry cadence. This can delay eligibility for the existing Broker-relocation path beyond the no-Relay absolute recovery budget.

```text
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

1. Preserve the existing three-failure Direct/Relay hysteresis.
2. Preserve nonblocking discovery, RAM-only Broker retarget, TLS identity, credentials, and durable pairing state.
3. Do not create a second Direct/Relay state machine.
4. While runtime remains `DIRECT`, Wi-Fi is connected, and MQTT remains disconnected, drive Broker relocation from an independent monotonic MQTT-failure timer.
5. Start bounded discovery after the existing 10-second persistent MQTT-failure threshold without waiting for business telemetry.
6. Keep candidate verification and rollback bounded by the existing discovery/candidate/cleanup policy.
7. Preserve the physical stale-Broker oracle until a repaired exact artifact is ready for physical revalidation.

## Safety boundary

```text
BOARD_MUTATION=false
T1_LIVE_MUTATION=false
NODE_BROKER_HOST_MUTATION=false
MERGE=false
```
