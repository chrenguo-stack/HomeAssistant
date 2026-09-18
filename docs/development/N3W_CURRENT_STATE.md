# N3-W Current State

Updated: 2026-09-18  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/physical evidence takes precedence if later evidence proves drift.

## Repository / product source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

ALIGNMENT_BASE_MAIN=f6b9f3d60078998cd543d4e0482f5ae30f6d0dc7
FROZEN_PRODUCT_SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
FROZEN_PRODUCT_SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
```

Repository `main` may advance after documentation-only merges. That must not silently redefine the product source actually deployed to Board B.

## Recent integrated route

```text
PR420=MERGED   # documentation alignment after PR416 deployment
PR421=MERGED   # retained RTC watchdog breadcrumb
PR422=MERGED   # Relay unicast channel observability
PR423=MERGED   # async MQTT / disable MQTT log forwarding in physical harness
PR424=MERGED   # explicit single-radio ownership / bounded Direct probes
PR425=MERGED   # transactional Direct failback + Relay channel fixation
PR426=MERGED   # documentation alignment through PR425 artifact preparation
```

Exact product repair merges:

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

KF-092 remains closed and is not reopened by later radio-ownership or failback work.

## Physical defect / repair sequence

### Task watchdog

PR #423 repaired the synchronous MQTT/log-forwarding watchdog hazard. Fresh physical retest proved:

```text
TASK_WDT_REPRODUCED=false
UNCOMMANDED_REBOOT=false
PR423_TASK_WDT_REPAIR_PHYSICAL_VALIDATION=PASS
MANAGER_RESTART_COUNT=0
```

### Historical single-radio channel conflict

After the watchdog repair, a same-boot run still had approximately 110.061 s Manager-visible blackout and captured:

```text
CURRENT_CHANNEL=5
PEER_CHANNEL=11
RAW_ERROR=12397
RAW_ERROR_12397=ESP_ERR_ESPNOW_CHAN
```

PR #424 introduced explicit `DIRECT_WIFI / RELAY_ESPNOW / DIRECT_PROBE` ownership. PR #425 then made Direct failback commit ordering transactional and fixed Relay channel before encrypted-peer / RelayActive commit.

## PR #425 exact Board B artifact

```text
ARTIFACT_RUN_ID=35294123841
ARTIFACT_ID=10528055066
ARTIFACT_NAME=n3w-pr425-boardb-exact-main
ESPHOME_VERSION=2026.4.3

APPLICATION_SIZE=1128720
APPLICATION_SHA256=bf3af5490745f1279a4e90d57a8e96b46525ae8debaf6f806ed2ae72180836c0

OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

## PR #425 Board B deployment

The exact artifact was written to the intended ESP32-C6 target.

```text
BOARD_B_PR425_DEPLOYMENT=PASS
APPLICATION_WRITE=PASS
OTADATA_WRITE=PASS
APPLICATION_HASH_VERIFY=PASS
OTADATA_HASH_VERIFY=PASS

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false

AUTHORIZED_WRITE_CONSUMED=true
REPLAY_PERMITTED=false
```

## Post-flash and battery Direct baselines

```text
BOARD_B_PR425_POSTFLASH_DIRECT_BASELINE=PASS
BOARD_B_BATTERY_DIRECT_BASELINE=PASS
DIRECT_TELEMETRY_CONTINUOUS=true
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
```

The battery reboot established a new boot session; the later Direct -> Relay transition was performed without another power cycle.

## PR #425 same-boot Direct -> Relay physical result

```text
SAME_BOOT_DIRECT_TO_RELAY=PASS
MANAGER_RELAY_ACCEPTANCE=PASS
BOARD_A_RELAY_GATEWAY_STABLE=true
UNCOMMANDED_REBOOT=false
MANAGER_RESTART_COUNT=0

INITIAL_MANAGER_VISIBLE_GAP_MS=30034
INITIAL_MISSING_SEQUENCE_COUNT=5
```

This is materially shorter than the earlier approximately 110.061 s blackout.

The physical window did not include the low-level `n3w_u` / current-channel / peer-channel diagnostic oracle, so it does not prove the historical `ESP_ERR_ESPNOW_CHAN` class impossible. KF-094 therefore remains open conservatively pending stronger low-level confirmation / complete round-trip acceptance.

## KF-096: periodic Relay blackout during Direct recovery probes

Fresh physical evidence after Relay activation repeatedly showed:

```text
~60 s Relay telemetry
-> ~15 s telemetry suppression
-> Relay resumes
-> repeat
```

At the current ~5 s telemetry cadence this drops about three business samples per probe window.

Exact deployed source contains:

```text
kRecoveryProbeIntervalMs=60000
kRecoveryProbeWindowMs=15000
kRecoveryProbeMs=2000
```

and rejects telemetry while ownership is `DIRECT_PROBE`.

Therefore:

```text
KF096_DOMAIN=PRODUCT
KF096_STATUS=OPEN
KF096_ROOT_CAUSE=SOURCE_CONFIRMED_AND_PHYSICAL_TIMING_CONFIRMED
```

This is not classified as random RF loss, Board A instability, or Manager restart.

## Current acceptance matrix

```text
KF092_STATUS=CLOSED_PASS
KF093_TASK_WDT=GUARDED
KF094_SINGLE_RADIO_CHANNEL_OWNERSHIP=OPEN
KF095_FAILBACK_COMMIT_ORDER=GUARDED
KF096_DIRECT_PROBE_TELEMETRY_BLACKOUT=OPEN

PR425_POST_MERGE_CI=PASS
PR425_EXACT_ARTIFACT_BINDING=PASS
PR425_BOARD_B_DEPLOYMENT=PASS
PR425_POSTFLASH_DIRECT_BASELINE=PASS
PR425_BATTERY_DIRECT_BASELINE=PASS

PR425_SAME_BOOT_DIRECT_TO_RELAY_FUNCTIONAL_RESULT=PASS
PR425_INITIAL_MANAGER_VISIBLE_GAP_MS=30034

PR425_RELAY_STEADY_STATE_CONTINUITY=FAIL
PR425_RELAY_TO_DIRECT_FAILBACK_VALIDATION=NOT_EXECUTED

OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

## Required guards

- USB path is only a locator; board-targeted write authorization remains explicit and single-use.
- Do not open application serial as a passive oracle; it can reset the board.
- Do not mutate Board A, T1 Manager/Broker, DynSec, credentials, or TLS merely to diagnose the current source defect.
- Keep repository-main authority separate from frozen deployed product-source authority.
- Do not attribute the entire historical ~110 s or current ~30 s Direct -> Relay gap to a single phase without phase-specific evidence.
- Do not claim historical `ESP_ERR_ESPNOW_CHAN` eliminated unless post-fix low-level channel/error diagnostics prove it.
- `ESP_OK` from ESP-NOW submit is not async RF delivery proof.
- Direct recovery must not achieve failback responsiveness by silently discarding periodic Relay business telemetry.
- Consumed physical authorizations are never replayable.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_PR425_RELAY_DIRECT_PROBE_TELEMETRY_BLACKOUT_SOURCE_REPAIR_20260918_01

BOARD_ACCESS_REQUIRED=false
BOARD_MUTATION=false
SERIAL_OPEN=false
T1_MUTATION=false
SOURCE_REVIEW_REQUIRED=true
HOST_TEST_REQUIRED=true
```

First objective: redesign the bounded Direct recovery mechanism so Direct restoration can still be detected without deterministic Relay telemetry loss. Compare buffering, shorter probe slices, backoff/adaptive probing, and any ESP-IDF-supported scan/association alternatives against the single-radio ownership contract.

## Public/private evidence boundary

Public GitHub may store source, tests, artifact hashes, sanitized timing/acceptance results, and architecture decisions. Do not commit raw credentials, setup secrets, private keys, raw NVS, private host addresses, raw Manager/Broker logs, or raw board identity material.
