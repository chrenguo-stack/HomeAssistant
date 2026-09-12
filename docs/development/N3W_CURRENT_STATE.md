# N3-W Current State

Updated: 2026-09-12
Status: `CURRENT_STATE_AUTHORITY`

This is the concise public-safe authority for the current N3-W state. Fresh exact repository, runtime, and physical evidence takes precedence if later evidence proves drift.

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN_AT_SYNC_BASE=7478e0fbcf893761ab76cc9952e09e77cda22755
REPOSITORY_MAIN_TREE_AT_SYNC_BASE=91d2e4767887dad86525cf521e476d4a1234551a
PRODUCT_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
LAST_PRODUCT_SOURCE_CHANGE=PR_376
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
```

Repository main must always be queried fresh. Repository main may advance through documentation-only alignment commits without changing the frozen firmware / diagnostic source authority. Documentation-only descendants do not redefine the frozen product-source authority.

Active architecture authority remains:

`docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

Latest public-safe KF-089 progress archive:

`docs/development/N3W_KF089_ID17_ID20R1_SCHEMA5_BOARD_A_DEPLOYMENT_AND_BOOT_POSTCHECK_PROGRESS_ALIGNMENT_20260912.md`

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
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PROVEN
KF089_AUTHENTICATED_RELAY_ACQUISITION=PROVEN

B_RELAY_ACTIVE=PROVEN
B_RELAY_TELEMETRY_SUBMISSION=PROVEN
B_UNICAST_TX_COMPLETION=PROVEN

A_SCHEMA5_APPLICATION_BOOT=PROVEN
A_SCHEMA5_RUNTIME_ALIVE=PROVEN
A_SCHEMA5_DIRECT_RUNTIME=PROVEN
A_SCHEMA5_COMPACT_BASELINE_ZERO=PROVEN

A_COMPACT_RX_UNDER_RELAY_TRAFFIC=NOT_YET_PROVEN
A_COMPACT_DECODE_UNDER_RELAY_TRAFFIC=NOT_YET_PROVEN
A_COMPACT_FORWARD_UNDER_RELAY_TRAFFIC=NOT_YET_PROVEN

KF089_END_TO_END_RELAY_TELEMETRY=NOT_YET_PROVEN
FIRST_UNPROVEN_STAGE=A_COMPACT_RX_UNDER_RELAY_TRAFFIC
```

The earlier evidence gap between Board B unicast completion and Board A compact reception has been narrowed. Board B Schema-v5 evidence already proves RelayActive, compact submission, and unicast completion. ID20R1 now proves Board A actually boots exact Schema-v5 and starts the next Relay experiment with every compact receive/processing counter at zero.

## Observability authority

```text
DIAGNOSTIC_SCHEMA_VERSION=5
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
DIAGNOSTIC_KEY=snapshot
PRODUCT_TARGET_DIAGNOSTICS_ENABLED=false
PHASE4_GENERIC_DIAGNOSTICS_ENABLED=true
```

ID20R1 established the following clean Board A Schema-v5 baseline before any new two-board Relay traffic:

```text
schema_version=5
path_state=0
current_channel=11
direct_channel_hint=11
relay_advertisement_attempts=26
relay_advertisement_submit_success=26
broadcast_completion_count=26
broadcast_completion_success=26
relay_active_count=0
relay_telemetry_attempts=0

compact_rx_count=0
compact_state_reject_count=0
compact_child_binding_failure=0
compact_decode_success=0
compact_decode_failure=0
compact_wrap_failure=0
compact_forward_attempts=0
compact_forward_submit_success=0
compact_forward_submit_failure=0
```

This is the receiver-side before-state authority for the next bounded A/B Relay validation.

## Board A Schema-v5 deployment / boot boundary

The bounded ID17–ID20R1 sequence is now closed PASS:

```text
ID17_SLOT_STATE_READONLY_PRECLAIM=PASS
ID18_INACTIVE_APP0_SCHEMA5_DEPLOYMENT=PASS
ID19_SLOT_SWITCH_ONLY=PASS
ID20R1_SCHEMA5_BOOT_POSTCHECK=PASS
```

Current public-safe Board A state:

```text
BOARD_A_APP0_EXACT_SCHEMA5=true
BOARD_A_APP0_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
BOARD_A_APP1_ROLLBACK_SHA256=5a3004647de0ef71e7be5664863a62b76a47c0cfdb32e38b07a296ca379f7562
BOARD_A_SELECTED_SLOT=0
BOARD_A_ACTIVE_OTA_SEQ=5
BOARD_A_ACTIVE_OTA_STATE=2
BOARD_A_SCHEMA5_APPLICATION_BOOT=PROVEN
BOARD_A_SCHEMA5_RUNTIME_ALIVE=PROVEN
BOARD_A_SCHEMA5_COMPACT_BASELINE_ZERO=PROVEN
BOARD_A_POSTCHECK_END_STATE=ROM_DOWNLOAD_MODE
```

ID18 wrote only inactive app0 and preserved otadata plus app1. ID19 changed only the bounded OTA selection metadata and did not rewrite app0/app1. ID20R1 performed exactly one normal application boot, then fresh ROM re-entry and read-only postcheck. No controlled Relay experiment was executed during ID20R1.

## Board B relevant evidence boundary

No Board B physical access occurred in ID17–ID20R1. The relevant frozen Schema-v5 Board B evidence remains:

```text
BOARD_B_SCHEMA5=PROVEN
BOARD_B_PATH_STATE=RELAY_ACTIVE
BOARD_B_RELAY_ACTIVE_COUNT=1
BOARD_B_RELAY_TELEMETRY_ATTEMPTS=44
BOARD_B_RELAY_TELEMETRY_SUBMIT_SUCCESS=44
BOARD_B_UNICAST_COMPLETION_COUNT=44
BOARD_B_UNICAST_COMPLETION_SUCCESS=41
BOARD_B_UNICAST_COMPLETION_FAILURE=3
```

`relay_telemetry_submit_success` is synchronous encrypted-peer submission success and is not itself a TX completion or receiver-side application-processing result. The unicast completion counters are the separate completion evidence.

## Execution-package authority

The exact execution commits that produced the ID17–ID20R1 evidence are:

```text
PR392_ID17_HEAD=645f06a8bb0dc3873d7309f7a24d7e99862eca26
PR393_ID18_HEAD=b796acc305a06610b34c1d0d0e35fcf2b37336ff
PR394_ID19_HEAD=643df426a03a20b319d8faa2a9d62eda9c56d6a6
PR395_ID20R1_HEAD=88c7d29a1c6f9fc2b17e371b0c6dd95f8867ab61
```

These PRs remain open/unmerged at this freeze. Their open state does not invalidate physical evidence produced from the exact authorized commits. No merge is implied by this current-state document.

## T1 runtime-convergence boundary

T1 runtime convergence remains closed PASS and was not accessed during ID17–ID20R1.

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

Detailed public-safe T1 archive:

`docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`

## Required guards

- USB port is a locator only and is not board identity authority.
- Board-targeted mutation requires explicit operator target/connection confirmation before board access.
- Fresh ROM silicon identity is required before any board write.
- Application serial open is not a passive runtime oracle.
- Lab diagnostic NVS writes are distinct from product NVS mutation.
- Discovery RX means decoded handler RX, not accepted advertisement.
- Historical discovery counts are boot-session cumulative, not exact final RF-window counts.
- A transmit submission success must not be conflated with a TX completion callback.
- Board B TX completion must not be conflated with Board A application-layer compact receive/decode/forward evidence.
- `NOT_PROVEN` must not be rewritten as numeric zero when the applicable diagnostic schema did not expose the counter.
- A normal application boot attestation and a proven Schema-v5 postcheck are separate evidence statements; a later postcheck STOP must not erase the fact that a boot already occurred.
- Stateful destructive rematerialization must use a quiesced snapshot unless an application-consistent online snapshot mechanism is proven.
- Public GitHub may store source, tests, hashes, sanitized closures, and public-safe state; raw NVS, full canonical MACs, credentials, private board identities, private host paths/addresses, and raw sensitive evidence remain private.

## Current ONE gate

```text
NEXT_ONE_GATE=PREPARE_KF089_SCHEMA5_TWO_BOARD_RELAY_VALIDATION_PACKAGE
```

This is currently a Host/GitHub-only package-preparation gate. It does not itself authorize Board A or Board B access, application boot, controlled RF, T1 access, or mutation.

After exact-head package review and CI, a fresh physical authorization will be required for the bounded two-board Relay validation.

## Route from current state

```text
PREPARE_SCHEMA5_TWO_BOARD_RELAY_VALIDATION_PACKAGE
-> HOST_REVIEW_AND_CI
-> FRESH_TWO_BOARD_PRECLAIM
-> SEPARATELY_AUTHORIZED_BOUNDED_RELAY_TRAFFIC_WINDOW
-> DURABLE_A/B_SCHEMA5_READBACK
-> STAGE_BY_STAGE_RELAY_TELEMETRY_ADJUDICATION
```

The next evidence chain must localize the same bounded Relay traffic window across:

```text
B unicast completion
-> A compact_rx_count
-> A state/capability gate
-> A child binding
-> A compact decode
-> A wrap
-> A forward attempt
-> A forward submit
```

Acceptance boundaries retained from earlier phases:

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_STARTUP_GATE_REPAIR=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PROVEN
KF089_AUTHENTICATED_RELAY_ACQUISITION=PROVEN
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```
