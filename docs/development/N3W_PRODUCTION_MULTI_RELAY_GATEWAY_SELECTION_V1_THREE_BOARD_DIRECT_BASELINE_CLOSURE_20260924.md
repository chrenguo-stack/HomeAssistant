# N3-W Production Multi-Relay Gateway Selection V1 — Three-Board Direct 90s Precheck

Date: 2026-09-24

## Superseding disposition

This document was initially written as a formal three-board Direct baseline closure. That classification was incorrect.

The later frozen physical acceptance plan recovered on 2026-09-24 requires R0 to use:

```text
OBSERVATION_SECONDS=180
MIN_CANONICAL_SEQ_ADVANCEMENT_PER_BOARD=2
```

Therefore this 90-second observation is retained only as precheck evidence.

```text
THREE_BOARD_DIRECT_90S_PRECHECK=PASS
R0_FROZEN_ACCEPTANCE=NOT_YET_EXECUTED
FORMAL_R0_PASS=false
```

Current physical plan authority:

`docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_PHYSICAL_ACCEPTANCE_R0_R7_FROZEN_PLAN_20260923.md`

## Scope

This public-safe record proves that A/B/replacement-C were concurrently alive on Direct after the replacement Board C power transition.

It does not authorize the superseded Board-C-as-Child route.

No raw NODE_ID, MAC, pairing ID, Setup Secret, MQTT credential, application key, T1 locator, USB path, or private log is included.

## Manager authority

```text
MANAGER_RUNNING=true
MANAGER_SOURCE_REVISION=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_RESTART_COUNT_UNCHANGED=true
```

## Board A precheck

```text
BOARD_A_SOURCE_BEFORE=direct
BOARD_A_SEQ_BEFORE=5
BOARD_A_BOOT_SHA256=3415ac0fcf7c4469b6c6f28af102b681f18918acde4be2bc3a93589c901afc53
BOARD_A_SOURCE_AFTER=direct
BOARD_A_SEQ_AFTER=7
BOARD_A_SEQ_ADVANCEMENT=2
BOARD_A_SAME_BOOT=true
BOARD_A_DIRECT_STABLE=true
BOARD_A_GATEWAY_NONE=true
```

## Board B precheck

```text
BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SEQ_BEFORE=5
BOARD_B_BOOT_SHA256=a533d36f010238f978f6e6aed7b1505143e6e21e578e2e7b05c1332017cff5a3
BOARD_B_SOURCE_AFTER=direct
BOARD_B_SEQ_AFTER=7
BOARD_B_SEQ_ADVANCEMENT=2
BOARD_B_SAME_BOOT=true
BOARD_B_DIRECT_STABLE=true
BOARD_B_GATEWAY_NONE=true
```

## Replacement Board C precheck

```text
BOARD_C_SOURCE_BEFORE=direct
BOARD_C_SEQ_BEFORE=5
BOARD_C_BOOT_SHA256=000f6f4ade1994bef54e26f1e2086872e8e49e1fc61d6a67cdf9b53f8cf9fb34
BOARD_C_SOURCE_AFTER=direct
BOARD_C_SEQ_AFTER=6
BOARD_C_SEQ_ADVANCEMENT=1
BOARD_C_SAME_BOOT=true
BOARD_C_DIRECT_STABLE=true
BOARD_C_GATEWAY_NONE=true
```

## Observation and mutation boundary

```text
READINESS_WAIT_MAX_SECONDS=180
THREE_BOARD_DIRECT_READY=true
OBSERVATION_SECONDS=90

BOARD_ACCESS=false
T1_MUTATION=false
DATABASE_MUTATION=false
SERVICE_RESTART=false

RESULT=PASS_THREE_BOARD_DIRECT_90S_PRECHECK
```

The first attempted executor failed before producing evidence because it tried to run host-level Docker inspection from inside the Manager container. R2 separated host inspection from container-internal read-only SQLite observation and produced the evidence above. That harness incident did not establish a product failure.

## Same-boot evidence

The observed boot hashes remain useful evidence of the current live sessions, but they are not formal R0 authority until the 180-second R0 gate passes.

```text
BOARD_A_PRECHECK_BOOT_SHA256=3415ac0fcf7c4469b6c6f28af102b681f18918acde4be2bc3a93589c901afc53
BOARD_B_PRECHECK_BOOT_SHA256=a533d36f010238f978f6e6aed7b1505143e6e21e578e2e7b05c1332017cff5a3
BOARD_C_PRECHECK_BOOT_SHA256=000f6f4ade1994bef54e26f1e2086872e8e49e1fc61d6a67cdf9b53f8cf9fb34
```

## Correct next gate

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_R0_THREE_BOARD_DIRECT_180S_BASELINE_20260924_01
NEXT_GATE_AUTHORIZED=true
PHYSICAL_MOVEMENT=false
```

Do not execute the superseded `BOARD_C_DUAL_GATEWAY_DIRECT_TO_RELAY` route.
