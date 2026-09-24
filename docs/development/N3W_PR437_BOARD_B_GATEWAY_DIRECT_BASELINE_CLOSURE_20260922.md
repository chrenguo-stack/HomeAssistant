# N3-W PR #437 Board B gateway-side Direct baseline closure — 2026-09-22

Status: `CLOSED_PASS`

## Scope

This gate proves that the runtime-bound Board B is a stable Direct candidate for the Gateway side while Board A simultaneously preserves the same boot session established by its post-write Direct baseline.

It does not yet execute the Board A Direct -> Relay movement.

## Runtime bindings

```text
BOARD_A_NODE_ID_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5
BOARD_A_BOOT_SESSION_SHA256=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776

BOARD_B_NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
BOARD_B_BOOT_SESSION_SHA256=45a08a743fda98fc778118c46d2872538e78c79029c0323215a8cdf3acce78f2
```

## 90-second dual-Direct baseline

```text
BOARD_A_SEQ_BEFORE=685
BOARD_A_SEQ_AFTER=703
BOARD_A_SEQ_DELTA=18
BOARD_A_SOURCE_BEFORE=direct
BOARD_A_SOURCE_AFTER=direct
BOARD_A_SAME_BOOT=true

BOARD_B_SEQ_BEFORE=520
BOARD_B_SEQ_AFTER=539
BOARD_B_SEQ_DELTA=19
BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SOURCE_AFTER=direct
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
BOARD_A_SAME_BOOT_PRESERVED=true
BOARD_A_DIRECT_REMAINS_HEALTHY=true
BOARD_B_GATEWAY_DIRECT_BASELINE=CLOSED_PASS
DUAL_DIRECT_ROLE_SWAP_STARTING_CONDITION=PASS

NEXT_ONE_GATE=N3W_PR437_BOARD_A_SAME_BOOT_DIRECT_TO_RELAY_ROLE_SWAP_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```

Do not reset, power-cycle or open passive application serial on either participant before the same-boot role-swap movement. If either board changes boot session, this dual-Direct baseline must be re-established.
