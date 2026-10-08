# N3-W Auto Safe Fallback Gate F R2 Stale Broker Runtime Failure — 2026-10-04

Status: `R2_PHYSICAL_ACCEPTANCE_FAIL_FORENSIC_REQUIRED`

## Frozen source / artifact

```text
SOURCE_REPAIR_R2_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
R2_EXACT_ARTIFACT_ID=11303803442
APPLICATION_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
```

Board B minimal write and post-write reconciliation passed. Application readback matched the frozen artifact, partition table remained unchanged, and runtime otadata was stable after boot. Product NVS was not written or erased.

## Physical acceptance preconditions

The stale Broker oracle remained intact before the controlled reset:

```text
BOARD_B_8883_ESTABLISHED_BEFORE=0
MANAGER_RESTART_COUNT_BEFORE=1
MANAGER_NODE_BROKER_HOST_STILL_STALE=true
CANONICAL_CURSOR_FOUND=true
BOOT_SESSION_BEFORE=dc40c82e1467cf88
SEQ_BEFORE=112
SOURCE_BEFORE=direct
UPDATED_AT_BEFORE=2026-09-24T13:28:35.713Z
BOARD_NVS_MUTATION=false
T1_MUTATION=false
```

Private IP literals are intentionally not archived here.

## Controlled reset / 120 s result

A controlled Board B reset was issued without changing NVS or T1 configuration. T1-side TCP observation then watched for a Board B connection to Broker port 8883 for the entire 120-second acceptance budget.

```text
CONTROLLED_RESET_COMPLETE=true
RESET_COMMAND_SECONDS=0
MQTT_FIRST_ESTABLISHED_SECONDS=-1
MQTT_RECOVERY_WITHIN_120S=FAIL
CURSOR_AFTER_FOUND=true
BOOT_SESSION_AFTER=dc40c82e1467cf88
SEQ_AFTER=112
SOURCE_AFTER=direct
UPDATED_AT_AFTER=2026-09-24T13:28:35.713Z
MANAGER_RESTART_COUNT_AFTER=1
MANAGER_NODE_BROKER_HOST_STILL_STALE=true
BOARD_NVS_MUTATION=false
T1_MUTATION=false
```

Therefore R2 did not recover MQTT or Manager-visible telemetry inside the frozen no-Relay absolute 120-second budget.

## Interpretation

R2 closed the source-level defect where standalone Direct Broker relocation was indirectly gated by 60-second business telemetry cadence. The exact R2 binary compiled successfully and contains the standalone relocation/fail-closed markers, but the physical stale-Broker recovery still failed.

The next forensic split is intentionally narrower:

```text
A = Direct MQTT failure trigger never emits Manager discovery traffic
B = discovery traffic is emitted but candidate response / retarget / MQTT validation fails downstream
```

Do not modify T1 Broker configuration, Board NVS, or pairing state until this split is physically established.

## Gate state

```text
R2_SOURCE_REPAIR=PASS
R2_EXACT_ARTIFACT=PASS
R2_BOARD_WRITE=PASS
R2_STALE_BROKER_PHYSICAL_ACCEPTANCE=FAIL
AUTO_FALLBACK_RECOVERY_OBSERVED=false
FORENSIC_REQUIRED=true
MERGE=false
```
