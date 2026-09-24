# N3-W Production Multi-Relay Gateway Selection V1 — R2 A-Child / C-Only-Gateway Closure

Date: 2026-09-24

## Result

```text
R2_ACCEPTANCE=PASS
CHILD=BOARD_A
ONLY_VIABLE_GATEWAY=BOARD_C
BOARD_C_STATIONARY=true

BOARD_A_PREMOVE_SOURCE=direct
BOARD_A_PREMOVE_SEQ=67
BOARD_A_FIRST_RELAY_SEQ=70
BOARD_A_FINAL_RELAY_SEQ=72
FIRST_RELAY_GATEWAY=BOARD_C

DIRECT_TO_RELAY_MISSING_SEQ_COUNT=2
MOVE_TO_FIRST_RELAY_MS=51431
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

RESULT=PASS_R2_A_CHILD_C_ONLY_GATEWAY_DIRECT_TO_RELAY
```

The two missing sequence numbers at the Direct -> Relay boundary remain inside the frozen Option-B boundary and do not fail R2.

## Physical state at closure

```text
BOARD_A_SOURCE=relay
BOARD_A_ACTIVE_GATEWAY=BOARD_C
BOARD_B_SOURCE=direct
BOARD_C_SOURCE=direct
BOARD_C_MOVEMENT=false
BOARD_C_POWER_CHANGE=false
```

## R3 bridge requirement

R3 is a fresh multi-candidate selection round with both B and C viable and B clearly stronger. It must start from Board A Direct, not by changing RF conditions while A is already active on C, because that would exercise the later stickiness/no-proactive-roaming semantics reserved for R5.

Therefore the next gate restores A to Direct on the same boot before R3 setup.

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R2_TO_R3_A_SAME_BOOT_DIRECT_RESTORE_20260924_01
NEXT_GATE_AUTHORIZED=true
```
