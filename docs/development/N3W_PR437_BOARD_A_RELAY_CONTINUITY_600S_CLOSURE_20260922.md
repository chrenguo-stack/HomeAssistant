# N3-W PR #437 Board A Relay continuity 600 s closure — 2026-09-22

Status: `CLOSED_PASS`

## Scope

This gate validates reversed-role Relay steady-state continuity after the previously closed role-swap transition:

```text
Board A = Relay Child
Board B = Direct / Gateway
```

No board movement, reboot, power cycle, application-serial access, or T1 runtime mutation occurred during the observation.

## 600-second evidence

```text
OBSERVATION_SECONDS=600

BOARD_A_SEQ_START=258
BOARD_A_SEQ_END=378
BOARD_A_SEQ_DELTA=120
BOARD_A_SOURCE_START=relay
BOARD_A_SOURCE_END=relay
BOARD_A_BOOT_SESSION_SHA256=51382692150b4a9feb6f49587fa24825b55036723b1aa5fc67a82a82201a56b1
BOARD_A_SAME_BATTERY_BOOT=true
BOARD_A_RELAY_GATEWAY_IS_BOARD_B_START=true
BOARD_A_RELAY_GATEWAY_IS_BOARD_B_END=true

BOARD_B_SEQ_START=970
BOARD_B_SEQ_END=1090
BOARD_B_SEQ_DELTA=120
BOARD_B_SOURCE_START=direct
BOARD_B_SOURCE_END=direct
BOARD_B_BOOT_SESSION_SHA256=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2
BOARD_B_SAME_BOOT=true
BOARD_B_DIRECT_REMAINS_HEALTHY=true
```

## Durable sequence continuity

```text
EXPECTED_ROW_COUNT=121
ACCEPTED_ROW_COUNT=121
MISSING_SEQUENCE_COUNT=0
MISSING_SEQUENCE_RANGE=NONE

MAX_MANAGER_INTERARRIVAL_SECONDS=31.542
MAX_BOARD_A_CURSOR_AGE_SECONDS=31.521
MAX_BOARD_B_CURSOR_AGE_SECONDS=5.019

SOURCE_NON_RELAY_OBSERVED=false
GATEWAY_MISMATCH_OBSERVED=false
```

The 31.542-second maximum Manager interarrival is retained as a latency/buffering observation. It is not data loss because every expected durable replay tuple from seq 258 through 378 is present.

## Runtime stability

```text
T1_MANAGER_RUNNING_BEFORE=true
T1_MANAGER_RUNNING_AFTER=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_STARTED_AT_UNCHANGED=true

BOARD_A_MUTATION=false
BOARD_B_MUTATION=false
T1_RUNTIME_MUTATION=false
APPLICATION_SERIAL_OPEN=false
```

## Disposition

```text
N3W_PR437_BOARD_A_RELAY_CONTINUITY_600S=CLOSED_PASS
REVERSED_ROLE_RELAY_STEADY_STATE=PASS
REVERSED_ROLE_RELAY_ZERO_MISSING_600S=PASS
ROLE_SYMMETRY_STEADY_STATE_EVIDENCE=PASS

NEXT_ONE_GATE=N3W_PR437_BOARD_A_SAME_BOOT_RELAY_TO_DIRECT_FAILBACK_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```

Keep Board A in the Relay-child location and Board B in the Direct/Gateway location until the failback gate is explicitly authorized.
