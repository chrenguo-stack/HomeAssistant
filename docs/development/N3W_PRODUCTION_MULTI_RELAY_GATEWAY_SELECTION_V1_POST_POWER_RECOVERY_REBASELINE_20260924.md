# N3-W Production Multi-Relay Gateway Selection V1 — Post-Power-Recovery Rebaseline

Date: 2026-09-24

## Event

Board B experienced a second power-off event after the earlier operator-caused reboot. Low battery was suspected by the operator. Battery replenishment was completed and Boards A/B/C were then powered on.

```text
BOARD_B_POWER_EVENT=OBSERVED
LOW_BATTERY_CAUSE=SUSPECTED_NOT_PROVEN
BATTERY_REPLENISHMENT_COMPLETED=true
BOARD_A_POWERED_ON=true
BOARD_B_POWERED_ON=true
BOARD_C_POWERED_ON=true

PRODUCT_RADIO_FAILURE_PROVEN=false
```

## Evidence disposition

```text
R1_ACCEPTANCE=PASS_RETAINED
R2_ACCEPTANCE=PASS_RETAINED
R3_ACCEPTANCE=PASS_RETAINED

PREVIOUS_R4_R7_CURRENT_BOOT_AUTHORITY=INVALIDATED_BY_POWER_CYCLE
R4_R7_CURRENT_BOOT_BASELINE_REQUIRED=true
```

No later R4-R7 same-boot claim may reuse any pre-power-event boot hash.

## Next gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R4_R7_POST_POWER_RECOVERY_CURRENT_BOOT_BASELINE_20260924_01
NEXT_GATE_AUTHORIZED=true

OBSERVATION_SECONDS=180
MIN_CANONICAL_SEQ_ADVANCEMENT_PER_BOARD=2
PHYSICAL_MOVEMENT=false
T1_MUTATION=false
DATABASE_MUTATION=false
SERVICE_RESTART=false
```
