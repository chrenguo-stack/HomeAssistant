# N3-W Production Multi-Relay Gateway Selection V1 — R1 A-Child / B-Only-Gateway Closure

Date: 2026-09-24

## Result

```text
R1_ACCEPTANCE=PASS
CHILD=BOARD_A
ONLY_VIABLE_GATEWAY=BOARD_B
BOARD_C_STATIONARY=true

BOARD_A_PREMOVE_SOURCE=direct
BOARD_A_PREMOVE_SEQ=46
BOARD_A_FIRST_RELAY_SEQ=49
BOARD_A_FINAL_RELAY_SEQ=51
FIRST_RELAY_GATEWAY=BOARD_B

DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
MOVE_TO_FIRST_RELAY_MS=103470
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

RESULT=PASS_R1_A_CHILD_B_ONLY_GATEWAY_DIRECT_TO_RELAY
```

The two missing sequence numbers at the Direct -> Relay boundary remain inside the frozen Option-B delivery boundary and do not reclassify R1 as a failure.

## Physical state at closure

```text
BOARD_A_SOURCE=relay
BOARD_A_ACTIVE_GATEWAY=BOARD_B
BOARD_B_SOURCE=direct
BOARD_C_SOURCE=direct
BOARD_C_MOVEMENT=false
BOARD_C_POWER_CHANGE=false
```

## R2 bridge requirement

R2 is a separate single-candidate acceptance round:

```text
R2_CHILD=BOARD_A
R2_ONLY_VIABLE_GATEWAY=BOARD_C
```

R2 must not be satisfied by simply failing Board B while A is already active on B; that would exercise the later failure-driven reselection semantics reserved for R6.

Therefore the next gate is a non-acceptance bridge that restores A to Direct on the same boot before the R2 C-only setup.

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R1_TO_R2_A_SAME_BOOT_DIRECT_RESTORE_20260924_01
NEXT_GATE_AUTHORIZED=true
```
