# N3-W Production Multi-Relay Gateway Selection V1 — R6 Active-Gateway Failure Reselection Closure

Date: 2026-09-24

## Result

```text
R6_ACCEPTANCE=PASS

BOARD_A_SOURCE_INITIAL=relay
BOARD_A_SEQ_INITIAL=60
ACTIVE_GATEWAY_BEFORE=BOARD_C

BOARD_B_SOURCE_INITIAL=direct
BOARD_B_SEQ_INITIAL=60

BOARD_C_SOURCE_INITIAL=direct
BOARD_C_SEQ_INITIAL=195

R6_POSITION_OPERATOR_CONFIRMED=true
ACTIVE_GATEWAY_C_PATH_FAILURE_CONFIRMED_BY_OPERATOR=true
SURVIVING_GATEWAY_B_AVAILABLE_CONFIRMED_BY_OPERATOR=true
BOARD_A_DIRECT_UNAVAILABLE_CONFIRMED_BY_OPERATOR=true

RESELECTION_OBSERVED=true
ACTIVE_GATEWAY_AFTER=BOARD_B

LAST_BOARD_C_RELAY_SEQ=65
FIRST_BOARD_B_RELAY_SEQ=66
C_TO_B_RESELECTION_MISSING_SEQ_COUNT=0
MOVE_TO_FIRST_BOARD_B_RELAY_MS=250287

DIRECT_RECOVERY_OBSERVED=false
INTERMEDIATE_DISCOVERY_CANONICAL_OBSERVABLE=false
DISCOVERY_TRANSITION_REQUIRED_BY_FROZEN_STATE_MACHINE=true

BOARD_A_FINAL_SOURCE=relay
BOARD_A_FINAL_SEQ=69
BOARD_A_FINAL_GATEWAY=BOARD_B
POST_RESELECTION_ADVANCE_COUNT=3

BOARD_B_FINAL_SOURCE=direct
BOARD_C_FINAL_SOURCE=direct

BOARD_A_BOOT_PRESERVED=true
BOARD_B_BOOT_PRESERVED=true
BOARD_C_BOOT_PRESERVED=true

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

RESULT=PASS_R6_ACTIVE_GATEWAY_FAILURE_RESELECTION
```

## Acceptance meaning

The healthy active Relay binding from R5 was Board C. R6 made the C->A path genuinely unavailable while Board B remained viable and Direct. Board A did not recover Direct. The active Relay changed from C to B in the same boot and then continued advancing.

The Manager canonical cursor does not expose the transient in-device DISCOVERY state. The frozen source state machine requires the Relay-active failure path to leave Relay Active through Discovery before a new Gateway-selection epoch can activate Board B. Physical evidence therefore proves the externally observable C->B reselection while the intermediate Discovery transition remains source-authority corroboration.

## Next gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R7_SAME_BOOT_RELAY_TO_DIRECT_RECOVERY_EXECUTION_20260924_01
NEXT_GATE_AUTHORIZED=true
```
