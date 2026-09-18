# N3-W Current State

Updated: 2026-09-18  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/physical evidence takes precedence if later evidence proves drift.

## Repository / product source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

ALIGNMENT_BASE_MAIN=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
PRODUCT_SOURCE_AUTHORITY=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
REPOSITORY_MAIN_AT_ARTIFACT_GATE=e2390faf2452730264c19687bf4022df974f04bd
REPOSITORY_MAIN_TREE_AT_ARTIFACT_GATE=94566c80256db64e8cf4b0cbece9bfd0f1acc417

PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c
PR431_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f
PR431_MERGE=d1b5c3acbd32cca95483743ffe2edba9aa3f904f

FROZEN_DEPLOYED_PRODUCT_SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
FROZEN_DEPLOYED_PRODUCT_SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
```

PR #431 is merged at product-source authority `d1b5c3acbd32cca95483743ffe2edba9aa3f904f`, with Astra-approved review HEAD `137303c7b08fff36920d05e77c2f1bcc20b38d1f` as the second merge parent. Post-merge public-safety and greenhouse-manager CI are PASS. The older PR #428 artifact remains historical build/binding evidence only and is not deployment-eligible. Board B still runs the frozen PR #425 artifact. Repository documentation may advance beyond the product-source authority; source, candidate artifact, and deployed physical source remain separate authorities.

## Recent integrated route

```text
PR420=MERGED   # documentation alignment after PR416 deployment
PR421=MERGED   # retained RTC watchdog breadcrumb
PR422=MERGED   # Relay unicast channel observability
PR423=MERGED   # async MQTT / disable MQTT log forwarding in physical harness
PR424=MERGED   # explicit single-radio ownership / bounded Direct probes
PR425=MERGED   # transactional Direct failback + Relay channel fixation
PR426=MERGED   # documentation alignment through PR425 artifact preparation
PR427=MERGED   # documentation alignment after PR425 physical validation
PR428=MERGED   # KF-096 Direct recovery continuity source repair
PR431=MERGED   # finite successor: recovery-exit / teardown lifecycle closure
```

Exact product repair merges:

```text
PR421_MERGE=fb762e2ccb54393e7610339d05d164b7ea975bba
PR422_MERGE=a01725644d9b0b4ee0a461c1579211829f1aa69e
PR423_MERGE=35944fa928bb1fcf5527e476fb5dbfcfcdc11ead
PR424_MERGE=664fcbe88bae76bc9fc6e5e240067e3cbae7c649
PR425_MERGE=096528fbf61948d6c69197f1c8994ce8e7d672f4
PR427_MERGE=58b6679c5cb8da5c935d581b66ba129b02db4b8a
PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c
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

## PR #428 KF-096 source repair

PR #428 repaired the source-level continuity defect but has not yet been physically deployed or accepted.

```text
PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c
MAIN_AFTER_PR428=f357db25390ffd097e9b8608293870772f9cb16c

PR428_PREMERGE_CI=13_OF_13_PASS
PR428_POSTMERGE_PUBLIC_REPOSITORY_SAFETY_CI=PASS
PR428_POSTMERGE_PUBLIC_REPOSITORY_SAFETY_RUN=35308124872
PR428_POSTMERGE_GREENHOUSE_MANAGER_CI=PASS
PR428_POSTMERGE_GREENHOUSE_MANAGER_RUN=35308124851

PR428_EXACT_ARTIFACT_BUILD=PASS
PR428_EXACT_ARTIFACT_BINDING=PASS
PR428_ARTIFACT_RUN_ID=35309484471
PR428_ARTIFACT_ID=10533235759
PR428_ARTIFACT_NAME=n3w-pr428-boardb-exact-source
PR428_APPLICATION_SHA256=b3e2311818d539c2abf98e4fa9ff431069b414da6f9993f350e4a7c427929f3a
PR428_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PR428_ARTIFACT_ZIP_SHA256=ce5f2de1a152bceb746b22b1aaca7364374ed9f91656230359fed4079776a55e

PR428_PHYSICAL_DEPLOYMENT=NOT_EXECUTED
PR428_PHYSICAL_VALIDATION=NOT_EXECUTED
KF096_STATUS=OPEN
```

The merged repair keeps Relay telemetry in ordered bounded buffering during full Direct verification / Relay restore, uses single-flight ESP-NOW unicast completion ordering, probes the remembered AP BSSID before opening a full Direct verification window, applies 60/120/240/480 s recovery backoff while Relay remains healthy, restores and verifies the concrete Relay channel after presence scanning, and keeps the diagnostic current-channel oracle tied to real Wi-Fi readback rather than logical working-channel state.

This source/CI result does not close KF-096. The deployed Board B remains on PR #425, the historical post-fix `ESP_ERR_ESPNOW_CHAN` elimination still lacks a fresh physical low-level oracle, and Relay -> Direct failback has still not been physically executed on PR #428.

## PR #428 exact artifact binding

```text
BUILD_BRANCH=build/n3w-pr428-boardb-artifact-20260918
WORKFLOW_SOURCE_COMMIT=ec256e8b219942d61ecf583ae558e9aef31b0482
ARTIFACT_RUN_ID=35309484471
ARTIFACT_ID=10533235759
ARTIFACT_NAME=n3w-pr428-boardb-exact-source
ARTIFACT_EXPIRES_AT=2026-09-25T05:09:29Z

SOURCE_HEAD=f357db25390ffd097e9b8608293870772f9cb16c
SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64
ESPHOME_VERSION=2026.4.3
ESP_IDF=5.5.4

APPLICATION_SIZE=1133424
APPLICATION_SHA256=b3e2311818d539c2abf98e4fa9ff431069b414da6f9993f350e4a7c427929f3a

OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

ARTIFACT_ZIP_SIZE=723298
ARTIFACT_ZIP_SHA256=ce5f2de1a152bceb746b22b1aaca7364374ed9f91656230359fed4079776a55e

RAM_USED=50648/327680
FLASH_USED=1133068/3932160

PR428_EXACT_ARTIFACT_BUILD=PASS
PR428_EXACT_ARTIFACT_BINDING=PASS
```

This artifact is not a deployed state. It is now frozen historical evidence and is not deployment-eligible after the PR #431 successor repair. KF-084 remains applicable: a later rebuild from the same source must not silently replace the frozen hashes above.



## PR #431 merged successor / source authority

PR #431 completed three Astra review rounds and is merged.

```text
PR431_STATE=MERGED
PR431_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f
PR431_MERGE=d1b5c3acbd32cca95483743ffe2edba9aa3f904f

PR431_PREMERGE_CI=11_OF_11_PASS
PR431_POSTMERGE_PUBLIC_REPOSITORY_SAFETY_CI=PASS
PR431_POSTMERGE_PUBLIC_REPOSITORY_SAFETY_RUN=35321513253
PR431_POSTMERGE_GREENHOUSE_MANAGER_CI=PASS
PR431_POSTMERGE_GREENHOUSE_MANAGER_RUN=35321513207

PR431_POSTMERGE_PHASE4_SIMPLIFIED_PRODUCT_RUNTIME=PASS
PR431_POSTMERGE_ESP32_C6_CHILD_COMPILE=PASS
PR431_POSTMERGE_ESP32_C6_RELAY_COMPILE=PASS
PR431_POSTMERGE_ESP32_C6_PHYSICAL_HARNESS_COMPILE=PASS

ASTRA_FINAL_REVIEW=PASS
A1_PARTIAL_INIT_TEARDOWN=CLOSED
A2_STARTUP_UNCONFIRMED_EXIT=CLOSED
REAL_DRIVER_FAULT_INJECTION_COVERAGE=SUFFICIENT
NO_NEW_MERGE_BLOCKER=true
```

The merged finite repair preserves the existing radio architecture. It fixes BSSID configuration provenance, bounds unicast/restore exits, uses a fresh-boot boundary for abnormal missing completion, tracks partial ESP-NOW initialization with an independent SDK-started state, and reboots rather than indefinitely retrying startup when teardown is unconfirmed.

Source/CI success does not close KF-096 and does not authorize Board B access or flashing. A new exact artifact must be built and bound from the merged product-source authority before any later physical gate.

## Current acceptance matrix

```text
KF092_STATUS=CLOSED_PASS
KF093_TASK_WDT=GUARDED
KF094_SINGLE_RADIO_CHANNEL_OWNERSHIP=OPEN
KF095_FAILBACK_COMMIT_ORDER=GUARDED
KF096_DIRECT_PROBE_TELEMETRY_BLACKOUT=OPEN

PR428_SOURCE_REPAIR=MERGED
PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c
PR428_PREMERGE_CI=13_OF_13_PASS
PR428_POSTMERGE_CI=PASS
PR428_EXACT_ARTIFACT_BUILD=PASS
PR428_EXACT_ARTIFACT_BINDING=PASS
PR428_ARTIFACT_RUN_ID=35309484471
PR428_ARTIFACT_ID=10533235759
PR428_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR428_PHYSICAL_VALIDATION=NOT_EXECUTED
PR428_ARTIFACT_DISPOSITION=FROZEN_HISTORICAL_NOT_FOR_DEPLOYMENT

PR431_SOURCE_REPAIR=MERGED
PR431_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f
PR431_MERGE=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
PR431_PREMERGE_CI=11_OF_11_PASS
PR431_POSTMERGE_CI=PASS
PR431_ASTRA_FINAL_REVIEW=PASS
PR431_EXACT_ARTIFACT_PREPARATION=PASS
PR431_EXACT_ARTIFACT_BUILD=NOT_EXECUTED
PR431_EXACT_ARTIFACT_BINDING=NOT_EXECUTED
PR431_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR431_PHYSICAL_VALIDATION=NOT_EXECUTED

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
- PR #428 artifact success is historical evidence only and must not be deployed after the PR #431 successor merge. PR #431 merge/source/CI success must not be promoted to KF-096 physical closure; a new exact PR #431 artifact, exact binding, explicit target preflight, deployment authorization, and physical acceptance remain separate later gates.
- Consumed physical authorizations are never replayable.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_KF096_PR431_EXACT_ARTIFACT_BUILD_AND_BINDING_EXECUTION_20260918_01

PRODUCT_SOURCE_AUTHORITY=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
PRODUCT_SOURCE_TREE=3f161c1550e1df48db7cd5a5970db1b11932bef0
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_GIT_BLOB_SHA=3d13e2197520c375b56d682b37773ef28e194421

PREPARATION_AUTHORITY=
docs/development/N3W_KF096_PR431_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260918.md

WORKFLOW_TEMPLATE_SHA256=
5c5313bb627d50ca8337ebea310c588fefc3b32c5eedd08f99d09fa03b6f6bfc

ARTIFACT_BUILD_AUTHORIZATION_REQUIRED=true
ARTIFACT_BUILD=NOT_EXECUTED
ARTIFACT_BINDING=NOT_EXECUTED

BOARD_ACCESS_REQUIRED=false
BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
T1_MUTATION=false
```

Preparation is complete. The next gate may create the reserved build-only workflow branch and execute the exact-source artifact build only after separate explicit authorization. It must fail closed on source/tree/target/toolchain/template mismatch and must not access Board B, serial, Flash, or T1.

## Public/private evidence boundary

Public GitHub may store source, tests, artifact hashes, sanitized timing/acceptance results, and architecture decisions. Do not commit raw credentials, setup secrets, private keys, raw NVS, private host addresses, raw Manager/Broker logs, or raw board identity material.
