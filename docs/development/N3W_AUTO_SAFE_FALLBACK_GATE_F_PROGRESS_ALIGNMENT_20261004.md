# N3-W Auto Safe Fallback Gate F — Progress Alignment — 2026-10-04

Status: `SOURCE_REPAIR_R2_CI_PENDING`

## Repository authority

```text
PR=522
PR_STATE=OPEN_DRAFT
PR_MERGED=false
PR_HEAD_BRANCH=fix/n3w-auto-safe-fallback-production-core-convergence-20261003
PR_HEAD_BEFORE_SOURCE_REPAIR=7716dfd816436f6bc92c247c6779f807810f9f2e
SOURCE_R1=ece559a550692a15d58ca0975b17aea7e4a4cddf
TEST_R1=d2297cd402bdbf6a2476d37e230545f514a1a593
SOURCE_R2=91dfe3850fd64e4742e9773e6e8dffd724db7d88
TEST_R2=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
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
ACTIVE_GENERATION=3
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

## Serial evidence and reboot-suspect closure

Board B loaded provisioned runtime state, started in Direct mode, and repeatedly failed MQTT transport connection to the stale Broker endpoint. One new telemetry sample was held, then the same queued sample was repeatedly polled without a Direct MQTT opportunity.

No Broker-relocation discovery, Broker candidate attempt, Broker candidate promotion, or phased Direct-recovery log was observed during the original failure capture.

A separate 600-second continuous serial forensic window was then run after a 20-second arming period. It produced no spontaneous reboot evidence:

```text
REBOOT_SIGNATURE_COUNT=0
N3W_SAFE_REBOOT_COUNT=0
BROWNOUT_COUNT=0
WATCHDOG_COUNT=0
PANIC_COUNT=0
BOARD_B_UNEXPECTED_REBOOT_OBSERVED=false
```

The observed status-LED extinction was instead correlated with the product low-battery path:

```text
LOW_BATTERY_ENTRY_COUNT=1
BATTERY_SAMPLE_1=0.00V
BATTERY_SAMPLE_2=0.00V
BATTERY_SAMPLE_3=0.00V
STATUS_LED_OFF_CAUSE=LOW_BATTERY_PROTECTION
```

Therefore the previous unexpected-reboot hypothesis is closed for the observed event. Low-battery behavior remains a separate bench-condition concern and must not be confused with the Broker-relocation failure.

## Source defect classification

Production integration uses:

```text
BUSINESS_TELEMETRY_INTERVAL=60s
DIRECT_FAILURES_TO_DISCOVERY=3
FAILOVER_TRIGGER_WORST_ALIGNMENT_APPROX=180s
NO_RELAY_ABSOLUTE_BUDGET=120s
BROKER_RELOCATION_MQTT_FAILURE_TRIGGER=10s
```

The pre-repair implementation records Direct path-health failure when a new business telemetry sample is generated. Polling a held FIFO item uses transport-only accounting and does not advance Direct-failure hysteresis.

Therefore the effective Direct/no-MQTT recovery trigger was coupled to business telemetry cadence and could delay eligibility for Broker relocation beyond the no-Relay absolute recovery budget.

```text
DIRECT_NO_MQTT_RECOVERY_TRIGGER_DEPENDS_ON_BUSINESS_SAMPLE_CADENCE=true
SOURCE_TRIGGER_DEFECT=CONFIRMED
GATE_F_PHYSICAL_ACCEPTANCE_COMPLETE=false
```

## Source repair R1

R1 introduced an independent product-loop trigger while the runtime remains `DIRECT`, Wi-Fi is connected, and MQTT is disconnected. The existing 10-second MQTT-failure threshold, discovery session, target filtering, RAM-only retarget, TLS identity, credentials, and durable pairing state were preserved.

R1 intentionally did not change the existing three-failure Direct/Relay hysteresis.

R1 contract and exact F1.0-RC2 compile passed, but source review found a fail-closed gap in the standalone candidate path: `retarget_runtime_broker_(candidate, true)` can switch the runtime Broker address before its disconnect/reconnect request reports failure. The initial wrapper path could then reset without first guaranteeing rollback to the stable Broker address.

## Source repair R2

R2 closes the fail-closed gap without broad state-machine changes:

1. standalone reset with `rollback=true` always invokes the existing rollback helper, rather than only when `broker_candidate_active_` is already true;
2. candidate retarget/reconnect setup failure immediately invokes rollback before returning failure;
3. standalone Direct/MQTT relocation runs only while the existing phased `DirectRecoveryAttempt` is `IDLE`, preventing both recovery entry points from concurrently owning the shared `broker_*` relocation state;
4. business telemetry cadence remains outside the standalone trigger path;
5. no durable pairing, Broker credential, TLS identity, or NVS mutation is added.

Regression contracts now explicitly guard the IDLE ownership boundary and fail-closed rollback ordering.

## Current validation

At the current R2 HEAD, completed unrelated and safety checks include:

```text
PUBLIC_REPOSITORY_SAFETY=PASS
GREENHOUSE_MANAGER_CI=PASS
GATE_F_BOARD_B_PREFLIGHT_CI=PASS
```

The following R2 N3-W workflows are still running and must close before artifact generation:

```text
AUTO_SAFE_FALLBACK_PRODUCTION_CONVERGENCE=IN_PROGRESS
FULL_CHANNEL_FALLBACK_REGRESSION=IN_PROGRESS
MULTI_RELAY_GATEWAY_SELECTION_REGRESSION=IN_PROGRESS
```

The repaired exact artifact must not be generated or written to Board B until R2 source review and the exact production compile pass.

## Current gate

```text
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_DIRECT_MQTT_BROKER_RELOCATION_TRIGGER_SOURCE_REPAIR_R2_20261004_01
SOURCE_R2_IMPLEMENTED=true
SOURCE_R2_REVIEW=PASS_PENDING_CI
EXACT_PRODUCTION_COMPILE=PENDING
REPAIRED_ARTIFACT_BUILD=HOLD
BOARD_WRITE=HOLD
T1_LIVE_MUTATION=false
NODE_BROKER_HOST_MUTATION=false
STALE_BROKER_PHYSICAL_ORACLE_PRESERVED=true
MERGE=false
```
