# N3-W PR #437 Board A battery-powered Direct rebaseline closure — 2026-09-22

Status: `CLOSED_PASS`

## Scope

Board A required a power-source change from USB to battery before physical movement. Because that change caused one expected reboot, the previous USB-powered same-boot baseline was invalidated. This gate establishes a new battery-powered same-boot origin while keeping Board B unchanged in its Direct/Gateway position.

## Physical state

```text
BOARD_A_BATTERY_POWERED=true
BOARD_A_REBOOT_COMPLETED=true
BOARD_A_STILL_IN_WIFI_COVERAGE=true
BOARD_B_UNCHANGED=true
```

## Battery boot binding

```text
BOARD_A_BATTERY_BOOT_BOUND=true
BOARD_A_OLD_BOOT_REPLACED=true

OLD_BOARD_A_BOOT_SESSION_SHA256=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776
CURRENT_BOARD_A_BATTERY_BOOT_SESSION_SHA256=51382692150b4a9feb6f49587fa24825b55036723b1aa5fc67a82a82201a56b1

CURRENT_BOARD_B_BOOT_SESSION_SHA256=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2
```

## 90-second dual-Direct rebaseline

```text
OBSERVATION_SECONDS=90

BOARD_A_SOURCE_BEFORE=direct
BOARD_A_SEQ_BEFORE=55
BOARD_A_SOURCE_AFTER=direct
BOARD_A_SEQ_AFTER=74
BOARD_A_SEQ_DELTA=19
BOARD_A_SAME_BATTERY_BOOT=true

BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SEQ_BEFORE=767
BOARD_B_SOURCE_AFTER=direct
BOARD_B_SEQ_AFTER=786
BOARD_B_SEQ_DELTA=19
BOARD_B_SAME_BOOT=true
```

## Manager stability and mutation boundary

```text
T1_MANAGER_RUNNING_BEFORE=true
T1_MANAGER_RUNNING_AFTER=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_STARTED_AT_UNCHANGED=true

BOARD_A_MUTATION=false
BOARD_B_MUTATION=false
T1_RUNTIME_MUTATION=false
```

## Disposition

```text
N3W_PR437_BOARD_A_BATTERY_DIRECT_REBASELINE=CLOSED_PASS
BOARD_A_BATTERY_SAME_BOOT_ORIGIN_ESTABLISHED=true
BOARD_B_GATEWAY_DIRECT_REMAINS_HEALTHY=true

NEXT_ONE_GATE=N3W_PR437_BOARD_A_SAME_BOOT_DIRECT_TO_RELAY_ROLE_SWAP_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```

Board A must remain on the current battery boot and must not be reset or power-cycled before or during the Direct -> Relay physical movement.
