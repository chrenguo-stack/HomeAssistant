# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Current T1 runtime-convergence archive: `docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`  
Previous detailed KF-089 progress archive: `docs/development/N3W_KF089_RELAY_ACQUISITION_TELEMETRY_OBSERVABILITY_AND_SCHEMA_V5_PROGRESS_ALIGNMENT_20260910.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Current repository authority

Fresh `main` observed after the clean KF-089 code/package integration sequence:

```text
REPOSITORY_MAIN=1bbd4f3f1cfbccaa383d326a28bc972ed4ee202b
REPOSITORY_MAIN_TREE=5b9bdc77585f3c1990b4123fccfb84f4d16d281d
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

Historical PR #400 / #403 / #404 remain provenance for the original accepted live package heads. Current `main` contains the clean ID23→ID24→ID25→ID26 integration route through PR #406→#407→#408.

PR #409 remains an unmerged documentation/central-guard candidate. No PR #409 merge authority is implied by this index.

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

## Boundaries not proven by this closeout

```text
HOME_ASSISTANT_ENTITY_UPDATE=NOT_IN_SCOPE
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

## Current ONE gate

```text
NEXT_ONE_GATE=KF089_CLOSEOUT_DOCS_AND_CENTRAL_GUARD_REVIEW
PR406_PR407_PR408_INTEGRATION=PASS
PHYSICAL_AUTHORIZATION_REQUIRED=false
T1_AUTHORIZATION_REQUIRED=false
PR409_MERGE_AUTHORIZED=false
```

Before any PR #409 merge decision, the candidate must contain the refreshed current-state documents and a fresh exact-base KF-089 edit to `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`, followed by focused diff review and public-repository safety CI.

Historical archives remain historical and are not rewritten solely to erase dated intermediate states. In particular, stale text saying `KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN` remains valid only for the dated archive in which it was recorded, not for the current state after the 2026-09-14 ID26 PASS.
