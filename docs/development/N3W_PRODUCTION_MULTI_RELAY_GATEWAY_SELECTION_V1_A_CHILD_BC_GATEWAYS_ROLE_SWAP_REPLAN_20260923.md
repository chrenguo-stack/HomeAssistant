# N3-W Production Multi-Relay Gateway Selection V1 — A Child / B+C Gateways role-swap replan

Status: `APPROVED_REPLAN`

## Reason

Board C changed boot session during the active C-as-Child P1B route without operator contact.
Board C power instability is a primary physical-test confounder for same-boot Child acceptance.

The active physical route is therefore changed so Board A becomes the portable Child under
test, while Boards B and C remain stationary Direct + MQTT Gateway candidates in Wi-Fi
coverage and can use stable fixed power.

## Source compatibility

The production Gateway Selection V1 source is node-role generic rather than Board-label
specific. Selection uses the Child node identity and candidate Relay node identities. The
exact-head host contract exercises generic child/relay identities and the deterministic
selection digest over Child + Relay node IDs.

Historical physical evidence also proved A-as-Child / B-as-Gateway operation on the earlier
PR437 route. That evidence is not a substitute for current-artifact multi-Gateway acceptance,
but it supports the role swap as a valid test topology.

## Superseded active route

```text
OLD_CHILD_UNDER_TEST=C
OLD_GATEWAY_CANDIDATES=A,B
OLD_P1A_C_THROUGH_A=PASS
OLD_GATEWAY_B_RELAY_DELIVERY_TO_MANAGER=PROVEN
OLD_P1B_C_THROUGH_B_SAME_BOOT=NOT_CLOSED
OLD_ROUTE_STATUS=SUPERSEDED_BY_ROLE_SWAP
HISTORICAL_EVIDENCE_RETAINED=true
```

## New active topology

```text
CHILD_UNDER_TEST=A
GATEWAY_CANDIDATE_1=B
GATEWAY_CANDIDATE_2=C

BOARD_A_ROLE=PORTABLE_CHILD_UNDER_TEST
BOARD_B_ROLE=STATIONARY_DIRECT_RELAY_CANDIDATE
BOARD_C_ROLE=STATIONARY_DIRECT_RELAY_CANDIDATE

BOARD_B_DIRECT_MQTT_REQUIRED=true
BOARD_C_DIRECT_MQTT_REQUIRED=true
BOARD_C_STABLE_FIXED_POWER_REQUIRED=true
```

## Revised physical acceptance sequence

```text
R0=A/B/C fresh Direct rebaseline under new roles
R1=A can Relay through B alone
R2=A can Relay through C alone
R3=dual-Gateway geometry B-strong -> A selects B
R4=dual-Gateway geometry C-strong -> A selects C
R5=healthy active-Gateway stickiness
R6=active-Gateway failure -> A reselects surviving Gateway
R7=A same-boot Relay -> Direct recovery
```

For R3/R4, both B and C must remain Direct + MQTT healthy. Physical geometry changes may be
used to favor one candidate, but the production artifact does not expose exact internal
candidate RSSI arithmetic; therefore the run proves selected Gateway identity, not an exact
numeric 3 dB receiver-side threshold.

## Next gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_A_CHILD_BC_GATEWAYS_DIRECT_REBASELINE_20260923_01

AUTO_EXECUTE_NEXT_GATE=false
BOARD_FLASH_WRITE=false
BOARD_NVS_WRITE=false
T1_RUNTIME_MUTATION=false
```
