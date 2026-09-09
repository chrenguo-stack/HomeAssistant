# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current T1 runtime-convergence archive: `docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`  
Previous formal fresh-RF handoff: `docs/development/N3W_KF089_SCHEMA_V4_FRESH_RF_EXECUTION_PREEXECUTION_NEW_CHAT_HANDOFF_V1.0_20260908.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Current source authority

```text
REPOSITORY_MAIN=QUERY_GITHUB_FRESH
REPOSITORY_MAIN_TREE=QUERY_GITHUB_FRESH
ALIGNMENT_BASE_MAIN=406f6022cc8a4267397a338156592aa507a3ff3a
ALIGNMENT_BASE_TREE=6bf72d98097fdd32354451a5b177fe1b28b2a15a
PRODUCT_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
DIAGNOSTIC_SCHEMA_VERSION=4
```

Documentation-only descendants do not redefine product-source authority.

## Frozen physical boundary

```text
BOARD_A_STATE=BATTERY_POWERED_AT_FIXED_RELAY_ANCHOR_POSITION
BOARD_B_STATE=UNPOWERED_AT_QUALIFIED_RF_POSITION
BOARD_B_SELECTED_SLOT=app1
BOARD_B_APP1_SCHEMA_V4_DEPLOYED=true
BOARD_B_POST_DEPLOYMENT_APPLICATION_SESSION_CREATED=false
```

Board B remains unpowered. Fresh RF execution has not resumed.

## Current KF-089 product boundary

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_AUTONOMOUS_DISCOVERY_ENTRY=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=NOT_PROVEN
FIRST_UNPROVEN_STAGE=DISCOVERY_ADVERTISEMENT_ACCEPTANCE
```

## Current T1 runtime-convergence boundary

```text
AUTHORITATIVE_MANAGER_COUNT=1
LEGACY_MANAGER_COUNT=0
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_BROKER_COUNT=0
N3W_ACTIVE_COMPOSE_LINEAGE_COUNT=1

CLEAN_BROKER_RUNNING=true
CURRENT_MANAGER_RUNNING=false

CURRENT_BLOCKER=T1_DOCKER_HOST_PORT_BINDING_RUNTIME_MATERIALIZATION_FAILURE
ROOT_DOMAIN=DOCKER_RUNTIME
ROOT_CLASS=HOST_PORT_BINDING_RUNTIME_MATERIALIZATION_FAILURE
ROOT_SUBCLASS=HOSTCONFIG_BINDING_PRESENT_NETWORKSETTINGS_MAPPING_ABSENT
```

The clean Broker is internally healthy (listener/TLS/DynSec/config/data continuity PASS), but Docker runtime host-port publication is absent despite correct Compose declaration and `HostConfig.PortBindings`. Current Manager remains stopped to avoid restart-loop noise.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_KF089_T1_DOCKER_HOST_PORT_BINDING_RUNTIME_READONLY_FORENSIC_20260909_01
```

The next gate is strictly read-only and investigates Docker host-port materialization: host bind-address validity, network driver/bridge/veth, host listener/proxy, iptables/nftables/NAT rules, Docker daemon network/programming errors, old-successful-network semantics, removed-network correlation, and daemon network-config drift.

## Route after T1 convergence

After the clean T1 runtime is proven, including controlled reboot/boot-recovery acceptance, return to:

```text
BOARD_A_DIRECT_POST_T1_RECOVERY_READONLY_VERIFICATION
-> canonical Board A Direct RF prewindow
-> fresh schema-v4 RF execution
```

Do not retain stale current-state text claiming that Board B is still at the test Mac or that the fresh-RF gate is immediately executable. Historical archives remain historical and are not rewritten.
