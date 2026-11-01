# N3-W KF-096 PR #437 Final Physical Closure Alignment — 2026-09-19

Status: `CURRENT_PROGRESS_ALIGNMENT`

This document records the final physical evidence for PR #437 exact HEAD and closes KF-096 only. It does not merge PR #437 and does not close overall N3-W failover acceptance.

## Exact authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR437_STATE=OPEN_DRAFT
PR437_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
PR437_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0

PR437_ARTIFACT_RUN_ID=35414060819
PR437_ARTIFACT_ID=10575077512
PR437_ARTIFACT_NAME=n3w-pr437-boardb-exact-source
PR437_ARTIFACT_ZIP_SHA256=b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814
PR437_APPLICATION_SHA256=407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb
PR437_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PR437_MANIFEST_SHA256=98a6dec323e8057a30d6b1e332d549fe54288f3b45fcbbbf460292871f7a91a0

PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS
```

The historical automated Board B identity comparison before write remained FAIL. The operator-confirmed one-time override is historical execution evidence only and is not reusable authority for future board mutation.

## Same-boot Direct -> Relay

Board A remained stationary as the Relay gateway. Board B moved from the fresh battery Direct baseline to the qualified Relay location without reboot.

```text
PR437_SAME_BOOT_DIRECT_TO_RELAY=PASS

LAST_DIRECT_SEQ=896
LAST_DIRECT_TIME=2026-09-19T13:58:00.762Z

FIRST_RELAY_SEQ=903
FIRST_RELAY_TIME=2026-09-19T13:58:35.849Z

MANAGER_VISIBLE_GAP_MS=35087
MISSING_SEQUENCE_RANGE=897-902
MISSING_SEQUENCE_COUNT=6

POST_RELAY_SEQ_ADVANCEMENT=PASS
FINAL_SOURCE=relay
SAME_BOOT_DIRECT_TO_RELAY=true
MANAGER_RESTART_COUNT_UNCHANGED=true
```

The functional path transition passed, but it was not lossless. The six missing sequences are retained as an unresolved Direct -> Relay transition-loss fact and are not erased by later Relay continuity.

## Relay steady-state continuity

Board B remained at the Relay location for a 600 s read-only Manager durable-state observation.

```text
OBSERVATION_SECONDS=600

START_SOURCE=relay
START_SEQ=996
END_SOURCE=relay
END_SEQ=1116

ACCEPTED_ROW_COUNT=121
MISSING_SEQUENCE_COUNT=0
MISSING_SEQUENCE_RANGE=NONE

SOURCE_NON_RELAY_OBSERVED=false
BOARD_B_SAME_BOOT=true
MANAGER_RESTART_COUNT_UNCHANGED=true

MAX_MANAGER_INTERARRIVAL_GAP_MS=20589
MAX_GAP_SEQ_PAIR=1089->1090
```

The 20.589 s Manager interarrival gap was followed by:

```text
1089->1090 20589 ms
1090->1091   202 ms
1091->1092    50 ms
1092->1093    51 ms
1093->1094  4112 ms
1094->1095  5044 ms
```

All seq 996..1116 were durably present. This proves no sequence loss in the 600 s Relay window and provides strong evidence of ordered catch-up after a temporary delivery pause.

A follow-up read-only attempt to retrieve payload-level `uptime_ms` found no persisted payload-history database for the target range:

```text
UPTIME_EVIDENCE_AVAILABLE=false
CLASSIFICATION=PERSISTED_PAYLOAD_NOT_AVAILABLE_FOR_TARGET_RANGE
```

Therefore the exact location of the backlog is not proven. Preserve:

```text
ORDERED_CATCHUP_OBSERVED=true
BOARD_B_PROBE_FIFO_CAUSE=STRONGLY_SUPPORTED_NOT_YET_CONFIRMED
```

Do not treat the 20.589 s interarrival gap as zero latency. It is retained as a realtime-delivery observation, while data continuity is classified independently.

## Same-boot Relay -> Direct failback

Board B was moved back into the previously qualified Direct Wi-Fi coverage area without reboot. Board A remained unchanged.

```text
PR437_RELAY_TO_DIRECT_FAILBACK=PASS

LAST_RELAY_SEQ=1489
LAST_RELAY_TIME=2026-09-19T14:47:29.931Z

FIRST_DIRECT_SEQ=1491
FIRST_DIRECT_TIME=2026-09-19T14:47:40.620Z

POST_DIRECT_LAST_SEQ=1493
POST_DIRECT_ADVANCE_COUNT=2
FINAL_SOURCE=direct

SAME_BOOT_RELAY_TO_DIRECT=true
RELAY_AFTER_FIRST_DIRECT_OBSERVED=false

MANAGER_VISIBLE_FAILBACK_GAP_MS=10689

MISSING_SEQUENCE_COUNT=0
MISSING_SEQUENCE_RANGE=NONE
TRANSITION_DATA_CONTINUITY=PASS

FAILBACK_FUNCTIONAL_RESULT=PASS
MANAGER_RESTART_COUNT_UNCHANGED=true
```

The observation loop did not necessarily sample seq 1490 as the latest cursor state, but the durable replay registry showed no missing sequence across the transition.

## KF-096 closure

KF-096 was created for the PR #425 behavior where healthy Relay periodically entered Direct recovery probing and business telemetry was discarded during the probe window. The resulting pattern repeatedly lost about three samples per probe cycle.

The exact PR #437 physical route now proves:

```text
PR437_RELAY_DATA_CONTINUITY_600S=PASS
RELAY_MISSING_SEQUENCE_COUNT=0
ORDERED_CATCHUP_OBSERVED=true

OLD_KF096_PERIODIC_DATA_LOSS_REPRODUCED_IN_THIS_WINDOW=false

PR437_RELAY_TO_DIRECT_FAILBACK=PASS
RELAY_TO_DIRECT_DATA_CONTINUITY=PASS

KF096_STATUS=CLOSED_PASS
```

The closure is specific to the periodic Relay Direct-recovery-probe data-loss defect. It does not claim zero realtime delivery pause, does not prove the exact FIFO location for every catch-up record, and does not prove the historical `ESP_ERR_ESPNOW_CHAN` class impossible.

## Remaining N3-W acceptance fact

```text
DIRECT_TO_RELAY_TRANSITION_DATA_LOSS=STILL_PRESENT
DIRECT_TO_RELAY_MISSING_SEQUENCE_COUNT=6
DIRECT_TO_RELAY_MISSING_SEQUENCE_RANGE=897-902

OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

This transition-loss fact is separate from the closed KF-096 steady-state periodic data-loss defect and requires later disposition.

## Mutation boundary

```text
BOARD_A_MUTATION=false
BOARD_B_FLASH_MUTATION=false
T1_RUNTIME_MUTATION=false
APPLICATION_SERIAL_OPEN=false
PR437_MERGE=false
```

## Next ONE gate

```text
NEXT_ONE_GATE=N3W_KF096_PR437_PREMERGE_FINAL_REVIEW_20260919_01
```

The next gate is repository-only. It must fresh-rebind PR #437 exact head, workflow status, mergeability, and this documentation alignment. It must preserve the unresolved six-sequence Direct -> Relay transition loss and must not merge PR #437 without separate explicit authorization.
