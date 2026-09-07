# N3-W Current State

Updated: 2026-09-07  
Status: `CURRENT_STATE_AUTHORITY`

This file is the concise public-safe authority for the current N3-W development state. Prefer fresh exact repository/runtime/physical evidence over this file if a later session discovers drift.

## Repository / source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN=QUERY_GITHUB_FRESH
PRODUCT_SOURCE_AUTHORITY=483ff1c662dc74d6e12529e27a69819e68160f9e
PRODUCT_SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
LAST_PRODUCT_SOURCE_CHANGE=PR_370
PR_369=MERGED
PR_370=MERGED
```

`483ff1c... -> 3f3deb6...` was rechecked on 2026-09-07 and contained documentation-only descendants. No product/test source change after PR #370 was found at that alignment point.

Active architecture authority:

`docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

Current product direction remains:

- provisioned runtime startup must not require an already-established Wi-Fi association;
- Direct Wi-Fi remains preferred;
- when Direct is unavailable, the node must be able to enter node-local autonomous bounded Relay discovery;
- full custom Wi-Fi/ESP-NOW radio ownership remains deferred unless physical evidence requires it.

## KF-089 source / product status

```text
KF089_ROOT_CAUSE_SOURCE_REPAIR=MERGED
KF089_STARTUP_GATE_REPAIR=PASS
TARGET_RUNTIME_READY_PHYSICAL=PASS
AUTONOMOUS_RELAY_DISCOVERY=NOT_PROVEN
AUTHENTICATED_RELAY_ACQUISITION=NOT_PROVEN
END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_PROVEN
```

PR #369 removed the live-Wi-Fi startup gate. The clean battery cold-boot retest proved the provisioned runtime became ready exactly once, but did not prove Relay acquisition.

## Observability product/source authority

PR #370 added lab-only schema-v3 observability without changing the product protocol path.

```text
DIAGNOSTIC_SCHEMA_VERSION=3
DIAGNOSTIC_NAMESPACE=gh_n3w_diag
DIAGNOSTIC_KEY=snapshot
PRODUCT_TARGET_DIAGNOSTICS_ENABLED=false
PHASE4_GENERIC_DIAGNOSTICS_ENABLED=true
```

Exact physical artifact:

```text
SOURCE_COMMIT=483ff1c662dc74d6e12529e27a69819e68160f9e
SOURCE_TREE=300b8fae886c954fe888edee17d6810e3c979bdc
FIRMWARE_IMAGE_SIZE=1114144
FIRMWARE_IMAGE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

The factory image remains unauthorized for KF-089 board refresh work.

## Board A — current physical state

Board A has completed its serial-free Direct baseline using the real remote T1 plus the durable schema-v3 snapshot.

Fresh T1 / durable binding evidence:

```text
T1_DIRECT_ACCEPTED_COUNT=18
T1_DIRECT_REJECTED_COUNT=0
T1_DIRECT_DUPLICATE_COUNT=0
T1_SEQ_FIRST=435
T1_SEQ_LAST=452
T1_INGRESS_SOURCE=direct

DIAG_BOOT_SESSION=11540229135812002993
T1_BOOT_SESSION=11540229135812002993
BOARD_A_DIAG_SESSION_BINDING=PASS
SESSION_ATTRIBUTION=PASS

DIAG_PATH_STATE=DIRECT
DIAG_CURRENT_CHANNEL=11
DIAG_DIRECT_CHANNEL_HINT=11
DIAG_SCAN_ATTEMPTS=0
DIAG_SCAN_FAILURES=0

DIAG_ADVERTISEMENT_ATTEMPTS=1304
DIAG_ADVERTISEMENT_SUBMIT_SUCCESS=1304
DIAG_ADVERTISEMENT_SUBMIT_FAILURE=0
DIAG_BROADCAST_COMPLETION_COUNT=1304
DIAG_BROADCAST_COMPLETION_SUCCESS=1304
DIAG_BROADCAST_COMPLETION_FAILURE=0

BOARD_A_T1_ACCEPTANCE_BINDING=PASS
BOARD_A_DURABLE_DIAG_BINDING=PASS
BOARD_A_DIRECT_BASELINE=PASS
```

Board A application-slot normalization then completed successfully:

```text
PRE_SELECTED_SLOT=1
POST_SELECTED_SLOT=1

PRE_APP0_IMAGE_SHA256=524690230c7164c889fd8cc4653c51bcba58132e187358b3685311b725c01825
PRE_APP1_IMAGE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d

POST_APP0_IMAGE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
POST_APP1_IMAGE_SHA256=efae17f4d863a1f54d6bf3537cd0b04082b9ad6bed2b948c7c8318a403b0756d
APP0_UNUSED_TAIL_ERASED=true

BOARD_A_APP0_EXACT_OBSERVABILITY=PASS
BOARD_A_APP1_EXACT_OBSERVABILITY=PASS
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS
```

Mutation invariants were preserved:

```text
PARTITION_TABLE_PRESERVED=PASS
OTADATA_PRESERVED=PASS
NVS_PRESERVED_DURING_MUTATION=PASS
APP1_PRESERVED=PASS
PRODUCT_NVS_MUTATION=false
```

Current live physical condition at handoff:

```text
BOARD_A_MODE=ROM_DOWNLOAD_MODE
BOOT_GPIO9_STILL_ASSERTED=true
APPLICATION_POSTCHECK_EXECUTED=false
POSTCHECK_T1_DIRECT_ACCEPTED=0
PRODUCT_FAILURE=false
```

The lack of postcheck telemetry is expected because Board A remained in ROM Download Mode; the application did not start. This is not evidence of a firmware failure.

## Board B — current boundary

Board B has **not** yet been refreshed to the schema-v3 observability image in the current route.

```text
BOARD_B_OBSERVABILITY_REFRESH=NOT_EXECUTED
BOARD_B_BOTH_SLOTS_EXACT_MAIN=NOT_PROVEN
```

Do not begin Board B work until Board A postcheck closes PASS.

## Remote T1

The actual remote T1 authority has been recovered and proved live:

```text
REMOTE_T1_AUTHORITY_FOUND=PASS
REMOTE_T1_SSH_BINDING=PASS
REMOTE_T1_RUNTIME_BINDING=PASS
T1_MANAGER_RUNNING=true
T1_BROKER_RUNNING=true
REMOTE_T1_LIVE_OBSERVER_AVAILABLE=true
REMOTE_T1_OBSERVER_TYPE=MANAGER_CANONICAL_ACCEPTANCE
```

Do not substitute localhost ports/containers for T1 authority.

## Harness guards retained

- Native-USB serial open was observed to trigger an application reset with the reused collector; do not use that collector as a passive runtime oracle.
- `gh_n3w_diag/snapshot` writes are expected lab-diagnostic NVS writes; distinguish them from product NVS mutation.
- Channel 11 is a valid current home/direct channel and is within the frozen `{1,6,11}` discovery allowlist.
- KF-088 remains relevant: GPIO9 low/held means ROM Download Mode. Release BOOT/GPIO9 before normal application startup.
- Task contracts must not simultaneously globally forbid a mutation and later require that same mutation.

## Current ONE gate

```text
NEXT_ONE_GATE=KF089_BOARD_A_RELEASE_BOOT_AND_POSTCHECK
```

Purpose: release BOOT/GPIO9, perform one normal Board A power-cycle/start with BOOT released, then use the real remote T1 observer to prove stable Direct runtime and preserved product identity/security state. No flash/NVS/source/T1 mutation is allowed.

After that gate passes, the next stage is:

```text
AFTER_PASS_NEXT_STAGE=KF089_OBSERVABILITY_BOARD_B_REFRESH_AND_DURABLE_DIRECT_BASELINE
AUTO_EXECUTE_AFTER_PASS=false
```

## Frozen acceptance boundaries

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_STARTUP_GATE_REPAIR=PASS
BOARD_A_DIRECT_BASELINE=PASS
BOARD_A_BOTH_SLOTS_EXACT_MAIN=PASS
KF089_AUTONOMOUS_RELAY_ACQUISITION=OPEN
LIVE_DIRECT_TO_RELAY_FAILOVER=NOT_YET_ADJUDICATED
LIVE_RELAY_TO_DIRECT_RECOVERY=NOT_YET_ADJUDICATED
```

## Evidence boundary

Public GitHub stores source, tests, hashes, sanitized closures and architecture decisions. Raw NVS, credentials, Setup Secrets, private board identities, remote-host details and other sensitive physical evidence remain private/local.
