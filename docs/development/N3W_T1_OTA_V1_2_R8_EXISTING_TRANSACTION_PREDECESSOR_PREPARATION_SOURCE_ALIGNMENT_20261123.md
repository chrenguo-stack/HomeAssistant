# N3-W T1 OTA V1.2 R8 — existing-transaction exact 2026.10.0 predecessor preparation source alignment

Date: 2026-11-23

## 0. Scope and stop

```text
TASK=N3W_T1_OTA_V1_2_R8_EXISTING_TRANSACTION_ARCHITECTURE_PREDECESSOR_PREP_REBIND
BASE_BRANCH=review/t1-ota-r8-spare-preflight-20261122
BASE_HEAD=7879981a809cdc2bc51d1aeeb45a7d6336c60214
INVALID_PARALLEL_ROUTE=review/t1-ota-r8-predecessor-switch-20261122
INVALID_PARALLEL_ROUTE_CONSUMED=false

T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
DOCKER_MUTATION=false
SERVICE_MUTATION=false
POWER_MUTATION=false
MERGE=false
```

This source slice starts from the R8 Attempt 03 PASS handoff. It does not continue PR #823 and does not
reuse its private journal or predecessor-switch state machine.

The next live boundary remains blocked until exact T1/USB/Docker/service write authorization is reviewed.

## 1. Architecture decision

The exact `2026.10.0` predecessor is prepared by a **new ordinary HA U0-U13 transaction**, not by reopening
a previously committed 10.0 -> 10.4 transaction and not by creating a second recovery engine.

For the preparation transaction:

```text
current / recoverable pre-state = local/n3w-homeassistant:2026.10.4-5881590f
bounded preparation target     = local/n3w-homeassistant:2026.10.0-0c73235a
success terminal               = existing U13A COMMITTED
failure terminal               = existing U13B ROLLED_BACK to exact 2026.10.4
```

After a successful preparation transaction reaches healthy exact `2026.10.0`, the representative R8 OTA is
a separate fresh product transaction from 10.0 -> 10.4.

This keeps the V1.2 invariant that a committed transaction is terminal and that automatic rollback authority is
not silently revived after commit.

## 2. Reused product primitives

No phase or recovery primitive is added.

| Responsibility | Existing V1.2 primitive |
| --- | --- |
| durable transaction | `HaUsbStateStore` + HA U0-U13 |
| candidate admission | `LocalApprovedHaRelease` + release pin |
| transaction creation | `HaUsbIpcExecutor.submit(PREPARE)` |
| existing non-empty USB preparation | `record_existing_media_bound` + `prepare_mounted_archives` |
| current 10.4 rollback image | live predecessor export during `prepare_requested` |
| protected HA data | `HaMountedBackupProvider.create_consistent_backup` |
| first stop ownership | `HaPredecessorRecovery.install_recovery_point` |
| exact current-image release | `capture_predecessor_release` + `release_exact_predecessor` |
| post-release real-space gate | `HaMountedBackupProvider._require_internal_space` / bound-image load gate |
| exact 10.0 import | `HaMountedBackupProvider.load_target_image` + portable image verification |
| failed-target removal | `release_rollback_target` |
| image-only rollback | `_reconcile_predecessor_release` |
| data rollback | `_resume_ha_data_rollback` |
| boot/restart recovery | `resume_host_recovery` |
| healthy rollback terminal | existing U13B |

The new `maintenance_submit_approved_release()` function is only an operator-maintenance entry into the
existing `HaUsbIpcExecutor`. It owns no state and performs no direct Docker, USB, service, or recovery action.

## 3. Exact 2026.10.0 authority

New source authority:

```text
TARGET_MANIFEST=infra/n3w-t1/upgrades/homeassistant-2026.10.0-r8-predecessor-preparation.json
TARGET_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
TARGET_ARCHIVE_SIZE_BYTES=2448553472
TARGET_ARCHIVE_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
TARGET_PLATFORM=linux/arm64

ARTIFACT_RUN_ID=41275979177
ARTIFACT_ID=13070404405
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-24382caae4a1f5d459297f86e8d18f10a848ca64
ARTIFACT_DIGEST_SHA256=99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93
ARTIFACT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
```

The 2026-11-01 clean-reference closure records the same image ID, archive size, archive SHA-256 and platform.
Attempt 03 binds the operator Mac cache to the same archive values, so no 10.0 rebuild is required.

The reverse preparation target reuses the canonical 10.0/10.4 compatibility review:

```text
REVIEW_CANONICAL_SHA256=8b02e9bb0143fc4fc7900c4c0e4c52b27f92725cd41f1f03b82ba67ffb9e0267
PERSISTENT_SCHEMA_COMPATIBLE=true
ROLLBACK_COMPATIBLE_SOURCE_REVIEW=true
PREPARATION_PREDECESSOR_SOURCE_HEAD=fb7cfc857003ace3d368521d76ca2320ba399736
PREPARATION_TARGET_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
```

## 4. User-control isolation

The reverse target is a maintenance preparation authority, not a customer update.

The normal `T1OtaManager` continues to compare semantic versions and reports no update when installed
`2026.10.4` is presented with target `2026.10.0`. Therefore ordinary PREPARE through the product control
plane remains rejected with `ota_update_not_available`.

Only the privileged maintenance entry can submit the already-pinned candidate directly to
`HaUsbIpcExecutor`. Candidate materialization, release pinning, prepare/install authority issuance and the
destructive install boundary remain separate existing gates.

## 5. Capacity rule

R8 does not use the historical fixed 1.5 GiB reserve.

The preparation transaction inherits PR #821 single-image behavior:

```text
verify target + exact current recovery bytes
-> quiesce writers
-> create and verify protected data backup
-> persist exact release intent
-> release exact current HA container/image
-> observe release
-> remeasure actual internal free space
-> only then load exact 2026.10.0 target
```

If the actual post-release space is insufficient, the target is not loaded. Recovery continues from the same
transaction and the exact 10.4 recovery material.

## 6. Focused source coverage

The new focused test proves:

1. the exact 10.0 target is bound to the archived artifact and canonical compatibility review;
2. the normal Manager refuses to expose the reverse target as a customer update;
3. the privileged maintenance entry creates only the existing U1 transaction with current=10.4 and target=10.0;
4. no authorization is claimed/consumed at PREPARE.

The existing HA USB R2/single-image suite remains the authoritative fault matrix for the shared primitives,
including normal cutover, insufficient internal capacity, archive drift, target import/activation failure,
released-predecessor recovery, protected-data rollback and recovery-health failure.

## 7. Live boundary still blocked

No live command has been executed by this source slice.

Before the first real predecessor-preparation write, rebind and explicitly review:

```text
T1_TARGET=exact spare T1
SOURCE_HEAD=exact reviewed branch head
CURRENT_HA=local/n3w-homeassistant:2026.10.4-5881590f
TARGET_HA=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_ARCHIVE_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
USB_FILESYSTEM_UUID=read-only re-proven exact value
CURRENT_BASELINE=healthy and transaction-idle
ROLLBACK=existing U13B using freshly exported exact 10.4 + protected HA data backup
AUTHORIZED_SCOPE=only exact predecessor-preparation transaction
```

The first T1 transaction write, USB target materialization, Docker image release/load, service stop/start or
data restore remains unauthorized at this source stop.
