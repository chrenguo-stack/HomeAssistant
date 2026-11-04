# N3-W Pre-U1 normal product runtime acceptance plan

Date: 2026-11-04

## 0. Status and purpose

```text
PLAN=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE
PLAN_STATUS=FROZEN_FOR_NEXT_CHAT_EXECUTION
U0_RESULT=CLOSED_PASS
U0_REOPEN=false
U1_MANAGER_A_TO_B_STATUS=SUSPENDED
U1_LIVE_APPLY_AUTHORIZED=false
T1_A_ACCESS=false
T1_B_ROLE=CLEAN_REFERENCE_AND_PRE_U1_BUSINESS_RUNTIME
MERGE=false
```

This stage is inserted after U0 and before Manager A -> B U1.

Purpose:

1. convert the clean upgrade-validation T1_B from a near-laboratory business state into a bounded,
   realistic normal-product state;
2. exercise Home Assistant local-user onboarding and the real user-facing UI;
3. exercise one registered node with real sensor telemetry;
4. add a second node through the normal product registration path;
5. prove two-node normal runtime without Manager/Broker/Home Assistant restart or manual database work;
6. re-run the updater safety baseline and prove normal business use did not alter the U0 hard upgrade
   authority;
7. freeze a public-safe `PRE_U1_BUSINESS_RUNTIME_REFERENCE` for the later Manager A -> B validation.

This plan does not replace or modify the archived U0 Baseline A.

## 1. Why this does not invalidate U0

A1 explicitly separates upgrade-safety invariants from expected business-runtime drift.

The following are expected to change during normal product use and must not be gated by historical
exact equality:

- Home Assistant entity/device/config-entry counts;
- Broker/Dynamic Security client and role population;
- registration and node population;
- normal telemetry state;
- user-facing Home Assistant state.

The following remain upgrade-safety authority and must not drift unexpectedly:

- Manager/Home Assistant/Broker approved image identity;
- platform;
- per-component runtime contract;
- fixed Broker/HA/custom-component configuration authority;
- persistent path type/ownership;
- supported SQLite schema identity/version;
- Manager/Home Assistant MQTT identity;
- FC4 CA and system CA;
- Dynamic Security structural authority.

Therefore adding a Home Assistant local user or a second normal node does not reopen U0. A fresh
post-business revalidation is nevertheless required before U1.

## 2. Frozen current authority

```text
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_PRODUCT_SOURCE=b863ddd959090ca139af76bd68dbef31d773e6de
MANAGER_A_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
PLATFORM_ALL=linux/arm64

BASELINE_A_MANIFEST=infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json
BASELINE_A_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
BASELINE_A_BYTES=2275
A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7
A2_ARCHITECTURE_SHA256=447f57f3563cb7766f145a2ea005d5d79d1beee7585ed07c6572ce2b3a833faa
```

## 3. Hard rules for this stage

```text
HOMEASSISTANT_CLOUD_REQUIRED=false
HOMEASSISTANT_LOCAL_OWNER_ALLOWED=true
HOMEASSISTANT_STORAGE_DIRECT_EDIT=false
MQTT_INTEGRATION_MANUAL_RECONFIGURE=false
DIRECT_T1_DATABASE_WRITE=false
DIRECT_CREDENTIAL_INJECTION=false
DIRECT_NODE_ID_WRITE=false
BROKER_ACL_BROADENING=false
SERVICE_RESTART_AS_TEST_REPAIR=false
U1_UPGRADE_EXECUTION=false
U1_TARGET_B_BUILD=false
```

Normal user/product writes are allowed only in their own bounded gate.

Do not "clean up" the system back to U0 after PASS. The resulting normal business state is the
intended predecessor state for future U1.

## 4. Test topology

### Node A — real business telemetry reference

Use the already registered production node as the continuity reference when fresh evidence proves it
is healthy.

Target sensor profile:

- SCD30 CO2;
- SHT30 air temperature/humidity;
- BH1750 illuminance;
- RS485 soil temperature/moisture/EC.

The purpose is product-path telemetry and Home Assistant state continuity, not metrology/calibration
certification.

### Node B — additional lifecycle reference

Use a second fresh/unregistered ESP32-C6 production node through the normal product registration
route.

Node B may remain sensorless during this stage. Its primary purpose is to prove multi-node
registration, separate identity/credential state, Manager/Broker coexistence and automatic Home
Assistant discovery.

Raw hardware IDs, pairing IDs, setup secrets, MQTT passwords and key material remain private and
must not be committed to GitHub.

## 5. Gate sequence

```text
G0 READONLY_PREFLIGHT
 -> G1 HOMEASSISTANT_LOCAL_ONBOARDING
 -> G2 NODE_A_REAL_SENSOR_RUNTIME
 -> G3 NODE_B_NORMAL_FIRST_REGISTRATION
 -> G4 TWO_NODE_NORMAL_RUNTIME
 -> G5 PRE_U1_BUSINESS_REFERENCE_AND_UPGRADE_SAFETY_REVALIDATION
```

A failure or STOP in one gate does not authorize the next gate.

---

# G0 — Fresh read-only preflight

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_20261104_01
LIVE_RUNTIME_MUTATION=false
BOARD_MUTATION=false
HOMEASSISTANT_MUTATION=false
PAIRING_MUTATION=false
```

## Purpose

Prove the current live T1_B is still a safe starting point after U0 and before introducing normal
business writes.

## Required checks

Repository/GitHub:

- fresh rebind PR #774 and candidate head;
- confirm U0 closure and Baseline A authority;
- confirm Manager A -> B remains suspended.

T1/runtime:

- host system state acceptable;
- relevant failed units absent;
- Broker, Manager and Home Assistant running;
- expected product service set exact;
- no unresolved updater transaction;
- pairing/registration mutation path quiescent;
- no active certificate lifecycle mutation;
- current images/platform/runtime contracts match Baseline A;
- current updater `baseline` succeeds.

Home Assistant:

- HTTP/UI endpoint is reachable;
- only determine whether local onboarding is already complete or still required;
- do not read/export user passwords/tokens;
- do not patch `.storage`;
- do not create an account in G0.

Current node state:

- establish whether the existing registered node is online/offline;
- collect public-safe counts/status only;
- do not alter credentials or registration state.

## PASS

```text
G0_PASS_IF=
  U0_BASELINE_HARD_AUTHORITY_MATCH
  AND PRODUCT_SERVICES_HEALTHY
  AND NO_ACTIVE_UPDATER_TRANSACTION
  AND NO_ACTIVE_PAIRING_MUTATION
  AND HOMEASSISTANT_HTTP_REACHABLE
```

If the baseline differs, STOP and classify the exact field. Do not automatically repair or reset the
T1.

---

# G1 — Home Assistant local-user onboarding and UI acceptance

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G1_HA_LOCAL_ONBOARDING_20261104_01
MUTATION_TYPE=NORMAL_HOMEASSISTANT_USER_STATE
HOMEASSISTANT_CLOUD=false
```

## Operation

If Home Assistant already has a usable local Owner, use it and do not create an extra account merely
for the test.

If first-use onboarding is still pending, the operator uses the official Home Assistant Web UI to:

1. create the local Owner account;
2. log in successfully;
3. finish only the minimum local onboarding required to reach the normal UI;
4. skip Home Assistant Cloud/Nabu Casa;
5. do not manually replace/reconfigure the product MQTT integration;
6. do not edit YAML or `.storage`.

No account password, token, email or other private login material is copied into chat or GitHub.

## Acceptance

- local login succeeds after normal page reload;
- Overview/Settings are usable;
- MQTT integration has no visible failed/reconfigure state;
- Broker, Manager and Home Assistant service identities/images are unchanged;
- no unexpected product service restart;
- no direct configuration or storage patch was required.

Home Assistant local auth/session data is legitimate business state and is not rolled back after PASS.

---

# G2 — Node A real sensor runtime acceptance

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G2_NODE_A_REAL_SENSOR_RUNTIME_20261104_01
BOARD_PHYSICAL_WORK=true
T1_DATABASE_MUTATION=false
REGISTRATION_MUTATION=false
```

## Operation

Using the already registered Node A:

1. preserve its current NODE_ID/credentials;
2. connect the intended production sensor set;
3. boot through the ordinary production path;
4. allow sensor initialization/warm-up;
5. observe at least five consecutive normal telemetry cycles after warm-up.

Target raw measurements:

```text
air_temperature_c
air_humidity_pct
co2_ppm
illuminance_lx
soil_temperature_c
soil_moisture_pct
soil_ec_us_cm
```

Derived/product measurements may also be observed:

```text
vpd_kpa
dew_point_c
absolute_humidity_g_m3
ppfd_umol_m2_s
dli_today_mol_m2_d
dli_yesterday_mol_m2_d
battery_v
battery_pct
```

## Acceptance

- Node A keeps the same registered identity; no re-pairing is needed;
- at least five consecutive canonical telemetry updates advance for Node A;
- all physically connected raw sensor channels are present with finite/schema-valid values after
  warm-up;
- their quality does not remain in an error/not-present state;
- Manager does not repeatedly reject valid Node A telemetry;
- Home Assistant has one Node A device identity, not duplicates;
- the relevant entities show live state and continue updating;
- where Home Assistant history is enabled, multiple state points can be observed;
- no Broker/Manager/HA restart is needed to make the data appear.

Absolute calibration accuracy is out of scope. A plausible/schema-valid reading is sufficient for
this gate.

---

# G3 — Second node normal first registration

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G3_NODE_B_FIRST_REGISTRATION_20261104_01
T1_BUSINESS_MUTATION=true
BOARD_ACCESS=true
DIRECT_DATABASE_WRITE=false
DIRECT_CREDENTIAL_INJECTION=false
```

## Precondition

Use one genuinely fresh/unregistered Node B.

Before the user confirms registration, prove:

- no active registration transaction;
- Node A remains healthy;
- no existing Node B registration/credential assignment for the private target identity;
- product services remain healthy.

## Operation

Use only the normal product UX:

```text
fresh Node B
 -> normal Wi-Fi/product setup as required
 -> LCD/normal registration entry
 -> user selects/confirms the intended T1
 -> normal registration/pairing protocol
 -> durable Manager COMMIT
 -> product runtime
```

Forbidden shortcuts:

- SQLite writes;
- manual NODE_ID assignment;
- manual MQTT credential insertion;
- manual DynSec client creation;
- reuse of consumed pairing authorization.

## Acceptance

T1/Manager:

- exactly one new logical Node B is registered;
- Node B NODE_ID is distinct from Node A;
- registration state is APPROVED/committed through the supported path;
- Node B credential lifecycle generation 1 becomes ACTIVE;
- Node B application-key state is valid;
- the deterministic DynSec client/role/ACL state exists for Node B;
- the temporary pairing window closes;
- no unresolved cleanup/reconciliation remains.

Continuity:

- Node A identity/credentials/state remain unchanged;
- Node A telemetry continues;
- Broker, Manager and Home Assistant are not restarted as part of registration.

Home Assistant:

- Node B telemetry causes automatic discovery;
- Node B appears as a separate device without manual MQTT integration changes;
- Node A is not duplicated or overwritten.

Node B may remain sensorless; missing physical sensor measurements are not a G3 failure.

---

# G4 — Two-node normal runtime acceptance

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G4_TWO_NODE_RUNTIME_20261104_01
TARGET_OBSERVATION_MINUTES=10
DIRECT_RELAY_FAILOVER_TEST=false
```

## Operation

Run Node A and Node B together under ordinary Direct-mode product conditions.

Observe for at least 10 minutes after both nodes have reached stable product runtime.

## Acceptance

- both node identities remain unique and stable;
- both canonical telemetry cursors continue advancing;
- no persistent cross-node Topic/identity collision occurs;
- no persistent valid-telemetry rejection occurs;
- Node A real sensor entities keep updating;
- Node B remains visible/available with the capabilities its hardware actually provides;
- Home Assistant contains one device per node and no duplicate device/entity identity caused by the
  second registration;
- Broker, Manager and Home Assistant remain running;
- no relevant failed unit appears;
- no unexpected Manager/Broker/HA restart is required.

This is not a packet-loss or radio failover stress test. Direct/Relay roaming/failover remains a
separate already-bounded domain.

---

# G5 — Freeze Pre-U1 business runtime reference and revalidate upgrade safety

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G5_FREEZE_REFERENCE_20261104_01
LIVE_PRODUCT_MUTATION=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
```

## Required proof

After G1-G4 PASS:

1. run the reviewed updater `baseline` twice without intervening mutation;
2. require the two fresh outputs to be byte-identical;
3. compare the fresh hard baseline with archived U0 Baseline A;
4. require no unexpected hard-authority drift;
5. capture a separate public-safe normal-business reference.

Expected strongest result:

```text
FRESH_BASELINE_READ_1_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
FRESH_BASELINE_READ_2_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
FRESH_BASELINE_EQUALS_U0_BASELINE_A=true
```

If exact byte equality does not hold, U0 historical evidence remains valid, but U1 entry is STOP
until the changed field is classified against A1.

## Public-safe business reference

Freeze a machine-readable/reference document containing only non-secret or hashed facts, for example:

- exact product image/platform/runtime-contract authority;
- Baseline A SHA and fresh revalidation SHA;
- approved node count;
- active credential assignment count;
- active node-lease count;
- DynSec population counts/structural status, not secrets;
- Home Assistant device/entity/config-entry counts and storage versions;
- product service running/restart observations;
- Node A/Node B identity only as public-safe hashes if identity correlation is needed;
- proof that Node A has real sensor telemetry;
- proof that Node B is independently registered;
- proof that both nodes are visible in HA.

Do not commit raw hardware identity, pairing ID, Setup Secret, MQTT password, key material, HA
password/token or private network locator.

## Final PASS

```text
PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE=CLOSED_PASS
PRE_U1_BUSINESS_RUNTIME_REFERENCE_FROZEN=true
PRE_U1_UPGRADE_SAFETY_REVALIDATION=PASS
U0_REOPEN=false
U1_MANAGER_A_TO_B_MAY_BE_RECONSIDERED=true
U1_AUTO_RESUME=false
```

---

## 6. Failure classification

### Home Assistant onboarding/UI failure

Do not immediately modify the HA container or `.storage`. Determine whether the failure is:

- first-use UI state;
- MQTT integration/bootstrap state;
- authentication/onboarding state;
- service health;
- network/browser access.

### Sensor failure

Do not classify the T1/Manager as failed solely because one physical sensor does not initialize.
Separate:

- wiring/power/bus;
- sensor warm-up;
- board firmware;
- telemetry schema;
- Manager validation;
- HA presentation.

### Node B registration failure

Preserve failed transaction evidence. Do not delete database rows, regenerate identities or replay
consumed authorization to manufacture a clean retry.

### Hard baseline drift after normal business use

STOP U1. Classify the field under A1. Do not reset the T1 back to U0 solely to regain equality.

## 7. Evidence and GitHub archival

After every gate:

- record the exact gate result;
- preserve sanitized direct evidence;
- update current state only after the gate closes;
- do not rely on chat-only conclusions.

After G5 PASS create:

```text
infra/n3w-t1/clean-reference/pre-u1-business-runtime-reference-<date>.json
docs/development/N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_CLOSURE_<date>.md
```

and align:

- `docs/development/N3W_CURRENT_STATE.md`;
- `docs/development/N3W_CURRENT_STATE_INDEX.md`;
- `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`.

## 8. Out of scope

This stage does not require:

- Manager A -> B source repair or live upgrade;
- Home Assistant image upgrade;
- Broker image upgrade;
- Home Assistant Cloud/Nabu Casa;
- direct HA `.storage` manipulation;
- Direct/Relay failover retest;
- LoRa;
- long-duration soak;
- sensor laboratory calibration;
- solar/battery endurance;
- T1_A legacy/dirty validation.

## 9. Next one gate

```text
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_20261104_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

G0 is read-only. It is the only gate authorized for automatic entry in the next chat. G1-G3 require
their own explicit execution boundary because they create user/business/physical state.
