# N3-W Auto Safe Fallback — Direct MQTT Broker Relocation Trigger — Source Repair R2 Closure — 2026-10-04

Status: `SOURCE_REPAIR_R2_CLOSED_PASS`

## Frozen source authority

```text
TASK=N3W_AUTO_SAFE_FALLBACK_DIRECT_MQTT_BROKER_RELOCATION_TRIGGER_SOURCE_REPAIR_R2_20261004_01
PR=522
PR_STATE=OPEN_DRAFT
PR_MERGED=false
SOURCE_R1=ece559a550692a15d58ca0975b17aea7e4a4cddf
SOURCE_R2=91dfe3850fd64e4742e9773e6e8dffd724db7d88
TEST_R2=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
FROZEN_SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
FROZEN_SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
MERGE=false
```

Later documentation-only commits on the PR branch do not change the frozen product source above.

## Physical failure that triggered this repair

Gate F established a valid existing-identity pairing and credential-recovery baseline, but the production node still held a historical Broker LAN address while the current Broker was reachable at a different LAN address. The node remained in Direct Wi-Fi with MQTT transport failures and did not start Broker relocation.

The first exact physical oracle therefore failed:

```text
PAIRING_RECOVERY=PASS
CREDENTIAL_RECOVERY=PASS
STALE_BROKER_HOST_PRESERVED=true
BOARD_B_8883_ESTABLISHED_COUNT=0
POST_RECOVERY_TELEMETRY_PASS=false
GATE_F_STALE_BROKER_HOST_RUNTIME_ACCEPTANCE=FAIL
```

Exact private addresses are intentionally omitted from the repository.

## Root cause

Production business telemetry is generated every 60 seconds and Direct-to-Discovery hysteresis requires three Direct failures. Direct/no-MQTT business samples were therefore able to gate Broker relocation behind approximately 180 seconds of business cadence, exceeding the 120-second no-Relay absolute recovery budget even though the Broker-relocation MQTT failure trigger itself is 10 seconds.

```text
BUSINESS_TELEMETRY_INTERVAL=60s
DIRECT_FAILURES_TO_DISCOVERY=3
OLD_EFFECTIVE_TRIGGER_WORST_ALIGNMENT_APPROX=180s
NO_RELAY_ABSOLUTE_BUDGET=120s
BROKER_RELOCATION_MQTT_FAILURE_TRIGGER=10s
```

## R1 repair

R1 added a cadence-independent Direct MQTT health trigger. While the runtime remains Direct, Wi-Fi is connected, and MQTT is disconnected, an independent monotonic timer now drives the existing discovery/retarget mechanisms after the existing 10-second persistent MQTT-failure threshold.

R1 preserves:

- the existing three-failure Direct/Relay hysteresis;
- nonblocking Manager discovery;
- RAM-only Broker-host retargeting;
- TLS server name, CA, MQTT identity and credentials;
- durable pairing and Broker state;
- candidate TTL, retry spacing and bounded candidate windows.

## R2 review repair

Source review found one fail-closed gap in R1: runtime retarget could have switched the client address before disconnect/reconnect setup returned failure, while the standalone path did not unconditionally restore the stable Broker address.

R2 closes this and prevents overlap with phased Direct recovery:

```text
A1_STANDALONE_RETARGET_SETUP_FAILURE_ROLLBACK=CLOSED
A2_STANDALONE_AND_PHASED_RECOVERY_MUTUAL_EXCLUSION=CLOSED
```

R2 behavior:

1. standalone Direct Broker relocation runs only while `DirectRecoveryPhase::IDLE`;
2. candidate retarget setup failure immediately calls the existing rollback helper;
3. rollback reset is unconditional when rollback is requested, including the partial-retarget window before the candidate-active flag is set;
4. the original phased Direct-recovery Broker relocation path remains unchanged.

## Automated validation

Latest R2 validation completed successfully:

```text
AUTO_SAFE_FALLBACK_PRODUCTION_CONVERGENCE_CI=PASS
PR474_FULL_CHANNEL_REGRESSION_CI=PASS
MULTI_RELAY_GATEWAY_SELECTION_REGRESSION_CI=PASS
F1_0_RC2_TARGET_CONFIG_VALIDATION=PASS
F1_0_RC2_EXACT_COMPILE=PASS
GATE_F_BOARD_B_PREFLIGHT_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI=PASS
```

The contract suite additionally guards that the standalone trigger is independent of telemetry submission cadence, is limited to the Direct path, does not mutate durable identity/credentials, is bounded, rolls back fail-closed on retarget setup failure, and does not run concurrently with phased Direct recovery.

## Exact artifact binding inputs

```text
SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
TARGET_BLOB_SHA=32a2b3cb29be4e1bce46807d8825b6a4c37999ec
TELEMETRY_BRIDGE_BLOB_SHA=ce16f2389d146f9b25e95cbb628547e11ce36bd6
TRANSPORT_BLOB_SHA=aa39d4b083f2db1b30a76efb1afef156db355a35
PRODUCT_CORE_INIT_BLOB_SHA=75949b916144383ae57ebe90ece41e9f248b8cbe
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

## Separate Board-B LED forensic closure

The reported irregular status-LED extinction was investigated in a continuous 600-second serial session. No spontaneous reboot, N3-W fail-safe reboot, brownout, watchdog or panic was observed. The LED-off event coincided with three consecutive 0.00 V battery samples and entry into low-battery protection. This is a separate bench-power/battery-sensing condition and is not evidence of the Broker-relocation defect.

## Safety boundary / next gate

```text
SOURCE_REPAIR_R2=PASS
REPAIRED_EXACT_ARTIFACT_NOT_YET_BOUND=true
BOARD_MUTATION=false
T1_LIVE_MUTATION=false
STALE_BROKER_PHYSICAL_ORACLE_PRESERVED=true
PHYSICAL_REVALIDATION_NOT_STARTED=true
MERGE=false
```

Next gate:

```text
N3W_AUTO_SAFE_FALLBACK_DIRECT_MQTT_BROKER_RELOCATION_TRIGGER_R2_EXACT_ARTIFACT_BUILD_AND_BINDING_20261004_01
```
