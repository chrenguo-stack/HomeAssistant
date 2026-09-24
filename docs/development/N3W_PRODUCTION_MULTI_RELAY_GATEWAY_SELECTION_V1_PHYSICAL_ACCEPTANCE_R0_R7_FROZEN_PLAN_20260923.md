# N3-W Production Multi-Relay Gateway Selection V1 — R0–R7 Frozen Physical Acceptance Plan

Frozen by user decision: 2026-09-23  
Repository recovery/alignment: 2026-09-24

## Purpose

This document restores the later frozen physical acceptance plan that supersedes the earlier source-design physical outline where Board C was the Child.

The earlier source-design outline remains valid as historical design context, but it is not the current physical operator plan.

## Frozen physical roles

```text
BOARD_A_ROLE=CHILD_UNDER_TEST
BOARD_B_ROLE=RELAY_GATEWAY_CANDIDATE
BOARD_C_ROLE=RELAY_GATEWAY_CANDIDATE

BOARD_C_POWER=FIXED_STABLE
BOARD_C_MOVEMENT=STATIONARY

BOARD_A_MOVABLE=true
BOARD_B_MOVABLE=true
BOARD_C_MOVABLE=false
```

Board C in this plan is the replacement Board C with the new hardware/NODE identity established on 2026-09-24. The retired Board C must not be reused.

## Global constraints

```text
R0_R7_ORDER_FROZEN=true
DYNAMIC_LOAD_BALANCING=false
PROACTIVE_RSSI_ROAMING=false

ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true
ACTIVE_RELAY_FAILURE_RESELECTION=true

SAME_BOOT_EVIDENCE_REQUIRED=true
UNPLANNED_RESET_INVALIDATES_RELEVANT_BASELINE=true
UNPLANNED_POWER_CYCLE_INVALIDATES_RELEVANT_BASELINE=true
USB_RECONNECT_DURING_SAME_BOOT_ROUTE=FORBIDDEN
```

The exact source/host policy remains:

```text
PRIMARY_RANKING=RSSI
RSSI_EQUIVALENT_BAND_DB=3
TIE_BREAK=STABLE_CHILD_RELAY_SHA256
CANDIDATE_WINDOW_MS=6500
CANDIDATE_RSSI_UPDATE_RULE=ARITHMETIC_MEAN
```

The physical plan does not require ordinary free-space placement to prove the exact 3 dB boundary. Exact `<=3 dB` semantics, stable-hash tie-break, arithmetic-mean RSSI aggregation and 6500 ms candidate-window behavior are source/host-test authorities. Physical R3/R4 only need a clear, practical quality advantage.

## R0 — Fresh three-board Direct baseline

Purpose: establish a clean same-boot starting point for all three participants.

```text
OBSERVATION_SECONDS=180
MIN_CANONICAL_SEQ_ADVANCEMENT_PER_BOARD=2

BOARD_A_SOURCE=direct
BOARD_B_SOURCE=direct
BOARD_C_SOURCE=direct

BOARD_A_GATEWAY_NONE=true
BOARD_B_GATEWAY_NONE=true
BOARD_C_GATEWAY_NONE=true

BOARD_A_BOOT_STABLE=true
BOARD_B_BOOT_STABLE=true
BOARD_C_BOOT_STABLE=true

MANAGER_RESTART_COUNT_UNCHANGED=true
```

No movement occurs during R0.

## R1 — A loses Direct; B-only Relay path

Purpose: prove Board A as Child can enter Relay through Board B when B is the only viable Gateway candidate.

```text
CHILD=BOARD_A
EXPECTED_ACTIVE_GATEWAY=BOARD_B
BOARD_C_NOT_VIABLE_AS_GATEWAY_FOR_THIS_ROUND=true
SAME_BOOT_DIRECT_TO_RELAY_REQUIRED=true
```

The method used to make C non-viable must not reboot or mutate C. The physical arrangement may use placement/RF isolation consistent with the existing test environment.

## R2 — A loses Direct; C-only Relay path

Purpose: prove the symmetric single-candidate path through Board C.

```text
CHILD=BOARD_A
EXPECTED_ACTIVE_GATEWAY=BOARD_C
BOARD_B_NOT_VIABLE_AS_GATEWAY_FOR_THIS_ROUND=true
SAME_BOOT_DIRECT_TO_RELAY_REQUIRED=true
```

Board C remains on fixed stable power and is not moved.

## R3 — Both B/C viable; B clearly stronger

Purpose: prove multi-candidate selection prefers B when B has a clear physical RSSI advantage.

```text
CHILD=BOARD_A
CANDIDATE_SET=BOARD_B,BOARD_C
CLEAR_RSSI_WINNER=BOARD_B
EXPECTED_ACTIVE_GATEWAY=BOARD_B
```

This is a physical preference test, not an exact 3 dB threshold measurement.

## R4 — Both B/C viable; C clearly stronger

Purpose: prove the opposite clear-winner case.

```text
CHILD=BOARD_A
CANDIDATE_SET=BOARD_B,BOARD_C
CLEAR_RSSI_WINNER=BOARD_C
EXPECTED_ACTIVE_GATEWAY=BOARD_C
```

This is also a physical preference test, not an exact 3 dB threshold measurement.

## R5 — Healthy active Gateway remains sticky

Purpose: prove no proactive roaming.

Starting from a healthy active Relay session, make the other Gateway clearly stronger without failing the active Gateway.

```text
ACTIVE_GATEWAY_HEALTHY=true
OTHER_GATEWAY_BECOMES_STRONGER=true

EXPECTED_ACTIVE_GATEWAY_UNCHANGED=true
PROACTIVE_ROAMING_OBSERVED=false
DYNAMIC_LOAD_BALANCING_OBSERVED=false
```

## R6 — Active Gateway failure causes reselection

Purpose: prove failure-driven reselection.

The current active Gateway is made genuinely unavailable while the other candidate remains viable.

```text
ACTIVE_GATEWAY_FAILURE=true
CHILD_RETURNS_TO_DISCOVERY=true
SURVIVING_GATEWAY_AVAILABLE=true
EXPECTED_RESELECTION_TO_SURVIVOR=true
```

The active Gateway must fail through the product's ordinary Relay-failure path; do not simulate success by directly mutating Manager state.

## R7 — Same-boot Relay -> Direct recovery

Purpose: prove Board A can return to Direct without reboot after the multi-Relay route.

```text
CHILD=BOARD_A
SAME_BOOT_RELAY_TO_DIRECT_REQUIRED=true
FINAL_SOURCE=direct
POST_DIRECT_ADVANCEMENT_REQUIRED=true
MANAGER_RESTART_COUNT_UNCHANGED=true
```

## Acceptance sequencing

```text
R0
-> R1
-> R2
-> R3
-> R4
-> R5
-> R6
-> R7
```

Do not reorder or silently substitute Board C as the Child.

If a round requires a reboot or power-source change, the relevant same-boot baseline must be re-established before continuing.

## 2026-09-24 precheck disposition

A 90-second three-board Direct observation was completed before this authority was recovered.

Observed:

```text
BOARD_A_SEQ=5->7
BOARD_B_SEQ=5->7
BOARD_C_SEQ=5->6
ALL_THREE_SOURCE=direct
ALL_THREE_SAME_BOOT=true
MANAGER_RESTART_COUNT_UNCHANGED=true
```

Disposition:

```text
THREE_BOARD_DIRECT_90S_PRECHECK=PASS
R0_FROZEN_ACCEPTANCE=NOT_YET_EXECUTED
REASON=R0_REQUIRES_180S_AND_MIN_SEQ_ADVANCEMENT_2_PER_BOARD
```

The 90-second result is useful liveness evidence but must not be relabeled as formal R0 PASS.

## Next gate after authority recovery

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R0_THREE_BOARD_DIRECT_180S_BASELINE_20260924_01
NEXT_GATE_AUTHORIZED=true

PHYSICAL_MOVEMENT=false
BOARD_MUTATION=false
T1_MUTATION=false
DATABASE_MUTATION=false
SERVICE_RESTART=false
```
