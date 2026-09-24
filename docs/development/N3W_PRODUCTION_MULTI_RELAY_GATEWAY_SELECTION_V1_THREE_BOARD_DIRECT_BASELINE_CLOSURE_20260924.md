# N3-W Production Multi-Relay Gateway Selection V1 — Three-Board Direct Baseline Closure

Date: 2026-09-24

## Scope

This public-safe closure records the A/B/replacement-C concurrent Direct baseline immediately before three-node multi-Relay physical selection testing.

No raw NODE_ID, MAC, pairing ID, Setup Secret, MQTT credential, application key, T1 locator, USB path, or private log is included.

## Manager authority

```text
MANAGER_RUNNING=true
MANAGER_SOURCE_REVISION=8fbedc7e0778ce91d146cd5f0772bebdd20ad13a
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_RESTART_COUNT_UNCHANGED=true
```

## Board A baseline

```text
BOARD_A_SOURCE_BEFORE=direct
BOARD_A_SEQ_BEFORE=5
BOARD_A_BOOT_SHA256=3415ac0fcf7c4469b6c6f28af102b681f18918acde4be2bc3a93589c901afc53
BOARD_A_SOURCE_AFTER=direct
BOARD_A_SEQ_AFTER=7
BOARD_A_SAME_BOOT=true
BOARD_A_SEQ_ADVANCED=true
BOARD_A_DIRECT_STABLE=true
BOARD_A_GATEWAY_NONE=true
```

## Board B baseline

```text
BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SEQ_BEFORE=5
BOARD_B_BOOT_SHA256=a533d36f010238f978f6e6aed7b1505143e6e21e578e2e7b05c1332017cff5a3
BOARD_B_SOURCE_AFTER=direct
BOARD_B_SEQ_AFTER=7
BOARD_B_SAME_BOOT=true
BOARD_B_SEQ_ADVANCED=true
BOARD_B_DIRECT_STABLE=true
BOARD_B_GATEWAY_NONE=true
```

## Replacement Board C baseline

```text
BOARD_C_SOURCE_BEFORE=direct
BOARD_C_SEQ_BEFORE=5
BOARD_C_BOOT_SHA256=000f6f4ade1994bef54e26f1e2086872e8e49e1fc61d6a67cdf9b53f8cf9fb34
BOARD_C_SOURCE_AFTER=direct
BOARD_C_SEQ_AFTER=6
BOARD_C_SAME_BOOT=true
BOARD_C_SEQ_ADVANCED=true
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

RESULT=PASS_THREE_BOARD_DIRECT_BASELINE
```

The first attempted baseline executor failed before producing baseline evidence because it tried to run host-level Docker inspection from inside the Manager container. That harness incident did not mutate Board/T1 state and is not classified as a product failure. R2 separated host inspection from container-internal read-only SQLite observation and passed.

## Same-boot authority for following physical route

The boot hashes above are the frozen starting authority for the next physical route. Any reset or power cycle of a participating board invalidates its same-boot baseline and requires re-baselining before a same-boot claim.

```text
BOARD_A_SAME_BOOT_AUTHORITY=3415ac0fcf7c4469b6c6f28af102b681f18918acde4be2bc3a93589c901afc53
BOARD_B_SAME_BOOT_AUTHORITY=a533d36f010238f978f6e6aed7b1505143e6e21e578e2e7b05c1332017cff5a3
BOARD_C_SAME_BOOT_AUTHORITY=000f6f4ade1994bef54e26f1e2086872e8e49e1fc61d6a67cdf9b53f8cf9fb34

POWER_CYCLE_DURING_SAME_BOOT_ROUTE=FORBIDDEN
RESET_DURING_SAME_BOOT_ROUTE=FORBIDDEN
USB_RECONNECT_DURING_SAME_BOOT_ROUTE=FORBIDDEN
```

## Next gate

```text
NEXT_ONE_GATE=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_BOARD_C_DUAL_GATEWAY_DIRECT_TO_RELAY_PREFLIGHT_20260924_01
NEXT_GATE_AUTHORIZED=true
```

The next gate must preserve Boards A/B as healthy Direct Relay candidates and move only replacement Board C from Wi-Fi coverage to the qualified Relay-only location. Initial acceptance is limited to proving same-boot Direct -> Relay, a selected Gateway belonging to the A/B candidate set, and continued A/B Direct health. Selection-policy ranking, active-Relay stickiness, failure-driven reselection, and Relay -> Direct failback remain separate evidence steps.
