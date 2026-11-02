# N3-W T1_Core_Updater R2 FAILED_EMERGENCY source repair progress — 2026-11-03

```text
TASK=N3W_T1_CORE_UPDATER_R2_FAILED_EMERGENCY_SOURCE_REPAIR_20261103_01
BASE_MAIN=ae67dc9da98b16c8bb6a23bc45afa2c5adbc4aee
BRANCH=fix/n3w-t1-core-updater-readiness-failed-emergency-recovery-20261103

LIVE_T1_MUTATION=false
BOARD_ACCESS=false
APPLY_RETRY=false
EXPLICIT_ROLLBACK=false
```

## Live forensic authority

R2 preflight passed and target B was already `PRESENT_AND_EXACT`. Apply then returned `automatic_rollback_failed`, leaving transaction `FAILED_EMERGENCY / ROLLBACK_FAILED`.

Fresh read-only forensic established:
- compose binding restored to predecessor Manager A;
- compose-env SHA restored to the exact pre-R2 value;
- Manager A runtime image ID restored;
- Home Assistant image unchanged;
- Broker runtime unchanged;
- restart counts remain 0;
- eight consecutive listener samples are stable at 8883=1, 47110=1, 47111=1, 47112=0.

Journal timing shows services active/container creation preceded greenhouse-manager runtime readiness by roughly 12 seconds.

## Source defects

### KF-135 readiness race

Current `LocalHost.wait_services()` returns after systemd is active and Manager/HA containers exist. Strict `inspect()` then immediately requires all four listeners.

Repair:
- centralize strict listener contract as `EXPECTED_LISTENERS`;
- use the same snapshot in `inspect()`;
- keep waiting in `wait_services()` until containers exist and listener snapshot equals the strict contract;
- timeout remains bounded at 120 seconds and fails closed.

### KF-136 non-terminal recovery dead-end

The old rollback path accepted only COMMITTED/APPLYING. Review of the full lifecycle also found that a process/host interruption after the transaction becomes `ROLLING_BACK` creates the same class of dead-end.

V2 repair:
- explicit rollback/recovery accepts APPLYING, ROLLING_BACK and FAILED_EMERGENCY histories;
- transaction history is not treated as current runtime authority;
- validate predecessor image authority first;
- read current Manager binding before any service mutation;
- if predecessor A is already strictly healthy, close to ROLLED_BACK with `t1_mutation=false`;
- if target B remains bound/active or application services are stopped, use the existing controlled rollback path to restore predecessor A;
- if binding/runtime is unknown, fail closed before stop/restart/env rewrite;
- never silently convert a non-terminal target runtime into COMMITTED.

## Regression coverage

Added/expanded tests:
- service readiness waits through an initial missing-listener sample and returns only after exact listener contract;
- APPLYING/STOPPING with predecessor already healthy closes without restart;
- ROLLING_BACK is re-entrant after process/host interruption;
- recovered FAILED_EMERGENCY closes without runtime mutation;
- FAILED_EMERGENCY with target still active can restore predecessor under explicit rollback confirmation;
- unknown Manager binding fails before service mutation;
- target image load/start failure and rollback-start failure paths;
- application-stopped predecessor recovery;
- terminal ROLLED_BACK recovery cannot be replayed.

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_R2_FAILED_EMERGENCY_SOURCE_REPAIR_CI_AND_REVIEW_20261103_01
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
```
