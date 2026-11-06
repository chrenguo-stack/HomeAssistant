# N3-W T1 Home Assistant Low-Storage USB-Assisted OTA + Data Rollback Architecture V1.0

DATE=2026-11-06
STATUS=ARCHITECTURE_FROZEN_SOURCE_IMPLEMENTATION_NOT_STARTED
PRODUCT_SCOPE=N3-W T1 / Home Assistant Container / 16GB-class internal storage
PRIMARY_REASON=dual Home Assistant image residency is not acceptable on the current ~14.45GB root filesystem

## 0. Decision summary

```text
NORMAL_RUNNING_HA_IMAGE_COUNT_INTERNAL=1
PRIMARY_NETWORK_OTA=OCI_REGISTRY_EXACT_DIGEST
LOW_STORAGE_OTA=USB_ASSISTED_TRANSACTION
LOW_STORAGE_USB_FILESYSTEM=ext4
LOW_STORAGE_USB_FORMAT_OWNER=T1
USER_PRELOAD_REQUIRED=false
USER_COMPUTER_REQUIRED=false

OFFLINE_RECOVERY_ARTIFACT=RETAIN
OFFLINE_RECOVERY_ARTIFACT_CURRENT_FORM=homeassistant-arm64.tar.gz

HA_DATA_BACKUP_REQUIRED_BEFORE_DESTRUCTIVE_CUTOVER=true
SUCCESS_PATH_RESTORE_PREUPGRADE_DATA_BACKUP=false
ROLLBACK_PATH_RESTORE_PREUPGRADE_DATA_BACKUP=true

CURRENT_P5_REAPPLY=HOLD_BEFORE_CLAIM
CURRENT_P5_AUTHORIZATION_REUSABLE_WHILE_UNCLAIMED=true
SOURCE_IMPLEMENTATION_STARTED=false
```

The product must not depend on a user computer for ordinary updates. The T1 owns download, removable-media preparation, integrity verification, cutover, health validation and rollback.

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

The user experience remains:

```text
发现更新
-> 点击升级
-> 若内部空间足够，直接升级
-> 若内部空间不足，提示插入U盘
-> 用户确认U盘会被清空
-> T1自动完成其余操作
-> 成功 / 已自动恢复
```

The user must not need to understand Docker, OCI, tar archives, SSH, ext4, image digests or rollback mechanics.

## 3. Two OTA transport modes

### 3.1 Normal network OTA

Preferred future transport:

```text
N3W OTA control plane
-> signed update manifest
-> N3W-controlled OCI registry
-> T1 pulls exact digest
-> Docker/OCI layer reuse occurs automatically when possible
```

This is the normal path when internal storage admission proves that temporary predecessor + target coexistence is safe.

Layer reuse is an optimization, not an architectural correctness requirement.

### 3.2 Low-storage OTA

When internal storage cannot safely hold predecessor + target + reserve:

```text
LOW_STORAGE_MODE=true
-> require removable USB storage
-> T1 formats it as ext4
-> T1 prepares all recovery/staging assets on USB
-> only after all assets are verified may internal predecessor be removed
-> target is then installed internally
```

The low-storage path deliberately avoids long-term dual HA image residency.

## 4. USB ownership and formatting policy

### 4.1 Mandatory T1-managed formatting

For the automatic low-storage update path:

```text
USB_FILESYSTEM_REQUIRED=ext4
USER_PREPARED_COMPATIBLE_FILESYSTEM_ACCEPTED=false
AUTO_USE_EXISTING_FILESYSTEM=false
FORMAT_REQUIRED=true
DESTRUCTIVE_CONFIRMATION_REQUIRED=true
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
- capacity is sufficient for the transaction admission formula.

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

The user does not prepare the three upgrade assets.

T1 writes them after format:

```text
/n3w-update/
├── transaction/
│   ├── manifest.json
│   ├── phase.json
│   └── checksums.json
├── predecessor/
│   ├── image-recovery.*
│   └── identity.json
├── target/
│   ├── homeassistant-arm64.tar.gz
│   └── identity.json
└── backup/
    └── ha-data-backup.*
```

Exact filenames/formats remain implementation details; transaction semantics are frozen by this document.

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
OFFLINE_RECOVERY_ARTIFACT
LOW_STORAGE_STAGED_TARGET_ARTIFACT
```

In low-storage online OTA, T1 downloads the exact target artifact directly to USB and verifies it before destructive cutover.

In normal space-sufficient OTA, OCI registry layer pull remains preferred.

Ordinary users do not download/copy this archive with a computer.

A separate future service/offline-recovery workflow may use the same artifact.

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

## 9. Low-storage transaction state machine

### Phase U0 — read-only admission

Verify:

- production baseline healthy;
- current HA exact predecessor identity;
- update target exact authority;
- internal free-space state;
- low-storage route required;
- no active updater transaction.

No USB mutation.

### Phase U1 — USB selection and destructive confirmation

- detect eligible removable disk;
- display device model/capacity;
- user confirms all contents may be erased;
- bind selected device identity for this transaction.

### Phase U2 — USB format and media qualification

- unmount eligible partitions;
- create GPT + single ext4 partition;
- mount by filesystem UUID;
- perform bounded write/fsync/read/hash self-test;
- measure usable capacity.

Failure here leaves T1 production unchanged.

### Phase U3 — prepare target

- download exact target archive directly to USB;
- verify size, SHA-256, target identity and platform;
- fsync.

Production HA remains running.

### Phase U4 — prepare predecessor recovery image

- export exact current predecessor directly to USB;
- compress/stream without internal full-copy staging;
- verify restorable identity;
- fsync.

Production HA remains running.

### Phase U5 — final pre-destructive admission

Require simultaneously:

```text
TARGET_ARTIFACT_VERIFIED=true
PREDECESSOR_RECOVERY_VERIFIED=true
USB_FILESYSTEM=ext4
USB_UUID_BOUND=true
USB_CAPACITY_PASS=true
PRODUCTION_PRESTATE_STILL_EXACT=true
AUTHORIZATION_NOT_CONSUMED=true
```

Any drift stops before production mutation.

### Phase U6 — HA data snapshot

- quiesce HA using production owner semantics;
- create consistent HA_DATA_BACKUP directly to USB;
- verify archive/snapshot integrity;
- fsync data + metadata;
- persist transaction phase to internal state and USB.

### Phase U7 — destructive claim boundary

Only now may the updater consume the one-shot live update authorization.

After claim, replay is forbidden.

### Phase U8 — free internal predecessor capacity

- remove predecessor container/runtime object as required;
- remove predecessor image from internal image store;
- verify expected reclaimed space;
- do not delete Manager/Broker images or unrelated data.

The predecessor remains recoverable from USB.

### Phase U9 — install target

- load exact target archive from USB into internal image store;
- verify runtime image identity;
- publish target binding;
- recreate HA container using the preserved production `/config`.

### Phase U10 — target health acceptance

Verify at minimum:

- correct exact target image;
- expected binding/network/runtime contract;
- required listeners;
- HA HTTP readiness;
- HA MQTT readiness;
- Manager/Broker peer continuity;
- no unexpected restart loop;
- HA readiness budget appropriate for real recreate duration.

### Phase U11A — success commit

On PASS:

```text
transaction=COMMITTED
current_internal_ha_image=target
preupgrade_data_backup=retained_on_USB
predecessor_recovery_package=retained_on_USB
```

Do not restore the old data backup.

User may be told the update is complete and the USB can be removed only after commit evidence is durable.

### Phase U11B — automatic rollback

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

- before U7: production predecessor remains authoritative; transaction can be abandoned/restarted safely;
- after U7: boot must enter transaction recovery classification before normal HA activation;
- if the bound USB is present, resume forward/rollback according to durable phase;
- if the bound USB is missing, do not claim recovery success and do not invent a replacement device.

If USB is removed after predecessor internal image deletion:

```text
RECOVERY_MEDIA_REQUIRED=true
AUTO_REPLAY=false
AUTO_FORMAT_OTHER_USB=false
```

The system must request reinsertion of the same filesystem UUID.

## 11. USB capacity admission

Do not rely on a fixed marketing capacity alone.

Runtime admission must account for:

```text
USB_REQUIRED_BYTES =
  target_artifact_bytes
+ predecessor_recovery_worst_case_bytes
+ ha_data_backup_worst_case_bytes
+ transaction_metadata_and_working_bytes
+ removable_media_reserve_bytes
```

For product guidance:

```text
MINIMUM_NOMINAL_USB_GUIDANCE=16GB
RECOMMENDED_USB=32GB_OR_LARGER
FINAL_ACCEPTANCE=RUNTIME_MEASURED_CAPACITY_GATE
```

A 16GB device is not automatically accepted if the measured backup/data requirement is larger.

## 12. Internal capacity policy

Normal steady state for the current hardware:

```text
INTERNAL_HA_GENERATION_COUNT=1
```

The product must not intentionally leave predecessor + target HA images resident after a completed update.

Space-sufficient mode may temporarily keep two generations only when admission proves the reserve is safe.

Low-storage mode uses USB recovery authority specifically so the predecessor can be removed internally before target import.

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

Current P5 assumptions that are now under review:

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
USB_T1_FORMAT_EXT4=ACCEPTED
USB_USER_PRELOAD_REQUIRED=false
USB_THREE_ASSETS_T1_OWNED=true
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
15. normal OTA vs low-storage route selection test.

## 17. Explicit non-goals for V1 architecture

Not decided here:

- exact UI implementation;
- exact backup archive encoding;
- exact encryption/key-recovery implementation;
- OCI registry provider;
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
- compare current P5 assumptions against this architecture;
- verify actual 2026.10.0 vs 2026.10.4 RootFS layer digest overlap as diagnostic evidence;
- decide whether current P5 authorization/package is retired, superseded or partially reusable;
- produce a bounded source-design delta;
- not perform T1 mutation.
