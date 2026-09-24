# N3-W Production Multi-Relay Gateway Selection V1 — R0-R7 Final Physical Acceptance Closure

Date: 2026-09-24

## Final conclusion

```text
PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_ACCEPTANCE=PASS
R0_R7_FROZEN_SEQUENCE=COMPLETED
```

The frozen R0-R7 physical acceptance sequence is complete.

## Acceptance matrix

```text
R0=PASS
R1=PASS
R2=PASS
R3=PASS
R4=PASS
R5=PASS
R6=PASS
R7=PASS
```

### R0 — three-board Direct baseline

```text
OBSERVATION_SECONDS=180
BOARD_A_SEQ_ADVANCEMENT=3
BOARD_B_SEQ_ADVANCEMENT=3
BOARD_C_SEQ_ADVANCEMENT=3
ALL_THREE_SOURCE=direct
MANAGER_RESTART_COUNT_UNCHANGED=true
RESULT=PASS
```

### R1 — A loses Direct; B-only Relay

```text
EXPECTED_GATEWAY=BOARD_B
OBSERVED_GATEWAY=BOARD_B
DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
RESULT=PASS
```

### R2 — A loses Direct; C-only Relay

```text
EXPECTED_GATEWAY=BOARD_C
OBSERVED_GATEWAY=BOARD_C
DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
RESULT=PASS
```

### R3 — B clearly stronger

```text
CANDIDATES=BOARD_B,BOARD_C
CLEAR_WINNER=BOARD_B
OBSERVED_GATEWAY=BOARD_B
DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
RESULT=PASS
```

### R4 — C clearly stronger

Attempt 1 was inconclusive because the physical RSSI premise was not instrumented and the stable hash tie-break for this A/B/C identity set favors Board B inside the <=3 dB equivalent band.

Attempt 2 increased the physical RF separation substantially and passed:

```text
CANDIDATES=BOARD_B,BOARD_C
CLEAR_WINNER=BOARD_C
OBSERVED_GATEWAY=BOARD_C
DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
MOVE_TO_FIRST_RELAY_MS=129119
POST_RELAY_ADVANCE_COUNT=2
RESULT=PASS
```

### R5 — healthy active Gateway remains sticky

```text
ACTIVE_GATEWAY=BOARD_C
OTHER_GATEWAY=BOARD_B
BOARD_B_MADE_CLEARLY_STRONGER=true
OBSERVATION_SECONDS=120
BOARD_A_SEQ_ADVANCEMENT=5
PROACTIVE_ROAM_TO_BOARD_B=false
RESULT=PASS
```

### R6 — active Gateway failure causes reselection

```text
ACTIVE_GATEWAY_BEFORE=BOARD_C
SURVIVING_GATEWAY=BOARD_B
ACTIVE_GATEWAY_AFTER=BOARD_B
LAST_BOARD_C_RELAY_SEQ=65
FIRST_BOARD_B_RELAY_SEQ=66
C_TO_B_RESELECTION_MISSING_SEQ_COUNT=0
MOVE_TO_FIRST_BOARD_B_RELAY_MS=250287
POST_RESELECTION_ADVANCE_COUNT=3
DIRECT_RECOVERY_OBSERVED=false
RESULT=PASS
```

The transient in-device Discovery state is required by the frozen source state machine but is not represented by the Manager canonical cursor. The physical evidence therefore proves externally observable C->B reselection; the intermediate Discovery transition is source-authority corroboration.

### R7 — same-boot Relay -> Direct recovery

```text
ACTIVE_GATEWAY_BEFORE=BOARD_B
LAST_RELAY_SEQ=69
FIRST_DIRECT_SEQ=74
RELAY_TO_DIRECT_MISSING_SEQ_COUNT=4
MOVE_TO_FIRST_DIRECT_MS=35761
POST_DIRECT_ADVANCE_COUNT=2
FINAL_SOURCE=direct
FINAL_GATEWAY=NONE
RESULT=PASS
```

R7 proves same-boot recovery to Direct but does not prove zero-loss handover.

## Boot-authority boundary

The full acceptance program contains an operator-caused Board B reboot and a later power event before R4. Those events occurred after the earlier R1-R3 results had already closed.

The affected same-boot authority was explicitly invalidated and a new three-board current-boot baseline was established before R4.

Therefore:

```text
R1_R3_RESULTS=VALID_RETAINED
R4_R7_RESULTS=VALID_ON_POST_POWER_RECOVERY_CURRENT_BOOT_BASELINE

GLOBAL_R0_TO_R7_SINGLE_UNINTERRUPTED_BOOT_CLAIM=false
R0_R7_ACCEPTANCE_SEQUENCE_COMPLETED=true
```

The acceptance conclusion is not a claim that all seven rounds occurred under one uninterrupted boot epoch.

## R4-R7 frozen current-boot authority

```text
BOARD_A_BOOT_SHA256=
7f9468e1ead5b54d2db26493ca59982e97482cba23f7ba803ed2f3d48e6103d9

BOARD_B_BOOT_SHA256=
61ba94d58fd2cfc22c65a5dc6a0ca7325eade37de7aacfee064acacec6c4bb58

BOARD_C_BOOT_SHA256=
000f6f4ade1994bef54e26f1e2086872e8e49e1fc61d6a67cdf9b53f8cf9fb34
```

R4, R5, R6 and R7 all preserved this authority.

## Product-policy conclusions physically supported

```text
SINGLE_GATEWAY_B_PATH=PASS
SINGLE_GATEWAY_C_PATH=PASS

MULTI_GATEWAY_CLEAR_WINNER_B=PASS
MULTI_GATEWAY_CLEAR_WINNER_C=PASS

HEALTHY_ACTIVE_GATEWAY_STICKY=PASS
PROACTIVE_ROAMING_OBSERVED=false

ACTIVE_GATEWAY_FAILURE_RESELECTION=PASS
C_TO_B_RESELECTION_ZERO_MANAGER_VISIBLE_SEQ_GAP=true

SAME_BOOT_RELAY_TO_DIRECT_RECOVERY=PASS
```

The exact <=3 dB equivalent-band semantics, arithmetic-mean RSSI aggregation, stable hash tie-break, and 6500 ms candidate-window implementation remain source/host-test authorities rather than exact physical threshold measurements.

## Boundary-loss observations

Physical acceptance observed transition-boundary losses in some Direct/Relay changes.

```text
R1_DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
R2_DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
R3_DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
R4_DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
R6_C_TO_B_RESELECTION_MISSING_SEQ_COUNT=0
R7_RELAY_TO_DIRECT_MISSING_SEQ_COUNT=4
```

Therefore:

```text
ZERO_LOSS_ALL_TRANSITIONS_PROVEN=false
OPTION_B_BOUNDED_TRANSITION_BEHAVIOR_REMAINS_APPLICABLE=true
```

## Final runtime state

```text
BOARD_A_SOURCE=direct
BOARD_A_GATEWAY=NONE
BOARD_B_SOURCE=direct
BOARD_C_SOURCE=direct
MANAGER_RESTART_COUNT=0
```

## Frozen production source/artifact authority

```text
SOURCE_COMMIT=8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c
ARTIFACT_ID=10693728323
ARTIFACT_NAME=n3w-production-gwsel-v1-r2-8c445f2-exact-source
```

## Closure

```text
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1=PHYSICAL_ACCEPTANCE_PASS
R0_R7_FINAL_ACCEPTANCE_CLOSED=true
PRODUCT_SOURCE_REPAIR_REQUIRED_BY_THIS_ACCEPTANCE=false
```
