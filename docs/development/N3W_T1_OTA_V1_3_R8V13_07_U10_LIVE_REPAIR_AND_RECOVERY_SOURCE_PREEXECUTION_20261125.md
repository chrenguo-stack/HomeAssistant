# N3-W T1 OTA V1.3 R8V13-07 U10 live repair and recovery source preexecution

Date: 2026-11-25

## Status

```text
STAGE=N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE
TASK=R8V13-07
PHYSICAL_PREFLIGHT=PASS
LIVE_MUTATION=false
INSTALL_REPLAY=false
SECOND_TRANSACTION=false
R8V13_08_BLOCKED=true
```

The exact physical read-only preflight is archived in:

`docs/development/N3W_T1_OTA_V1_3_R8V13_07_U10_LIVE_REPAIR_READONLY_PREFLIGHT_PHYSICAL_PASS_20261125.md`

## Bound physical state

```text
TRANSACTION_ID=d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4
TRANSACTION_STATUS=ACTIVE
TRANSACTION_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
RECOVERY_REQUIRED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
TX_FILE_SHA256=4c68793fb1909366aa9acee7c06b74f3bac12dfae8681b1c4a6407abd6d2bd44
COMPOSE_ENV_SHA256=8f4a73bfa8126f9e4ee993197cece40fddcdf140c994687a391014d627c0e8cc
LIVE_OLD_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
LIVE_TARGET_LAUNCH_SHA256=955f0f69553f8f80639fab630dd23e23aec40d9e84a48f23536712701dbb1d05
FROZEN_PREDECESSOR_LAUNCH_SHA256=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
PREDECESSOR_IMAGE_PRESENT=false
TARGET_IMAGE_PRESENT=true
ROLLBACK_WRITERS_QUIESCED=true
USB_MOUNT_TARGET=/mnt/n3w-ha-r8-predecessor
```

## Successor artifact

```text
SOURCE_HEAD=a9b76d77c2a930a21089af7fe0cc814f4db60a9a
ARTIFACT_ID=14939405227
ARTIFACT_SHA256=9843b55453ba0025cbedae228c20e10da6b45b8284e559d2c8035876d98d42e5
MANIFEST_SHA256=489aa375fda2b0fba76ee4e9bd30ab168ce9ee00feff05ee074af5b656d1eca8
OLD_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
NEW_PYZ_SHA256=d7915bc3e42531a829ab22ecb74a7148878c3a2310313e4f1ac07acc8785185e
```

## Exact executor

```text
EXECUTOR=tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_U10_LIVE_REPAIR_AND_RECOVER_20261125_01.sh
EXECUTOR_BLOB=71685aa3bc417e0c45f415f6cff074ea189e463e
EXECUTOR_SHA256=4ed3a2dfe0bd6435a562305482ed5d1cc4b54bac7646370728b391eea188f90e
TEST=tests/tools/test_n3w_t1_ota_r8v13_07_u10_live_repair_and_recover.py
SOURCE_WIRING_HEAD=8b2ecfab0c931940ba5887e747921092c53170f3
```

The executor is intentionally one exact recovery gate:

1. verify the frozen transaction/env/image/media/recovery-owner evidence;
2. verify the exact successor artifact and successor pyz;
3. prove with the staged successor pyz that target-bound compose normalizes back to the frozen predecessor launch contract;
4. stop only the recovery retry timer/service and OTA IPC socket/service;
5. atomically replace only `/opt/n3w-t1-core-updater/ha-recovery.pyz`;
6. invoke the already-installed `n3w-t1-ha-recovery-retry.service`, which owns `--resume-pending`;
7. require the same transaction to finish `ROLLED_BACK/U13B_ROLLED_BACK`;
8. require the exact 2026.10.4 predecessor image/runtime/env and health to be restored;
9. require the 2026.10.0 failed target image to be absent;
10. leave the retry timer and OTA IPC socket active.

It does not submit INSTALL, issue another INSTALL authority, create another transaction, format/delete USB data, perform Broker OTA, reboot, merge, release, or enter R8V13-08.

## Failure semantics

Before recovery execution starts, a publication failure may atomically restore the old pyz.

After `n3w-t1-ha-recovery-retry.service` has started, the executor never restores the known-defective old pyz. It retains the repaired pyz and rearms the recovery control plane so the durable transaction remains recoverable.

## CI

```text
FOCUSED_CI_RUN=45508521268
FOCUSED_CI_STATUS=IN_PROGRESS_AFTER_3_CHECKS
ACTIVE_POLLING_STOPPED=true
```

Run link: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/45508521268

The run was not cancelled. No duplicate run was dispatched to bypass the polling limit.

## Authorization boundary

```text
SOURCE_TEST_CI_ARCHIVE_CONTINUATION=AUTHORIZED
LIVE_REPAIR_MUTATION_AUTHORIZED=false
EXECUTE_EXISTING_TRANSACTION_RECOVERY=false
INSTALL_REPLAY_ALLOWED=false
SECOND_TRANSACTION_ALLOWED=false
```

Do not execute the physical executor until its focused CI reaches SUCCESS and the exact live mutation/recovery scope receives explicit user authorization.
