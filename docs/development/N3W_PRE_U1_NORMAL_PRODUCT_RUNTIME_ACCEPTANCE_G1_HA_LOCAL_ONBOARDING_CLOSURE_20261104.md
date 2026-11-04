# N3-W Pre-U1 normal product runtime acceptance — G1 Home Assistant local onboarding closure

Date: 2026-11-04

## 0. Result

```text
GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G1_HA_LOCAL_ONBOARDING_20261104_01
RESULT=CLOSED_PASS
MUTATION_TYPE=NORMAL_HOMEASSISTANT_USER_STATE
HOMEASSISTANT_CLOUD=false
BOARD_ACCESS=false
PAIRING_MUTATION=false
UPDATER_MUTATION=false
SERVICE_RESTART=false
MERGE=false
STOP=true
```

G1 is closed PASS. This closure does not authorize G2 physical board work.

## 1. User-facing Home Assistant acceptance

The operator completed the normal Home Assistant local onboarding path through the official Web UI.

```text
HA_LOCAL_OWNER_CREATED=true
HA_LOGIN_SUCCESS=true
HA_OVERVIEW_USABLE=true
HA_SETTINGS_USABLE=true
MQTT_INTEGRATION_VISIBLE=true
MQTT_INTEGRATION_ERROR_VISIBLE=false
UNEXPECTED_ERROR_VISIBLE=false
HOMEASSISTANT_CLOUD_USED=false
DIRECT_STORAGE_EDIT=false
MANUAL_MQTT_RECONFIGURE=false
```

No password, token, email, or other private login material is recorded here.

## 2. Fresh post-onboarding host/runtime evidence

```text
SYSTEM_STATE=running
RELEVANT_FAILED_UNIT_COUNT=0
PRODUCT_CONTAINER_COUNT=3

MANAGER_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d

MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
BROKER_RESTART_COUNT=0
NO_CONTAINER_RESTART_SINCE_G0=true
```

The normal Home Assistant onboarding write did not force an unexpected Broker, Manager, or Home Assistant container restart.

## 3. Updater and product contract continuity

The reviewed updater transport hash remained:

```text
UPDATER_PYZ_SHA256=54f2e6299fa8905d33033ea86b5d449f16ad4dcd6ae8c7a3e9d647d6001e22fa
```

Fresh updater state:

```text
UPDATER_STATUS=PASS
UPDATER_TRANSACTION_STATUS=COMMITTED
UPDATER_TRANSACTION_PHASE=COMMITTED
UPDATER_RECOVERY_REQUIRED=false
ACTIVE_UPDATER_MUTATION=false
```

All three component inspect operations returned PASS.

```text
MANAGER_RUNTIME_CONTRACT_SHA256=ad1d38f6191c0c00afcfbee3ca489d5f95a86fefcb17976c273597c04609d6e1
HOMEASSISTANT_RUNTIME_CONTRACT_SHA256=bc69586866551709110435ea25bfdff9d41bc8e366f6ace8d4b7bba3db5f6868
BROKER_RUNTIME_CONTRACT_SHA256=b4e002c7eb494812629b1a99d7e53b712d5f2239460c99334556976b6fdad492

MANAGER_MQTT_AUTHENTICATED=true
HOMEASSISTANT_MQTT_AUTHENTICATED=true
```

No product image or runtime-contract drift was observed.

## 4. Pairing and listener continuity

```text
PAIRING_WINDOW_STATE=CLOSED
PAIRING_CLOSE_REASON=committed
ACTIVE_PAIRING_MUTATION=false

TCP_1883=LISTEN_LOOPBACK
TCP_8883=LISTEN_WILDCARD
TCP_8123=LISTEN
TCP_47110=1
UDP_47111=1
TCP_47112=0
```

Home Assistant onboarding did not open the product registration ingress.

## 5. Home Assistant onboarding state

Fresh unauthenticated onboarding status:

```text
HOMEASSISTANT_HTTP_STATUS=200
HOMEASSISTANT_ONBOARDING_HTTP_STATUS=200
HOMEASSISTANT_ONBOARDING_USER_DONE=true
HOMEASSISTANT_ONBOARDING_CORE_CONFIG_DONE=true
HOMEASSISTANT_ONBOARDING_ANALYTICS_DONE=true
HOMEASSISTANT_ONBOARDING_INTEGRATION_DONE=true
HOMEASSISTANT_ONBOARDING_COMPLETE=true
```

The expected G1 business-state mutation is therefore present and usable.

## 6. PASS classification

```text
LOCAL_OWNER_USABLE=true
NORMAL_UI_USABLE=true
MQTT_INTEGRATION_HEALTHY_BY_UI=true
PRODUCT_IMAGES_UNCHANGED=true
RUNTIME_CONTRACTS_UNCHANGED=true
NO_UNEXPECTED_PRODUCT_RESTART=true
NO_ACTIVE_UPDATER_MUTATION=true
NO_ACTIVE_PAIRING_MUTATION=true

G1_RESULT=CLOSED_PASS
```

This normal Home Assistant user/session state is intentionally retained. It is not rolled back to U0.

## 7. Next boundary

```text
PRE_U1_G0=CLOSED_PASS
PRE_U1_G1=CLOSED_PASS
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G2_NODE_A_REAL_SENSOR_RUNTIME_20261104_01
G2_BOARD_PHYSICAL_WORK=true
AUTO_EXECUTE_NEXT_GATE=false
NEW_G2_PHYSICAL_AUTHORIZATION_REQUIRED=true

BOARD_ACCESS=false
STOP=true
```

G2 will use the already registered Node A, preserve its identity and credentials, connect the intended production sensor set, and prove at least five consecutive canonical telemetry cycles after warm-up. G2 is not executed by this closure.

## 8. Known-failure disposition

```text
NEW_KF_REQUIRED=false
KNOWN_FAILURE_UPDATE_REQUIRED=false
```
