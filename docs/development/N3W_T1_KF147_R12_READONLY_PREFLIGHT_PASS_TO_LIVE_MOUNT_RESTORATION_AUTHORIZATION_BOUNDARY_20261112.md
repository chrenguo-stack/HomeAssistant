# N3-W KF-147 R12 real-T1 read-only preflight PASS → live mount-restoration authorization boundary
# 2026-11-12

```text
RESULT=PASS
REMOTE_RETURN_CODE=0
READ_ONLY=true
RESTORATION_ELIGIBLE=true
R12_SOURCE_AUTHORITY_HEAD=52b0b8aecbd0641e369227b4c4f636bacf876a6d
R12_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_POST_REBOOT_U4_MOUNT_RESTORATION_R12_20261112_01
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
LIVE_EXECUTION_AUTHORIZED=false
TRANSACTION_PHASE=U4_READY_TO_INSTALL
TRANSACTION_SHA256=dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259
IPC_PHASE=READY_TO_INSTALL
TARGET_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
TARGET_SIZE_BYTES=835309535
BOUND_USB_PRESENT=true
BOUND_USB_MOUNTED=false
OBSERVED_PARTITION=/dev/sda1
DURABLE_USB_BINDING=FILESYSTEM_UUID_PLUS_PUBLIC_FINGERPRINT
FIXED_DEV_SDX_BINDING=false
MANAGER_STATUS=running
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_STATUS=running
HOMEASSISTANT_RESTART_COUNT=0
BROKER_STATUS=running
BROKER_RESTART_COUNT=0
OTA_SERVICE_STATUS=active/running
OTA_SERVICE_RESTART_COUNT=0
RUNTIME_DIRECTORY_CREATION_ATTEMPTED=false
WRITABLE_MOUNT_ATTEMPTED=false
WRITABLE_MOUNT_RESTORED=false
HOST_STATE_MUTATION=false
HOST_SOURCE_MUTATION=false
USB_MUTATION=false
TRANSACTION_MUTATION=false
HOMEASSISTANT_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
U5_TRANSITION=false
U6_PLUS=false
BOARD_ACCESS=false
MERGE=false
NEXT_ONE_GATE=R12_LIVE_MOUNT_RESTORATION_EXPLICIT_AUTHORIZATION
EXPLICIT_USER_AUTHORIZATION_REQUIRED=true
AUTO_RETRY_R11=false
```

## Result

The operator executed the exact R12 `--preflight-only` package against the real T1. The executor returned PASS with remote return code 0 and `restoration_eligible=true`.

The preflight freshly proved the R10-installed three-file source slice, exact U4 transaction, stable Manager/Home Assistant/Broker runtime, active OTA service, IPC `READY_TO_INSTALL`, expected target binding, and exact bound USB present but unmounted.

## Device-node evidence

The bound media was observed as `/dev/sda1` after reboot, while earlier stages had observed another `/dev/sdX` node. R12 admitted it through the persisted filesystem UUID and public fingerprint rather than a hard-coded device path.

Therefore:

```text
/dev/sdX = volatile locator
filesystem UUID + public fingerprint = durable bound-media identity
```

A later preflight or live executor must not require the media to remain specifically `/dev/sdb1`.

## Mutation and authorization boundary

This attempt remained strictly read-only: no runtime directory creation, no writable mount/remount, no authorization claim or consumption, no Host/source/USB/transaction/product mutation, no U5/U6+ transition, no board access and no merge.

The requested stop boundary is reached.

## Next gate

```text
NEXT_ONE_GATE=R12_LIVE_MOUNT_RESTORATION_EXPLICIT_AUTHORIZATION
LIVE_MUTATION_DEFAULT=false
EXPLICIT_USER_AUTHORIZATION_REQUIRED=true
```

R11 must not be automatically retried. R12 live execution requires a separate explicit user authorization for the exact mount-restoration action.
