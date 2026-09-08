# N3-W Current State

Updated: 2026-09-08
Status: `CURRENT_STATE_AUTHORITY`

This is the concise public-safe authority for the current N3-W state. Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=QUERY_GITHUB_FRESH
REPOSITORY_MAIN_TREE=QUERY_GITHUB_FRESH
ALIGNMENT_BASE_MAIN=fe116efabbd986263b043aa1a36ad74bf283bafa
ALIGNMENT_BASE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
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

## KF-089 status

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

## Observability authority

```text
DIAGNOSTIC_SCHEMA_VERSION=4
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
DIAGNOSTIC_KEY=snapshot
PRODUCT_TARGET_DIAGNOSTICS_ENABLED=false
PHASE4_GENERIC_DIAGNOSTICS_ENABLED=true
```

## Board boundaries

```text
BOARD_A_STATE=BATTERY_POWERED_AT_FIXED_RELAY_ANCHOR_POSITION
BOARD_A_CONNECTED_TO_MAC=false
BOARD_B_STATE=ROM_DOWNLOAD_MODE_AT_TEST_MAC
BOARD_B_SELECTED_SLOT=app1
BOARD_B_APP1_SCHEMA_V4_DEPLOYED=true
BOARD_B_APP1_FIRMWARE_SHA256=d99edb9d0352dec6f3aa473147f91da17d55b5758397ed7d52e12cadcc475b74
BOARD_B_APP1_FIRMWARE_SIZE=1114608
BOARD_B_APP0_ROLLBACK_PRESERVED=true
BOARD_B_POST_DEPLOYMENT_APPLICATION_SESSION_CREATED=false
```

## T1 boundary

```text
REMOTE_T1_CANONICAL_OBSERVER=MANAGER_CANONICAL_ACCEPTANCE
T1_PRECLAIM_OBSERVER_READY=PASS
T1_LIVE_STATE_REQUIRES_FRESH_READONLY_REBIND=true
```

## Required guards

- USB port is a locator only and is not board identity authority.
- Board-targeted mutation requires explicit operator target/connection confirmation before board access.
- Fresh ROM silicon identity is required before any board write.
- Application serial open is not a passive runtime oracle.
- Lab diagnostic NVS writes are distinct from product NVS mutation.
- Discovery RX means decoded handler RX, not accepted advertisement.
- Historical discovery counts are boot-session cumulative, not exact final RF-window counts.

## Current ONE gate after alignment merge

```text
NEXT_ONE_GATE=N3W_KF089_SCHEMA_V4_FRESH_RF_SESSION_EXECUTION_20260908_01
```

Acceptance boundaries:

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_STARTUP_GATE_REPAIR=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=NOT_PROVEN
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

Public GitHub stores source, tests, hashes, sanitized closures, and architecture decisions. Raw NVS, credentials, private board identities, remote-host details, and other sensitive physical evidence remain private/local.
