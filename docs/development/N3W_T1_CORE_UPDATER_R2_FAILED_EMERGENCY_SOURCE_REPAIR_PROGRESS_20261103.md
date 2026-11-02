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

### KF-136 FAILED_EMERGENCY closure dead-end

Current rollback accepts only COMMITTED/APPLYING while `prepare_new()` rejects FAILED_EMERGENCY.

Repair:
- allow explicit rollback to read FAILED_EMERGENCY;
- require predecessor image still exists with exact predecessor runtime ID;
- require strict current inspect PASS;
- require current Manager already equals predecessor A;
- require HA identity stability and Broker continuity;
- only then change transaction state to `ROLLED_BACK / RECOVERY_COMPLETE_FAILED_EMERGENCY`;
- report `t1_mutation=false`;
- if predecessor is not already restored, fail closed without runtime mutation.

## Regression coverage

Added tests:
- service readiness waits through an initial missing-listener sample and returns only after exact listener contract;
- recovered FAILED_EMERGENCY closes without runtime mutation;
- FAILED_EMERGENCY with target still active refuses to close and leaves transaction unchanged.

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_R2_FAILED_EMERGENCY_SOURCE_REPAIR_CI_AND_REVIEW_20261103_01
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
```
