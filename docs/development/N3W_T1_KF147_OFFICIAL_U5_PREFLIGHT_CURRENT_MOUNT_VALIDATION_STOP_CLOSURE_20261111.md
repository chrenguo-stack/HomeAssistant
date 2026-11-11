# N3-W T1 KF-147 Official U5 Preflight Current Mount Validation STOP Closure
# 2026-11-11

## 1. Result

```text
TASK=N3W_T1_KF147_OFFICIAL_U5_PREFLIGHT_DYNAMIC_USB_BINDING_SOURCE_REPAIR_AND_CURRENT_MOUNT_VALIDATION_20261111_01
PR=807
SOURCE_REPAIR_HEAD=b72985f7570afc6ac3183090d3888742998789e9
FULL_REPAIR_CI_PASS=true

T1_PREFLIGHT_EXECUTED=true
T1_ACCESS=true
READ_ONLY_PREFLIGHT=true
STATUS=STOP
REMOTE_RETURNCODE=2
REASON=Stop:usb_mount_not_u5_writable:nodev,noexec,norecovery,nosuid,relatime,ro
CURRENT_MOUNT_FRESH_STATE=READ_ONLY_NO_RECOVERY
OFFICIAL_U5_PREFLIGHT_PASS=false

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
LIVE_EXECUTION_AUTHORIZED=false
REMOTE_STAGING=false
HOST_SOURCE_MUTATION=false
USB_MUTATION=false
HOMEASSISTANT_MUTATION=false
U6_PLUS=false
BOARD_ACCESS=false
MERGE=false
SSH_MASTER_CLEANUP=true
```

## 2. Interpretation

The repaired official U5 preflight behaved correctly on the real T1. It no longer failed on the
`/dev/sdb1` pathname. Instead, it reached the actual mount-mode admission check and
rejected the transaction-bound USB because the fresh mount is read-only.

The observed mount options are:

```text
nodev,noexec,norecovery,nosuid,relatime,ro
```

This is consistent with the U4 recovery purpose: preserve and inspect the prepared USB without
journal replay or writes. It is not U5 install readiness. Product U4→U5 processing calls
`sync_transaction_metadata(u5, media)`, so a writable bound filesystem is a real requirement.

The observed kernel spelling `norecovery` also shows why the durable guard should not depend only
on the earlier `noload` spelling. The decisive condition remains fail-closed writable admission:
`rw` required and `ro` rejected.

## 3. Boundary audit

No live authorization was claimed or consumed. No remote staging, host-source mutation, USB
mutation, Home Assistant mutation, U4→U5 transition, U6+, board access or merge occurred. SSH
master cleanup completed.

The private evidence directory remains operator-local and is intentionally not copied into this
public repository. This closure records only the public-safe terminal result provided by the
operator.

## 4. Disposition

```text
SOURCE_REPAIR_RESULT=CLOSED_PASS
CI_RESULT=CLOSED_PASS
REAL_T1_DYNAMIC_BINDING_VALIDATION=PASS
REAL_T1_U5_WRITABLE_ADMISSION=EXPECTED_STOP
NEW_SOURCE_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false
CURRENT_BLOCKER=BOUND_USB_IS_RECOVERY_MOUNTED_READ_ONLY_AND_NOT_U5_WRITABLE
```

Weakening the preflight is not an acceptable fix. The current media must first be restored to the
product-required writable mount under a separately reviewed and authorized live-mutation gate.

## 5. Next gate

```text
NEXT_ONE_GATE=N3W_T1_KF147_U5_WRITABLE_MOUNT_RESTORATION_SOURCE_DESIGN_AND_PREEXECUTION_20261111_01
NEXT_GATE_SCOPE=REPOSITORY_ONLY_DESIGN_AND_PREEXECUTION
LIVE_REMOUNT_OR_UNMOUNT_AUTHORIZED=false
U4_TO_U5_TRANSITION_AUTHORIZED=false
INSTALL_AUTHORIZED=false
```

The design must preserve the same UUID/public fingerprint, parent USB/removable/non-RO device
properties, root-device exclusion, exact transaction-derived mount target, exact prepared target
archive and unchanged U4 transaction. A later live step must require separate explicit authority.
After writable restoration, rerun the same official U5 preflight before any U4→U5 transition.
