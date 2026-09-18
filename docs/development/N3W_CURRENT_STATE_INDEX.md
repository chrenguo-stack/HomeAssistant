# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current progress alignment: `docs/development/N3W_PR425_PHYSICAL_VALIDATION_AND_PROBE_BLACKOUT_ALIGNMENT_20260918.md`  
Previous progress alignment: `docs/development/N3W_PROGRESS_ALIGNMENT_20260918.md`  
Historical PR #416 handoff: `docs/development/N3W_PR416_CONTROLLED_CHANNEL_TX_POSTFLASH_DIRECT_BASELINE_NEW_CHAT_HANDOFF_V1.0_20260917.md`  
Current local-development-environment authority: `docs/development/local-environment-records/2026-09-17-macos-x86_64.json`  
Current KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Repository / deployed product authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

ALIGNMENT_BASE_MAIN=f6b9f3d60078998cd543d4e0482f5ae30f6d0dc7
FROZEN_PRODUCT_SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
FROZEN_PRODUCT_SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
```

Documentation-only merges may advance repository `main` without changing the product source actually deployed to Board B.

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

KF-096 is the current active source-repair target: Relay mode periodically pauses business telemetry while the single radio is reassigned to bounded Direct recovery probing.

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

Do not execute Relay -> Direct physical recovery, move Board B again, or perform further Board/T1 mutation until the KF-096 source design is reviewed and the next physical gate is explicitly authorized.
