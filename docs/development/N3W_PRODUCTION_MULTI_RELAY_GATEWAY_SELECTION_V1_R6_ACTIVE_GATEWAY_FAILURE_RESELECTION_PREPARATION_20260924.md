# N3-W Production Multi-Relay Gateway Selection V1 — R6 Active-Gateway Failure Reselection Preparation

Date: 2026-09-24

## Authority

Frozen physical plan:
`docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_ACCEPTANCE_R0_R7_FROZEN_PLAN_20260923.md`

Frozen roles/constraints:

```text
BOARD_A_ROLE=CHILD_UNDER_TEST
BOARD_B_ROLE=RELAY_GATEWAY_CANDIDATE
BOARD_C_ROLE=RELAY_GATEWAY_CANDIDATE

BOARD_A_MOVABLE=true
BOARD_B_MOVABLE=true
BOARD_C_MOVABLE=false
BOARD_C_POWER=FIXED_STABLE
```

## R5 closure state

```text
R5_ACCEPTANCE=PASS
BOARD_A_SOURCE=relay
BOARD_A_ACTIVE_GATEWAY=BOARD_C
BOARD_B_SOURCE=direct
BOARD_C_SOURCE=direct
BOARD_B_STRONGLY_BETTER_THAN_C_FOR_A=true
```

## R6 physical method

Do not power off, reset, move, or mutate Board C.

Use Board A movement to create an ordinary RF-path failure of the currently active C->A Relay link while preserving Board B as the viable surviving Relay candidate.

```text
MOVE_BOARD_A=true
MOVE_BOARD_B=false
MOVE_BOARD_C=false
BOARD_C_POWER_CHANGE=false

BOARD_A_DIRECT_MUST_REMAIN_UNAVAILABLE=true
BOARD_C_TO_A_RELAY_PATH_MUST_BECOME_UNAVAILABLE=true
BOARD_B_TO_A_RELAY_PATH_MUST_REMAIN_VIABLE=true

EXPECTED_INITIAL_ACTIVE_GATEWAY=BOARD_C
EXPECTED_RESELECTION_GATEWAY=BOARD_B
EXPECTED_FINAL_SOURCE=relay
```

This exercises the product's ordinary Relay delivery-failure path. It does not simulate success by mutating Manager state and does not use a Gateway reboot/power-off as the acceptance mechanism.

## Acceptance

```text
ACTIVE_GATEWAY_C_PATH_FAILURE_CONFIRMED_BY_OPERATOR=true
SURVIVING_GATEWAY_B_AVAILABLE=true
DIRECT_NOT_RECOVERED_DURING_R6=true

BOARD_A_FINAL_SOURCE=relay
BOARD_A_FINAL_GATEWAY=BOARD_B
POST_RESELECTION_ADVANCEMENT_REQUIRED=2

BOARD_A_BOOT_PRESERVED=true
BOARD_B_BOOT_PRESERVED=true
BOARD_C_BOOT_PRESERVED=true
MANAGER_RESTART_COUNT_UNCHANGED=true
```

The Manager canonical cursor cannot expose the RAM-only intermediate DISCOVERY state directly. The frozen source state machine requires active-Relay failure to leave RELAY_ACTIVE through Discovery before a new selection epoch can activate another Relay. Physical evidence therefore proves C->B reselection plus same-boot continuity; the intermediate Discovery transition is source-authority corroboration, not a separately observable canonical cursor value.

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R6_ACTIVE_GATEWAY_FAILURE_RESELECTION_EXECUTION_20260924_01
NEXT_GATE_AUTHORIZED=true
```
