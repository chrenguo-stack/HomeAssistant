# N3-W Current State

Updated: 2026-09-18  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/physical evidence takes precedence if later evidence proves drift.

## Repository / product source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

FROZEN_PRODUCT_SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
FROZEN_PRODUCT_SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
```

Repository `main` may advance after documentation-only merges. That must not silently redefine the frozen Board B candidate firmware source above.

## Recent integrated route

```text
PR420=MERGED   # documentation alignment after PR416 deployment
PR421=MERGED   # retained RTC watchdog breadcrumb
PR422=MERGED   # Relay unicast current-channel / peer-channel observability
PR423=MERGED   # prevent synchronous MQTT/log watchdog stall
PR424=MERGED   # explicit single-radio ownership / bounded Direct probes
PR425=MERGED   # transactional Direct failback + Relay channel fixation
```

Exact merge commits:

```text
PR421_MERGE=fb762e2ccb54393e7610339d05d164b7ea975bba
PR422_MERGE=a01725644d9b0b4ee0a461c1579211829f1aa69e
PR423_MERGE=35944fa928bb1fcf5527e476fb5dbfcfcdc11ead
PR424_MERGE=664fcbe88bae76bc9fc6e5e240067e3cbae7c649
PR425_MERGE=096528fbf61948d6c69197f1c8994ce8e7d672f4
```

## Frozen accepted baselines

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF092_STATUS=CLOSED_PASS
```

KF-092 remains closed and is not reopened by the current radio-ownership route.

## Physical defect sequence now established

### 1. Task watchdog during Direct loss

RTC breadcrumb + source forensic proved the physical harness could block the ESPHome main loop through synchronous MQTT/log forwarding while Direct Wi-Fi disappeared.

PR #423 changed the lab MQTT path to async backend send and disabled MQTT log forwarding.

Fresh physical retest proved:

```text
TASK_WDT_REPRODUCED=false
UNCOMMANDED_REBOOT=false
PR423_TASK_WDT_REPAIR_PHYSICAL_VALIDATION=PASS
MANAGER_RESTART_COUNT=0
```

### 2. Same-boot Direct -> Relay still had ~110 s blackout

After the watchdog repair, a fresh same-boot run still showed approximately:

```text
MANAGER_VISIBLE_GAP_MS≈110061
SAME_BOOT_DIRECT_TO_RELAY=PASS
```

Relay encrypted unicast observability then captured:

```text
UNICAST_FAILURE_COUNT=2
FIRST_FAILURE_CURRENT_CHANNEL=5
FIRST_FAILURE_PEER_CHANNEL=11
FIRST_FAILURE_RAW_ERROR=12397
RAW_ERROR_12397=ESP_ERR_ESPNOW_CHAN
LATER_SUCCESS_CURRENT_CHANNEL=11
LATER_SUCCESS_PEER_CHANNEL=11
```

This is direct evidence that the radio and encrypted peer could disagree on channel during failover.

### 3. Root source defect

ESPHome Wi-Fi reconnect/scanning and N3-W Relay/Discovery could both control the one ESP32-C6 2.4 GHz radio.

PR #424 introduced explicit ownership states:

```text
DIRECT_WIFI
RELAY_ESPNOW
DIRECT_PROBE
```

Relay/Discovery now disables ESPHome Wi-Fi reconnect before standalone ESP-NOW takes the radio. Failed Direct probes restore Relay state and rebind channel/encrypted peer.

### 4. PR #424 review found a failback commit-order defect

Source review proved a Direct recovery could commit logical `DIRECT` before concrete channel restoration. A restoration failure could therefore leave logical state `DIRECT` while component ownership remained `DIRECT_PROBE`, suppressing telemetry indefinitely.

PR #425 fixes the ordering:

```text
concrete Direct radio/channel restore
→ logical DIRECT commit
```

On failure, Relay/Discovery remains authoritative and Direct recovery hysteresis resets.

PR #425 also fixes Relay channel before encrypted peer installation and before `RelayActive` commit, and uses the already-owned fixed Relay channel for Challenge instead of starting another temporary off-channel operation.

## PR #425 source / CI closure

```text
PR425_HEAD=253e28b08db8ca7854ad25d72e3270decd02506d
PR425_MERGE=096528fbf61948d6c69197f1c8994ce8e7d672f4

POST_MERGE_PUBLIC_REPOSITORY_SAFETY_CI=PASS
POST_MERGE_GREENHOUSE_MANAGER_CI=PASS
POST_MERGE_GREENHOUSE_MANAGER_RUN=35293249780

PHASE4_SINGLE_RADIO_OWNERSHIP_CONTRACTS=PASS
PHASE4_SIMPLIFIED_PRODUCT_RUNTIME=PASS
ESP32C6_CHILD_BUILD=PASS
ESP32C6_RELAY_BUILD=PASS
ESP32C6_PHASE4_PHYSICAL_HARNESS_BUILD=PASS
```

## Frozen PR #425 Board B artifact

Build-only workflow:

```text
BUILD_BRANCH=build/n3w-pr425-boardb-artifact-20260918
ARTIFACT_RUN_ID=35294123841
ARTIFACT_ID=10528055066
ARTIFACT_NAME=n3w-pr425-boardb-exact-main
```

Exact source binding:

```text
SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
ESPHOME_VERSION=2026.4.3
```

Frozen write files:

```text
APPLICATION_SIZE=1128720
APPLICATION_SHA256=bf3af5490745f1279a4e90d57a8e96b46525ae8debaf6f806ed2ae72180836c0

OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

ARTIFACT_ARCHIVE_SHA256=b69f9f3736eca8da40cafa1b8cc63d8fb901dee99a8f3afb5724e216bffc6c62
```

The build-only branch is not product authority and must not be merged merely to preserve the artifact.

## Current physical boundary

```text
BOARD_B_PR425_FLASH=false
BOARD_A_MUTATION=false
SERIAL_OPEN=false
T1_RUNTIME_MUTATION=false
BROKER_MANAGER_DYNSEC_MUTATION=false
```

The Board B artifact exists and is exact-bound, but the target board has not yet been touched for this deployment route.

Historical USB paths and board identifiers are not sufficient mutation authority. A future write requires fresh ROM silicon identity and security/flash-state confirmation.

## Current acceptance matrix

```text
KF092_STATUS=CLOSED_PASS

PR423_TASK_WDT_REPAIR=PASS
PR423_PHYSICAL_VALIDATION=PASS

PR424_SINGLE_RADIO_OWNERSHIP_SOURCE_REPAIR=PASS
PR425_FAILBACK_COMMIT_ORDER_SOURCE_REPAIR=PASS
PR425_POST_ACCEPT_CHANNEL_FIXATION_SOURCE_REPAIR=PASS

PR425_POST_MERGE_CI=PASS
PR425_EXACT_MAIN_ARTIFACT_BINDING=PASS

PR425_BOARD_B_DEPLOYMENT=PENDING
PR425_DIRECT_TO_RELAY_PHYSICAL_VALIDATION=PENDING
PR425_RELAY_STEADY_STATE_PROBE_GAP_VALIDATION=PENDING
PR425_RELAY_TO_DIRECT_FAILBACK_VALIDATION=PENDING
HOME_ASSISTANT_ENTITY_UPDATE=SEPARATE_OPEN_ITEM
```

## Current design note: bounded Direct probes

Relay mode currently schedules bounded Direct recovery probes approximately every 60 s with a probe window up to 15 s. While in `DIRECT_PROBE`, Relay telemetry submission is paused.

This is intentional current source behavior, not yet a proven product-acceptance result. Later physical validation must measure:

- repeated failed probe recovery back to Relay;
- actual telemetry pause duration;
- successful Relay -> Direct recovery;
- a subsequent Direct -> Relay transition;
- no persistent no-send state if a recovery operation fails.

## Required guards

- USB path is only a locator; any Board write requires fresh silicon identity.
- Do not open application serial as a passive oracle; it can reset the board.
- Do not mutate Board A, T1 Manager/Broker, DynSec, credentials, or TLS merely to validate Board B firmware.
- Do not rewrite bootloader, partition table, or product NVS unless a separately justified route explicitly requires it.
- Keep repository-main authority separate from frozen product-source/artifact authority.
- Do not attribute the entire historical ~110 s blackout to one channel event; report failover phases separately.
- `ESP_OK` from an ESP-NOW submit is not async RF delivery proof.
- Consumed physical authorizations are never replayable.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_PR425_BOARD_B_WRITE_TARGET_PREFLIGHT_20260918_01
BOARD_ACCESS_REQUIRED=true
PREFLIGHT_READ_ONLY=true
FLASH_WRITE=false
SERIAL_OPEN=false
T1_MUTATION=false
```

Purpose: before any Board B write, freshly confirm the physically connected target, ESP32-C6 silicon identity, expected flash size, Secure Boot / Flash Encryption state, and bind those facts to the frozen PR #425 artifact.

The actual app+otadata write requires a separate explicit Board B write authorization after this preflight passes.

## Local development environment authority

Current redacted environment authority remains:

`docs/development/local-environment-records/2026-09-17-macos-x86_64.json`

No Mac-local state was accessed by this documentation alignment. This file aligns the current conversation/evidence state to GitHub.

## Public/private evidence boundary

Public GitHub may store source, tests, public-safe artifact hashes, sanitized timing/acceptance results, and architecture decisions. Do not commit raw credentials, raw NVS, private keys, private host addresses, raw Manager/Broker logs, or private board identity material.
