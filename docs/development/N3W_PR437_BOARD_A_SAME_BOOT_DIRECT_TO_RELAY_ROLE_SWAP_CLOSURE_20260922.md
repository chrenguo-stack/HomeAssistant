# N3-W PR #437 Board A same-boot Direct -> Relay role-swap closure — 2026-09-22

Status: `CLOSED_PASS`

## Scope

This gate validates the previously missing role direction:

```text
Board B = stationary Direct / Gateway
Board A = moving Direct -> Relay Child
```

Both boards used the same frozen PR #437 physical artifact. Board A had already been rebaselined on battery power before movement.

## Premovement authority

```text
BOARD_A_NODE_ID_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5
BOARD_A_BOOT_SESSION_SHA256=51382692150b4a9feb6f49587fa24825b55036723b1aa5fc67a82a82201a56b1
BOARD_A_SOURCE_PREMOVE=direct
BOARD_A_SEQ_PREMOVE=174

BOARD_B_NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
BOARD_B_BOOT_SESSION_SHA256=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2
BOARD_B_SOURCE_PREMOVE=direct
BOARD_B_SEQ_PREMOVE=886
```

## Transition result

```text
MOVE_START_TIME=2026-09-22T06:15:49.699Z

BOARD_A_LAST_DIRECT_TIME=2026-09-22T06:16:09.112Z
BOARD_A_LAST_DIRECT_SEQ=178

FIRST_RELAY_CURSOR_TIME=2026-09-22T06:16:36.764Z
FIRST_RELAY_CURSOR_SEQ=181

POST_RELAY_LAST_TIME=2026-09-22T06:16:37.022Z
POST_RELAY_LAST_SEQ=183
POST_RELAY_SEQ_DELTA=2

MOVE_START_TO_FIRST_OBSERVED_RELAY_MS=47144
MANAGER_VISIBLE_GAP_MS=27652

MISSING_SEQUENCE_COUNT=2
MISSING_SEQUENCE_RANGE=179-180
```

## Same-boot and gateway proof

```text
BOARD_A_SAME_BATTERY_BOOT=true
BOARD_A_RELAY_GATEWAY_IS_BOARD_B=true
BOARD_A_LAST_SOURCE_RELAY=true

BOARD_B_SOURCE_AFTER=direct
BOARD_B_SEQ_AFTER=895
BOARD_B_SEQ_DELTA=9
BOARD_B_SAME_BOOT=true
BOARD_B_DIRECT_REMAINS_HEALTHY=true

MANAGER_CANONICAL_RELAY_ACCEPTANCE=PASS
POST_RELAY_SEQ_ADVANCEMENT=PASS
SAME_BOOT_DIRECT_TO_RELAY=true
```

## Reliability boundary

The missing seq 179-180 are preserved as transition-boundary evidence. The frozen Option-B contract does not claim end-to-end every-sample delivery after a real transport attempt, so this measured loss does not fail the functional role-swap gate.

Historical opposite-role PR #437 physical runs also showed bounded Direct -> Relay boundary loss of 1 and 3 sequences while Relay steady-state continuity separately passed.

```text
ROLE_SYMMETRY_FUNCTIONAL_EVIDENCE=PASS
DIRECT_TO_RELAY_ZERO_LOSS=NOT_GUARANTEED
END_TO_END_EVERY_SAMPLE_DELIVERY=false
```

## Runtime stability and mutation boundary

```text
T1_MANAGER_RUNNING_BEFORE=true
T1_MANAGER_RUNNING_AFTER=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_STARTED_AT_UNCHANGED=true

BOARD_A_FLASH_MUTATION=false
BOARD_A_PRODUCT_NVS_MUTATION=false
BOARD_B_MUTATION=false
T1_RUNTIME_MUTATION=false
APPLICATION_SERIAL_OPEN=false
```

## Disposition

```text
N3W_PR437_BOARD_A_SAME_BOOT_DIRECT_TO_RELAY_ROLE_SWAP=CLOSED_PASS
A_AS_CHILD_B_AS_GATEWAY_DIRECT_TO_RELAY=PASS

BOARD_A_POSITION=RELAY_CHILD_LOCATION
BOARD_B_POSITION=DIRECT_GATEWAY_LOCATION

NEXT_ONE_GATE=N3W_PR437_BOARD_A_RELAY_CONTINUITY_600S_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```

Keep the physical topology unchanged. Do not reset, power-cycle or move either participant before the next gate if this same-boot Relay state is to be preserved.
