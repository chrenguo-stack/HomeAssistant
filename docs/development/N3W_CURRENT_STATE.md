# N3-W Current State

Updated: 2026-09-09  
Status: `CURRENT_STATE_AUTHORITY`

This is the concise public-safe authority for the current N3-W state. Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=QUERY_GITHUB_FRESH
REPOSITORY_MAIN_TREE=QUERY_GITHUB_FRESH
ALIGNMENT_BASE_MAIN=55e9bd5e4bcbcf359bd69ecddda32813cdff8ffb
ALIGNMENT_BASE_TREE=cac1fe4c4ce22c54420eb990401da1141a3f6626
PRODUCT_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
LAST_PRODUCT_SOURCE_CHANGE=PR_376
```

Repository main must always be queried fresh. Documentation-only descendants do not redefine the frozen product-source authority.

Active architecture authority remains:

`docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

Current product direction:

- provisioned runtime startup does not require an existing Wi-Fi association;
- Direct remains preferred;
- when Direct is unavailable, node-local bounded autonomous Relay discovery is allowed;
- full custom radio-ownership architecture remains deferred unless evidence requires it.

## KF-089 product status

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_AUTONOMOUS_DISCOVERY_ENTRY=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=NOT_PROVEN
KF089_AUTHENTICATED_RELAY_ACQUISITION=NOT_PROVEN
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=DISCOVERY_ADVERTISEMENT_ACCEPTANCE
```

The current T1 runtime-convergence detour does not change this product-level acceptance boundary.

## Observability authority

```text
DIAGNOSTIC_SCHEMA_VERSION=4
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
DIAGNOSTIC_KEY=snapshot
PRODUCT_TARGET_DIAGNOSTICS_ENABLED=false
PHASE4_GENERIC_DIAGNOSTICS_ENABLED=true
```

## Physical boundary

```text
BOARD_A_STATE=BATTERY_POWERED_AT_FIXED_RELAY_ANCHOR_POSITION
BOARD_A_CONNECTED_TO_MAC=false
BOARD_B_STATE=UNPOWERED_AT_QUALIFIED_RF_POSITION
BOARD_B_SELECTED_SLOT=app1
BOARD_B_APP1_SCHEMA_V4_DEPLOYED=true
BOARD_B_APP1_FIRMWARE_SHA256=d99edb9d0352dec6f3aa473147f91da17d55b5758397ed7d52e12cadcc475b74
BOARD_B_APP1_FIRMWARE_SIZE=1114608
BOARD_B_APP0_ROLLBACK_PRESERVED=true
BOARD_B_POST_DEPLOYMENT_APPLICATION_SESSION_CREATED=false
```

Fresh RF execution has not resumed. The original fresh-RF attempt stopped before the canonical Board A Direct prewindow completed; Board B was not powered and the 120 s RF observation did not start. Board B remains unpowered at the qualified RF position until a future explicit physical gate.

## T1 runtime-convergence boundary

A controlled T1 cleanup/rematerialization detour is active.

Legacy runtime cleanup has completed:

```text
AUTHORITATIVE_MANAGER_COUNT=1
LEGACY_MANAGER_COUNT=0
AUTHORITATIVE_BROKER_COUNT=1
LEGACY_BROKER_COUNT=0
LEGACY_NETWORK_REMOVE_COUNT=2
N3W_ACTIVE_COMPOSE_LINEAGE_COUNT=1
```

A private quiesced preservation/rollback package was completed before destructive rematerialization.

Current clean Broker is internally healthy:

```text
CLEAN_BROKER_RUNNING=true
BROKER_RESTART_COUNT=0
BROKER_REQUIRED_LISTENER_PRESENT=true
BROKER_TLS_LISTENER_PRESENT=true
BROKER_DYNSEC_RUNTIME=PASS
BROKER_CONFIG_AUTHORITY=PASS
BROKER_DYNSEC_AUTHORITY=PASS
BROKER_TLS_AUTHORITY=PASS
BROKER_DATA_CONTINUITY=PASS
BROKER_RESTART_POLICY=unless-stopped
```

Current Manager is deliberately stopped after failed Manager recovery against the clean Broker host path:

```text
CURRENT_MANAGER_CLASS=ROLLED_BACK_MANAGER
CURRENT_MANAGER_RUNNING=false
CURRENT_MANAGER_CONFIG_REPAIR_REQUIRED=false
CURRENT_MANAGER_CREDENTIAL_REPAIR_REQUIRED=false
```

The Manager's observed failure path was:

```text
TCP_CONNECT -> ENETUNREACH
```

The active root blocker is now below Compose declaration and container HostConfig:

```text
RAW_RECIPE_PUBLICATION=PRESENT
EFFECTIVE_COMPOSE_PUBLICATION=PRESENT
CONTAINER_HOSTCONFIG_PUBLICATION=PRESENT
CONTAINER_RUNTIME_PUBLICATION=ABSENT
OLD_SUCCESSFUL_HOST_PUBLICATION=PRESENT

CURRENT_BLOCKER=T1_DOCKER_HOST_PORT_BINDING_RUNTIME_MATERIALIZATION_FAILURE
ROOT_DOMAIN=DOCKER_RUNTIME
ROOT_CLASS=HOST_PORT_BINDING_RUNTIME_MATERIALIZATION_FAILURE
ROOT_SUBCLASS=HOSTCONFIG_BINDING_PRESENT_NETWORKSETTINGS_MAPPING_ABSENT
```

Historical correlation must also remain visible:

```text
MOST_RELEVANT_EXISTING_KNOWN_FAILURE=KF-035
KF035_RECURRENCE_PROVEN=false
```

`KF-035` previously proved that host-network Manager Broker-TLS continuity depends on the exact address returned inside the Manager image/host-network namespace, and that publishing 8883 to the wrong loopback bind address produces `Network is unreachable`. The present incident is not yet proven to be the same root cause because the current container has correct `HostConfig.PortBindings` but no runtime mapping. The next read-only forensic must therefore test the HostIP/bind-address/interface validity first before escalating to a generic Docker NAT/runtime defect.

The adjacent `KF-034` explains why Manager host networking is intentional: the pairing limited-broadcast path was not carried correctly by Docker bridge/port-publication deployment.

Home Assistant remains a non-target service and has not been restarted/recreated during this cleanup.

Detailed public-safe archive:

`docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`

## Required guards

- USB port is a locator only and is not board identity authority.
- Board-targeted mutation requires explicit operator target/connection confirmation before board access.
- Fresh ROM silicon identity is required before any board write.
- Application serial open is not a passive runtime oracle.
- Lab diagnostic NVS writes are distinct from product NVS mutation.
- Discovery RX means decoded handler RX, not accepted advertisement.
- Historical discovery counts are boot-session cumulative, not exact final RF-window counts.
- Manager/Broker authority must not be selected by container name alone.
- Strict read-only gates must not create temporary files.
- Stateful destructive rematerialization must use a quiesced snapshot unless an application-consistent online snapshot mechanism is proven.
- `Config.ExposedPorts`, `HostConfig.PortBindings`, and actual runtime `NetworkSettings.Ports` / `docker port` mappings are separate evidence layers.
- A Compose `ports:` declaration is not sufficient proof that Docker runtime host publication exists.
- For the host-network Manager/Broker path, the exact Manager-image + host-network namespace resolution is authoritative for Broker bind-address compatibility; host-side resolution alone is insufficient (KF-035).

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_KF089_T1_DOCKER_HOST_PORT_BINDING_RUNTIME_READONLY_FORENSIC_20260909_01
```

This gate is read-only. Keep clean Broker running and current Manager stopped. Priority 1 is the KF-035 comparator: inspect the exact HostIP class in current `HostConfig.PortBindings` and prove that every required explicit bind address/interface exists and is UP. Only after that should it inspect Docker network/bridge/veth state, host listener/proxy state, iptables/nftables/NAT publication rules, Docker daemon network errors, old-successful-network semantics, removed-network correlation, and daemon networking configuration drift. It must not restart/recreate Manager or Broker, mutate routes/firewall/DNS, restart Docker, reboot T1, access boards, or resume RF.

## Route after T1 convergence

T1 convergence is not complete until Broker host publication, Manager→Broker TLS MQTT, HA continuity, residue cleanup, and a controlled T1 reboot/boot-recovery acceptance all pass.

Only then return to:

```text
BOARD_A_DIRECT_POST_T1_RECOVERY_READONLY_VERIFICATION
-> canonical Board A Direct RF prewindow
-> fresh schema-v4 RF execution
```

Acceptance boundaries remain:

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_STARTUP_GATE_REPAIR=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=NOT_PROVEN
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

Public GitHub stores source, tests, hashes, sanitized closures, architecture decisions, and sanitized runtime alignment. Raw NVS, credentials, private board identities, remote-host details, private paths/addresses, and other sensitive physical evidence remain private/local.
