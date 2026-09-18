# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current progress alignment: `docs/development/N3W_PR425_PHYSICAL_VALIDATION_AND_PROBE_BLACKOUT_ALIGNMENT_20260918.md`  
Current merged source repair: PR #428 / `f357db25390ffd097e9b8608293870772f9cb16c`  
Previous progress alignment: `docs/development/N3W_PROGRESS_ALIGNMENT_20260918.md`  
Historical PR #416 handoff: `docs/development/N3W_PR416_CONTROLLED_CHANNEL_TX_POSTFLASH_DIRECT_BASELINE_NEW_CHAT_HANDOFF_V1.0_20260917.md`  
Current local-development-environment authority: `docs/development/local-environment-records/2026-09-17-macos-x86_64.json`  
Current KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Repository / deployed product authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

ALIGNMENT_BASE_MAIN=f357db25390ffd097e9b8608293870772f9cb16c
CURRENT_REPOSITORY_MAIN=f357db25390ffd097e9b8608293870772f9cb16c
CURRENT_REPOSITORY_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64

PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c

FROZEN_DEPLOYED_PRODUCT_SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
FROZEN_DEPLOYED_PRODUCT_SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
```

Repository `main` now includes PR #428. Board B still runs the PR #425 artifact, so the merged repository source and deployed physical source remain separate authorities until PR #428 receives an exact artifact build/binding and later explicit deployment authorization.

## Current physical route summary

```text
PR425_EXACT_ARTIFACT_BUILD=PASS
PR425_BOARD_B_DEPLOYMENT=PASS
PR425_POSTFLASH_DIRECT_BASELINE=PASS
PR425_BATTERY_DIRECT_BASELINE=PASS

PR425_SAME_BOOT_DIRECT_TO_RELAY_FUNCTIONAL_RESULT=PASS
PR425_INITIAL_MANAGER_VISIBLE_GAP_MS=30034

PR425_RELAY_STEADY_STATE_CONTINUITY=FAIL
KF096_PERIODIC_DIRECT_PROBE_BLACKOUT=PROVEN
PR425_RELAY_TO_DIRECT_FAILBACK_VALIDATION=NOT_EXECUTED

PR428_SOURCE_REPAIR=MERGED
PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c
PR428_PREMERGE_CI=13_OF_13_PASS
PR428_POSTMERGE_CI=PASS
PR428_EXACT_ARTIFACT_BUILD=NOT_EXECUTED
PR428_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR428_PHYSICAL_VALIDATION=NOT_EXECUTED

OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

## Current known-failure disposition

```text
KF092=CLOSED_PASS / GUARDED
KF093=GUARDED
KF094=OPEN
KF095=GUARDED
KF096=OPEN
```

KF-096 remains OPEN, but its source-repair phase is merged in PR #428 and all exact-head plus post-merge CI has passed. Physical closure is intentionally not claimed: Board B still runs PR #425, no PR #428 exact artifact has been bound or deployed, and Relay -> Direct plus low-level channel-oracle validation remain pending.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_KF096_PR428_EXACT_ARTIFACT_BUILD_AND_BINDING_20260918_01
EXACT_SOURCE_REQUIRED=f357db25390ffd097e9b8608293870772f9cb16c
EXACT_SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64
BUILD_ONLY=true
BOARD_ACCESS_REQUIRED=false
BOARD_MUTATION=false
SERIAL_OPEN=false
T1_MUTATION=false
SOURCE_MUTATION=false
```

Do not execute Relay -> Direct physical recovery, move Board B, flash PR #428, or perform Board/T1 mutation in the artifact-build gate. First freeze an exact artifact bound to merge commit `f357db25390ffd097e9b8608293870772f9cb16c`; any physical deployment remains a later explicitly authorized gate.
