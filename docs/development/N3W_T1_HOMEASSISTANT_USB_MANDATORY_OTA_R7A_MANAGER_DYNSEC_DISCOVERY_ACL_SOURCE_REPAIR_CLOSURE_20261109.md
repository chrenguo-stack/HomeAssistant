# N3-W T1 Home Assistant mandatory-USB OTA
# R7A Manager DynSec Discovery ACL source repair closure — 2026-11-09

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_MANAGER_DYNSEC_DISCOVERY_ACL_SOURCE_REPAIR_20261109_01
RESULT=CLOSED_PASS
KF=KF-145
EXECUTABLE_SOURCE_HEAD=f2ea76d245ef98196624aca088f492c60d6f8821
PR=800
LIVE_T1_MUTATION=false
BROKER_LIVE_DYNSEC_MUTATION=false
PREPARE=false
USB_INSERTION=false
CONFIRM_USB_ERASE=false
MERGE=false
```

## 1. Incident

Boundary B pre-PREPARE diagnostics proved that the live Manager was healthy, OTA enabled,
the approved Home Assistant manifest was present, and the Manager rendered non-empty retained
Discovery payloads for:

- `homeassistant/update/n3w_t1_homeassistant/config`
- `homeassistant/button/n3w_t1_homeassistant_prepare/config`
- `homeassistant/button/n3w_t1_homeassistant_confirm_usb/config`

Home Assistant nevertheless had zero matching N3-W T1 devices and zero matching entities.

Source review found that the current Manager service identity still allowed only the historical
`homeassistant/device/+/config` and `homeassistant/binary_sensor/+/config` publish routes.
The new OTA Update/Button Discovery routes were not included in the Manager DynSec plan.

## 2. Root cause

```text
ROOT_CAUSE=MANAGER_DYNSEC_ROLE_DID_NOT_AUTHORIZE_R7A_OTA_DISCOVERY_TOPICS
FALSE_PASS_PATH=OTA_MQTT_UNIT_TESTS_USED_A_FAKE_CLIENT_AND_DID_NOT_EXERCISE_REAL_DYNSEC_PUBACK
KF144_REOPENED=false
```

This is independent from KF-144. KF-144 remains the already-closed simplified-runtime OTA
Settings compatibility incident.

## 3. Repair

The Manager service identity now adds exactly three publish permissions:

```text
homeassistant/update/n3w_t1_homeassistant/config
homeassistant/button/n3w_t1_homeassistant_prepare/config
homeassistant/button/n3w_t1_homeassistant_confirm_usb/config
```

The repair deliberately does **not** grant `homeassistant/#` to Manager.

Regression coverage now proves:

1. exact topic ACLs are present and broad `homeassistant/#` Manager publish remains absent;
2. every HomeAssistantUpdateSurface Discovery topic is authorized by the Manager identity plan;
3. isolated real Mosquitto + Dynamic Security accepts the three OTA Discovery publishes from
   the real Manager service identity and delivers them to the real Home Assistant service identity;
4. wrong client IDs remain rejected.

## 4. Historical S20 contract protection

The first repaired head exposed eight `greenhouse-manager CI` failures because the consumed
historical S20 executor intentionally freezes a 17-ACL Manager plan while the current Manager
plan now contains 20 ACLs.

```text
FAILED_HEAD=538126c538c73fbc4ba21b4246fabd78f4c26339
FAILED_RUN=42500168128
FAILURE=service_acl_count_drift
FAILED_TESTS=8
PASSED_TESTS=1531
SKIPPED_TESTS=1
```

The historical executor was **not** changed to accept 20 ACLs and its frozen dependency SHA was
not rewritten. Its already-consumed authorization semantics remain immutable. Tests instead
freeze the historical 17-ACL plan when testing historical S20 behavior and separately prove that
feeding the current 20-ACL plan into the historical executor still fails closed with
`service_acl_count_drift`.

## 5. Exact-head CI

Required CI for the source repair head `f2ea76d245ef98196624aca088f492c60d6f8821`:

```text
greenhouse-manager CI=SUCCESS
RUN=42500786838

M2 Dynamic Security CI=SUCCESS
RUN=42500787022

N3W T1 S20 real service handoff CI=SUCCESS
RUN=42500786915

N3W CI fast source and exact closure contract=SUCCESS
RUN=42500787067

Public repository safety CI=SUCCESS
RUN=42500787018

N3W T1 Core Stack current authority CI=SUCCESS
RUN=42500786825

N3W T1 deployment gate CI=SUCCESS
RUN=42500786888
```

Some unrelated/extended workflows were still running at the final source-closure observation.
They are not represented as completed evidence by this closure.

## 6. Current live disposition

The repository source is repaired, but the production Broker still requires fresh read-only
classification and then a separately authorized live DynSec role update. No production Broker
ACL has been changed by this gate.

```text
KF145_STATUS=SOURCE_REPAIR_CLOSED_PASS_LIVE_REVALIDATION_PENDING
BOUNDARY_B_STATUS=STOPPED_BEFORE_PREPARE
PREPARE_INVOKED=false
DEDICATED_USB_INSERTED=false
CONFIRM_USB_ERASE_AUTHORIZED=false
```

## 7. Next one gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_MANAGER_DYNSEC_DISCOVERY_ACL_LIVE_READONLY_PREFLIGHT_20261109_01
```

Purpose: read-only inspect the current production Manager MQTT identity, its exact DynSec role and
ACL set, Broker/Manager/Home Assistant health, and confirm the three OTA Discovery permissions are
absent before designing any live mutation.

Allowed:
- read-only T1/Broker/Manager/Home Assistant inspection;
- sanitized evidence capture;
- comparison with executable source head above.

Forbidden:
- DynSec mutation;
- credential rotation;
- Broker/Manager/Home Assistant restart;
- PREPARE;
- USB insertion;
- CONFIRM_USB_ERASE;
- U2+;
- board work;
- merge.

After PASS, a distinct live DynSec ACL apply authorization is required. The read-only preflight
does not itself authorize mutation.
