# N3-W T1 KF-147 U5 Writable Mount Restoration — Source Design and Preexecution
# 2026-11-11

## 1. Gate

```text
TASK=N3W_T1_KF147_U5_WRITABLE_MOUNT_RESTORATION_SOURCE_DESIGN_AND_PREEXECUTION_20261111_01
PR=807
BASE_SOURCE_HEAD=b72985f7570afc6ac3183090d3888742998789e9
LIVE_T1_MUTATION_AUTHORIZED=false
USB_REMOUNT_AUTHORIZED=false
U4_TO_U5_TRANSITION_AUTHORIZED=false
INSTALL_AUTHORIZED=false
MERGE=false
```

The previous official U5 preflight is source/CI CLOSED_PASS and reached the real T1 mount-mode check. The live result was a fail-closed STOP because the transaction-bound ext4 USB is currently mounted with `ro` and `norecovery`. No authorization was claimed or consumed and no live mutation occurred.

## 2. Independent source finding

The current product backend `SubprocessPrepareBackend.reopen_bound_media()` has two branches:

1. if the bound partition is not mounted, it mounts the exact UUID/fingerprint-bound partition at the transaction-derived target with the normal product options `nodev,nosuid,noexec`;
2. if the partition is already mounted at the correct transaction target, it accepts that mount after identity/filesystem checks and does not convert its mode.

Therefore the present recovery mount is a special predecessor state. Entering U5 directly would leave the filesystem read-only until `sync_transaction_metadata(u5, media)` attempts to persist U5 metadata. That is too late for admission and is rejected by the official preflight.

Product source should not be changed to silently remount an already-mounted filesystem: doing so would turn a broadly used reopen/read path into an implicit live USB mutation path.

## 3. ext4 journal-recovery fact that constrains the design

Linux ext4 documents `norecovery` and `noload` as aliases that suppress journal loading. It also documents that ordinary read-only ext4 mounts may replay the journal, while `ro,noload` is used specifically to prevent those writes. A writable restoration must therefore stop using both recovery-suppression aliases and return to the normal ext4 journal path.

The restoration must not rely on a simple `mount -o remount,rw` from the current `ro,norecovery` state. The chosen design is an explicit unmount followed by a fresh ext4 mount with the product-normal writable options. This makes the journal transition explicit and auditable.

## 4. Frozen restoration design

A dedicated one-shot execution package should be added rather than modifying the product daemon. It must support two modes:

- `--preflight-only`: read-only, permitted before live authorization;
- `--execute`: denied unless a fresh gate ID, explicit confirmation, manifest `live_execution_authorized=true`, and unclaimed/unconsumed one-shot authorization state all match.

### 4.1 Required preflight evidence

Before any mutation, require all of the following:

- exact expected package commit and clean tracked worktree;
- exact installed predecessor source hashes used by the accepted U4 transaction;
- R6 terminal/consumed predecessor evidence remains intact and non-replayable;
- active transaction is exactly `U4_READY_TO_INSTALL`, status ACTIVE, target/capacity verified, authorization unclaimed/unconsumed;
- exact transaction SHA-256 remains `dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259`;
- filesystem UUID uniquely resolves to one current partition;
- parent disk is USB, removable, block-device RO=false, and matches transaction public fingerprint;
- root device is excluded by block identity, not by pathname;
- filesystem is ext4 with label `N3W-UPDATE`;
- current mount is exactly the transaction-derived target and the same block source by MAJ:MIN;
- preflight process and OTA daemon share the same mount namespace;
- current mount contains `ro,nodev,nosuid,noexec`, does not contain `rw`, and is treated as the expected recovery state; `noload` and `norecovery` are equivalent recovery-suppression observations;
- exact 835,309,535-byte target archive exists and SHA-256 remains `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`;
- OTA service is active/running; Manager, Home Assistant and Broker identities/restart counts remain unchanged; Manager IPC remains READY_TO_INSTALL.

Any drift stops before authorization claim and before unmount.

### 4.2 Mutation sequence after a fresh authorization

The first durable action is the one-shot authorization claim. After a post-claim revalidation, the only planned live mount mutation is:

1. `umount <exact transaction mount target>`;
2. re-resolve UUID/fingerprint/root exclusion and prove the USB is now unmounted everywhere;
3. fresh mount with `mount -t ext4 -o rw,nodev,nosuid,noexec <current UUID-resolved partition> <exact transaction mount target>`;
4. validate source/target/MAJ:MIN, namespace and mount options; require `rw,nodev,nosuid,noexec`, reject `ro,noload,norecovery`;
5. re-hash the exact target archive and unchanged U4 transaction;
6. revalidate installed source, service, three containers and Manager IPC;
7. STOP successfully at writable-mount restoration. Do not enter U5 in this executor.

The fresh writable mount may legitimately perform ext4 journal recovery. That is USB mutation and must be reported as such; it is precisely why this step requires separate live authorization.

### 4.3 Failure and rollback contract

- If preflight or post-claim revalidation fails before unmount: no USB mutation; STOP.
- If `umount` fails: treat the original recovery mount as still authoritative; STOP; no automatic retry.
- If unmount succeeds but fresh writable mount fails: attempt one bounded rollback mount using `ro,noload,nodev,nosuid,noexec` at the same target, then verify the exact target and U4 transaction. Report rollback success/failure explicitly; never loop.
- If writable mount succeeds but post-validation fails: attempt one bounded unmount and rollback to `ro,noload,nodev,nosuid,noexec`. Once a writable mount was attempted, `usb_mutation=true` remains true even if rollback succeeds because journal replay or metadata writes may already have happened.
- Any rollback failure becomes a terminal manual-recovery state. No service restart, source deployment, U4→U5 transition or installation is allowed as part of rollback.

## 5. Admission repair found during this gate

The real T1 reported `norecovery`, while the repaired official U5 preflight manifest initially listed only `ro` and `noload` as forbidden. Because `ro` was present, the live run still stopped correctly. However a hypothetical `rw,norecovery` mount could otherwise evade the alias check.

This gate therefore makes the localized regression repair:

```text
mount_forbidden_options=[ro,noload,norecovery]
```

A focused test must prove that `rw,norecovery,nodev,nosuid,noexec` is rejected with `usb_mount_not_u5_writable`.

## 6. Source disposition

```text
PRODUCT_DAEMON_IMPLICIT_REMOUNT=false
DEDICATED_ONE_SHOT_RESTORATION_EXECUTOR_REQUIRED=true
SOURCE_REPAIR_REQUIRED=true
LIVE_EXECUTION_REQUIRED_LATER=true
CURRENT_LIVE_AUTHORIZATION=false
```

The next source gate may implement the one-shot executor, manifest, tests and CI wiring. It remains repository-only. Only after exact source/CI review and a fresh read-only preflight may a separate user authorization permit the real unmount/writable-mount operation.

## 7. Next gate

```text
NEXT_ONE_GATE=N3W_T1_KF147_U5_WRITABLE_MOUNT_RESTORATION_EXECUTOR_SOURCE_REPAIR_AND_CI_20261111_01
NEXT_GATE_MODE=REPOSITORY_ONLY
T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
MERGE=false
```
