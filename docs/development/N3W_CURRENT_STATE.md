# N3-W Current State

Updated: 2026-09-09  
Status: `CURRENT_STATE_AUTHORITY`

This is the concise public-safe authority for the current N3-W state. Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=de061392f2293febf2fc8adef895975ebb085cf6
REPOSITORY_MAIN_TREE=737c9b620757225b4456056e9a826250f9c16e71
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

T1 runtime convergence is closed PASS. The final state has one Manager, one
Broker, one active N3-W Compose lineage, and the Broker's required private and
external reachability networks.

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
BROKER_TLS_DYNSEC_RUNTIME=PASS
MANAGER_TO_BROKER_TLS_MQTT=PASS
HA_TO_BROKER_RUNTIME_CONTINUITY=PASS
T1_RUNTIME_RESIDUE_POSTCHECK=PASS
T1_CONTROLLED_REBOOT_BOOT_RECOVERY=PASS
```

The final root cause was deployment-network loss during successor recipe
materialization: the external reachability network attachment was omitted,
leaving the clean Broker internal-only and preventing usable host publication.
The exact external attachment and host mappings were restored. Manager
recovered automatically after the controlled reboot; Home Assistant also
retained a post-reboot live authenticated MQTT relationship with the current
Broker. No product source or firmware authority changed.

The controlled reboot acceptance used one reboot only and required no manual
container start, stop, restart, recreate, network repair, or Docker daemon
restart.

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
NEXT_ONE_GATE=N3W_KF089_BOARD_A_DIRECT_POST_T1_RECOVERY_READONLY_VERIFICATION_20260910_01
```

This gate is read-only and must not access Board A, move either board, or
resume RF. It verifies the post-T1 Board A Direct runtime baseline before any
future physical gate; it does not execute that physical gate automatically.

## Route after T1 convergence

T1 convergence is complete. Return to:

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
