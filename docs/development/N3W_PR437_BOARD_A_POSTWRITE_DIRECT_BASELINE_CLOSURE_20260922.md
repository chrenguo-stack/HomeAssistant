# N3-W PR #437 Board A post-write Direct baseline closure — 2026-09-22

Status: `CLOSED_PASS`

## Scope

This gate verifies that the operator-confirmed Board A, after synchronization to the frozen PR #437 physical artifact, resumes Manager-visible Direct telemetry and remains on one stable boot session for a bounded 90-second observation.

It does not yet prove Board B gateway readiness, Board A Direct -> Relay transition, Relay continuity, or Relay -> Direct return.

## Runtime binding

Two earlier observers stopped safely:

1. fresh ROM hardware hash -> Manager registration returned zero matches;
2. pre-reset diagnostic boot session -> post-reset current canonical cursor returned zero matches.

Both were observer-design failures rather than product failures.

The accepted runtime binding method was:

```text
METHOD=MANAGER_PRE_SNAPSHOT_PLUS_CONTROLLED_BOARD_RESET_PLUS_UNIQUE_CANONICAL_BOOT_CHANGE
CONTROLLED_RESET=PASS
RESET_PERSISTENT_MUTATION=false
BOARD_A_RUNTIME_BINDING=PASS
BOARD_A_NODE_ID_SHA256=7ad414b84b17eef4de09cd71ccd676fcf5bb43eb72649939fc6423851d8a5eb5
```

## Direct baseline

```text
OBSERVATION_SECONDS=90

BOARD_A_SOURCE_BEFORE=direct
BOARD_A_SEQ_BEFORE=0
BOARD_A_BOOT_SESSION_SHA256_BEFORE=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776

BOARD_A_SOURCE_AFTER=direct
BOARD_A_SEQ_AFTER=19
BOARD_A_SEQ_DELTA=19
BOARD_A_BOOT_SESSION_SHA256_AFTER=50197d0358be1b2a8f6595f72e64ef9d77b0926925a0cd74fd3ebe87a9f24776

BOARD_A_SAME_BOOT=true
BOARD_A_CANONICAL_ADVANCED=true
BOARD_A_LAST_SOURCE_DIRECT=true
BOARD_A_CANONICAL_DIRECT_BASELINE=PASS
```

## Manager stability

```text
T1_MANAGER_RUNNING_BEFORE=true
T1_MANAGER_RUNNING_AFTER=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_RESTART_COUNT_UNCHANGED=true
MANAGER_STARTED_AT_UNCHANGED=true

T1_RUNTIME_MUTATION=false
PRODUCT_NVS_MUTATION=false
BOARD_A_FLASH_WRITE=false
```

## Disposition

```text
N3W_PR437_BOARD_A_POSTWRITE_DIRECT_BASELINE=CLOSED_PASS
BOARD_A_SAME_BOOT_ACCEPTANCE_SESSION=ESTABLISHED
ROLE_SWAP_PHYSICAL_ACCEPTANCE=NOT_YET_EXECUTED

NEXT_ONE_GATE=N3W_PR437_BOARD_B_GATEWAY_DIRECT_BASELINE_20260922_01
AUTO_EXECUTE_NEXT_GATE=false
```

Board A must not be reset or power-cycled before the role-swap transition if the current same-boot evidence is to be preserved.
