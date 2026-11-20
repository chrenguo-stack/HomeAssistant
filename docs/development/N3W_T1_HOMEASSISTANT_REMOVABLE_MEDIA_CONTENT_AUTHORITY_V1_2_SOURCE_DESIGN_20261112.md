
# N3-W T1 Home Assistant removable-media content-authority V1.2 source design
# 2026-11-12

GATE=REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_DESIGN
STATUS=SOURCE_DESIGN_FROZEN
ARCHITECTURE_AUTHORITY=docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_REMOVABLE_MEDIA_CONTENT_AUTHORITY_ARCHITECTURE_V1.2_20261112.md
ARCHITECTURE_REVIEW=docs/development/N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_ARCHITECTURE_REVIEW_20261112.md

EXECUTABLE_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false

CURRENT_LIVE_TRANSACTION_PHASE=U4_READY_TO_INSTALL
CURRENT_TRANSACTION_SCHEMA=gh.n3w-t1-core-updater-homeassistant-usb-transaction/1
CURRENT_R12_READONLY_PREFLIGHT=PASS
R12_LIVE_MOUNT_RESTORATION=SUPERSEDED_NOT_EXECUTED
AUTO_RETRY_R11=false

## 1. Design objective

Implement the approved V1.2 rule with the smallest safe source delta:

- physical USB identity is not business authority;
- current /dev/sdX is runtime-only;
- UUID/fingerprint are observation/diagnostic values only;
- current transaction + exact content identity are durable authority;
- current real U4 transaction must remain readable and move forward without reset/reformat;
- pre-U9 replacement media may be re-prepared;
- post-U9 recovery requires exact complete recovery content, not the same physical stick.

The source repair must not weaken root-disk protection, capacity admission, exact artifact verification, backup protection, one-shot authorization or rollback completeness.

## 2. Compatibility decision: do not bump the active transaction schema in the first repair

The first V1.2 source repair SHALL keep:

HA_USB_TX_SCHEMA=gh.n3w-t1-core-updater-homeassistant-usb-transaction/1

Reason:

- the real T1 already holds a valid U4 transaction using schema /1;
- transaction_id_sha256 is derived from release/current/target authority and does not include USB identity;
- the current validator does not require an exact key set;
- additive identity fields can therefore be introduced without rewriting the live U4 document before the user performs any next action.

This avoids a dedicated transaction-schema migration executor.

The /1 contract becomes an additive backward-compatible internal schema for this bounded repair. A future schema /2 may be introduced after the active U4 line is terminal, but it is not required for the current correction.

Old U4 documents without new identity fields remain valid. The INSTALL revalidation path must populate the exact target identity before the U4->U5 transition.

No old U6+ transaction may be silently treated as V1.2-complete merely because verification booleans are present. If a future live legacy U6+ transaction is encountered without exact recovery identities, fail closed for explicit reconciliation.

## 3. Durable transaction fields

Keep existing fields for compatibility, but change their semantics:

usb_device_identity_public_fingerprint
usb_filesystem_uuid
usb_mount_authority
usb_measured_usable_bytes

These become historical preparation-media observations/capacity evidence. They must never be compared against a later USB as continuity authority.

Add optional fields initialized to null for new transactions and tolerated as absent in existing U4:

target_artifact_identity
predecessor_recovery_identity
ha_data_backup_identity
recovery_content_manifest_sha256

### 3.1 target_artifact_identity

Canonical document derived only from a freshly verified ImageRecoveryRecord:

kind=target
image_ref
archive_sha256
archive_size_bytes
portable_identity_sha256
platform
verified=true
fsynced=true

Required from U5 onward.

Legacy U4 may have target_artifact_verified=true with no target_artifact_identity. That is intentionally allowed only until INSTALL revalidation.

### 3.2 predecessor_recovery_identity

Canonical document derived from freshly verified predecessor ImageRecoveryRecord.

Required from U7 onward.

### 3.3 ha_data_backup_identity

Canonical document derived from freshly verified HaDataBackupRecord:

archive_sha256
archive_size_bytes
manifest_sha256
verified
fsynced
consistent_preupgrade_point
complete_production_config
storage_integrity_verified
ownership_metadata_present
confidentiality_protected
authenticity_protected
unsupported_external_state

Required from U8 onward.

### 3.4 recovery_content_manifest_sha256

At U8 compute:

sha256(canonical({
  transaction_id_sha256,
  release_identity,
  target_artifact_identity,
  predecessor_recovery_identity,
  ha_data_backup_identity
}))

Do not include:

- /dev path;
- filesystem UUID;
- public fingerprint;
- model;
- serial/WWN;
- mount path.

Therefore a byte/content-equivalent copy on another safe USB yields the same recovery authority.

## 4. State validator changes

tools/n3w_t1_core_updater_ha_usb_state.py

Required changes:

1. Continue accepting current schema /1.
2. Treat missing new identity keys as null for legacy documents.
3. Preserve current U0-U4 documents.
4. Require exact target_artifact_identity at U5+.
5. Require exact predecessor_recovery_identity at U7+.
6. Require exact ha_data_backup_identity and recovery_content_manifest_sha256 at U8+.
7. Recompute and compare recovery_content_manifest_sha256 during validation at U8+.
8. Keep authorization requirements at U9+ unchanged.
9. Keep current booleans for compatibility, but booleans alone are never sufficient once the phase requires an exact identity document.
10. Stop requiring UUID/fingerprint equality across phases. Existing observation fields may remain populated.

Do not make target/recovery identity user-supplied. They are generated only from verified host-side records.

## 5. Core transition changes

tools/n3w_t1_core_updater_ha_usb.py

### 5.1 record_target_ready

Persist target_artifact_identity from the verified target record in addition to target_artifact_verified=true for new/reprepared flows.

### 5.2 request_install

Change the bounded contract so U4->U5 receives a freshly verified target record.

Before transition:

- validate exact target ref;
- validate target SHA;
- validate target size;
- validate portable identity/platform;
- persist target_artifact_identity.

This is how the current legacy U4 transaction is upgraded in place without a schema migration.

### 5.3 record_predecessor_recovery_and_ha_quiesced

Persist predecessor_recovery_identity from the verified predecessor record.

### 5.4 record_recovery_admission

Remove:

require_same_filesystem_uuid(current usb UUID, observed USB UUID)

Remove:

current measured-capacity exact equality with original post-format measurement

Keep:

- current capacity evidence PASS;
- exact target;
- exact predecessor;
- exact backup;
- production prestate exact;
- recovery free-space admission.

Persist:

ha_data_backup_identity
recovery_content_manifest_sha256

Revalidate target_artifact_identity and predecessor_recovery_identity against the fresh records before U8.

### 5.5 rollback and power-loss classification

record_rollback_complete must no longer accept observed_usb_filesystem_uuid as recovery authority.

Instead require evidence that:

- current media is safe;
- recovery content manifest equals internal expected hash;
- exact predecessor record validates;
- exact HA backup record validates;
- predecessor image restore succeeded;
- HA data restore succeeded.

classify_power_loss_reentry after U9 changes from:

usb_present + same UUID

to:

recovery_media_present + exact_recovery_content_verified

If media absent or exact content cannot be proven:

RECOVERY_MEDIA_REQUIRED

## 6. Media object semantics

tools/n3w_t1_core_updater_ha_prepare.py
tools/n3w_t1_core_updater_ha_prepare_host.py
tools/n3w_t1_core_updater_ha_usb_media.py

PreparedUsbMedia may retain:

locator
public_fingerprint
filesystem_uuid
measured_usable_bytes
mount_path

but all are runtime/session observations.

Within one open media session, UUID/fingerprint/major-minor checks may still be used as TOCTOU protection so the device cannot silently change between inspection and a write.

What is forbidden is comparing those observations to an old transaction and rejecting exact content merely because the physical media changed.

This distinction is mandatory:

same-session anti-swap guard = KEEP
cross-session physical identity continuity = REMOVE

## 7. Replace reopen_bound_media with content-oriented resolution

The old semantic contract:

reopen_bound_media(transaction)
-> find stored UUID
-> require stored fingerprint
-> reopen same physical media

must be replaced by a content-oriented resolver, conceptually:

resolve_transaction_media(
    transaction,
    required_content,
    write_required
) -> PreparedUsbMedia | None

The exact function name may follow repository conventions.

Algorithm:

1. fresh lsblk inventory;
2. consider only USB/removable disks;
3. exclude root/internal device;
4. exclude disks backing production mounts;
5. require safe partition shape;
6. inspect ext4 media;
7. mount unmounted media only at transaction-derived private runtime mount path using nodev,nosuid,noexec;
8. if already mounted, accept only an exact updater-owned runtime mount; mounted elsewhere fails closed;
9. measure effective usable capacity and current free space;
10. inspect required content;
11. select exactly one media satisfying the current content requirement;
12. if zero, return bounded media/content-required state;
13. if more than one exact match, fail closed and ask the user to remove extra media.

Do not use stored UUID/fingerprint as the selection key.

## 8. Stable serial/WWN is no longer required

Current _stable_fingerprint rejects a relevant USB when both serial and WWN are absent.

V1.2 rejects that requirement.

A safe USB without serial/WWN can still satisfy:

- removable USB mass storage;
- not root/internal;
- not production-mounted;
- correct filesystem/layout;
- sufficient capacity;
- exact transaction content.

For destructive formatting, a short-lived selection token may be computed from the current inventory snapshot, including current locator, major:minor, model, size and serial/WWN when available.

That token:

- is not durable transaction identity;
- is not recovery authority;
- is used only to bind the user's confirmation to the exact currently displayed kernel device instance;
- is freshly revalidated immediately before wipefs/sfdisk/mkfs.

Therefore remove the product requirement that every USB expose a stable serial or WWN.

## 9. Newly-inserted requirement is retired as a format authority

Current U1 discovery records baseline fingerprints and only offers a device that appears after the baseline.

V1.2 source design removes this as a hard product requirement.

New destructive-format safety contract:

- exactly one safe eligible removable USB is present;
- user sees model + capacity;
- root/internal/production-mounted devices are excluded;
- explicit erase confirmation is required;
- immediately before wipe, the exact selected current locator + major:minor + model + size/session token are re-enumerated;
- any drift fails closed.

If multiple eligible USB devices are present:

USB_MULTIPLE_ELIGIBLE_DEVICES

The user removes extras and retries.

This is simpler and permits anonymous/low-cost USB devices.

The existing baseline/newly_inserted prepare-state fields may be retired in the source repair after focused compatibility tests prove no current active U1 transaction requires them. The current real transaction is U4, so current live continuity does not depend on the U1 baseline.

## 10. Existing compatible media and formatting

Read-only inspection comes before formatting.

Automatic writable reuse contract:

- safe removable USB;
- expected partition shape;
- ext4;
- product-owned N3W-UPDATE layout;
- sufficient effective usable capacity;
- updater mount/path protections valid.

If exact target/current transaction data already exists, reuse it.

If compatible product media is empty or stale before U9, PREPARE may replace only product-owned transaction content without whole-device formatting.

If media is incompatible or the user requests a clean preparation, existing explicit destructive formatting confirmation remains mandatory.

The N3W-UPDATE label is a product-layout marker, not a physical identity.

## 11. Capacity semantics

tools/n3w_t1_core_updater_ha_capacity.py

Current install revalidation already correctly subtracts target bytes that are already stored.

Keep that behavior.

For reused media, distinguish:

effective_usable_capacity_bytes
current_free_bytes

Recommended statvfs model:

used_bytes =
  (f_blocks - f_bfree) * f_frsize

current_free_bytes =
  f_bavail * f_frsize

effective_usable_capacity_bytes =
  used_bytes + current_free_bytes

This preserves a stable approximation of space usable by the product while files already occupy the filesystem.

The 14 GiB floor applies to effective_usable_capacity_bytes, not to current free bytes.

Phase-specific admission:

PREPARE fresh:
  enough total usable capacity for full transaction formula.

U4/U5 with exact target already stored:
  current_free_bytes >= remaining predecessor + backup + working + reserve requirement.

U8 after target/predecessor/backup already exist:
  current_free_bytes >= working + reserve requirement.

Remove any equality rule requiring current free bytes to equal the original post-format value.

## 12. U4 replacement-media behavior

The current real transaction is U4.

INSTALL flow:

1. resolve current safe media by scan, not stored UUID;
2. inspect target path;
3. if exact target exists:
   - verify full size/SHA/platform;
   - persist target_artifact_identity;
   - run remaining-capacity admission;
   - transition U4->U5.
4. if target absent/corrupt but writable compatible product media exists:
   - do not claim authorization;
   - do not enter U5;
   - clear target_artifact_verified/identity;
   - move U4 back to U3 through one explicit bounded transition;
   - reprepare/download exact target;
   - return to U4 READY_TO_INSTALL.
5. user then starts INSTALL again.

Therefore add one safe backward transition:

U4_READY_TO_INSTALL -> U3_TARGET_DOWNLOADING_VERIFYING

Allowed only when:

- phase is pre-U9;
- production predecessor remains exact/healthy;
- no authorization claimed/consumed;
- no predecessor recovery/backup exists for the active destructive stage;
- reason is target media absent/invalid/reprepare required.

This is preferable to deleting/recreating the transaction.

## 13. U2/U3 resume behavior

Current test/behavior requires the same bound media.

Replace with:

- rediscover safe compatible media;
- if exact/partial current target content can be safely continued, continue;
- if replacement compatible media has no target, prepare target there;
- never reformat another disk automatically;
- formatting remains a separate explicit confirmation path.

For the first implementation, partial download reuse is not required. A stale temporary may be deleted only inside the product-owned target directory and then redownloaded from zero.

## 14. USB-side metadata

Current USB transaction metadata contains UUID/fingerprint.

Keep legacy files readable, but add content authority that is independent of physical media.

Recommended additive file:

/n3w-update/transaction/content-authority.json

It contains:

schema
transaction_id_sha256
release_identity
target_artifact_identity
predecessor_recovery_identity or null
ha_data_backup_identity or null
recovery_content_manifest_sha256 or null

It excludes physical-media identity.

Existing manifest.json may retain observed UUID/fingerprint for diagnostics, but verification must not use them as recovery authority.

sync_transaction_metadata must fsync content-authority.json before any phase transition that depends on it.

At U8, internal transaction and USB content-authority hash must agree before U9 claim.

## 15. IPC/public-state changes

tools/n3w_t1_core_updater_ha_ipc.py

Keep user intents:

PREPARE
CONFIRM_USB_ERASE
INSTALL

Do not expose paths/UUID/fingerprint.

Add/normalize bounded public outcomes as needed:

USB_REQUIRED
USB_MULTIPLE_ELIGIBLE_DEVICES
USB_CAPACITY_INSUFFICIENT
TARGET_REPREPARING
READY_TO_INSTALL
RECOVERY_MEDIA_REQUIRED

A missing/replaced USB at U4 is not a fatal OTA transaction error.

If INSTALL finds no exact target but a writable compatible media is available, public state returns to PREPARING/TARGET_REPREPARING after U4->U3.

## 16. Current live U4 compatibility

The current T1 U4 transaction has:

- exact transaction authority;
- target_artifact_verified=true;
- old UUID/fingerprint fields;
- no target_artifact_identity field.

The first V1.2 source deployment must be able to start and report status without rewriting that file.

Only when INSTALL is requested:

- fresh media discovery runs;
- exact target is fully reverified;
- target_artifact_identity is persisted;
- transition to U5 occurs.

No R12 mount-restoration executor is required.

No format, reset or PREPARE replay is required if current target verifies.

## 17. Source file delta

Primary executable files for the later source-repair gate:

tools/n3w_t1_core_updater_ha_usb_state.py
- additive exact content fields;
- phase-dependent validation;
- recovery manifest verification;
- U4->U3 bounded transition.

tools/n3w_t1_core_updater_ha_usb.py
- persist target/predecessor/backup exact identities;
- remove cross-session UUID continuity gates;
- content-based rollback/power-loss admission.

tools/n3w_t1_core_updater_ha_usb_media.py
- remove stable physical identity as admission authority;
- retain same-session anti-swap checks;
- adjust candidate model as required.

tools/n3w_t1_core_updater_ha_prepare.py
- content-oriented media resolver interface;
- compatible-media reuse;
- U4 reprepare path;
- INSTALL exact target persistence.

tools/n3w_t1_core_updater_ha_prepare_host.py
- scan current safe media instead of stored UUID;
- compatible ext4/product-layout inspection;
- runtime mount resolution;
- anonymous USB support;
- effective usable/current free capacity measurement;
- content-authority metadata.

tools/n3w_t1_core_updater_ha_capacity.py
- explicit total/effective usable vs current free semantics;
- reuse-phase admission helpers if needed.

tools/n3w_t1_core_updater_ha_backup.py
tools/n3w_t1_core_updater_ha_recovery.py
- record serialization helpers may be added;
- no weakening of existing exact validation.

tools/n3w_t1_core_updater_ha_ipc.py
- bounded reprepare/recovery media status projection.

## 18. Tests to change

tests/tools/test_n3w_t1_core_updater_ha_usb_r1.py
- retire same-UUID-as-authority test;
- add target/predecessor/backup identity persistence;
- add content-manifest hash enforcement;
- add post-U9 recovery content tests.

tests/tools/test_n3w_t1_core_updater_ha_usb_r2.py
- synthetic different-media exact-content acceptance;
- blank post-U9 rejection;
- rollback uses exact content, not UUID.

tests/tools/test_n3w_t1_core_updater_ha_prepare_r7a.py
- replace same-bound-media resume contract;
- add different safe media reprepare;
- add old U4 exact-target INSTALL upgrade-in-place;
- add U4->U3->U4 bounded reprepare.

tests/tools/test_n3w_t1_core_updater_ha_prepare_host_r7a.py
- /dev node renumbering;
- different UUID/fingerprint exact target acceptance;
- anonymous USB without serial/WWN;
- safe already-mounted updater runtime media;
- mounted-elsewhere rejection;
- root/production disk rejection;
- same-session device swap rejection.

tests/tools/test_n3w_t1_core_updater_ha_capacity_kf147.py
- effective usable capacity with files already present;
- U4/U5 remaining-space admission;
- U8 remaining reserve admission.

tests/tools/test_n3w_t1_core_updater_ha_ipc.py
- TARGET_REPREPARING projection;
- replacement media is not terminal error;
- no path/UUID/fingerprint exposure.

## 19. Mandatory regression matrix

SOURCE_REPAIR_PASS requires all of:

1. current old-schema U4 document reads unchanged;
2. status on current U4 does not mutate the transaction;
3. same USB /dev/sdb1 -> /dev/sda1 accepted;
4. same USB remove/reinsert accepted;
5. reboot + unmounted media accepted;
6. different UUID/fingerprint with exact target accepted before U9;
7. blank compatible media at U4 causes U4->U3 reprepare, not false U5;
8. corrupt target is never accepted;
9. wrong release target never accepted;
10. anonymous USB without serial/WWN can be safely used;
11. root/internal disk never eligible;
12. production-mounted disk never eligible;
13. multiple eligible disks fail closed;
14. destructive format still requires explicit confirmation;
15. pre-wipe re-enumeration prevents wrong-disk formatting;
16. U5 stores exact target identity;
17. U7 stores exact predecessor identity;
18. U8 stores exact HA backup identity + recovery content manifest hash;
19. U9 impossible without all exact identities;
20. post-U9 same UUID but wrong content is rejected;
21. post-U9 different UUID with exact complete recovery content is accepted;
22. post-U9 blank media returns RECOVERY_MEDIA_REQUIRED;
23. post-U9 blank media is never auto-formatted;
24. power-loss recovery uses exact content authority;
25. rollback PASS requires exact predecessor + exact HA backup restore;
26. authorization remains one-shot/no replay;
27. Manager never receives block-device/path authority;
28. R12 live restoration is not needed by the corrected path;
29. Generic V2 Manager/Broker regression remains unchanged;
30. public repository safety remains clean.

## 20. Implementation order

Recommended bounded source-repair sequence:

A. transaction content identities + validators
B. media resolver + anonymous USB + capacity semantics
C. U4/U3/U5 controller behavior
D. post-U9 recovery/rollback content authority
E. USB-side content-authority metadata
F. IPC/status normalization
G. focused unit/synthetic tests
H. independent source review
I. CI/exact binding
J. fresh real-T1 read-only preexecution

No real T1 mutation should occur before A-I close.

## 21. R11/R12 disposition

R11:
AUTO_RETRY=false
DISPOSITION=HISTORICAL_OLD_MEDIA_CONTINUITY_PATH

R12:
READONLY_PREFLIGHT=VALID_PASS_EVIDENCE
LIVE_MOUNT_RESTORATION=SUPERSEDED_NOT_EXECUTED
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

The corrected source path owns the next live continuation.

## 22. Closure

SOURCE_DESIGN=PASS
SOURCE_DESIGN_FROZEN=true
EXECUTABLE_SOURCE_REPAIR_REQUIRED=true
CURRENT_LIVE_U4_PRESERVABLE=true
DEDICATED_TRANSACTION_MIGRATION_EXECUTOR_REQUIRED=false
R12_LIVE_REQUIRED=false

NEXT_ONE_GATE=REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_REPAIR
NEXT_GATE_MODE=SOURCE_ONLY
LIVE_T1_MUTATION=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
