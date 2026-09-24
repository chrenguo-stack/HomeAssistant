# N3-W Production Multi-Relay Gateway Selection V1 — R7 Same-Boot Relay-to-Direct Recovery Closure

Date: 2026-09-24

## Result

```text
R7_ACCEPTANCE=PASS

BOARD_A_SOURCE_INITIAL=relay
BOARD_A_SEQ_INITIAL=69
BOARD_A_ACTIVE_GATEWAY_BEFORE=BOARD_B

BOARD_B_SOURCE_INITIAL=direct
BOARD_B_SEQ_INITIAL=70

BOARD_C_SOURCE_INITIAL=direct
BOARD_C_SEQ_INITIAL=207

MOVE_BOARD_A_TO_DIRECT_COVERAGE=true
MOVE_BOARD_B=false
MOVE_BOARD_C=false
BOARD_C_POWER_CHANGE=false

FIRST_DIRECT_OBSERVED=true
LAST_RELAY_SEQ=69
FIRST_DIRECT_SEQ=74
RELAY_TO_DIRECT_MISSING_SEQ_COUNT=4
MOVE_TO_FIRST_DIRECT_MS=35761

BOARD_A_GATEWAY_AFTER_DIRECT=NONE

BOARD_A_FINAL_SOURCE=direct
BOARD_A_FINAL_SEQ=76
BOARD_A_FINAL_GATEWAY=NONE
POST_DIRECT_ADVANCE_COUNT=2

BOARD_B_FINAL_SOURCE=direct
BOARD_C_FINAL_SOURCE=direct

BOARD_A_SAME_BOOT_RELAY_TO_DIRECT=true
BOARD_A_BOOT_PRESERVED=true
BOARD_B_BOOT_PRESERVED=true
BOARD_C_BOOT_PRESERVED=true

BOARD_B_MOVEMENT=false
BOARD_C_MOVEMENT=false
BOARD_C_POWER_CHANGE=false

MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_RESTART_COUNT_UNCHANGED=true

T1_MUTATION=false
DATABASE_MUTATION=false
SERVICE_RESTART=false
FLASH_MUTATION=false
NVS_MUTATION=false

RESULT=PASS_R7_SAME_BOOT_RELAY_TO_DIRECT_RECOVERY
```

## Boundary-loss disposition

The Relay-to-Direct transition observed four missing sequence numbers between the last Manager-visible Relay sequence and the first Manager-visible Direct sequence.

```text
LAST_RELAY_SEQ=69
FIRST_DIRECT_SEQ=74
MISSING_SEQ=70,71,72,73
MISSING_SEQ_COUNT=4
```

R7 acceptance requires same-boot recovery to Direct plus post-Direct advancement. It does not establish a zero-loss handover guarantee. This closure therefore records the boundary gap explicitly and does not relabel the transition as lossless.

## Final state

```text
BOARD_A_SOURCE=direct
BOARD_A_GATEWAY=NONE
BOARD_B_SOURCE=direct
BOARD_C_SOURCE=direct
MANAGER_RESTART_COUNT=0
```
