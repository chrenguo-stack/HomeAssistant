# N3-W T1 OTA Upgrade — independent product development stage

Date: 2026-10-28

## 1. Product-stage declaration

```text
STAGE=N3W_T1_OTA_UPGRADE
STAGE_TYPE=INDEPENDENT_PRODUCT_DEVELOPMENT_STAGE
BRANCH=product/n3w-t1-ota-upgrade-20261028
BASE_MAIN=2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e

BLOCKS_R10_PHYSICAL_ACCEPTANCE=false
R10_BLOCKS_THIS_STAGE=false
MERGE=false
T1_MUTATION=false
BOARD_MUTATION=false
```

This workstream is intentionally independent from the active R10 scan-triggered first-pairing physical-acceptance stack.

R10 may use a bounded engineering maintenance upgrade to align one development T1, but that maintenance action is not itself the product OTA implementation.

## 2. Product goal

Turn the existing T1 exact-release / rollback / lifecycle primitives into a customer-facing software-update capability that does not require developer SSH operation.

Target user experience:

```text
new signed release available
-> T1 verifies eligibility and storage
-> user explicitly authorizes update
-> T1 downloads only required update objects
-> private rollback snapshot
-> transactional production-software update
-> local health verification
-> reboot only when required
-> independent post-update acceptance
-> commit or automatic rollback
```

Normal product OTA updates the N3-W production software stack, not the Armbian operating system.

Armbian / kernel / bootloader update is a separate future lifecycle problem and must not be silently folded into normal OTA.

## 3. Hardware / current-host baseline relevant to OTA

Current project evidence for the real T1 shows:

- Amlogic S912 arm64-class host;
- 2 GiB RAM;
- 16 GiB-class eMMC hardware;
- live root and /boot are partitions on the same ~14.6 GiB-class /dev/mmcblk2 device;
- root=/dev/mmcblk2p2 and /boot=/dev/mmcblk2p1;
- no second user-data disk was observed;
- Docker/containerd production runtime is already proven;
- Ethernet/Wi-Fi networking is available;
- a historical storage probe observed 9,229,160,448 free bytes in one test state, but that value is not a permanent product minimum and must be re-read at update time.

Conclusion:

```text
APPLICATION_LEVEL_OTA_HARDWARE_CAPABLE=true
OS_AB_ROOTFS_OTA_PROVEN=false
DUAL_ROOTFS_SLOT_PRESENT=false
NORMAL_OTA_TARGET=N3W_PRODUCTION_SOFTWARE_ONLY
```

The hardware is sufficient for transactional application/container updates. It does not currently provide a proven A/B root-filesystem layout for atomic full-OS replacement.

## 4. Why the existing ~2.5 GiB fresh-install payload is not an OTA format

The existing deployable/fresh-production package was designed to build or provision a complete product environment. Historical exact evidence includes an approximately 2.535 GiB payload containing multiple complete ARM64 service images and runtime assets.

That packaging model is suitable for factory/fresh installation, not for routine field OTA.

OTA must not re-download all of:

- Home Assistant image;
- Mosquitto image;
- greenhouse-manager image;
- unchanged production runtime files;

when only one component changed.

```text
FRESH_INSTALL_PACKAGE_IS_OTA_PACKAGE=false
FULL_2_5_GIB_REDOWNLOAD_FOR_ROUTINE_UPDATE=REJECTED
```

## 5. Initial OTA architecture direction

### 5.1 Signed release manifest

Each OTA release should publish a small signed manifest containing:

- release ID / version;
- source head;
- minimum compatible current release;
- component set and exact digests;
- required migration level;
- required free space;
- reboot requirement;
- rollback compatibility;
- release signature/key ID.

The T1 first downloads only this manifest.

### 5.2 Component-level update plan

The T1 compares the manifest against its current installed component digests.

Only changed components are scheduled.

Expected component classes:

```text
greenhouse-manager image
Home Assistant image
Mosquitto image
N3-W HA custom component/assets
Compose/systemd/dispatcher/tools
database migration code
```

A Manager-only release must not download Home Assistant or Mosquitto.

### 5.3 Content-addressed container distribution

Preferred long-term transport for container images:

- OCI registry or equivalent content-addressed blob store;
- image manifests bound by digest;
- layer reuse;
- only missing layers transferred;
- no mutable `latest` authority;
- downloaded blobs verified before activation.

This is substantially more suitable than shipping `docker save` tar files for every update.

The current production rule `pull_policy: never` remains correct for normal runtime. OTA may use a separate updater to stage verified OCI content, after which production still starts only exact local immutable tags/digests.

### 5.4 Small file updates

Compose/systemd/scripts/configuration files should be packaged separately as a small signed runtime bundle rather than embedded in a multi-gigabyte image package.

### 5.5 Transaction and rollback

Reuse existing project strengths:

- exact current-state preflight;
- private database/state backup;
- enough free-space proof before mutation;
- one-shot transaction marker;
- no mutation replay after ambiguous failure;
- controlled service lifecycle;
- post-update acceptance;
- rollback to the exact predecessor release.

For application-level OTA, rollback should normally retain the predecessor container image/layers until the successor has passed acceptance.

## 6. Recommended release classes

```text
CLASS_A_MANAGER_ONLY
CLASS_B_RUNTIME_FILES_ONLY
CLASS_C_HOMEASSISTANT_COMPONENT
CLASS_D_BROKER_COMPONENT
CLASS_E_MULTI_COMPONENT
CLASS_OS_ARMBIAN_SEPARATE_NOT_NORMAL_OTA
```

Most N3-W feature releases should fall into A/B/C and therefore be much smaller than the factory installation package.

## 7. Download policy

Normal design target:

```text
MANIFEST_FIRST=true
CHANGED_COMPONENTS_ONLY=true
MISSING_OCI_LAYERS_ONLY=true
RESUMABLE_DOWNLOAD=true
SHA256_OR_OCI_DIGEST_REQUIRED=true
SIGNED_RELEASE_REQUIRED=true
FULL_FRESH_PACKAGE_FALLBACK_ONLY_FOR_SERVICE_RECOVERY=true
```

Do not rely on transferring the entire fresh-install artifact for ordinary OTA.

## 8. User autonomy target

This stage targets user-authorized OTA, not uncontrolled automatic mutation.

Recommended V1 UX:

```text
T1 checks for update metadata periodically
-> HA/local web UI shows available version + release notes
-> user presses Upgrade
-> update preflight
-> download/stage while services continue running
-> final short maintenance window
-> health verification
-> success or automatic rollback
```

Automatic background downloading may be allowed later. Automatic installation without user approval should remain a separate policy decision.

## 9. OS-update boundary

Because /boot and root currently share the same eMMC and no A/B rootfs contract is proven, normal product OTA must not rewrite the active root filesystem image.

Possible future OS-update routes require separate design, such as:

- A/B rootfs repartitioning on a future hardware/image generation;
- recovery partition + bootloader rollback contract;
- external recovery media/service procedure;
- controlled full-device reimage.

None is part of T1 OTA V1.

## 10. First development milestones

```text
OTA_0=REQUIREMENTS_AND_CURRENT_STORAGE_RUNTIME_REBIND
OTA_1=SIGNED_RELEASE_MANIFEST_AND_VERSION_COMPATIBILITY
OTA_2=COMPONENT_DIFF_PLANNER
OTA_3=OCI_MISSING_LAYER_DOWNLOAD_AND_LOCAL_STAGE
OTA_4=TRANSACTIONAL_APPLY_AND_ROLLBACK
OTA_5=LOCAL_UI_HOME_ASSISTANT_USER_APPROVAL
OTA_6=POWER_LOSS_NETWORK_LOSS_AND_STORAGE_PRESSURE_TEST
OTA_7=REAL_T1_END_TO_END_ACCEPTANCE
```

## 11. Initial non-goals

- Armbian/kernel OTA;
- bootloader OTA;
- automatic repartitioning;
- mandatory cloud dependency for normal system operation;
- silent forced updates;
- full fresh-install 2.5 GiB payload as the routine update transport.

## 12. Current stop point

```text
CURRENT_STATUS=INDEPENDENT_PRODUCT_STAGE_CREATED
IMPLEMENTATION_STARTED=false
LIVE_T1_OTA=false
NEXT_GATE=N3W_T1_OTA_UPGRADE_OTA0_REQUIREMENTS_AND_CURRENT_RUNTIME_READONLY_REBIND
```
