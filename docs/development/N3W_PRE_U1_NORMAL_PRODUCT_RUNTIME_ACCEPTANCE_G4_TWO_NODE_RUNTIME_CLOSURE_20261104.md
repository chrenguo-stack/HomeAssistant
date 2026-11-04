# N3-W Pre-U1 G4 two-node normal runtime closure

Date: 2026-11-04

## 1. Result

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G4_TWO_NODE_RUNTIME_20261104_01
RESULT=CLOSED_PASS

PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
PRE_U1_G2_RESULT=CLOSED_PASS
PRE_U1_G3_RESULT=CLOSED_PASS
PRE_U1_G4_RESULT=CLOSED_PASS

TARGET_OBSERVATION_MINUTES=10
OBSERVATION_START_UTC=2026-11-04T07:23:12Z
OBSERVATION_END_UTC=2026-11-04T07:33:13Z
OBSERVATION_SECONDS=601
DIRECT_RELAY_FAILOVER_TEST=false
```

The G4 route exercised both registered nodes together under ordinary Direct-mode product conditions only. No pairing, registration, board flashing, service restart or Direct/Relay failover action was used.

## 2. Two-node canonical continuity

Node A:

```text
NODE_ID_SHA256=7c5197ca0643ea0669c2ee43d5d89a994b09b0394fdd7e9872fea5aa4d97e090
SAMPLE_COUNT=11
SEQ_FIRST=44
SEQ_LAST=54
SEQ_DELTA=10
ADVANCING_INTERVAL_COUNT=10
SEQ_NEVER_DECREASED=true
BOOT_SESSION_COUNT=1
SOURCE=direct
```

Node B:

```text
NODE_ID_SHA256=589486b4e4e7fb05fc0a7e8994d977b67c60ce72770b80af6ee74eef0bd1d724
SAMPLE_COUNT=11
SEQ_FIRST=24
SEQ_LAST=34
SEQ_DELTA=10
ADVANCING_INTERVAL_COUNT=10
SEQ_NEVER_DECREASED=true
BOOT_SESSION_COUNT=1
SOURCE=direct
```

Every one-minute sample interval advanced for both nodes. No identity collision, boot reset or source transition occurred.

## 3. Business-state continuity

The read-only business snapshot was unchanged from start to end:

```text
REGISTERED_NODE_COUNT_START=2
REGISTERED_NODE_COUNT_END=2
ACTIVE_NODE_ID_LEASE_COUNT_START=2
ACTIVE_NODE_ID_LEASE_COUNT_END=2
ACTIVE_CREDENTIAL_ASSIGNMENT_COUNT_START=2
ACTIVE_CREDENTIAL_ASSIGNMENT_COUNT_END=2
UNRESOLVED_FIRST_REGISTRATION_COUNT_START=0
UNRESOLVED_FIRST_REGISTRATION_COUNT_END=0
```

## 4. Product-service continuity

Start and end evidence both showed:

```text
MANAGER_STATE=running
MANAGER_RESTART_COUNT=0
MANAGER_IMAGE=local/greenhouse-manager:fresh-b863ddd95909

HOMEASSISTANT_STATE=running
HOMEASSISTANT_RESTART_COUNT=0
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

BROKER_STATE=running
BROKER_RESTART_COUNT=0
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d

TCP_47110=LISTEN
UDP_47111=LISTEN
TCP_47112=CLOSED
```

No service restart was used as a test repair.

## 5. Home Assistant continuity

The first G4 end-check incorrectly returned zero devices because the observer command omitted the already-required `GH_SYSTEM_ID` fallback when the identity file was not found at the two attempted locations. That result is invalid observer evidence, not a product failure.

The corrected read-only check returned:

```text
NODE_A_HA_DEVICE_MATCH_COUNT=1
NODE_A_HA_ENTITY_COUNT=17
NODE_B_HA_DEVICE_MATCH_COUNT=1
NODE_B_HA_ENTITY_COUNT=6
G4_HA_CORRECTED_ENDCHECK=PASS
```

The operator additionally confirmed in the normal Home Assistant UI that:
- Node A real sensor values still continue changing;
- Node A and Node B remain two separate devices;
- no duplicate Node A device appeared.

Therefore:

```text
HA_TWO_NODE_DEVICE_CONTINUITY=PASS
HA_NODE_A_NOT_DUPLICATED=PASS
HA_NODE_A_NOT_OVERWRITTEN=PASS
NODE_A_REAL_SENSOR_UI_CONTINUITY=PASS
```

## 6. Sensor/UI cadence clarification

The exact deployed Node A/B artifact source is bound to:

```text
NODE_AB_FIRMWARE_SOURCE_HEAD=414ff0290db37e89a0e137d30f491e6c17cba2b0
TARGET=firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
N3W_TELEMETRY_INTERVAL=60s
SCD30_UPDATE_INTERVAL=30s
SHT30_UPDATE_INTERVAL=30s
BH1750_UPDATE_INTERVAL=30s
SOIL_READ_INTERVAL=20min
```

The N3-W telemetry package publishes the current sensor-state bundle only every 60 seconds. Therefore Home Assistant is not expected to show continuously changing values. Air/CO2/light local samples update at 30-second cadence, but HA receives the N3-W bundle at 60-second cadence. Soil readings can remain unchanged much longer because the exact target currently triggers the RS485 soil read cycle every 20 minutes.

This cadence observation is not a G4 failure because G4 tests runtime continuity, not production sampling-policy fitness. The 20-minute soil cadence is retained as a separate product-parameter review item before final production release.

## 7. Final classification

```text
TWO_NODE_IDENTITY_STABILITY=PASS
TWO_NODE_CANONICAL_TELEMETRY_CONTINUITY=PASS
NO_CROSS_NODE_COLLISION=PASS
NODE_A_REAL_SENSOR_CONTINUITY=PASS
NODE_B_RUNTIME_CONTINUITY=PASS
HOMEASSISTANT_TWO_DEVICE_CONTINUITY=PASS
PRODUCT_SERVICE_STABILITY=PASS
BUSINESS_STATE_STABILITY=PASS
PAIRING_WINDOW_REMAINED_CLOSED=PASS

OBSERVER_FALSE_NEGATIVE_CLASSIFIED=true
PRODUCT_FAILURE=false
NEW_KF_REQUIRED=false

RESULT=CLOSED_PASS
```

## 8. Next boundary

```text
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G5_FREEZE_REFERENCE_20261104_01
AUTO_EXECUTE_NEXT_GATE=false

G5_LIVE_PRODUCT_MUTATION=false
G5_UPDATER_APPLY=false
G5_UPDATER_ROLLBACK=false
PR774_MERGE=false
STOP=true
```

G5 is a separate read-only freeze/revalidation gate. This G4 closure does not enter it automatically.
