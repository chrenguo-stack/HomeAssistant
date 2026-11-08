# N3-W T1 Home Assistant mandatory-USB OTA
# KF-145 Manager DynSec Discovery ACL live read-only preflight closure — 2026-11-09

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_MANAGER_DYNSEC_DISCOVERY_ACL_LIVE_READONLY_PREFLIGHT_20261109_01
RESULT=CLOSED_PASS
KF=KF-145
SOURCE_REPAIR_HEAD=f2ea76d245ef98196624aca088f492c60d6f8821
PREEXECUTION_VALIDATION_HEAD=f6e37a2f22ad6990e42d798c98fcca5798ab8dd6
LIVE_T1_MUTATION=false
BROKER_LIVE_DYNSEC_MUTATION=false
PREPARE=false
USB_INSERTION=false
CONFIRM_USB_ERASE=false
MERGE=false
```

## 1. Fresh live health

The real production T1 remained healthy and unchanged at the read-only observation:

```text
HOST_DAEMON_ACTIVE=active
SERVICES_OWNER_ACTIVE=active

MANAGER_RUNNING_COUNT=1
MANAGER_IMAGE=local/greenhouse-manager:fresh-7807271e4c48
MANAGER_IMAGE_ID=sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0

HOMEASSISTANT_RUNNING_COUNT=1
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
HOMEASSISTANT_RUNNING=true
HOMEASSISTANT_RESTART_COUNT=0

BROKER_RUNNING_COUNT=1
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
BROKER_RUNNING=true
BROKER_RESTART_COUNT=0

MANAGER_OTA_ENABLED=true
HA_DISCOVERY_ENABLED=true
```

The raw Manager username/client-id are not archived. Public-safe identity hashes are:

```text
MANAGER_MQTT_USERNAME_SHA256=1b9d48662c46940b82afaab00fb283f983b68b532d7baae7c2e1ea4b5e020d1a
MANAGER_MQTT_CLIENT_ID_SHA256=c980da07d0ff6c9332e5e2a343b0c01642600be11136f787c5a28c9627114142
```

## 2. Authoritative live DynSec state

```text
DYNSEC_SHA256=c0a5058185684f1fd343ed350774d15b13d6db4b7277a961b98148814feef800
DYNSEC_CHANGE_INDEX=11
DYNSEC_CLIENT_COUNT=6
DYNSEC_ROLE_COUNT=12

DYNSEC_MANAGER_EXACT_CLIENT_MATCH_COUNT=1
DYNSEC_MANAGER_ROLE_BINDING_COUNT=1
DYNSEC_MANAGER_ROLE_MATCH_COUNT=1
DYNSEC_MANAGER_ACL_COUNT=17
DYNSEC_MANAGER_PUBLISH_ACL_COUNT=4
```

All three R7A OTA Discovery permissions are absent:

```text
OTA_UPDATE_DISCOVERY_AUTHORIZED=false
OTA_PREPARE_DISCOVERY_AUTHORIZED=false
OTA_CONFIRM_USB_DISCOVERY_AUTHORIZED=false
BROAD_HOMEASSISTANT_PUBLISH_ALLOW_COUNT=0
THREE_OTA_DISCOVERY_ACLS_ABSENT=true
```

The two historical Manager Discovery permissions remain present exactly once:

```text
HOMEASSISTANT_DEVICE_DISCOVERY_EXACT_ALLOW_COUNT=1
HOMEASSISTANT_BINARY_SENSOR_DISCOVERY_EXACT_ALLOW_COUNT=1
```

This proves the production Manager role is the old 17-ACL form while the repaired source
Manager plan contains 20 ACLs.

## 3. Product-facing consequence

```text
HA_T1_DEVICE_MATCH_COUNT=0
HA_T1_ENTITY_MATCH_COUNT=0
HA_USB_TRANSACTION_PRESENT=false
HA_USB_PREPARE_STATE_PRESENT=false
BOUNDARY_B_STATUS=STOPPED_BEFORE_PREPARE
```

Therefore the real live state matches the KF-145 source defect exactly. The missing Home
Assistant device/control surface is not a UI navigation issue.

## 4. Reactivation behavior validated before live mutation

The repaired source publishes the OTA Discovery surface from the Manager MQTT
`_on_connect()` callback. The isolated real Mosquitto + Dynamic Security integration was
extended to begin with the historical 17-ACL Manager role, add the three exact R7A Discovery
ACLs through Dynamic Security, require the affected Manager MQTT client to reconnect, and
then prove the reconnected Manager can publish the OTA Discovery topic.

```text
PREEXECUTION_VALIDATION_HEAD=f6e37a2f22ad6990e42d798c98fcca5798ab8dd6
greenhouse-manager_CI=SUCCESS
M2_DYNAMIC_SECURITY_CI=SUCCESS
S20_REAL_SERVICE_HANDOFF_CI=SUCCESS
MANUAL_MANAGER_RESTART_REQUIRED=false
BROKER_RESTART_REQUIRED=false
```

The project will not use a manual Manager/Broker restart as the normal KF-145 repair route.

## 5. Next live mutation contract

Proposed next gate:

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_MANAGER_DYNSEC_DISCOVERY_ACL_LIVE_APPLY_20261109_01
AUTHORIZATION_GRANTED=false
```

The live apply must:
- fresh-check the exact Manager client/role binding and 17-ACL prestate;
- create a root-only private prechange DynSec snapshot before the first ACL command;
- add exactly three `publishClientSend allow priority=100` ACLs:
  - `homeassistant/update/n3w_t1_homeassistant/config`
  - `homeassistant/button/n3w_t1_homeassistant_prepare/config`
  - `homeassistant/button/n3w_t1_homeassistant_confirm_usb/config`;
- preserve every other client, role, ACL, default-access field and credential;
- verify the exact 20-ACL Manager poststate by authoritative live readback;
- require Manager automatic MQTT reconnect without container restart/replacement;
- require the Home Assistant `N3-W T1` device plus Update/PREPARE entities to appear;
- keep HA-USB transaction and PREPARE state absent.

Before the exact 20-ACL poststate is proven, a failed/uncertain mutation rolls back only those
same three exact ACLs and requires semantic restoration of the proven prestate. After the exact
20-ACL poststate is proven, a later Discovery/UI acceptance failure does not roll back the
correct ACL repair; it is classified separately as reactivation incomplete.

Forbidden:
- credential rotation;
- Broker restart;
- Manager restart;
- Home Assistant restart;
- PREPARE;
- USB insertion;
- CONFIRM_USB_ERASE;
- U2+;
- board access;
- merge.
