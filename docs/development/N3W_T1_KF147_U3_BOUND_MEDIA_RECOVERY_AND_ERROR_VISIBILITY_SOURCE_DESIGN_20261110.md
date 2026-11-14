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

### 5.2 Third live stop after authorization claim and R4 successor

The authorization-bound retry on package head
`3c17f51bc8f19c12bc2aedbc59db0db4ee688201` passed the pre-claim and post-claim U3
preflight, claimed and consumed the recovery authorization, and successfully returned from
the exact `umount` command. It then stopped before the OTA service restart:

```text
status=STOP
first_failed_operation=Stop:stale_runtime_mount_persisted
authorization_claimed=true
authorization_consumed=true
replay_permitted=false
usb_reformat=false
u5_plus=false
```

The source review found that `mount_view()` used `findmnt --target <path>`. That operation
answers which filesystem contains a path; after the exact stale mount is removed it may still
return the parent filesystem containing the directory. Therefore the post-unmount verification
could report a persisted stale mount even when the exact mountpoint was already gone.

The successor repair changes the lookup to exact mountpoint semantics with
`findmnt --mountpoint <path>`. Because the previous recovery authorization is consumed, R4
uses a new gate/authorization identity and a new state root:

```text
GATE_ID=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_U3_BOUND_MEDIA_RECOVERY_TO_U4_R4_20261111_01
STATE_ROOT=/var/lib/n3w-t1-core-updater/kf147-u3-bound-media-recovery-r4-20261111-01
LIVE_EXECUTION_AUTHORIZED=false
```

R4 was committed fail-closed. The consumed predecessor authorization is never replayed.

After source and exact-binding CI passed for R4 exact source head
`9d6cfeadde89b66c89316161353cf26c7946b892`, a fresh read-only preflight on T1 returned
`status=PASS`, `recovery_eligible=true`, `stale_mount=null`, preserved the same U3
transaction and bound media, and confirmed Manager / Home Assistant / Broker continuity.
The user then explicitly granted a new R4 live recovery authorization for that exact source
head. The package now binds that R4 authorization while preserving the same U3 transaction,
filesystem UUID and USB public fingerprint.

### 5.3 R4 live resume stop before target download

The R4 live recovery claimed and consumed its one-shot authorization, restarted
`n3w-t1-ha-ota.service`, and successfully reopened the UUID-bound `/dev/sdb1` media.
A read-only IPC status query as the admitted Manager UID then reported:

```text
phase=ERROR
error_code=usb_runtime_directory_metadata_invalid
transaction_phase=U3_TARGET_DOWNLOADING_VERIFYING
target_artifact_verified=false
target_directory_absent=true
external_https_download_connection=false
```

Source review identifies a deterministic parent-directory creation defect in
`SubprocessPrepareBackend.sync_transaction_metadata()`. The previous code called
`Path(.../n3w-update/transaction).mkdir(parents=True, mode=0o700)` indirectly through
`_require_private_directory()`. Python may create the missing intermediate
`n3w-update` parent with the default parent-directory mode rather than the requested final
`0o700` mode. Later `prepare_target()` explicitly requires `n3w-update` itself to be
private and rejects the already-created parent with
`usb_runtime_directory_metadata_invalid` before creating any target temporary file or
opening the HTTPS artifact connection.

The focused source repair now creates and validates `n3w-update` explicitly first, then
creates and validates `n3w-update/transaction`. The repair does not automatically chmod an
already-existing live USB directory.

Fresh read-only metadata inspection on the mounted bound media proved the exact live defect:

```text
/run/n3w-t1-ota                          uid=0 gid=999 mode=0750
/run/n3w-t1-ota/media                    uid=0 gid=999 mode=0700
.../ca89774eb4254d0f                     uid=0 gid=0   mode=0755
.../ca89774eb4254d0f/n3w-update          uid=0 gid=999 mode=0770
.../n3w-update/transaction               uid=0 gid=999 mode=0700
.../n3w-update/target                    absent
```

The strict helper rejects group/other permission bits on `n3w-update`, so mode `0770` is
the direct trigger. The mounted ext4 root mode `0755` is not passed through that helper in
the resume path and is not the failing directory.

R5 is therefore a narrow successor gate. It is committed fail-closed and requires:
- the R4 executor to have reached a durable terminal timeout record;
- the exact existing U3 transaction, USB UUID/fingerprint and production containers;
- the same exact bound partition already mounted at the transaction mount target;
- `n3w-update` exactly root:999 mode `0770`;
- `transaction` exactly root:999 mode `0700`;
- no target directory yet.

After a fresh explicit R5 authorization, the only USB mutation allowed before service restart
is an fd-bound `fchmod(0700)` on that exact `n3w-update` directory followed by fsync and
revalidation. R5 does not wipe, repartition, format, unmount, replay destructive confirmation,
or enter U5.

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
R4_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_U3_BOUND_MEDIA_RECOVERY_TO_U4_R4_20261111_01
R4_AUTHORIZATION_CLAIMED=true
R4_AUTHORIZATION_CONSUMED=true
R4_REPLAY_PERMITTED=false
R4_SERVICE_RESTART_REACHED=true
R4_RUNTIME_ERROR=usb_runtime_directory_metadata_invalid
R4_TARGET_DOWNLOAD_STARTED=false
R4_U4_READY=false

LIVE_USB_UPDATE_DIR_UID=0
LIVE_USB_UPDATE_DIR_GID=999
LIVE_USB_UPDATE_DIR_MODE=0770
LIVE_USB_TRANSACTION_DIR_MODE=0700
LIVE_USB_TARGET_DIR_PRESENT=false

PRODUCT_SOURCE_PARENT_DIRECTORY_REPAIR_COMPLETE=true

R5_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_U3_PERMISSION_REPAIR_TO_U4_R5_20261111_01
R5_LIVE_EXECUTION_AUTHORIZED=false
R5_AUTHORIZATION_GRANTED=false
R5_AUTHORIZATION_CLAIMED=false
R5_AUTHORIZATION_CONSUMED=false
R5_REPLAY_PERMITTED=false
R5_PREFLIGHT_REQUIRES_R4_TERMINAL_FAILURE=true

USB_WIPE=false
USB_PARTITION=false
USB_FORMAT=false
DESTRUCTIVE_CONFIRMATION_REPLAY=false
U5_PLUS=false
MERGE=false
```
