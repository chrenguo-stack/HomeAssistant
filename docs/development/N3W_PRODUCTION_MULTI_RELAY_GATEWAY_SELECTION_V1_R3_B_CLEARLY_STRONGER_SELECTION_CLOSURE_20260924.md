# N3-W Production Multi-Relay Gateway Selection V1 — R3 B Clearly Stronger Selection Closure

Date: 2026-09-24

## Result

```text
R3_ACCEPTANCE=PASS

CHILD=BOARD_A
CANDIDATE_SET=BOARD_B,BOARD_C
CLEAR_RSSI_WINNER=BOARD_B
EXPECTED_ACTIVE_GATEWAY=BOARD_B
OBSERVED_ACTIVE_GATEWAY=BOARD_B

B_AND_C_VIABLE_CONFIRMED_BY_OPERATOR=true
B_CLEARLY_STRONGER_THAN_C_CONFIRMED_BY_OPERATOR=true
BOARD_C_STATIONARY=true

BOARD_A_PREMOVE_SOURCE=direct
BOARD_A_PREMOVE_SEQ=89
BOARD_A_FIRST_RELAY_SEQ=92
BOARD_A_FINAL_RELAY_SEQ=94

DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
MOVE_TO_FIRST_RELAY_MS=41117
POST_RELAY_ADVANCE_COUNT=2

BOARD_A_R0_BOOT_PRESERVED=true
BOARD_B_R0_BOOT_PRESERVED=true
BOARD_C_R0_BOOT_PRESERVED=true

BOARD_B_FINAL_SOURCE=direct
BOARD_C_FINAL_SOURCE=direct

MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_RESTART_COUNT_UNCHANGED=true

T1_MUTATION=false
DATABASE_MUTATION=false
SERVICE_RESTART=false
FLASH_MUTATION=false
NVS_MUTATION=false

RESULT=PASS_R3_B_CLEARLY_STRONGER_SELECTION
```

The two missing sequence numbers at the Direct -> Relay boundary remain inside the frozen Option-B delivery boundary and do not fail R3.

## Physical state at closure

```text
BOARD_A_SOURCE=relay
BOARD_A_ACTIVE_GATEWAY=BOARD_B
BOARD_B_SOURCE=direct
BOARD_C_SOURCE=direct
BOARD_C_MOVEMENT=false
BOARD_C_POWER_CHANGE=false
```

## R4 bridge requirement

R4 must be a fresh selection round with both B and C viable and C clearly stronger. It must not be created by making C stronger while A is already active on B, because that would exercise R5 sticky/no-proactive-roaming semantics.

Therefore the next gate restores A to Direct on the same boot before R4 RF setup.

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R3_TO_R4_A_SAME_BOOT_DIRECT_RESTORE_20260924_01
NEXT_GATE_AUTHORIZED=true
```
