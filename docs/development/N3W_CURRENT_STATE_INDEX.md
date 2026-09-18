# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current progress alignment: `docs/development/N3W_KF096_PR428_EXACT_ARTIFACT_BUILD_AND_BINDING_20260918.md`  
Previous physical alignment: `docs/development/N3W_PR425_PHYSICAL_VALIDATION_AND_PROBE_BLACKOUT_ALIGNMENT_20260918.md`  
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

ALIGNMENT_BASE_MAIN=e2390faf2452730264c19687bf4022df974f04bd
REPOSITORY_MAIN_AT_ARTIFACT_GATE=e2390faf2452730264c19687bf4022df974f04bd
REPOSITORY_MAIN_TREE_AT_ARTIFACT_GATE=94566c80256db64e8cf4b0cbece9bfd0f1acc417

PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c

FROZEN_DEPLOYED_PRODUCT_SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
FROZEN_DEPLOYED_PRODUCT_SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
```

Repository `main` includes PR #428 plus later documentation-only alignment. The PR #428 exact artifact is now built and bound, but Board B still runs PR #425; merged source, frozen candidate artifact, and deployed physical source remain separate authorities until an explicitly authorized deployment proves otherwise.

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
PR428_EXACT_ARTIFACT_BUILD=PASS
PR428_EXACT_ARTIFACT_BINDING=PASS
PR428_ARTIFACT_RUN_ID=35309484471
PR428_ARTIFACT_ID=10533235759
PR428_APPLICATION_SHA256=b3e2311818d539c2abf98e4fa9ff431069b414da6f9993f350e4a7c427929f3a
PR428_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
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

KF-096 remains OPEN. Its source repair is merged and the exact PR #428 artifact is now built/bound, but Board B still runs PR #425 and no PR #428 physical validation has occurred. Relay -> Direct and the post-fix low-level current/peer-channel oracle remain pending.

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_KF096_PR428_BOARD_B_WRITE_TARGET_PREFLIGHT_20260918_01
BOARD_ACCESS_REQUIRED=true
PREFLIGHT_READ_ONLY=true
FLASH_WRITE=false
SERIAL_OPEN=false
T1_MUTATION=false
ARTIFACT_MUTATION=false

FROZEN_APPLICATION_SHA256=b3e2311818d539c2abf98e4fa9ff431069b414da6f9993f350e4a7c427929f3a
FROZEN_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Do not move or access Board B, open serial, or flash PR #428 without a new explicit physical authorization. The next gate is read-only target preflight only; application/otadata write remains a later separately authorized mutation.
