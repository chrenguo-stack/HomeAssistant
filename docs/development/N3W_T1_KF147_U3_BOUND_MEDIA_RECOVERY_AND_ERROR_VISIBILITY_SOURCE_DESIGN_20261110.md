# N3W T1 KF-147 U3 Bound-Media Recovery and Error-Visibility Source Design

## 1. Trigger

The authorized destructive U1→U4 prepare execution on exact head
`ff6370c3b9e46e1ddf20409915e1b10dabb6e286` stopped after the one-shot
authorization was claimed and consumed.

The subsequent read-only forensic gate on PR #806 proved:

```text
DURABLE_STATE=DURABLE_U3
TRANSACTION_PHASE=U3_TARGET_DOWNLOADING_VERIFYING
TRANSACTION_STATUS=ACTIVE
PREPARE_CONFIRMATION_CONSUMED=true
USB_CAPACITY_VERIFIED=true
TARGET_ARTIFACT_VERIFIED=false
SAME_AUTHORIZATION_REPLAY_PERMITTED=false
```

The bound filesystem is still present and identity-consistent:

```text
USB_MODEL=Extreme
USB_PUBLIC_FINGERPRINT=e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93
USB_FILESYSTEM_UUID=967cf065-abe5-49ee-8499-7c3f50d2c48f
CURRENT_PARTITION=/dev/sdb1
FSTYPE=ext4
LABEL=N3W-UPDATE
MEASURED_USABLE_BYTES=29712691200
```

The current bound partition is not mounted, while the product runtime mount target still
reports an old `/dev/sda1` source. The current block inventory no longer contains
`/dev/sda`.

## 2. Source-level error-visibility defect

The U1 discovery worker and the confirm worker share the prepare controller lock.

A discovery iteration can capture U1 before confirmation, wait behind the confirm worker,
then complete after the confirm worker has already failed in U3. The discovery success path
previously cleared both:

```text
_discovery_error = None
_prepare_error = None
```

This can erase the real prepare-worker error and later project only
`ha_usb_prepare_worker_inactive`.

The source repair removes discovery ownership of `_prepare_error`.
Only the prepare worker may set or clear the prepare-worker error state.

## 3. Recovery invariant

The consumed destructive authorization is never replayed.

Recovery is constrained to the already-bound U3 transaction. It must not:

- submit `CONFIRM_USB_ERASE`;
- create a new PREPARE transaction;
- run wipefs;
- repartition the disk;
- run mkfs;
- change the filesystem UUID;
- change the bound public fingerprint;
- enter U5 or later.

## 4. Recovery mechanism

The existing product already defines the intended U2/U3 recovery path:

```text
daemon startup
-> start_background_recovery()
-> U2/U3 detected
-> _start_prepare_worker("resume")
-> HaUsbPrepareController.resume_prepare()
-> reopen_bound_media()
-> prepare_target()
-> record_target_ready()
-> U4
```

Therefore the recovery executor does not implement its own target-download pipeline.

The bounded live recovery sequence is:

1. fresh read-only U3 preflight;
2. verify exact transaction ID, release, target archive, filesystem UUID and USB fingerprint;
3. verify Manager / Home Assistant / Broker container continuity;
4. verify the current UUID-bound partition is unmounted;
5. verify any existing runtime mount is stale and is not backed by a currently live block path;
6. claim/consume a new recovery-only one-shot authorization;
7. rerun the complete U3 preflight;
8. unmount only the stale runtime mount target if present;
9. restart only `n3w-t1-ha-ota.service`;
10. allow existing product startup recovery to run `resume_prepare()`;
11. poll the durable transaction until U4 or the first failure;
12. at U4 verify exact archive size/SHA, same filesystem UUID and unchanged production containers;
13. stop before U5.

## 5. Authorization model

The recovery package previously bound the user's explicit recovery-only authorization to
exact head `e2ce7107897b21e3c7c7b88ebac5decd95cb0ec0`.

The first live attempt reached the remote Python entry point but stopped before recovery
authorization claim because the embedded remote script used `base64.b64decode()` without
importing `base64`. The observed result proved:

```text
authorization_claimed=false
authorization_consumed=false
usb_reformat=false
u5_plus=false
first_failed_operation=NameError:name 'base64' is not defined
```

The source repair adds the missing remote import and regression coverage. Because that repair
changes the executor blob and exact package head, the authorization bound to the predecessor
head is not inherited. The repaired package is intentionally returned to fail-closed state:

```text
live_execution_authorized=false
authorization_state.granted=false
authorization_state.claimed=false
authorization_state.consumed=false
authorization_state.replay_permitted=false
```

A fresh recovery-only authorization was explicitly granted by the user for repaired exact
source head `94aee49ccd9293cba0a3aae3ccb9abda1b6927c8` after source and exact-binding CI passed.
The package now binds that authorization while preserving the same existing U3 transaction,
bound filesystem UUID and USB fingerprint.

The recovery confirmation string is:

```text
EXECUTE KF147 U3 BOUND MEDIA RECOVERY TO U4: YES
```

### 5.1 Second preflight stop and lsblk tree repair

The authorization-bound live retry again stopped before authorization claim:

```text
status=STOP
first_failed_operation=Stop:bound_partition_inventory_invalid
authorization_claimed=false
authorization_consumed=false
usb_reformat=false
u5_plus=false
```

The root cause is deterministic: `lsblk --json` only emits the hierarchical
`children[]` structure when the `NAME` column is requested or tree mode is forced. The
recovery preflight requested `PATH,...` but not `NAME`, then attempted to locate the bound
partition by recursively walking `children[]`. On the target util-linux behavior this leaves
the parent disk without the partition subtree and causes
`bound_partition_inventory_invalid`.

The focused source repair adds `NAME` to the explicit lsblk output columns and regression
coverage for this requirement. Because this changes the executor blob, the prior recovery
authorization is not inherited.

After source and exact-binding CI passed for repaired exact source head
`766d486eb065269a1fde1f5c644d9f7aef17bf97`, the user explicitly granted a fresh
recovery-only authorization for that exact source. The package now binds that authorization
while preserving the same U3 transaction, filesystem UUID and USB public fingerprint.

## 6. Failure behavior

There is no automatic retry and no rollback.

- before recovery authorization claim: STOP, no mutation;
- after claim but before stale mount cleanup: STOP, authorization consumed, no replay;
- stale mount cleanup failure: STOP before service restart;
- service restart failure: STOP and manual recovery;
- U3 resume failure: STOP and preserve bound media for another forensic gate;
- U4 success: STOP before U5.

## 7. Current authorization state

```text
SOURCE_REPAIR_COMPLETE=true
RECOVERY_SOURCE_COMPLETE=true
PREDECESSOR_HEAD=e2ce7107897b21e3c7c7b88ebac5decd95cb0ec0
PREDECESSOR_AUTHORIZATION_CLAIMED=false
PREDECESSOR_AUTHORIZATION_CONSUMED=false
PREVIOUS_AUTHORIZED_SOURCE_HEAD=94aee49ccd9293cba0a3aae3ccb9abda1b6927c8
PREVIOUS_AUTHORIZATION_CLAIMED=false
PREVIOUS_AUTHORIZATION_CONSUMED=false
AUTHORIZED_SOURCE_HEAD=766d486eb065269a1fde1f5c644d9f7aef17bf97
RECOVERY_LIVE_EXECUTION_AUTHORIZED=true
RECOVERY_AUTHORIZATION_GRANTED=true
RECOVERY_AUTHORIZATION_CLAIMED=false
RECOVERY_AUTHORIZATION_CONSUMED=false
FRESH_REAUTHORIZATION_REQUIRED=false
T1_RECOVERY_MUTATION=false
MERGE=false
```
