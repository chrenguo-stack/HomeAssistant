# N3-W Pre-U1 G2 Node A real sensor runtime acceptance closure

Date: 2026-11-04

## 1. Result

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G2_NODE_A_REAL_SENSOR_RUNTIME_20261104_01
RESULT=CLOSED_PASS
U0_RESULT=CLOSED_PASS
U0_REOPEN=false
PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
PRE_U1_G2_RESULT=CLOSED_PASS
U1_MANAGER_A_TO_B_STATUS=SUSPENDED
U1_PLAN_PRESERVED=true

NODE_A_FIRMWARE_UNCHANGED=true
NODE_A_NVS_UNCHANGED=true
NODE_A_REPAIRED=false
NODE_A_IDENTITY_PRESERVED=true
REPAIR_PAIRING_REQUIRED=false

NODE_A_REAL_SENSOR_RUNTIME=PASS
CANONICAL_SOURCE=direct
CANONICAL_SAME_BOOT=true
FIVE_CONSECUTIVE_CANONICAL_ADVANCES=true
CANONICAL_SEQ_BASELINE=14
CANONICAL_SEQ_FINAL=19
CANONICAL_SEQUENCE_GAP=false

HA_NODE_DEVICE_MATCH_COUNT=1
HA_ALL_7_RAW_ENTITIES_PRESENT=true
HA_ALL_7_RAW_STATES_FINITE=true
HA_UI_NODE_A_SINGLE_DEVICE=true
HA_UI_7_RAW_ENTITIES_HAVE_VALUES=true
HA_UI_VALUES_CONTINUE_UPDATING=true

MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
SERVICE_RESTART_AS_TEST_REPAIR=false

T1_DATABASE_MUTATION=false
HOMEASSISTANT_STORAGE_DIRECT_EDIT=false
MQTT_INTEGRATION_MANUAL_RECONFIGURE=false
BROKER_ACL_BROADENING=false
```

G2 is closed PASS. Node A retained its existing registered identity and credentials; no firmware write, NVS reset, re-pairing, direct database write, Home Assistant storage edit, MQTT reconfiguration, Broker ACL change, or product-service restart was used to obtain the result.

## 2. Physical precondition evidence

The operator completed the intended production sensor hookup with the board fully powered through one path only.

```text
POWER_PATH=USB_ONLY
USB_AND_BOOST_SIMULTANEOUS=false

SCD30_CONNECTED=true
SHT30_CONNECTED=true
BH1750_CONNECTED=true
RS485_SOIL_CONNECTED=true
RS485_A_B_CONFIRMED=true
RS485_SENSOR_VCC_ACTIVE_V=4.85

NODE_A_BOOT_SUCCESS=true
LCD_NORMAL=true
VISIBLE_HARDWARE_FAULT=false
```

The RS485 sensor supply was measured at 4.85 V before the final runtime acceptance. No visible hardware fault was present.

## 3. Authoritative runtime evidence

The primary acceptance oracle was the Manager durable canonical cursor in the configured N3-W replay database, read with SQLite read-only mode plus `PRAGMA query_only=ON`.

Public-safe Node A correlation hash:

```text
NODE_ID_SHA256=7c5197ca0643ea0669c2ee43d5d89a994b09b0394fdd7e9872fea5aa4d97e090
BOOT_SESSION_SHA256=7423559e23a10d6c1cb0673a9c852c1ece955b5a011427fc953bdbec092e2c5b
```

The final G2 capture began at canonical sequence 14 and observed five strict same-boot advances:

```text
14 -> 15 -> 16 -> 17 -> 18 -> 19
SOURCE_EACH_ADVANCE=direct
G2_CONSECUTIVE_CURSOR_ADVANCES=5
G2_FIVE_CONSECUTIVE_CURSOR_ADVANCES=true
G2_CURSOR_CAPTURE_RC=0
```

Observed Manager timestamps advanced at approximately the configured 60-second N3-W telemetry cadence. No sequence gap or boot-session change occurred in the acceptance window.

Earlier read-only observations in the same physical session had already shown the same boot-session hash progressing from sequence 6 to 10 and later to 14. Those observations are supporting continuity evidence; the formal five-cycle acceptance authority is sequence 14 through 19.

## 4. Real sensor / Home Assistant evidence

The seven required raw channels were represented exactly once in the Home Assistant entity registry:

```text
air_temperature_c=1
air_humidity_pct=1
co2_ppm=1
illuminance_lx=1
soil_temperature_c=1
soil_moisture_pct=1
soil_ec_us_cm=1

HA_ALL_7_RAW_ENTITIES_PRESENT=true
HA_TARGET_DEVICE_ID_COUNT=1
HA_NODE_DEVICE_MATCH_COUNT=1
HA_RECORDER_DB_PRESENT=true
HA_ALL_7_RAW_STATES_FINITE=true
G2_HA_MACHINE_ACCEPTANCE=true
```

Home Assistant Recorder held finite current states for all seven entities. Home Assistant may apply the user's configured presentation units to device-class state values; Recorder presentation values are therefore used here as liveness/presence evidence, not as raw-unit metrology evidence.

The current N3-W telemetry builder in
`firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml`
only emits a sensor under `measurements` when the sensor has a finite state, and in that same branch sets the corresponding `quality` entry to `ok`. Missing values are omitted and receive `warming`, `fault`, or `stale` quality instead. Combined with Manager canonical acceptance and all seven HA measurement entities carrying finite state, the G2 requirement that connected raw channels not remain in an error/not-present state is satisfied.

Absolute sensor calibration is outside G2 scope. Finite/schema-valid acquisition and end-to-end runtime continuity are the acceptance target.

## 5. User-facing UI acceptance

The operator confirmed through the normal Home Assistant UI:

```text
HA_UI_NODE_A_SINGLE_DEVICE=true
HA_UI_7_RAW_ENTITIES_HAVE_VALUES=true
HA_UI_VALUES_CONTINUE_UPDATING=true
```

No duplicate Node A device was observed. The real sensor entities remained visible with values and continued updating.

## 6. Product-service continuity

At final machine acceptance:

```text
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
```

No Manager or Home Assistant restart was needed to make telemetry or entities appear. The gate did not authorize or perform a Broker/Manager/HA repair restart.

## 7. Read-only harness incidents

Two temporary observation attempts failed before the final R3 observer was used:

1. R1: the temporary Paho MQTT VERSION2 callback attempted `int(reason_code)` and raised a Python `TypeError`. This was an observer implementation defect.
2. R2: a temporary additional MQTT observer connection received `Not authorized`. This observer path was abandoned rather than modifying Dynamic Security, credentials, ACLs, Home Assistant MQTT configuration, or the running product identities.

Neither incident is classified as a product failure. During these observer-only failures the Manager durable cursor continued advancing on the same boot and Direct source. The final authority deliberately avoided creating any additional MQTT client and used durable canonical state plus read-only Home Assistant registry/Recorder evidence.

This preserves the existing rule that an observability/harness failure must not be promoted to a product failure when stronger product-state evidence is available.

## 8. Scope and non-claims

This G2 closure proves:

- the already registered Node A keeps its existing identity without repair pairing;
- SCD30, SHT30, BH1750 and the RS485 soil sensor are connected through the intended product path;
- seven required raw measurement channels reach the product runtime with finite/schema-valid state;
- the Manager canonical cursor advances continuously for at least five consecutive 60-second telemetry cycles;
- Home Assistant maintains one Node A device with the seven required raw entities;
- user-facing values remain live without product-service restart.

This G2 closure does not claim:

- laboratory calibration accuracy;
- long-duration soak;
- battery/solar endurance;
- Direct/Relay failover retest;
- formal production low-battery policy certification;
- second-node registration or two-node coexistence.

## 9. Next boundary

```text
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G3_NODE_B_FIRST_REGISTRATION_20261104_01
G3_T1_BUSINESS_MUTATION=true
G3_BOARD_ACCESS=true
AUTO_EXECUTE_NEXT_GATE=false
BOARD_ACCESS=false
STOP=true
```

G3 requires a genuinely fresh/unregistered second ESP32-C6 node and normal product first-registration physical work. G2 closure does not authorize G3 execution.

Authority plan:
`docs/development/N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_PLAN_20261104.md`.
