# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current T1 runtime-convergence archive: `docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`  
Previous formal fresh-RF handoff: `docs/development/N3W_KF089_SCHEMA_V4_FRESH_RF_EXECUTION_PREEXECUTION_NEW_CHAT_HANDOFF_V1.0_20260908.md`  
Current detailed KF-089 progress archive: `docs/development/N3W_KF089_RELAY_ACQUISITION_TELEMETRY_OBSERVABILITY_AND_SCHEMA_V5_PROGRESS_ALIGNMENT_20260910.md`
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Current source authority

```text
REPOSITORY_MAIN=8a79b44ae42cb71fef75389524ed9094badb85a6
REPOSITORY_MAIN_TREE=0c878193b894d58b17ae399aade9b610c380e6ce
PR381_BASE_MAIN=f7083fbb7a7ba228dcd5f253b9cba752f6c7104c
PR381_HEAD=b521ad1a5e223d2cf5a0de43fa6ff956339e9a0e
PR381_MERGE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
PRODUCT_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
```

Repository main may advance through documentation-only alignment commits
without changing the frozen firmware / diagnostic source authority.
Documentation-only descendants do not redefine product-source authority.

## Frozen physical boundary

```text
BOARD_A_STATE=LAST_PROVEN_DIRECT_AND_RELAY_CAPABLE_RUNTIME_STATE
BOARD_A_ACCESSED_DURING_LATER_HOST_ONLY_GATES=false
BOARD_B_STATE=ROM_DOWNLOAD_MODE_USB_CONNECTED_BATTERY_DISCONNECTED
BOARD_B_APPLICATION_BOOT_AFTER_FROZEN_CAPTURE=false
BOARD_B_APP1_ROLLBACK_PRESERVED=true
```

Board B remains in ROM download mode with its battery disconnected. No
Schema-v5 application boot or physical deployment has been executed.

## Current KF-089 product boundary

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

## Current T1 runtime-convergence boundary

```text
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
ACTIVE_DETOUR=NONE
AUTHORITATIVE_MANAGER_COUNT=1
LEGACY_MANAGER_COUNT=0
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_BROKER_COUNT=0
N3W_ACTIVE_COMPOSE_LINEAGE_COUNT=1
BROKER_NETWORK_COUNT_FINAL=2
BROKER_RUNTIME_MAPPING_COUNT=3
BROKER_HOST_PUBLICATION_RUNTIME=PASS
MANAGER_TO_BROKER_TLS_MQTT=PASS
HA_TO_BROKER_RUNTIME_CONTINUITY=PASS
T1_CONTROLLED_REBOOT_BOOT_RECOVERY=PASS
```

The final root cause was loss of the Broker external reachability network
attachment during successor recipe materialization. The exact attachment and
runtime host mappings were restored; Manager and Home Assistant recovered
their post-reboot Broker relationships. The detailed public-safe archive is
the current T1 runtime-convergence authority.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_KF089_SCHEMA_V5_TWO_BOARD_DEPLOYMENT_AND_RELAY_TELEMETRY_LOCALIZATION
```

Physical authorization is required for the next gate. It covers Schema-v5
two-board deployment and Relay-telemetry localization.

## Route after T1 convergence

With the clean T1 runtime and controlled reboot/boot-recovery acceptance
proven, return to:

```text
SCHEMA_V5_TWO_BOARD_DEPLOYMENT
-> TWO_BOARD_DIRECT_BASELINE
-> SELECTIVE_RF_LOCALIZATION_CAPTURE
-> B/A DURABLE_SCHEMA_V5_READBACK
-> DOWNSTREAM_RELAY_TELEMETRY_ADJUDICATION
```

Do not retain stale current-state text claiming that Board B is still at the test Mac or that the fresh-RF gate is immediately executable. Historical archives remain historical and are not rewritten.
