# N3-W T1 Core Stack OTA V1.3 — KF-153 pyz-only live repair pre-execution package

Date: 2026-11-24

## 0. Gate status

```text
TASK=N3W_T1_OTA_V1_3_KF153_LIVE_REPAIR
STATUS=AUTHORIZED_READY_TO_EXECUTE
AUTHORIZATION_GATE=N3W_T1_V1_3_KF153_LIVE_REPAIR_20261124_01
AUTHORIZATION_STATUS=APPROVED
T1_MUTATION=false
R8V13_07_RESULT=NOT_PASS
R8V13_08_BLOCKED=true
```

The KF-153 source repair, exact recovery package, real-T1 read-only preflight, live-patch executor and focused regression are all closed sufficiently to request the bounded live mutation gate. This document does not itself grant that gate.

## 1. Exact repaired recovery authority

```text
SOURCE_HEAD=90ce32ce4b6c329fd38c2771e352d129d6d00a86
RECOVERY_ARTIFACT_RUN=45357836296
RECOVERY_ARTIFACT_ID=14902399722
RECOVERY_ARTIFACT_DIGEST_SHA256=c19280ac1fcbca7ef0de10ba2a24c0e1993898b0de988693ae14cff2c8e63a66
RECOVERY_INSTALL_MANIFEST_SHA256=90e83d4c4ce2a25e6c9fbce0245344b8c3ba247a4b5ecc58d4e93c4ceb169877
OLD_LIVE_PYZ_SHA256=d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
NEW_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
NON_PYZ_SUCCESSOR_PARITY=PASS
```

## 2. Live entry proof

Real-T1 read-only preflight:

```text
DURABLE_TERMINAL_TRANSACTION=PASS
RUNTIME_IDENTITIES=PASS
CURRENT_PREDECESSOR_BINDING=PASS
NON_PYZ_SUCCESSOR_PARITY=PASS
TARGET_10_0_PRESENT=false
LIVE_MUTATION=false
RESULT=KF153_LIVE_REPAIR_READONLY_PREFLIGHT_PASS
```

The failed transaction is terminal and no-replay:

```text
TRANSACTION_ID_SHA256=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
TRANSACTION_FILE_SHA256=b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0
STATUS=ROLLED_BACK
PHASE=U8_RECOVERY_ADMISSION_COMPLETE
FAILURE_CODE=ha_usb_release_predecessor_container_drift
RECOVERY_REQUIRED=false
PRE_CUTOVER_PREDECESSOR_RESTORED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
OLD_TRANSACTION_REPLAY=false
OLD_CONTINUATION_REPLAY=false
```

## 3. Exact live-patch executor

```text
EXECUTOR=tools/execution_packages/n3w/t1_ota_kf153/N3W_T1_V1_3_KF153_LIVE_REPAIR_20261124_01.sh
EXECUTOR_SHA256=1e6184ffae961bf8dbbb00361a1b90f4a6a56401a67a70f34b150e867000e6e9
EXECUTOR_SOURCE_HEAD=ae3d43e372423d1eb46ba5f9dcadbeccd351f4ae
FOCUSED_CI_RUN=45361435421
FOCUSED_CI=SUCCESS
FOCUSED_TESTS=23_PASSED
BASH_SYNTAX=PASS
PUBLIC_REPOSITORY_SAFETY=SUCCESS
CURRENT_AUTHORITY_CI=SUCCESS
HA_TARGET_BINDING_CI=SUCCESS
```

## 4. Authorized mutation scope if the user grants the gate

The gate is intentionally narrower than a normal OTA transaction.

Allowed:

1. download and independently hash the exact recovery artifact;
2. stage only the repaired `ha-recovery.pyz` on the spare T1;
3. re-prove the exact terminal transaction, old pyz, application runtime and absent target image;
4. temporarily stop only:
   - `n3w-t1-ha-recovery-retry.timer`
   - `n3w-t1-ha-recovery-retry.service`
   - `n3w-t1-ha-ota-ipc.socket`
   - `n3w-t1-ha-ota-ipc.service`;
5. back up the old pyz in temporary staging;
6. atomically replace only `/opt/n3w-t1-core-updater/ha-recovery.pyz`;
7. fsync and verify the exact new SHA256;
8. re-arm the retry timer and IPC socket;
9. prove transaction bytes, HA/Manager/Broker runtime, launch binding and target-image absence remain unchanged;
10. remove temporary staging only after full PASS.

Failure rollback:

- if the new pyz has been published and any later check fails, re-quiesce the recovery control plane first;
- atomically restore the exact old pyz;
- verify old SHA256;
- restore timer/socket;
- stop with `RESULT=KF153_LIVE_REPAIR_STOP`.

## 5. Explicitly excluded

```text
APPLICATION_SERVICE_RESTART=false
HA_IMAGE_MUTATION=false
MANAGER_IMAGE_MUTATION=false
BROKER_MUTATION=false
USB_MUTATION=false
OLD_TRANSACTION_REPLAY=false
NEW_HA_TRANSACTION=false
HA_INSTALL_OR_CUTOVER=false
BROKER_OTA=false
HOST_REBOOT=false
MERGE=false
RELEASE=false
```

The execution package does not run `--resume-pending`, INSTALL, candidate materialization/activation, container/image removal, or any HA transaction command.

## 6. Success result and downstream boundary

Expected successful terminal output:

```text
LIVE_RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
DURABLE_TRANSACTION_UNCHANGED=PASS
APPLICATION_RUNTIME_UNCHANGED=PASS
TARGET_10_0_PRESENT=false
RESULT=KF153_LIVE_REPAIR_PASS
```

A PASS closes the KF-153 updater deployment only. It does not make R8V13-07 PASS.

After PASS:

1. archive the live patch result;
2. perform a fresh read-only post-patch closure;
3. prepare a completely new fresh R8V13-07 10.4→10.0 transaction/reacceptance package;
4. never reuse transaction `afbfeeb8...`;
5. keep R8V13-08 blocked until a new R8V13-07 reaches healthy U13A acceptance.

## 7. Authorization boundary

```text
AUTHORIZATION_GATE=N3W_T1_V1_3_KF153_LIVE_REPAIR_20261124_01
AUTHORIZATION_STATUS=APPROVED
FIRST_MUTATION=STOP_RECOVERY_RETRY_TIMER
```

The user explicitly approved this named gate in the continuation chat. Execution remains bounded to the scope above.


## 8. Explicit authorization grant

```text
AUTHORIZATION_GATE=N3W_T1_V1_3_KF153_LIVE_REPAIR_20261124_01
AUTHORIZATION_SOURCE=USER_EXPLICIT_APPROVAL_IN_CONTINUATION_CHAT
AUTHORIZATION_STATUS=APPROVED
AUTHORIZED_EXACT_RECOVERY_PYZ_PATCH=true
AUTHORIZED_RECOVERY_CONTROL_PLANE_QUIESCE=true
AUTHORIZED_OLD_PYZ_BACKUP=true
AUTHORIZED_ATOMIC_PYZ_REPLACEMENT=true
AUTHORIZED_FAILURE_ROLLBACK=true
AUTHORIZED_POST_PATCH_READONLY_CLOSURE=true

AUTHORIZED_APPLICATION_SERVICE_RESTART=false
AUTHORIZED_HA_IMAGE_MUTATION=false
AUTHORIZED_MANAGER_IMAGE_MUTATION=false
AUTHORIZED_BROKER_MUTATION=false
AUTHORIZED_USB_MUTATION=false
AUTHORIZED_OLD_TRANSACTION_REPLAY=false
AUTHORIZED_NEW_HA_TRANSACTION=false
AUTHORIZED_HA_INSTALL_OR_CUTOVER=false
AUTHORIZED_BROKER_OTA=false
AUTHORIZED_HOST_REBOOT=false
AUTHORIZED_MERGE=false
AUTHORIZED_RELEASE=false
```
