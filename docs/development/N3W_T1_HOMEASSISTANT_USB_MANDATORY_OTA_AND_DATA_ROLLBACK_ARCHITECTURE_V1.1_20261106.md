# N3-W T1 Home Assistant USB-Mandatory OTA + Data Rollback Architecture V1.1

DATE=2026-11-06
STATUS=ARCHITECTURE_V1_1_FROZEN_SOURCE_IMPLEMENTATION_NOT_STARTED
PRODUCT_SCOPE=N3-W T1 / Home Assistant Container / 16GB-class internal storage

> V1.1 supersedes V1.0 for future product/source design. V1.0 remains historical evidence of the earlier conditional-USB/OCI-terminal proposal.
PRIMARY_REASON=all Home Assistant version upgrades must avoid dual internal image residency and use one uniform removable-media transaction on the current ~14.45GB root filesystem

## 0. Decision summary

```text
NORMAL_RUNNING_HA_IMAGE_COUNT_INTERNAL=1
HOMEASSISTANT_UPDATE_USB_REQUIRED=true
USB_FILESYSTEM_REQUIRED=ext4
USB_FORMAT_OWNER=T1
USB_FORMAT_REQUIRED_FOR_EVERY_HA_VERSION_UPDATE=true
USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=15032385536
USB_NOMINAL_CAPACITY_NOT_AUTHORITY=true
RECOMMENDED_MARKET_USB_SIZE=32GB_OR_LARGER
USER_PRELOAD_REQUIRED=false
USER_COMPUTER_REQUIRED=false

PRIMARY_HA_OTA_TRANSFER_ARTIFACT=EXACT_COMPRESSED_HA_ARCHIVE
OFFLINE_RECOVERY_ARTIFACT=RETAIN_SAME_ARTIFACT_FAMILY
OFFLINE_RECOVERY_ARTIFACT_CURRENT_FORM=homeassistant-arm64.tar.gz

UPDATE_DISCOVERY_OWNER=N3W_T1_OTA_MANAGER
UPDATE_VERSION_AUTHORITY=N3W_OTA_SERVER_APPROVED_MANIFEST
HOMEASSISTANT_NOTIFICATION_SURFACE=MQTT_UPDATE_ENTITY

TARGET_DOWNLOAD_BEFORE_INSTALL_CONFIRMATION=true
TARGET_FULL_VERIFY_BEFORE_INSTALL_CONFIRMATION=true
USER_INSTALL_CONFIRMATION_AFTER_TARGET_READY=true
PREDECESSOR_EXPORT_AFTER_INSTALL_CONFIRMATION=true

HA_DATA_BACKUP_REQUIRED_BEFORE_DESTRUCTIVE_CUTOVER=true
SUCCESS_PATH_RESTORE_PREUPGRADE_DATA_BACKUP=false
ROLLBACK_PATH_RESTORE_PREUPGRADE_DATA_BACKUP=true

CURRENT_P5_REAPPLY=HOLD_BEFORE_CLAIM
CURRENT_P5_AUTHORIZATION_REUSABLE_WHILE_UNCLAIMED=true
SOURCE_IMPLEMENTATION_STARTED=false
```

The product must not depend on a user computer for ordinary updates. Every Home Assistant version update requires a removable USB device. The T1 owns update discovery, removable-media formatting, target download, integrity verification, predecessor export, HA data backup, cutover, health validation and rollback.

## 1. Why the architecture changes

Fresh T1 evidence on 2026-11-06 showed:

```text
ROOT_TOTAL_BYTES=14453903360
ROOT_AVAILABLE_BYTES≈572MB
ROOT_USAGE≈97%

HA_PREDECESSOR=local/n3w-homeassistant:2026.10.0-0c73235a
HA_PREDECESSOR_UNIQUE_SIZE≈5.224GB

HA_TARGET=local/n3w-homeassistant:2026.10.4-5881590f
HA_TARGET_UNIQUE_SIZE≈5.221GB

DUAL_HA_IMAGE_RESIDENCY≈10.445GB_UNIQUE
```

The current reapply capacity gate correctly stopped before authorization claim and before T1 mutation.

The current product must therefore stop assuming that both HA generations can reside internally during every upgrade.

## 2. Product north star

The user experience is one uniform path for every Home Assistant version update:

```text
T1发现经N3-W批准的新版本
-> Home Assistant界面显示“有可用更新”
-> 用户选择“准备升级”
-> 提示插入可清空的U盘
-> 用户确认U盘全部数据会被删除
-> T1整盘格式化为ext4
-> T1检查格式化后的实际可用容量 >= 14 GiB
-> T1把exact target archive直接下载到U盘
-> T1完整验证目标版本/大小/SHA-256/签名/平台/镜像身份
-> Home Assistant继续正常运行
-> UI显示“升级包已准备完成，可以开始升级”
-> 用户点击“开始升级”
-> T1导出旧HA镜像到U盘并验证
-> T1停止/静默HA并创建一致性的HA_DATA_BACKUP到U盘
-> 三份恢复/安装材料全部验证后才删除内部旧HA镜像
-> 从U盘加载新HA镜像
-> 挂回production /config并启动
-> 健康验证
-> 成功提交，或自动恢复旧镜像+旧数据
```

The user must not need to understand Docker, OCI, tar archives, SSH, ext4, image digests or rollback mechanics.

The product deliberately uses one update path even when internal free space would temporarily be sufficient. This avoids maintaining two materially different upgrade behaviors and guarantees that every update has external recovery media before destructive cutover.

## 3. OTA discovery, notification and transfer

### 3.1 Update discovery authority

Home Assistant Container does not own the product-level outer-container update lifecycle. N3-W therefore owns update discovery:

```text
N3W_T1_OTA_MANAGER
-> periodic HTTPS query
-> N3W OTA approved manifest
-> compare installed version with latest approved version
```

The manifest version is the latest version approved by N3-W validation, not automatically the newest upstream Home Assistant release.

Conceptual manifest fields include:

```text
installed_version
latest_approved_version
artifact_size
artifact_sha256
artifact_signature
artifact_download_locator
release_summary
compatibility_policy
rollout_policy
```

### 3.2 Home Assistant notification surface

The T1 OTA Manager publishes update state into Home Assistant as an MQTT Update entity.

Minimum user-visible states:

```text
UP_TO_DATE
UPDATE_AVAILABLE
USB_REQUIRED
PREPARING_UPDATE
READY_TO_INSTALL
INSTALLING
VERIFYING
COMMITTED
ROLLING_BACK
ROLLED_BACK
RECOVERY_MEDIA_REQUIRED
```

The Home Assistant UI is the notification/control surface. The actual update authority remains the T1 OTA Manager.

### 3.3 Primary transfer artifact

For the current 16GB-class T1 product:

```text
PRIMARY_HA_OTA_TRANSFER_ARTIFACT=EXACT_COMPRESSED_HA_ARCHIVE
OFFLINE_RECOVERY_ARTIFACT=RETAIN_SAME_ARTIFACT_FAMILY
```

The exact compressed Home Assistant archive is published by the N3-W OTA service/CDN after upstream source/digest/platform verification.

The T1 downloads the archive directly to the ext4 USB device. The target archive must not first be staged on the internal root filesystem.

OCI/registry remains useful in the build/release backend and for source provenance, but direct OCI layer pull into the T1 internal image store is not the primary product update path in V1.1.

## 4. USB ownership and formatting policy

### 4.1 Mandatory T1-managed formatting

For every Home Assistant version update:

```text
HOMEASSISTANT_UPDATE_USB_REQUIRED=true
USB_FILESYSTEM_REQUIRED=ext4
USER_PREPARED_COMPATIBLE_FILESYSTEM_ACCEPTED=false
AUTO_USE_EXISTING_FILESYSTEM=false
FORMAT_REQUIRED=true
DESTRUCTIVE_CONFIRMATION_REQUIRED=true
USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=15032385536
USB_NOMINAL_CAPACITY_NOT_AUTHORITY=true
RECOMMENDED_MARKET_USB_SIZE=32GB_OR_LARGER
```

The product must display a clear warning before formatting:

```text
“此U盘中的全部数据将被删除，并专用于本次系统升级与恢复。是否继续？”
```

Only after explicit confirmation may formatting begin.

### 4.2 Safe target selection

Before format, the T1 must prove all of the following:

- exactly one eligible newly inserted removable USB mass-storage device is selected;
- selected device is not the root/internal system device;
- no selected partition backs current production mounts;
- device identity/capacity shown to the user matches the selected target;
- device is not read-only;
- formatting succeeds as ext4 and the measured usable capacity is at least 14 GiB (15,032,385,536 bytes);
- capacity is sufficient for the complete transaction admission formula.

Ambiguity must fail closed.

### 4.3 Proposed disk layout

V1:

```text
GPT
└── single ext4 partition
    label=N3W-UPDATE
```

The ext4 journal remains enabled.

Suggested mount options:

```text
nodev,nosuid,noexec,noatime
```

The transaction binds the filesystem UUID. A different USB device must never be accepted as the active recovery authority.

## 5. What T1 writes to the USB

The user does not prepare any update/recovery asset.

After T1 formats the USB as ext4, it creates and owns the transaction contents:

```text
/n3w-update/
├── transaction/
│   ├── manifest.json
│   ├── phase.json
│   └── checksums.json
├── target/
│   ├── homeassistant-arm64.tar.gz
│   └── identity.json
├── predecessor/
│   ├── image-recovery.*
│   └── identity.json
└── backup/
    └── ha-data-backup.*
```

Preparation and installation are intentionally separated.

### 5.1 Preparation stage

While the current Home Assistant remains running:

```text
format/qualify USB
-> download exact target archive directly to USB
-> verify target artifact completely
-> fsync target + metadata
-> transaction=READY_TO_INSTALL
-> notify user that preparation is complete
```

At this point:

- predecessor image is still internal and unchanged;
- production /config is unchanged;
- no Home Assistant service interruption is required;
- no one-shot live install authorization is consumed.

### 5.2 Installation stage

Only after the user explicitly selects “开始升级”:

```text
revalidate same USB + target
-> export predecessor image directly to USB
-> verify predecessor recovery package
-> quiesce Home Assistant
-> create consistent HA_DATA_BACKUP directly to USB
-> verify + fsync
-> final recovery admission
-> destructive internal cutover
```

Exact filenames/formats remain implementation details; these phase semantics are frozen by this document.

## 6. Predecessor image recovery asset

Before destructive cutover, T1 must create a restorable predecessor image package directly on USB.

Conceptual implementation:

```text
current exact predecessor image
-> docker save stream
-> compression stream
-> USB
-> fsync
-> SHA-256 / size / image identity verification
```

No full predecessor archive should first be staged on the internal filesystem.

PASS requires that the recovery package can be independently identified as the exact current predecessor.

The predecessor recovery package is not the same as merely retaining a Docker tag.

## 7. Target artifact

The existing exact Home Assistant archive is retained.

Current frozen target example:

```text
homeassistant-arm64.tar.gz
archive_size_bytes=835309535
archive_sha256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
```

Its roles become:

```text
PRIMARY_HA_OTA_TRANSFER_ARTIFACT
OFFLINE_RECOVERY_ARTIFACT
USB_STAGED_TARGET_ARTIFACT
```

For every Home Assistant version update, T1 downloads the exact target artifact directly to the ext4 USB device and fully verifies it before telling the user that installation can start.

Ordinary users do not download/copy this archive with a computer.

A separate future service/offline-recovery workflow may use the same artifact family.

## 8. HA_DATA_BACKUP semantics

### 8.1 Required scope

Before deleting the internal predecessor image, the transaction must hold a complete pre-upgrade Home Assistant data recovery point on USB.

For the current product baseline this must cover at minimum:

- complete persistent `/config`;
- default Home Assistant SQLite database/history when used;
- storage/integration state under `/config`;
- all product-owned HA persistent files required to reproduce the pre-upgrade state.

External database use is not silently assumed.

V1 must fail closed if an externally hosted HA database or unsupported external state is detected and no matching snapshot adapter exists.

### 8.2 Consistency rule

A rollback backup must represent one internally consistent pre-upgrade point.

Preferred transaction sequence:

```text
target artifact verified on USB
predecessor recovery image verified on USB
USB capacity still PASS
-> quiesce Home Assistant
-> create HA_DATA_BACKUP directly to USB
-> fsync
-> integrity verification
-> only then allow destructive internal image removal
```

The exact backup encoding may be Home Assistant-native or an N3W-owned quiesced snapshot, but it must satisfy the same restore contract. The implementation choice is deferred to the P5 impact/source-design gate.

Home Assistant official guidance is treated as a product constraint: downgrading an image alone may be insufficient because a newer release can change database/integration data; rollback must restore data from the old-version recovery point.

### 8.3 Success-path rule

```text
SUCCESS_PATH_RESTORE_PREUPGRADE_DATA_BACKUP=false
```

After target container creation, it mounts the preserved production `/config`.

If the new HA version successfully migrates the data and passes health validation, that migrated state is the new canonical state.

Restoring the pre-upgrade backup after a successful target start would overwrite valid migration results and can discard post-start changes. It is therefore forbidden by default.

### 8.4 Rollback rule

```text
ROLLBACK_PATH_RESTORE_PREUPGRADE_DATA_BACKUP=true
```

If the target cannot be accepted:

```text
stop/quiesce target
-> remove failed target runtime
-> remove target internal image when required for capacity
-> restore exact predecessor image from USB
-> restore HA_DATA_BACKUP to the pre-upgrade state
-> restore predecessor binding/runtime contract
-> start predecessor
-> verify full health
```

Rollback PASS requires both image and data recovery.

## 9. USB-mandatory transaction state machine

### Phase U0 — update discovery and read-only admission

Verify:

- production baseline healthy;
- current HA exact predecessor identity;
- approved target authority available from N3-W OTA manifest;
- no active updater transaction.

Publish/update the MQTT Update entity.

No USB or production mutation.

### Phase U1 — user selects “准备升级”

Require removable USB media.

The product explains that the device will be erased and recommends 32GB or larger.

### Phase U2 — USB selection, destructive confirmation and format

- detect exactly one eligible removable disk;
- display device model/capacity;
- user confirms all contents may be erased;
- bind selected device identity;
- create GPT + single ext4 partition;
- mount by filesystem UUID;
- perform bounded write/fsync/read/hash self-test;
- require measured usable capacity >= 14 GiB;
- run the full transaction-capacity formula.

Failure here leaves production unchanged.

### Phase U3 — download and verify target

While Home Assistant remains running:

- download exact target archive directly to USB;
- verify approved version;
- verify size and SHA-256;
- verify signature/provenance contract;
- verify target image identity and linux/arm64 platform;
- fsync target and metadata.

### Phase U4 — READY_TO_INSTALL stop point

Require:

```text
TARGET_ARTIFACT_VERIFIED=true
USB_FILESYSTEM=ext4
USB_UUID_BOUND=true
USB_MEASURED_USABLE_CAPACITY_PASS=true
PRODUCTION_PRESTATE_STILL_HEALTHY=true
```

Publish:

```text
UPDATE_STATE=READY_TO_INSTALL
USER_MESSAGE=升级包已下载并验证完成，可以开始升级
```

No predecessor export, HA stop, HA data backup or internal image deletion occurs before the user starts installation.

### Phase U5 — user selects “开始升级”

Freshly revalidate:

- same bound USB UUID;
- target artifact still exact;
- current production predecessor still exact/healthy;
- live install authorization state is eligible and unconsumed.

### Phase U6 — prepare predecessor recovery image

With current Home Assistant still running:

- export exact current predecessor image directly to USB;
- compress/stream without internal full-copy staging;
- verify restorable image identity;
- fsync.

### Phase U7 — quiesce and create HA data recovery point

- quiesce Home Assistant using production owner semantics;
- create consistent HA_DATA_BACKUP directly to USB;
- verify archive/snapshot/database integrity;
- fsync data + metadata;
- persist transaction phase internally and on USB.

### Phase U8 — final pre-destructive recovery admission

Require simultaneously:

```text
TARGET_ARTIFACT_VERIFIED=true
PREDECESSOR_RECOVERY_VERIFIED=true
HA_DATA_BACKUP_VERIFIED=true
USB_FILESYSTEM=ext4
USB_UUID_BOUND=true
USB_CAPACITY_PASS=true
PRODUCTION_PRESTATE_EXACT=true
AUTHORIZATION_NOT_CONSUMED=true
```

Any failure stops before internal predecessor deletion.

### Phase U9 — destructive claim boundary

Only now may the updater consume the one-shot live installation authorization.

After claim, replay is forbidden.

### Phase U10 — free internal predecessor capacity

- remove predecessor container/runtime object as required;
- remove predecessor image from internal image store;
- verify expected reclaimed space;
- do not delete Manager/Broker images or unrelated data.

The predecessor remains recoverable from USB.

### Phase U11 — install target

- load exact target archive from USB into the internal image store;
- verify runtime image identity;
- publish target binding;
- recreate HA container using the preserved production /config.

### Phase U12 — target health acceptance

Verify at minimum:

- exact target image;
- expected binding/network/runtime contract;
- required listeners;
- HA HTTP readiness;
- HA MQTT readiness;
- Manager/Broker peer continuity;
- no unexpected restart loop;
- migrated production /config is usable;
- HA readiness budget appropriate for real recreate duration.

### Phase U13A — success commit

On PASS:

```text
transaction=COMMITTED
current_internal_ha_image=target
preupgrade_data_backup=retained_on_USB
predecessor_recovery_package=retained_on_USB
```

Do not restore the old data backup.

User may be told the update is complete and the USB can be removed only after commit evidence is durable.

### Phase U13B — automatic rollback

On target failure after destructive claim:

```text
transaction=ROLLBACK_IN_PROGRESS
-> target cleanup
-> predecessor image restore from USB
-> HA_DATA_BACKUP restore
-> predecessor runtime activation
-> health verification
```

PASS result:

```text
transaction=ROLLED_BACK
runtime=PREDECESSOR_BOUND_RUNNING
health=HEALTHY
data_state=PREUPGRADE_RECOVERY_POINT
```

## 10. Power-loss and USB-removal behavior

Transaction state must be durably recorded both internally and on the bound USB before each destructive phase transition.

If power is lost:

- before U9: production predecessor remains authoritative unless HA is temporarily quiesced for backup; no internal predecessor image has been deleted;
- after U9: boot must enter transaction recovery classification before normal HA activation;
- if the bound USB is present, resume forward/rollback according to durable phase;
- if the bound USB is missing, do not claim recovery success and do not invent a replacement device.

If USB is removed after the U9 destructive claim / predecessor internal image deletion:

```text
RECOVERY_MEDIA_REQUIRED=true
AUTO_REPLAY=false
AUTO_FORMAT_OTHER_USB=false
```

The system must request reinsertion of the same filesystem UUID.

## 11. USB capacity admission

Every Home Assistant version update requires a T1-formatted ext4 USB device.

The product must not trust the marketed capacity printed on the device.

Hard media gate:

```text
USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=15032385536
USB_MEASURED_USABLE_CAPACITY_MIN=14_GiB
USB_NOMINAL_CAPACITY_NOT_AUTHORITY=true
RECOMMENDED_MARKET_USB_SIZE=32GB_OR_LARGER
```

Formatting is performed first; measured usable ext4 capacity is evaluated afterward.

A marketed 16GB device can be rejected if its measured usable capacity is below 14 GiB.

The 14 GiB floor is necessary but not sufficient. Runtime admission must also satisfy:

```text
USB_REQUIRED_BYTES =
  target_artifact_bytes
+ predecessor_recovery_worst_case_bytes
+ ha_data_backup_worst_case_bytes
+ transaction_metadata_and_working_bytes
+ removable_media_reserve_bytes
```

Therefore:

```text
USB_PASS =
MEASURED_USABLE_BYTES >= 14_GiB
AND
MEASURED_USABLE_BYTES >= USB_REQUIRED_BYTES
```

## 12. Internal capacity policy

Normal steady state for the current hardware:

```text
INTERNAL_HA_GENERATION_COUNT=1
```

The product must not intentionally leave predecessor + target HA images resident after a completed update.

V1.1 does not provide a no-USB Home Assistant version-update path, even when internal free space appears sufficient.

The USB transaction is the single product path so that predecessor recovery image + HA data recovery point exist before destructive cutover.

Historical Manager images and generic broad Docker pruning are not substitutes for this policy.

## 13. Security of removable recovery data

HA_DATA_BACKUP contains credentials and private user configuration.

Therefore:

- USB backup data must not be left as casually readable plaintext by design;
- backup confidentiality/authenticity is required;
- keys must not be stored next to encrypted data in a form that defeats the protection;
- exact cryptographic/key-recovery design is deferred to the implementation gate;
- the update must never publish HA backup contents or private device identifiers to GitHub.

Image archives themselves are not treated as secret, but still require signed/hash-bound integrity.

## 14. Relationship to current P5

Current P5 assumptions that are now under review against the mandatory-USB V1.1 architecture:

- target `PRESENT_AND_EXACT` internally before apply;
- predecessor remains internally resident for automatic rollback;
- exact target archive transferred to T1 even when target already exists;
- capacity gate assumes coexistence/reapply semantics.

These assumptions are not automatically carried into the low-storage architecture.

Current live state:

```text
P5_REAPPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_REAPPLY_P5_20261106_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
LIVE_REAPPLY_STATUS=HELD_BEFORE_CLAIM
```

Do not continue the current P5 live reapply until a fresh impact review decides whether the authorization/package must be retired or superseded.

## 15. Formal acceptance requirements before source implementation

The architecture is ready for source-design impact review when all of the following are accepted:

```text
HOMEASSISTANT_UPDATE_USB_REQUIRED=true
USB_T1_FORMAT_EXT4=ACCEPTED
USB_MEASURED_USABLE_CAPACITY_MIN=14_GiB
USB_RECOMMENDED_MARKET_SIZE=32GB_OR_LARGER
USB_USER_PRELOAD_REQUIRED=false
USB_THREE_ASSETS_T1_OWNED=true
TARGET_DOWNLOAD_AND_VERIFY_BEFORE_INSTALL_CONFIRMATION=true
PREDECESSOR_EXPORT_AFTER_INSTALL_CONFIRMATION=true
UPDATE_DISCOVERY_OWNER=N3W_T1_OTA_MANAGER
HOMEASSISTANT_NOTIFICATION_SURFACE=MQTT_UPDATE_ENTITY
PRIMARY_HA_OTA_TRANSFER_ARTIFACT=EXACT_COMPRESSED_HA_ARCHIVE
INTERNAL_ONE_HA_GENERATION_STEADY_STATE=true
OFFLINE_RECOVERY_ARTIFACT_RETAINED=true
SUCCESS_BACKUP_RESTORE_FORBIDDEN_BY_DEFAULT=true
ROLLBACK_DATA_RESTORE_REQUIRED=true
POWER_LOSS_RECOVERY_REQUIRED=true
P5_LIVE_RETRY_HELD=true
```

## 16. Test strategy required for implementation

Future source implementation must include at least:

1. pure source/unit state-machine tests;
2. synthetic block-device tests proving internal disk can never be selected for format;
3. ext4 format/mount/UUID binding tests;
4. USB capacity edge tests;
5. target artifact corruption tests;
6. predecessor recovery artifact corruption tests;
7. HA data snapshot/restore byte-integrity tests;
8. power-loss injection at every phase U0-U11;
9. USB removal/reinsert tests before and after U7;
10. target activation success test;
11. target failure + image rollback + data restore test;
12. rollback failure classification;
13. no-second-claim/no-replay tests;
14. real T1 16GB low-storage physical acceptance;
15. mandatory-USB route enforcement test;
16. measured 14 GiB threshold boundary tests;
17. target preparation -> READY_TO_INSTALL user-stop test;
18. update-manifest discovery + MQTT Update entity state tests.

## 17. Explicit non-goals for V1 architecture

Not decided here:

- exact UI implementation;
- exact backup archive encoding;
- exact encryption/key-recovery implementation;
- OTA/CDN provider and signed-manifest implementation;
- cross-device HA migration/recovery;
- permanent external Docker/containerd root;
- automatic formatting of an offline service-prepared recovery disk;
- source changes to current P5.

Those decisions belong to later bounded gates.

## 18. Next gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_LOW_STORAGE_USB_OTA_TO_P5_IMPACT_READONLY_REVIEW_20261106_01
LIVE_MUTATION=false
BOARD_ACCESS=false
SOURCE_MUTATION=false
```

The next gate must:

- fresh rebind current P5 source/authorization/runtime facts;
- compare current P5 assumptions against mandatory-USB architecture V1.1;
- verify actual 2026.10.0 vs 2026.10.4 RootFS layer digest overlap as diagnostic evidence;
- decide whether current P5 authorization/package is retired, superseded or partially reusable;
- produce a bounded source-design delta including OTA Manager discovery, MQTT Update entity publication, USB preparation/install split, and HA data rollback;
- not perform T1 mutation.
