# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Current T1 runtime-convergence archive: `docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`  
Previous detailed KF-089 progress archive: `docs/development/N3W_KF089_RELAY_ACQUISITION_TELEMETRY_OBSERVABILITY_AND_SCHEMA_V5_PROGRESS_ALIGNMENT_20260910.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Current repository authority

Fresh main observed during closeout:

```text
REPOSITORY_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
REPOSITORY_MAIN_TREE=91d2e4767887dad86525cf521e476d4a1234551a
```

Accepted but still-unmerged KF-089 review stack:

```text
PR400_HEAD=b973934b760db975ada601819191c62fe0513a9e
PR403_HEAD=1f4cb36a2d1180753556eb08d2b46fa180d423e0
PR404_HEAD=83006bc87904843d6ca784355556032852c3813d
```

Do not describe current `main` as already containing the full KF-089 Manager Relay DynSec source repair until the stack is integrated and fresh main is rebound.

## Current deployed authorities

```text
BOARD_FIRMWARE_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
BOARD_FIRMWARE_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
DIAGNOSTIC_SCHEMA_VERSION=5
DEPLOYED_MANAGER_SOURCE=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
```

The running T1 Dynamic Security role has been repaired in place and the Manager subscription was reactivated with one controlled restart. Those live-state facts are distinct from repository-main integration.

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

## Boundaries not proven by this closeout

```text
HOME_ASSISTANT_ENTITY_UPDATE=NOT_IN_SCOPE
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

## Current ONE gate

```text
NEXT_ONE_GATE=KF089_PR_STACK_INTEGRATION_REVIEW
PHYSICAL_AUTHORIZATION_REQUIRED=false
T1_AUTHORIZATION_REQUIRED=false
```

Integration order:

```text
PR400
-> PR403
-> PR404
-> KF089_CLOSEOUT_DOCS_PR
```

Each stacked PR must be freshly diff-reviewed against the then-current main before integration. No merge authority is implied by this index.

Historical archives remain historical and are not rewritten. In particular, stale text saying `KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN` remains valid only for the dated archive in which it was recorded, not for the current state after the 2026-09-14 ID26 PASS.
