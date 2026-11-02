# N3-W T1_Core_Updater portable image identity source repair progress — 2026-11-02

## 1. Trigger

The first authorized Manager A -> B live apply used the reviewed updater package and exact Manager tar.

```text
PRE_STATUS=PASS
PRE_RECOVERY_REQUIRED=false
PRE_TRANSACTION=null
PRE_INSPECT=PASS
PRE_PLAN_WITH_TAR=PASS
PRE_MANAGER_TAR_VERIFIED=true
PRE_TARGET_IMAGE_PRESTATE=ABSENT

APPLY_RESULT=STOP
APPLY_REASON=target_image_binding_invalid
APPLY_RC=2

POST_TRANSACTION_STATUS=ROLLED_BACK
POST_TRANSACTION_PHASE=ROLLBACK_COMPLETE_PRESTOP
POST_RECOVERY_REQUIRED=false
SERVICES_STOP_BOUNDARY_REACHED=false
```

Manager, Home Assistant and Broker remained on their pre-apply runtime baseline with restart count 0.

The consumed live authorization is no-replay.

## 2. Root cause

`tools/n3w_t1_core_updater_core.py` reintroduced a build-store-specific identity rule:

```python
self.host.image_id(target.image) == target.image_id
```

and the post-start path also compared the running Manager image ID directly with the build-side target image ID.

That rule is invalid across the project's already-proven Docker classic/build store -> Docker 29 containerd store path. The repository already has the portable identity authority:

```text
tools/n3w_t1_portable_image_identity.py
```

which binds exact tar content to:

```text
platform
RootFS diff IDs
normalized config semantics
archive SHA-256
```

The failure is therefore a recurrence of the KF-106 cross-store image identity oracle class inside the newer T1_Core_Updater path. No new KF number is allocated.

## 3. Repair

Source repair branch:

```text
fix/n3w-t1-core-updater-portable-image-identity-20261102
```

Repair rules:

1. preserve target `image_id` as build-side provenance;
2. keep same-host predecessor checks using the T1-local Docker ID;
3. parse the exact Manager tar through `n3w_t1_portable_image_identity.py`;
4. verify preexisting/loaded target images by portable RootFS + config semantics;
5. store the verified T1-local target runtime image ID in the upgrade transaction;
6. use that T1-local runtime ID for post-start running-container binding and explicit rollback;
7. do not weaken tag, tar SHA, platform, Compose-delta, HA-continuity or Broker-continuity checks.

## 4. Test additions

Required regression coverage now includes:

```text
PLAN_PREEXISTING_CROSS_STORE_ID_WITH_TAR=PASS_EXPECTED
PLAN_CROSS_STORE_ID_WITHOUT_TAR=FAIL_CLOSED_EXPECTED
APPLY_BUILD_ID_DIFFERS_FROM_RUNTIME_ID_PORTABLE_MATCH=PASS_EXPECTED
APPLY_PORTABLE_CONFIG_OR_ROOTFS_MISMATCH=PRESTOP_ROLLBACK_EXPECTED
EXPLICIT_ROLLBACK_AFTER_CROSS_STORE_APPLY=PASS_EXPECTED
```

The Manager-only zipapp package must now include:

```text
n3w_t1_portable_image_identity.py
```

## 5. Live boundary

```text
LIVE_RETRY_AUTHORIZED=false
OLD_AUTHORIZATION_REPLAY_PERMITTED=false
T1_MUTATION_DURING_SOURCE_REPAIR=false
BOARD_ACCESS=false
```

After source/CI/package closure, the next live action is not apply. It is a fresh read-only T1 preflight using the replacement updater package and exact tar. Because the failed R1 loaded the target image before the pre-stop rollback, the repaired `plan --manager-tar` must prove any preexisting target tag is portable-identical.

Only after that PASS may a new live apply authorization be requested.
