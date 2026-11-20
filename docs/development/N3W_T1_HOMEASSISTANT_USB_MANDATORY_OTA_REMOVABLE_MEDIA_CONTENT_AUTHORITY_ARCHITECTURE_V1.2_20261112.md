
# N3-W T1 Home Assistant USB mandatory OTA removable-media content-authority architecture V1.2
# 2026-11-12

STATUS=ARCHITECTURE_V1_2_FROZEN
SUPERSEDES_MEDIA_IDENTITY_RULES_OF=V1.1_20261106
PRESERVES_OTHER_V1_1_SAFETY_RULES=true

## 0. Decision summary

HOMEASSISTANT_UPDATE_USB_REQUIRED=true
USB_PHYSICAL_DEVICE_CONTINUITY_REQUIRED=false
USB_DEVICE_NODE_CONTINUITY_REQUIRED=false
USB_FILESYSTEM_UUID_CONTINUITY_REQUIRED=false
USB_PUBLIC_FINGERPRINT_CONTINUITY_REQUIRED=false

USB_FILESYSTEM_REQUIRED=ext4
USB_PRODUCT_LABEL=N3W-UPDATE
USB_EXISTING_COMPATIBLE_MEDIA_INSPECTION=true
USB_FORMAT_REQUIRED_FOR_EVERY_HA_VERSION_UPDATE=false
USB_FORMAT_IF_INCOMPATIBLE_OR_CLEAN_PREPARE=true
DESTRUCTIVE_FORMAT_CONFIRMATION_REQUIRED=true

INTERNAL_TRANSACTION_IS_PRIMARY_AUTHORITY=true
EXACT_CONTENT_IDENTITY_IS_RECOVERY_AUTHORITY=true
USB_SIDE_METADATA_IS_MIRROR_NOT_SOLE_AUTHORITY=true

TARGET_EXACT_VERIFY_REQUIRED=true
PREDECESSOR_EXACT_VERIFY_REQUIRED_BEFORE_U9=true
HA_BACKUP_EXACT_VERIFY_REQUIRED_BEFORE_U9=true
BACKUP_CONFIDENTIALITY_AUTHENTICITY_REQUIRED=true

R12_LIVE_MOUNT_RESTORATION=SUPERSEDED_NOT_EXECUTED
AUTO_RETRY_R11=false

## 1. Product model

The USB device is removable storage and recovery transport. It is not a permanent transaction identity.

The product distinguishes:

runtime locator:
  current /dev/sdX path

media properties:
  removable USB
  filesystem/layout
  label
  writable state
  current free/usable capacity
  UUID/fingerprint as observations

transaction authority:
  transaction ID
  approved release identity
  exact target identity
  exact predecessor recovery identity
  exact HA backup identity

A runtime locator or media observation may change without invalidating content.

## 2. Safe media admission

A candidate must remain fail-closed against:

- internal/root device;
- production-mounted storage;
- non-USB/non-removable media;
- read-only media for any phase that needs writes;
- incompatible partition/filesystem layout;
- unsafe mount options;
- ambiguous multiple eligible media unless a later product rule explicitly resolves it.

For automatic compatible-media reuse:

- expected partition shape;
- ext4 filesystem;
- product label N3W-UPDATE;
- current measured capacity/free-space contract passes.

The label marks product-managed layout. It is not physical identity.

## 3. Existing compatible media

T1 first performs bounded read-only inspection.

If current transaction content is exact, reuse the media without formatting.

If content is absent/stale/corrupt:

before U9:
  production HA remains authoritative;
  current media may be re-prepared;
  incompatible media may be formatted only after explicit destructive confirmation.

after U9:
  never automatically format or erase candidate media;
  exact recovery content may be the only remaining predecessor authority.

## 4. Content authority

### 4.1 Target

Target acceptance requires:

- expected target image ref;
- expected archive size;
- expected archive SHA-256;
- expected portable image identity;
- linux/arm64 platform;
- approved release/manifest compatibility;
- fsync/durability contract.

### 4.2 Predecessor recovery

Before U9, persist and verify:

- predecessor image ref;
- predecessor archive SHA-256;
- archive size;
- portable identity;
- platform;
- durability.

### 4.3 HA backup

Before U9, persist and verify:

- backup archive SHA-256;
- backup archive size;
- backup manifest SHA-256;
- consistent pre-upgrade point;
- complete production config coverage;
- storage integrity;
- ownership metadata;
- confidentiality protection;
- authenticity protection;
- unsupported external state=false.

## 5. Internal durable state

V1.2 requires the internal transaction to carry exact recovery identities, not only verification booleans.

Required content fields by U8:

target_archive_sha256
target_archive_size_bytes
target_portable_identity_sha256

predecessor_image_ref
predecessor_archive_sha256
predecessor_archive_size_bytes
predecessor_portable_identity_sha256

ha_backup_archive_sha256
ha_backup_archive_size_bytes
ha_backup_manifest_sha256

recovery_content_manifest_sha256

Existing UUID/fingerprint fields may remain during migration as diagnostic/historical values, but they must not be used as continuity gates.

## 6. State-machine semantics

U0 READONLY_ADMISSION
  unchanged.

U1 PREPARE_REQUESTED
  discover safe media.
  inspect compatible existing product media before formatting.

U2 MEDIA_QUALIFIED
  semantic replacement for old USB_QUALIFIED_FORMATTED_BOUND.
  formatting is one route, not mandatory every time.

U3 TARGET_DOWNLOADING_VERIFYING
  verify existing exact target or prepare/download it.

U4 READY_TO_INSTALL
  target content exact.
  media identity continuity is not required.
  current capacity for remaining work must pass.

U5 INSTALL_REQUESTED_REVALIDATING
  rediscover currently present safe media.
  mount current runtime partition.
  revalidate target exactness.
  do not require old UUID/fingerprint.

U6 PREDECESSOR_RECOVERY_PREPARING
  export and verify predecessor recovery content.

U7 HA_QUIESCED_DATA_BACKUP_PREPARING
  create and verify protected HA backup.

U8 RECOVERY_ADMISSION_COMPLETE
  persist exact target + predecessor + backup identities.
  verify current recovery content set and capacity.
  no physical identity requirement.

U9 LIVE_AUTHORIZATION_CLAIMED
  unchanged one-shot destructive boundary.

U10-U12
  recovery authority is exact content set.
  no automatic media formatting.

U13A COMMITTED
  USB may be removed after durable commit.

U13B ROLLED_BACK
  rollback PASS requires exact predecessor restore + exact HA backup restore.

## 7. Replacement-media rules

Before U9:

same physical USB required=false
same UUID required=false
same fingerprint required=false

If replacement media lacks exact target:
  reprepare target while old production remains safe.

After U9:

same physical USB required=false
same UUID required=false
exact complete recovery set required=true

A cloned/content-equivalent compatible USB may be accepted only after full exact verification.

A blank compatible USB is not recovery media.

If exact recovery content is absent:

RECOVERY_MEDIA_REQUIRED=true
AUTO_FORMAT_OTHER_USB=false
AUTO_REPLAY=false

## 8. Capacity

The 14 GiB measured floor remains a product floor unless separately changed.

Fresh empty-media admission may use the existing complete-transaction formula.

Reused media requires phase-aware remaining-capacity admission:

current verified content
+ current free space
+ remaining required writes
+ working/reserve budget

must prove the transaction can complete.

Original post-format free-byte equality is not a media identity rule and must not be required after legitimate content has consumed space.

## 9. Power loss and reboot

Before U9:
  internal predecessor remains authority.
  reboot/rescan may use any safe compatible media.
  exact target may be reused or rebuilt.

After U9:
  boot classifies durable transaction before normal HA activation.
  locate safe compatible media.
  verify exact recovery content against internal transaction.
  resume forward/rollback only after content authority passes.

Device-node renumbering, UUID change, or fingerprint change alone is never a recovery failure.

## 10. Privilege boundary

Unchanged:

- greenhouse-manager never receives block-device path authority;
- MQTT/UI never supplies /dev path, UUID, fingerprint, mount path or shell command;
- privileged host code independently enumerates and validates media;
- no arbitrary path/Docker argument injection.

## 11. Current U4 migration

The current live transaction is U4 under the older schema.

V1.2 requires non-destructive forward migration:

- preserve target/release/transaction identity;
- retain old UUID/fingerprint fields only as historical observations;
- freshly enumerate current safe media;
- verify exact target content;
- advance through corrected U5 path;
- persist predecessor/backup exact identities before U9.

Do not reset transaction, reformat media, or replay old destructive confirmation merely to adopt V1.2.

## 12. Current R12/R11 disposition

R12 read-only PASS remains valid evidence that:

- current transaction is exact U4;
- current media is present and unmounted;
- device-node renumbering occurred without content/state loss;
- runtime remains stable.

R12 live mount restoration is superseded and must not execute under V1.2.

R11 must not be automatically retried. Its old precondition is replaced by corrected U4->U5 product revalidation.

## 13. Acceptance requirements

Source design/implementation must cover at least:

- device-node renumbering;
- reboot;
- remove/reinsert;
- different physical media with exact content;
- pre-U9 blank replacement reprepare;
- post-U9 blank replacement rejection;
- post-U9 exact content-equivalent replacement acceptance;
- target tamper;
- predecessor tamper;
- backup tamper;
- root/production disk rejection;
- ambiguous media;
- protected backup contract;
- one-shot authorization;
- old U4 migration;
- power-loss classification;
- rollback image + data restore.

## 14. Next gate

NEXT_ONE_GATE=REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_DESIGN
SOURCE_MUTATION=false
LIVE_T1_MUTATION=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
