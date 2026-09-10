# N3-W Current State

Updated: 2026-09-10
Status: `CURRENT_STATE_AUTHORITY`

This is the concise public-safe authority for the current N3-W state. Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=5d58727f5040281ee2beb9597f66a6a2da9bac57
REPOSITORY_MAIN_TREE=b27b2968ea4e0b3bcb5f8312c3d31d391bd8d3ed
PR381_BASE_MAIN=f7083fbb7a7ba228dcd5f253b9cba752f6c7104c
PR381_HEAD=b521ad1a5e223d2cf5a0de43fa6ff956339e9a0e
PR381_MERGE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
PR381_MERGE_TREE=b27b2968ea4e0b3bcb5f8312c3d31d391bd8d3ed
PRODUCT_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
LAST_PRODUCT_SOURCE_CHANGE=PR_376
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
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

The current T1 runtime-convergence detour does not change this product-level acceptance boundary.

## Observability authority

```text
DIAGNOSTIC_SCHEMA_VERSION=5
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
DIAGNOSTIC_KEY=snapshot
PRODUCT_TARGET_DIAGNOSTICS_ENABLED=false
PHASE4_GENERIC_DIAGNOSTICS_ENABLED=true
```

## Physical boundary

```text
BOARD_A_STATE=LAST_PROVEN_DIRECT_AND_RELAY_CAPABLE_RUNTIME_STATE
BOARD_A_ACCESSED_DURING_LATER_HOST_ONLY_GATES=false
BOARD_B_STATE=ROM_DOWNLOAD_MODE_USB_CONNECTED_BATTERY_DISCONNECTED
BOARD_B_APPLICATION_BOOT_AFTER_FROZEN_CAPTURE=false
BOARD_B_APP1_ROLLBACK_PRESERVED=true
```

The current physical boundary is frozen after the Schema-v4 durable
handshake/RelayActive capture and later host-only recovery evidence. Board B
is in ROM download mode with its battery disconnected; no application boot has
occurred after the frozen capture/recovery readback. Board A was not accessed
during later host-only/source gates, so its last proven Direct/Relay-capable
runtime state remains the applicable public-safe statement. No fresh Schema-v5
physical deployment has been executed.

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
NEXT_ONE_GATE=N3W_KF089_SCHEMA_V5_TWO_BOARD_DEPLOYMENT_AND_RELAY_TELEMETRY_LOCALIZATION
```

Physical authorization is required. The next route is Schema-v5 two-board
deployment, then two-board Direct baseline, selective-RF localization capture,
durable Schema-v5 readback, and downstream Relay-telemetry adjudication.

## Route after T1 convergence

T1 convergence is complete. Return to:

```text
SCHEMA_V5_TWO_BOARD_DEPLOYMENT
-> TWO_BOARD_DIRECT_BASELINE
-> SELECTIVE_RF_LOCALIZATION_CAPTURE
-> B/A DURABLE_SCHEMA_V5_READBACK
-> DOWNSTREAM_RELAY_TELEMETRY_ADJUDICATION
```

Acceptance boundaries remain:

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_STARTUP_GATE_REPAIR=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

Public GitHub stores source, tests, hashes, sanitized closures, architecture decisions, and sanitized runtime alignment. Raw NVS, credentials, private board identities, remote-host details, private paths/addresses, and other sensitive physical evidence remain private/local.
