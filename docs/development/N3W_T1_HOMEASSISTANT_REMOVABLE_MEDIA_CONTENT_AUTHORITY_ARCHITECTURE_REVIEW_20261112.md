
# N3-W T1 Home Assistant removable-media content-authority architecture review
# 2026-11-12

REVIEW=N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_ARCHITECTURE_REVIEW_20261112_01
RESULT=CLOSED_PASS_CHANGE_REQUIRED
SOURCE_REVIEW_ONLY=true
EXECUTABLE_SOURCE_MUTATION=false
T1_MUTATION=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false

CURRENT_LIVE_TRANSACTION_PHASE=U4_READY_TO_INSTALL
CURRENT_R12_PREFLIGHT=PASS
CURRENT_R12_LIVE_EXECUTION=HOLD_SUPERSEDED_BY_ARCHITECTURE_CHANGE

ARCHITECTURE_DIRECTION=REPLACE_PHYSICAL_MEDIA_CONTINUITY_WITH_CONTENT_AUTHORITY
DEVICE_NODE_AUTHORITY=false
FILESYSTEM_UUID_CONTINUITY_AUTHORITY=false
PUBLIC_FINGERPRINT_CONTINUITY_AUTHORITY=false
INTERNAL_TRANSACTION_AUTHORITY=true
EXACT_CONTENT_IDENTITY_AUTHORITY=true

NEXT_ONE_GATE=REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_DESIGN
NEXT_GATE_LIVE_MUTATION=false

## 1. Review question

The user approved an architecture correction:

- Linux device nodes such as /dev/sda1 and /dev/sdb1 are runtime locators only.
- A removable USB device should be admitted by safe removable-media properties, compatible filesystem/layout and sufficient capacity.
- The product should inspect the media for the exact files required by the current transaction.
- T1 reboot, USB removal/reinsertion, or device-node renumbering must not invalidate usable media.
- Physical continuity of one specific USB device is not itself a product requirement.

This review checks whether that correction preserves the safety and rollback properties of the current mandatory-USB Home Assistant OTA design.

## 2. Verdict

The correction is architecturally sound, but it cannot be implemented by merely deleting UUID/fingerprint comparisons.

The current design conflates three concepts:

runtime locator:
  /dev/sdX

media observation:
  filesystem UUID
  device public fingerprint
  model / capacity

transaction recovery authority:
  release identity
  transaction identity
  target archive identity
  predecessor recovery identity
  HA backup identity

Only transaction/content identity must remain durable business authority.

Recommended model:

USB = replaceable storage/recovery carrier

internal durable transaction
+ approved/signed release identity
+ exact artifact identities
= install/recovery authority

Filesystem UUID and public fingerprint may remain as diagnostics and mount-resolution hints, but must not decide whether exact transaction content is acceptable.

## 3. Conflict with frozen V1.1

Current architecture V1.1 explicitly requires:

- T1 formatting for every HA version update;
- transaction binding to filesystem UUID;
- a different USB device must never be accepted as active recovery authority;
- U5 and U8 require the same bound UUID;
- post-U9 recovery requires reinsertion of the same filesystem UUID.

Current source implements those rules:

- record_media_bound persists public fingerprint + filesystem UUID;
- transaction validation requires both from U2 onward;
- reopen_bound_media locates by the stored UUID and requires the stored fingerprint;
- _require_bound_media rejects UUID/fingerprint changes;
- record_recovery_admission requires the same UUID;
- record_rollback_complete requires the same UUID;
- classify_power_loss_reentry requires the same UUID after U9.

Therefore the proposed correction is a real architecture change, not an R12-only harness fix.

## 4. Safety invariants that remain

The following remain fail-closed:

- USB/removable mass-storage requirement;
- root/internal system-disk exclusion;
- production-mount exclusion;
- read-only rejection for write phases;
- exactly-one eligible-media rule unless separately redesigned;
- ext4 product filesystem contract;
- nodev,nosuid,noexec mount policy;
- symlink/path traversal protection;
- measured capacity admission;
- approved release authority;
- target archive size + SHA-256 + platform identity;
- predecessor recovery exact identity;
- HA backup integrity + confidentiality + authenticity;
- production predecessor/runtime revalidation;
- U9 one-shot authorization boundary;
- no broad Docker prune;
- rollback requires both predecessor image and HA data.

## 5. Correct media-admission model

### 5.1 Locator

/dev/sdX is never durable authority. It is resolved freshly from current block inventory each time media is accessed.

### 5.2 Compatible product media

For automatic product reuse, media should satisfy:

- removable USB mass storage;
- not root/internal storage;
- not backing production mounts;
- expected partition shape;
- ext4;
- label N3W-UPDATE;
- safe mount options;
- capacity sufficient for remaining transaction work.

The label is a product ownership/layout marker, not physical identity.

### 5.3 Existing media before formatting

An already compatible N3W-UPDATE filesystem should be inspected before destructive formatting.

If exact content for the current transaction is present and valid, reuse it.

If compatible media is empty, stale or invalid:

- before U9: it may be re-prepared under normal bounded user confirmation/ownership rules;
- after U9: never auto-format or erase it, because recovery content may be the only remaining predecessor authority.

A generic incompatible USB may still use the existing explicit destructive-format path.

USB_FORMAT_REQUIRED_FOR_EVERY_HA_VERSION_UPDATE=false
USB_FORMAT_REQUIRED_WHEN_MEDIA_INCOMPATIBLE_OR_CLEAN_PREPARE_SELECTED=true
EXISTING_COMPATIBLE_MEDIA_READONLY_INSPECTION=true

## 6. Content authority by phase

### U0-U3

Any safe compatible media may carry preparation data. If the target is absent or invalid, T1 downloads/prepares it again while production HA remains intact.

### U4 READY_TO_INSTALL

READY_TO_INSTALL is valid only when the current medium freshly proves:

- current transaction/release;
- exact target path/type;
- target archive size;
- target archive SHA-256;
- target platform/image identity;
- capacity for remaining U5-U8 work.

A changed device node, UUID or public fingerprint does not invalidate exact target content.

A blank replacement USB invalidates media readiness but does not corrupt the OTA transaction: return to preparation while production HA remains authoritative.

### U5-U8

Freshly admit current media and revalidate target. Then write and verify predecessor recovery archive, HA pre-upgrade backup, and transaction/recovery metadata.

At U8 the complete recovery content set, not physical identity, is authority.

### U9-U12

After destructive claim, a blank replacement disk must never be accepted simply because ext4/capacity pass.

Accept recovery media only when it contains the exact recovery set expected by the internal durable transaction.

same physical USB required=false
same filesystem UUID required=false
exact transaction recovery set required=true

If no exact recovery set exists:

RECOVERY_MEDIA_REQUIRED=true
AUTO_FORMAT_OTHER_USB=false
AUTO_REPLAY=false

A content-equivalent copy on another safe compatible USB may be accepted after full verification.

## 7. Required durable transaction change

This is the critical source-design requirement.

Current U8 persists predecessor/backup state only as booleans:

predecessor_recovery_verified=true
ha_data_backup_verified=true

That is insufficient once physical UUID continuity is removed.

Before U9, internal durable state must persist exact expected recovery identities, at minimum:

predecessor_image_ref
predecessor_archive_sha256
predecessor_archive_size_bytes
predecessor_portable_identity_sha256

ha_backup_archive_sha256
ha_backup_archive_size_bytes
ha_backup_manifest_sha256

target_archive_sha256
target_archive_size_bytes
target_portable_identity_sha256

recovery_content_manifest_sha256

Existing ImageRecoveryRecord and HaDataBackupRecord already expose nearly all required identities. Source repair should persist them instead of reducing them to booleans.

USB-side transaction metadata remains a durable mirror/recovery aid, not sole authority.

## 8. Capacity rule

Enough capacity must be phase-aware.

For fresh empty media, the existing full transaction formula remains valid.

For reused media containing already verified content, admission must account for:

verified bytes already present
+ current free bytes
+ remaining required writes
+ working/reserve budget

The product must not require the original post-format free-byte value after legitimate target/predecessor/backup files have consumed space.

Exact formula is deferred to the V1.2 source-design gate.

## 9. User experience

insert USB
-> T1 checks it
-> usable/current content exists: continue
-> preparation required: T1 prepares it
-> destructive formatting required: ask once with clear warning
-> READY_TO_INSTALL
-> user starts update

The user never selects device node, UUID, fingerprint, mount path, Docker image or file path.

## 10. Current R12 disposition

R12 was correct for old V1.1 same-media authority and its read-only preflight remains valid historical evidence.

Executing R12 live now would restore the old UUID/fingerprint-bound mount solely to satisfy an architecture rule this review retires.

R12_READONLY_PREFLIGHT=VALID_PASS_EVIDENCE
R12_LIVE_MOUNT_RESTORATION=HOLD_SUPERSEDED
R12_AUTHORIZATION_GRANTED=false
R12_AUTHORIZATION_CLAIMED=false
R12_AUTHORIZATION_CONSUMED=false
AUTO_RETRY_R11=false

Preferred successor: product source repair where U4->U5 freshly discovers safe media, mounts current runtime media, and validates content authority.

## 11. Compatibility with current live U4 transaction

Current T1 is already U4 under the old schema.

Preferred migration:

1. retain old UUID/fingerprint fields as historical/diagnostic data;
2. stop using them as continuity authority;
3. freshly discover present safe media;
4. verify current target by exact hash/size/platform against internal transaction;
5. allow U4->U5 only after content revalidation;
6. persist new predecessor/backup identities before U9.

This avoids destructive reset, reformat, or replay of earlier confirmation.

## 12. Primary source impact

tools/n3w_t1_core_updater_ha_usb.py
tools/n3w_t1_core_updater_ha_usb_state.py
tools/n3w_t1_core_updater_ha_usb_media.py
tools/n3w_t1_core_updater_ha_prepare.py
tools/n3w_t1_core_updater_ha_prepare_host.py
tools/n3w_t1_core_updater_ha_backup.py
tools/n3w_t1_core_updater_ha_recovery.py

IPC/public state should need only bounded status/error changes. Manager must not gain device-path authority.

R11/R12 execution packages become historical/superseded for live continuation after the V1.2 source successor is exact-bound.

## 13. Minimum regression matrix

1. same USB /dev/sdb1 -> /dev/sda1 accepted after content validation;
2. same USB removed/reinserted accepted;
3. T1 reboot with unmounted compatible media rediscovered;
4. different physical USB with exact target before U9 accepted;
5. blank compatible replacement before U9 enters reprepare, not false READY;
6. corrupt/wrong target rejected;
7. wrong release/transaction content rejected;
8. root/internal disk never selected;
9. production-mounted device never selected;
10. read-only media rejected for write phases;
11. multiple ambiguous media fail closed;
12. U8 persists exact predecessor + backup identities;
13. different UUID after U9 with exact complete recovery set accepted;
14. different UUID after U9 with missing/corrupt recovery content returns RECOVERY_MEDIA_REQUIRED;
15. blank replacement after U9 never auto-formatted;
16. content tamper rejected;
17. backup confidentiality/authenticity preserved;
18. no second live authorization claim/replay;
19. current old-schema U4 transaction migrates without destructive reset;
20. R12 live restoration not required by corrected product path.

## 14. Closure

ARCHITECTURE_REVIEW=CLOSED_PASS
USER_APPROVED_DIRECTION=YES
PHYSICAL_MEDIA_IDENTITY_AS_BUSINESS_AUTHORITY=REJECTED
CONTENT_AUTHORITY_MODEL=ACCEPTED
SOURCE_REPAIR_REQUIRED=true

NEXT_ONE_GATE=REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_DESIGN
LIVE_T1_MUTATION=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
