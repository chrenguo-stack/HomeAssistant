# N3-W Current State

Updated: 2026-09-19  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/physical evidence takes precedence if later evidence proves drift.

## Repository / product source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

ALIGNMENT_BASE_MAIN=d9afc55b04042806ed8b6e1b1ae3553742aba2be
PRODUCT_SOURCE_AUTHORITY=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
REPOSITORY_MAIN_AT_ALIGNMENT_START=d9afc55b04042806ed8b6e1b1ae3553742aba2be
REPOSITORY_MAIN_AFTER_PR439=02efd64312c4b01c19c0a18e6db543145a16ad9c
REPOSITORY_MAIN_AT_POSTWRITE_ALIGNMENT_START=0ea13c9f9f76fdf7fb79ec82393408ab144b4e18

PR431_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f
PR431_MERGE=d1b5c3acbd32cca95483743ffe2edba9aa3f904f

CURRENT_CANDIDATE_PR=437
CURRENT_CANDIDATE_SOURCE_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
CURRENT_CANDIDATE_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0
CURRENT_CANDIDATE_ARTIFACT_ID=10575077512

FROZEN_DEPLOYED_PRODUCT_SOURCE_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
FROZEN_DEPLOYED_PRODUCT_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0
```

PR #431 remains the latest merged product-source authority at `d1b5c3acbd32cca95483743ffe2edba9aa3f904f`. PR #437 remains the current unmerged draft successor candidate at exact HEAD `cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c`; its final source review, CI, and exact-artifact binding passed. Board B now runs the exact PR #437 artifact after an operator-confirmed target override of the automated identity mismatch. Repository main, merged product source, PR #437 candidate source, and deployed physical source remain separate authorities.

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
PR436=CLOSED_SUPERSEDED   # historical PR431-bound Board B executor, not valid for PR437
PR437=OPEN_DRAFT   # current Direct recovery liveness / deadline successor candidate
PR439=MERGED   # PR437-bound Board B preflight/write executor
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

Source/CI success does not close KF-096 and does not authorize Board B access or flashing. PR #431 remains the latest merged product-source authority, but its artifact is historical for the current validation route because the newer unmerged PR #437 candidate now has its own exact artifact.

## PR #437 current successor candidate

Local source review, repair, CI, repository cleanup, and exact-artifact binding are now aligned to GitHub.

```text
PR437_STATE=OPEN_DRAFT
PR437_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
PR437_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0
PR437_BASE_MAIN_AT_REPAIR=d9afc55b04042806ed8b6e1b1ae3553742aba2be

PR437_FINAL_SOURCE_REVIEW=PASS
PR437_NEW_SOURCE_BLOCKER_FOUND=false
A1_PHASE_DEADLINE_LATE_PROGRESS_BYPASS=CLOSED
A2_ABSOLUTE_DEADLINE_SUCCESS_PATH_BYPASS=CLOSED
A3_BSSID_WALLCLOCK_EXPIRY_INTEGRATION_GAP=CLOSED
DIRECT_COMMIT_AFTER_ABSOLUTE_DEADLINE=CLOSED

PR437_FINAL_GREENHOUSE_MANAGER_CI_RUN=35373202121
PR437_HEAD_WORKFLOW_COUNT=11
PR437_HEAD_WORKFLOW_SUCCESS_COUNT=11

PR437_EXACT_ARTIFACT_BUILD=PASS
PR437_EXACT_ARTIFACT_BINDING=PASS
PR437_ARTIFACT_RUN_ID=35414060819
PR437_ARTIFACT_ID=10575077512
PR437_ARTIFACT_NAME=n3w-pr437-boardb-exact-source
PR437_ARTIFACT_ZIP_SIZE=727532
PR437_ARTIFACT_ZIP_SHA256=b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814
PR437_APPLICATION_SIZE=1139600
PR437_APPLICATION_SHA256=407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb
PR437_OTADATA_SIZE=8192
PR437_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PR437_MANIFEST_SHA256=98a6dec323e8057a30d6b1e332d549fe54288f3b45fcbbbf460292871f7a91a0

PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS
PR437_PHYSICAL_VALIDATION=IN_PROGRESS

PR439_STATE=MERGED
PR439_REVIEW_HEAD=da6b1e7e364a0125c832e27c62b6c9741bdbfa17
PR439_MERGE=02efd64312c4b01c19c0a18e6db543145a16ad9c
PR439_FINAL_SOURCE_REVIEW=PASS
PR439_CI=12_OF_12_PASS
PR439_FOCUSED_TESTS=12_PASS
PR439_A1_SINGLE_USE_WRITE_AUTHORIZATION=CLOSED
PR439_A2_PARTITION_TABLE_FRESH_BINDING=CLOSED
```

Repository hygiene was also aligned: 18 merged recent N3-W branches were deleted, PR #436 was closed as superseded, the PR #437 branch was preserved, and historical artifact build branches were preserved.

The exact PR #437 artifact is the current Board B validation candidate. Artifact binding proves source-to-binary identity only; KF-096 remains OPEN until fresh physical evidence closes the required runtime route.

## PR #439 merged Board B preflight/write executor

PR #439 merged the PR #437-specific fail-closed Board B preflight/write executor after the final post-repair source review.

```text
PR439_STATE=MERGED
PR439_REVIEW_HEAD=da6b1e7e364a0125c832e27c62b6c9741bdbfa17
PR439_MERGE=02efd64312c4b01c19c0a18e6db543145a16ad9c

PR439_FINAL_SOURCE_REVIEW=PASS
PR439_NEW_SOURCE_BLOCKER_FOUND=false
PR439_CI=12_OF_12_PASS
PR439_FOCUSED_CI_RUN=35433539838
PR439_FOCUSED_TESTS=12_PASS

A1_SINGLE_USE_WRITE_AUTHORIZATION=CLOSED
A2_PARTITION_TABLE_FRESH_BINDING=CLOSED

BOARD_IDENTITY_GUARD=PASS
SECURITY_STATE_GUARD=PASS
PARTITION_TABLE_PREFLIGHT_BINDING=PASS
PARTITION_TABLE_PREWRITE_REBIND=PASS
PREFLIGHT_FRESHNESS_GUARD=PASS
AUTHORIZATION_CLAIM_BEFORE_MUTATION=PASS
AUTHORIZATION_REPLAY_GUARD=PASS
MINIMAL_WRITE_SCOPE=PASS
```

The executor is bound to PR #437 artifact `10575077512`. It performs a fresh read-only partition-table binding at `0x8000` over `0xC00` bytes and requires SHA-256 `6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca`. The write scope remains otadata at `0x9000` plus application at `0x10000`; bootloader, partition table, product NVS, and full-chip erase remain forbidden.

PR #439 merge does not authorize Board B Flash mutation. A bounded read-only Board B preflight is the next gate; any later Flash write requires a separate explicit one-shot authorization.

## PR #437 Board B deployment and post-write Direct baseline

The exact PR #437 artifact was written to the operator-confirmed Board B target. The automated frozen Board B hardware-identity comparison failed before write; the operator explicitly confirmed the physical target and authorized a one-time override. Raw identity material is not public evidence, the automated identity check must not be rewritten as PASS, and this override does not carry forward to future board mutations.

```text
PR437_BOARD_B_DEPLOYMENT=PASS

AUTOMATED_BOARD_IDENTITY_MATCH=FAIL
OPERATOR_TARGET_CONFIRMATION=PASS
OPERATOR_IDENTITY_OVERRIDE=true
RAW_BOARD_IDENTITY_PUBLIC=false
IDENTITY_OVERRIDE_REUSABLE=false

ARTIFACT_DOWNLOAD=PASS
ARTIFACT_INNER_BINDING=PASS
SECURITY_STATE=PASS
FLASH_SIZE=8MB
PARTITION_TABLE_BINDING=PASS

APPLICATION_WRITE=PASS
OTADATA_WRITE=PASS
APPLICATION_READBACK_HASH_VERIFY=NOT_EXECUTED
OTADATA_READBACK_HASH_VERIFY=NOT_EXECUTED

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false

WRITE_AUTHORIZATION_CLAIMED=true
WRITE_AUTHORIZATION_CONSUMED=true
WRITE_AUTHORIZATION_REPLAY_PERMITTED=false
```

A fresh T1/Manager canonical-cursor observation then proved the written firmware is live on Direct without opening application serial:

```text
PR437_POSTWRITE_DIRECT_BASELINE=PASS
OBSERVATION_SECONDS=90

BOARD_B_CANONICAL_CURSOR_BEFORE=FOUND
BOARD_B_CANONICAL_CURSOR_AFTER=FOUND
BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SOURCE_AFTER=direct

BOARD_B_SEQ_BEFORE=1370
BOARD_B_SEQ_AFTER=1388
BOARD_B_SEQ_DELTA=18

BOARD_B_SAME_BOOT=true
BOARD_B_CANONICAL_ADVANCED=true
BOARD_B_LAST_SOURCE_DIRECT=true

T1_MANAGER_RUNNING=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_STARTED_AT_UNCHANGED=true
MANAGER_RESTART_COUNT_UNCHANGED=true
```

The earlier bounded Manager log query returned zero matching Direct acceptance INFO lines. Canonical durable state advanced cleanly during the same period, so this is classified under the existing KF-010 logging-oracle guard:

```text
MANAGER_INFO_LOG_ORACLE=FALSE_NEGATIVE
PRODUCT_DIRECT_PATH_FAILURE=false
CANONICAL_DURABLE_EVIDENCE=PASS
```

PR #437 physical acceptance remains incomplete. The next physical stage is a same-boot Direct -> Relay transition on the deployed PR #437 firmware; Relay steady-state continuity and Relay -> Direct failback remain later gates.

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
PR431_EXACT_ARTIFACT_BUILD=PASS
PR431_EXACT_ARTIFACT_BINDING=PASS
PR431_ARTIFACT_RUN_ID=35339630187
PR431_ARTIFACT_ID=10544254111
PR431_APPLICATION_SHA256=c6cdab938a58ac1bc29f3a04a69d157acc23625ab239f8a644841de241af3730
PR431_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PR431_ARCHIVE_SHA256=94ff922ce50314ed6f3275376eb5b1e71ae27f27f6edd16f9dd0743259dd13b6
PR431_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR431_PHYSICAL_VALIDATION=NOT_EXECUTED
PR431_ARTIFACT_DISPOSITION=FROZEN_HISTORICAL_NOT_FOR_CURRENT_PR437_VALIDATION

PR437_SOURCE_REPAIR=OPEN_DRAFT
PR437_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
PR437_FINAL_SOURCE_REVIEW=PASS
PR437_HEAD_CI=11_OF_11_PASS
PR437_EXACT_ARTIFACT_BUILD=PASS
PR437_EXACT_ARTIFACT_BINDING=PASS
PR437_ARTIFACT_RUN_ID=35414060819
PR437_ARTIFACT_ID=10575077512
PR437_APPLICATION_SHA256=407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb
PR437_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PR437_ARCHIVE_SHA256=b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814
PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS
PR437_PHYSICAL_VALIDATION=IN_PROGRESS

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
- PR #428 and PR #431 artifacts are historical evidence for the current route. The exact PR #437 artifact `10575077512` is now deployed on the operator-confirmed Board B target and has a PASS post-write Direct baseline; full physical acceptance still requires Direct -> Relay, Relay steady-state continuity, and Relay -> Direct failback evidence.
- Consumed physical authorizations are never replayable.
- The one-time operator override of the automated Board B identity mismatch is frozen as historical execution evidence only. It does not change the repository identity guard and must not be inherited by any future board mutation.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_KF096_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260919_01

MERGED_PRODUCT_SOURCE_AUTHORITY=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
CURRENT_CANDIDATE_SOURCE_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
CURRENT_CANDIDATE_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0
DEPLOYED_BOARD_B_SOURCE_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
DEPLOYED_BOARD_B_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0

ARTIFACT_ID=10575077512
ARTIFACT_RUN_ID=35414060819
APPLICATION_SHA256=407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
ARCHIVE_SHA256=b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814

PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS

BOARD_B_FIRMWARE_FLASH=false
BOARD_A_MUTATION=false
APPLICATION_SERIAL_OPEN=false
T1_RUNTIME_MUTATION=false
PR437_MERGE=false
```

The next gate establishes a fresh Direct baseline on the deployed PR #437 firmware, confirms Board A as the stationary Relay gateway, then moves only Board B to the qualified Relay location without a reboot after the baseline. Manager canonical state is the authoritative observation path; zero matching INFO log lines alone must not be classified as product failure.

The gate stops after same-boot Direct -> Relay classification. It must not automatically continue into Relay steady-state continuity, Relay -> Direct failback, source repair, reflashing, or PR #437 merge.

## Public/private evidence boundary

Public GitHub may store source, tests, artifact hashes, sanitized timing/acceptance results, and architecture decisions. Do not commit raw credentials, setup secrets, private keys, raw NVS, private host addresses, raw Manager/Broker logs, or raw board identity material.
