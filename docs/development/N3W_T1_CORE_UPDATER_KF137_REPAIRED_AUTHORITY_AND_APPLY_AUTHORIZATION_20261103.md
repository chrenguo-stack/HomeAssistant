# N3-W T1 Core Updater KF-137 repaired authority and A -> B apply authorization — 2026-11-03

## 1. Source repair closure

```text
KF137=SOURCE_REPAIR_CLOSED_PASS
PR761_HEAD=06866acc9ff8f1e9acb7c3e23097a53031e9b313
PR761_CI=13/13_SUCCESS
PR761_MERGE_COMMIT=2e3f1c72e5ac17a9c8a1ecb378148a0d6d2d8c29

REPAIR=stop_services_accepts_inactive_or_failed
SYSTEMCTL_STOP_STILL_REQUIRED=true
MANAGER_RUNNING_CONTAINER_COUNT_MUST_BE_ZERO=true
HOMEASSISTANT_RUNNING_CONTAINER_COUNT_MUST_BE_ZERO=true
ACTIVE_STATE_REJECTED=true
```

The repair is intentionally narrow. It recognizes systemd `failed` as a valid non-active/stopped state only after successful `systemctl stop`, while independently retaining the zero-running-container proof for Manager and Home Assistant.

## 2. Exact repaired updater authority

```text
UPDATER_REVIEWED_HEAD=06866acc9ff8f1e9acb7c3e23097a53031e9b313
UPDATER_PR=761
UPDATER_MERGE_COMMIT=2e3f1c72e5ac17a9c8a1ecb378148a0d6d2d8c29

PACKAGE_RUN_ID=41561467986
PACKAGE_ARTIFACT_ID=13196564439
PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-3539c8f871e2
PACKAGE_ARTIFACT_DIGEST=sha256:e656223c776cc9f2f9fe0c334f2ae8d65bd26681617b0d6a0d82394f8833ac8c
UPDATER_PYZ_SHA256=6222ab4bdcb53e0b612777a585111f5ab2ab114a1c52a4997252937ef27033cc

MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0
MANAGER_REBUILT=false
ROLLBACK_COMPATIBLE=true
```

The package was produced from the exact repaired PR head, uploaded, re-downloaded, checksum-verified and executed with `--help` in CI.

## 3. Last live incident closure

```text
LAST_APPLY_RESULT=SAFE_STOP
LAST_APPLY_REASON=services_not_inactive
LAST_TRANSACTION_STATUS=ROLLED_BACK
LAST_TRANSACTION_PHASE=ROLLBACK_COMPLETE
LAST_RECOVERY_REQUIRED=false
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1

LAST_AUTHORIZATION_CONSUMED=true
LAST_AUTHORIZATION_REPLAY_PERMITTED=false
SECOND_APPLY_EXECUTED=false
EXPLICIT_ROLLBACK_EXECUTED=false
BOARD_ACCESS=false
```

## 4. New apply authorization

The user explicitly approved direct continuation to the repaired A -> B execution stage.

```text
APPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_KF137_REPAIRED_20261103_01
APPLY_AUTHORIZATION_GRANTED=true
APPLY_AUTHORIZATION_CLAIMED=true
APPLY_AUTHORIZATION_CONSUMED=false
AUTO_EXECUTE_AFTER_FRESH_PRECHECK=true

AUTHORIZED_SCOPE=EXACTLY_ONE_REPAIRED_V2_MANAGER_A_TO_B_APPLY
BOARD_ACCESS=false
```

This authorization allows:
- fresh status / inspect / plan using the exact repaired package;
- one A -> B apply if the fresh precheck still passes;
- post-apply status / inspect capture.

It does not allow:
- replay of any previous authorization;
- a second apply after failure;
- blind explicit rollback;
- manual transaction edit/delete;
- Home Assistant image mutation;
- Broker image mutation;
- host-platform mutation;
- Board, firmware or NVS mutation.

## 5. Execution boundary

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_KF137_REPAIRED_EXECUTION_20261103_01
LIVE_MUTATION_AUTHORIZED=true
BOARD_ACCESS=false
```

The execution package must fail before apply if any fresh predecessor, transaction, target tar, target portable identity, non-Manager continuity or listener precondition has drifted.
