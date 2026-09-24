# N3-W Production Multi-Relay Gateway Selection V1 — R2 A-Child / C-Only-Gateway Preflight Closure

Date: 2026-09-24

```text
R2_PREFLIGHT=PASS

MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
MANAGER_SOURCE_REVISION=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a

BOARD_A_ROLE=CHILD_UNDER_TEST
BOARD_A_SOURCE=direct
BOARD_A_SEQ=62
BOARD_A_R0_BOOT_MATCH=true
BOARD_A_GATEWAY_NONE=true
BOARD_A_CURSOR_FRESH=true

BOARD_B_ROLE=NONVIABLE_GATEWAY_FOR_R2
BOARD_B_SOURCE=direct
BOARD_B_SEQ=62
BOARD_B_R0_BOOT_MATCH=true
BOARD_B_GATEWAY_NONE=true
BOARD_B_CURSOR_FRESH=true

BOARD_C_ROLE=ONLY_VIABLE_GATEWAY_FOR_R2
BOARD_C_SOURCE=direct
BOARD_C_SEQ=62
BOARD_C_R0_BOOT_MATCH=true
BOARD_C_GATEWAY_NONE=true
BOARD_C_CURSOR_FRESH=true
BOARD_C_MOVEMENT=false

PHYSICAL_MOVEMENT=false
T1_MUTATION=false
DATABASE_MUTATION=false
SERVICE_RESTART=false

RESULT=PASS_R2_A_CHILD_C_ONLY_GATEWAY_PREFLIGHT
```

Next gate:

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R2_A_CHILD_C_ONLY_GATEWAY_DIRECT_TO_RELAY_EXECUTION_20260924_01
NEXT_GATE_AUTHORIZED=true
```

R2 execution must preserve the R0 boot sessions. Board C stays stationary on fixed stable power. Board B may be repositioned without reboot so that it remains Direct but is not viable as a Relay Gateway for Board A at the R2 Relay test location. Board A is then moved from Direct coverage to the Relay test location and must first become Relay through Board C.
