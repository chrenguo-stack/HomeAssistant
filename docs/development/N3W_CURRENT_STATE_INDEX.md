# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current broader multi-node Relay / Home Assistant MQTT-path alignment: `docs/development/N3W_MULTI_NODE_RELAY_HOME_ASSISTANT_MQTT_PATH_PROGRESS_ALIGNMENT_20260915.md`  
Current KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Current T1 runtime-convergence archive: `docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`  
Previous detailed KF-089 progress archive: `docs/development/N3W_KF089_RELAY_ACQUISITION_TELEMETRY_OBSERVABILITY_AND_SCHEMA_V5_PROGRESS_ALIGNMENT_20260910.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Current repository authority

KF-089 code/package integration baseline after the clean PR #406 → #407 → #408 sequence:

```text
KF089_CODE_PACKAGE_INTEGRATION_BASE_MAIN=1bbd4f3f1cfbccaa383d326a28bc972ed4ee202b
KF089_CODE_PACKAGE_INTEGRATION_BASE_TREE=5b9bdc77585f3c1990b4123fccfb84f4d16d281d
```

Integrated clean stack:

```text
PR406=MERGED
PR406_MERGE_COMMIT=d7d9cd9d49f795c71a96c5f28f90cbdd9930c5e2
PR407=MERGED
PR407_MERGE_COMMIT=9237e1ad1b4cf1850af40599ce173f07b00ad5cd
PR408=MERGED
PR408_MERGE_COMMIT=1bbd4f3f1cfbccaa383d326a28bc972ed4ee202b
ID23_ID24_ID25_ID26_REPOSITORY_INTEGRATION=PASS
MANAGER_RELAY_SOURCE_CONTRACT_INTEGRATION=PASS
```

Historical PR #400 / #403 / #404 remain provenance for the original accepted live package heads. The clean integration path through PR #406→#407→#408 is the repository authority for the KF-089 code/package stack.

The fixed SHA above is the KF-089 code/package integration baseline, not a permanent claim about the current repository tip after documentation-only descendants. Repository `main` must always be queried fresh.

## Current deployed authorities

```text
BOARD_FIRMWARE_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
BOARD_FIRMWARE_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
DIAGNOSTIC_SCHEMA_VERSION=5
DEPLOYED_MANAGER_SOURCE=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
LIVE_MANAGER_DYNSEC_REPAIR=PASS
```

The running T1 Dynamic Security role was repaired in place and the Manager subscription was reactivated with one controlled restart before the final ID26 revalidation. These live-state facts remain distinct from the repository revision of the deployed Manager image. The corrected source contract is now durable in repository `main`.

## KF-089 accepted product boundary

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
BOARD_SIDE_RELAY_CHAIN=PROVEN
T1_BROKER_MEDIATED_RELAY_INGRESS=PROVEN
MANAGER_RELAY_ACCEPTANCE=PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
```

Final ID26 attribution window:

```text
PREWINDOW_ACCEPTED_RELAY_COUNT=0
WINDOW_ACCEPTED_RELAY_COUNT=38
WINDOW_REJECTED_RELAY_COUNT=0
WINDOW_DUPLICATE_RELAY_COUNT=0
WINDOW_UNIQUE_ACCEPTED_RELAY_ROUTE_COUNT=1
```

## Current live safety boundary

```text
ID24_REPAIR_RESULT=PASS
ID25_REACTIVATION_RESULT=PASS
ID26_REVALIDATION_RESULT=PASS

ID26_MANAGER_RUNTIME_STABLE=true
ID26_BROKER_RUNTIME_STABLE=true
ID26_DYNSEC_STATE_UNCHANGED=true

BOARD_A_USB_ACCESS_DURING_ID26=false
BOARD_B_USB_ACCESS_DURING_ID26=false
SERIAL_OPEN_DURING_ID26=false
FLASH_WRITE_DURING_ID26=false
HOST_NVS_WRITE_DURING_ID26=false
MQTT_TEST_PUBLISH_DURING_ID26=false
```

## Broader multi-node Relay continuation — 2026-09-15

The broader acceptance route has advanced beyond the KF-089 cold/fresh single-child Relay boundary.

Fresh controlled physical validation proved simultaneous Board B + Board C Relay via Board A:

```text
WINDOW_ACCEPTED_RELAY_COUNT=82
WINDOW_REJECTED_RELAY_COUNT=0
WINDOW_DUPLICATE_RELAY_COUNT=0
WINDOW_UNIQUE_RELAY_ROUTE_COUNT=2
WINDOW_UNIQUE_RELAY_NODE_COUNT=2
WINDOW_UNIQUE_RELAY_GATEWAY_COUNT=1
BOARD_B_ACCEPTED_RELAY_COUNT=40
BOARD_C_ACCEPTED_RELAY_COUNT=42
BOARD_A_DIRECT_DURING_RELAY_COUNT=98
BOARD_B_DIRECT_DURING_RELAY_COUNT=0
BOARD_C_DIRECT_DURING_RELAY_COUNT=0
RELAY_GATEWAY_EQUALS_BOARD_A=true
BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PROVEN
```

Therefore:

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
```

Home Assistant entity-update validation is currently blocked by an infrastructure defect, not by a Relay failure. The current N3-W Home Assistant authority is `fc4-homeassistant` in project `n3wfc4`; the independent legacy `homeassistant` runtime has no A/B/C N3-W entities.

Fresh MQTT/TLS localization proved:

```text
FC4_HA_MQTT_IDENTITY_CONTRACT_OK=true
FC4_HA_PORT_MATCHES_BROKER_LISTENER=true
BROKER_CERT_VALID_NOW=true
BROKER_CERT_VALID_FOR_NEXT_30D=true
BROKER_CHAIN_VALID_FROM_HA_WITHOUT_HOSTNAME=true
TLS_DNS_SAN_SHA256_16=8203b89b390ddffc
CURRENT_HA_TARGET_SHA256_16=8203b89b390ddffc
MANAGER_RUNTIME_TARGET_SHA256_16=8203b89b390ddffc
```

The certificate-authoritative target name does not resolve inside the FC4 Home Assistant Docker namespace, while alternate internal Broker names are TCP-reachable but fail full TLS verification with hostname mismatch.

Current root cause and repair direction:

```text
ROOT_DOMAIN=INFRASTRUCTURE
ROOT_CLASS=DOCKER_NETWORK_DNS_TO_TLS_IDENTITY_BINDING
ROOT_CAUSE_CLASS=BROKER_SHARED_NETWORK_MISSING_ALIAS_FOR_EXISTING_TLS_DNS_SAN
REPAIR_DESIGN=ADD_EXISTING_TLS_DNS_SAN_AS_BROKER_SHARED_NETWORK_ALIAS
HOME_ASSISTANT_MQTT_ENTRY_CHANGE_REQUIRED=false
BROKER_CERT_ROTATION_REQUIRED=false
HOME_ASSISTANT_CREDENTIAL_CHANGE_REQUIRED=false
DYNSEC_MUTATION_REQUIRED=false
MANAGER_CONFIGURATION_CHANGE_REQUIRED=false
```

Detailed authority:

`docs/development/N3W_MULTI_NODE_RELAY_HOME_ASSISTANT_MQTT_PATH_PROGRESS_ALIGNMENT_20260915.md`

## Current broader acceptance boundary

```text
MAINLINE_ACCEPTANCE_ITEM_1_BOARD_BC_SIMULTANEOUS_RELAY_VIA_A=PASS
MAINLINE_ACCEPTANCE_ITEM_2_HOME_ASSISTANT_RELAY_ENTITY_UPDATE=BLOCKED_BY_HA_BROKER_TLS_DNS_BINDING
MAINLINE_ACCEPTANCE_ITEM_3_LIVE_DIRECT_TO_RELAY_FAILOVER=PENDING
MAINLINE_ACCEPTANCE_ITEM_4_LIVE_RELAY_TO_DIRECT_RECOVERY=PENDING
```

The accepted simultaneous Relay result remains valid and must not be reopened merely because the downstream Home Assistant MQTT consumer is blocked by Broker Docker-DNS/TLS-identity binding.

## KF-089 historical closeout boundary

```text
HOME_ASSISTANT_ENTITY_UPDATE=NOT_IN_SCOPE_OF_KF089_CLOSEOUT
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_ADJUDICATED_BY_KF089_CLOSEOUT
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_ADJUDICATED_BY_KF089_CLOSEOUT
```

These statements describe the scope of the KF-089 closeout only; the broader route above is the current authority for later acceptance work.

## Current ONE gate

```text
CURRENT_ONE_GATE=FC4_HOME_ASSISTANT_BROKER_TLS_SAN_NETWORK_ALIAS_REPAIR_PRECLAIM
MUTATION_AUTHORIZATION_GRANTED=false
```

The current gate is read-only. It must exact-bind the durable Compose/network authority, prove the existing TLS SAN is absent from the Broker shared-network DNS authority, prove alias-only intended delta, preserve Broker data/TLS/DynSec, preserve Manager/Home Assistant as non-target services, retain the accepted 8883 publication contract, and establish exact rollback before any live mutation authorization is considered.

Historical archives remain historical and are not rewritten solely to erase dated intermediate states. In particular, stale text saying `KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN` remains valid only for the dated archive in which it was recorded, not for the current state after the 2026-09-14 ID26 PASS.
