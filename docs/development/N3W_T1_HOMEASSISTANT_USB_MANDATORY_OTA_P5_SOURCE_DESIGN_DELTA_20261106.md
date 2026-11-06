# N3-W T1 Home Assistant mandatory-USB OTA -> P5 source-design delta — 2026-11-06

## 1. Scope and authority

This document is the source-design closure for:

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_DESIGN_DELTA
ARCHITECTURE_AUTHORITY=docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_AND_DATA_ROLLBACK_ARCHITECTURE_V1.1_20261106.md
IMPACT_REVIEW=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_TO_P5_IMPACT_READONLY_REVIEW_20261106_01
CURRENT_PR=#788
CURRENT_BRANCH=review/n3w-t1-core-updater-storage-policy-20261105

LIVE_T1_MUTATION=false
BOARD_ACCESS=false
EXECUTABLE_SOURCE_MUTATION=false
MERGE=false
```

It freezes the bounded source route only. It does not authorize formatting a USB device, stopping Home Assistant, deleting/loading Docker images, creating/restoring HA data backups, claiming a live authorization, or applying the current P5 package.

The current P5 reapply authorization remains historically granted but unclaimed/unconsumed and is superseded for product execution by this design.

## 2. Corrected removable-media product rule

The product rule is:

```text
HOMEASSISTANT_UPDATE_USB_REQUIRED=true
USB_FILESYSTEM_REQUIRED=ext4
USB_FORMAT_OWNER=T1
USB_FORMAT_REQUIRED_FOR_EVERY_HA_VERSION_UPDATE=true

USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=15032385536
USB_MEASURED_USABLE_CAPACITY_MIN=14_GiB
USB_NOMINAL_CAPACITY_NOT_AUTHORITY=true
RECOMMENDED_MARKET_USB_SIZE=16GB_OR_LARGER
```

"16GB or larger" is a market-facing minimum recommendation, not an admission authority. A device sold as 16GB must still be rejected when the T1-formatted ext4 filesystem provides less than 14 GiB measured usable capacity or fails the complete transaction-capacity formula.

This rule supersedes the earlier 32GB recommendation. The 14 GiB measured floor is unchanged.

## 3. P5 disposition

Current P5 assumptions that are incompatible with the mandatory-USB architecture are retired:

```text
target_image_prestate=PRESENT_AND_EXACT
candidate_image_preexisting=true
preexisting_exact_target_required=true
docker_load_expected=false
rollback_predecessor_already_resident=true
internal_/var/tmp_target_staging_as_product_path=true
```

Current P5 executable/package disposition:

```text
CURRENT_P5_EXECUTION_PACKAGE=RETIRED_FOR_PRODUCT_EXECUTION
CURRENT_P5_REAPPLY_RETRY=FORBIDDEN
CURRENT_P5_AUTHORIZATION=SUPERSEDED_UNCLAIMED
CURRENT_P5_AUTHORIZATION_CLAIMED=false
CURRENT_P5_AUTHORIZATION_CONSUMED=false
ARTIFICIAL_CONSUMPTION_FORBIDDEN=true
```

The old authorization remains historical evidence. A future destructive install requires a fresh authorization bound to the USB transaction and exact target.

## 4. Architecture boundary: keep the three-container product stack

The accepted T1 Core Stack continues to contain exactly three Docker product services:

```text
greenhouse-manager
Home Assistant
Mosquitto
```

Mandatory-USB OTA does not add a fourth Docker container.

The logical "N3-W T1 OTA Manager" is split by privilege:

```text
greenhouse-manager OTA control plane
  - query approved OTA manifest through a bounded provider interface
  - decide whether a newer approved HA version exists
  - publish Home Assistant MQTT Update discovery/state
  - expose preparation/install progress
  - accept only enumerated user intents
  - never format disks
  - never access Docker socket
  - never run arbitrary host commands

host-side T1 Core Updater HA-USB executor
  - removable-media qualification/format/mount/UUID binding
  - target download destination ownership
  - exact artifact verification
  - predecessor recovery export/verification
  - HA quiesce and data recovery-point creation
  - exact internal HA image deletion/load
  - target activation/acceptance
  - automatic image + data rollback
  - durable power-loss recovery classification
```

The split preserves the existing MQTT identity/discovery path while keeping root/Docker/block-device authority outside the greenhouse-manager container.

## 5. Source ownership

### 5.1 greenhouse-manager control plane

Bounded implementation is expected under the existing Manager source tree, with final names allowed to vary only for normal repository conventions:

```text
host/greenhouse-manager/src/greenhouse_manager/runtime/t1_ota_manager.py
host/greenhouse-manager/src/greenhouse_manager/runtime/ha_update.py
host/greenhouse-manager/src/greenhouse_manager/runtime/mqtt_service.py
```

Responsibilities:

- `t1_ota_manager.py`
  - approved-manifest provider interface;
  - current/target version comparison;
  - product OTA state projection;
  - enumerated PREPARE / INSTALL intent validation;
  - no root operations and no arbitrary command/path fields.

- `ha_update.py`
  - MQTT Update discovery/state payload construction;
  - stable entity identity;
  - current version, latest approved version, progress/state and bounded error projection;
  - no secret/private path publication.

- `mqtt_service.py`
  - publish retained Update discovery/state using the existing Manager MQTT session;
  - consume only the frozen OTA intent topic/payload schema if command ingress is enabled;
  - no second Manager MQTT client and no reuse of the production client ID by another process.

The exact Home Assistant UI composition remains outside this design. The MQTT Update entity is the mandatory notification/progress surface. If a companion button/entity is later required to represent the separate PREPARE action, that is an HA presentation decision and must not collapse PREPARE and INSTALL into one mutation boundary.

### 5.2 host-side HA USB updater

New Home Assistant-specific source should be additive around Generic V2:

```text
tools/n3w_t1_core_updater_ha_usb.py
tools/n3w_t1_core_updater_ha_usb_state.py
tools/n3w_t1_core_updater_ha_usb_media.py
tools/n3w_t1_core_updater_ha_backup.py
tools/n3w_t1_core_updater_ha_recovery.py
```

Responsibilities:

- `n3w_t1_core_updater_ha_usb.py`
  - U0-U13 transaction orchestrator;
  - exact target/current-runtime admission;
  - PREPARE versus INSTALL separation;
  - fresh live authorization claim only at U9;
  - target acceptance and rollback routing.

- `n3w_t1_core_updater_ha_usb_state.py`
  - durable HA-USB transaction schema;
  - atomic write + fsync;
  - same root process lock as Generic V2;
  - terminal history archival;
  - restart/power-loss phase classification.

- `n3w_t1_core_updater_ha_usb_media.py`
  - enumerate removable USB block devices;
  - prove selected device is not root/internal/production-mounted;
  - exactly-one eligible-device gate;
  - explicit destructive-confirmation gate;
  - GPT + single ext4 partition;
  - filesystem UUID binding;
  - bounded write/fsync/read/hash qualification;
  - measured usable bytes and full transaction-capacity admission.

- `n3w_t1_core_updater_ha_backup.py`
  - quiesced pre-upgrade HA data recovery-point interface;
  - backup manifest/integrity verification;
  - restore interface;
  - unsupported external state detection and fail-closed classification.

- `n3w_t1_core_updater_ha_recovery.py`
  - predecessor image export stream -> USB;
  - predecessor recovery identity verification;
  - target archive load USB -> internal image store;
  - exact targeted image removal;
  - predecessor image restore USB -> internal image store;
  - never broad prune.

The exact backup archive encoding and backup encryption/key-recovery mechanism remain separately reviewable implementation decisions, but the source interfaces must enforce the frozen integrity/confidentiality contract.

## 6. Generic V2 reuse boundary

Generic V2 is not rewritten.

Keep/reuse:

```text
exact ComponentTarget identity
portable image identity verification
baseline capture/validation concepts
component adapter current-binding logic
Home Assistant production-owner quiesce/activate primitives
single-component Compose binding validation
peer continuity validation
runtime/health inspection
private durable state patterns
process-level mutation lock
fail-closed error classification
```

Do not directly reuse `MultiComponentCoreUpdater.apply()` as the mandatory-USB HA transaction entry point because it currently:

1. creates/consumes the image-only transaction too early for U8/U9;
2. assumes the predecessor image remains internally resolvable for rollback;
3. performs image-only rollback;
4. has no HA_DATA_BACKUP restore contract;
5. does not model USB UUID/recovery-media authority.

Manager and Broker upgrade paths must remain behaviorally unchanged.

## 7. Durable transaction design

Use the existing private root:

```text
/var/lib/n3w-t1-core-updater
```

Add an HA-specific active transaction authority, conceptually:

```text
homeassistant-usb-upgrade.json
```

It shares the same process-level mutation lock with Generic V2. A non-terminal Generic V2 transaction blocks HA-USB mutation, and a non-terminal HA-USB transaction blocks Generic V2 mutation.

Minimum durable fields:

```text
schema
transaction_id_sha256
phase
status
component=homeassistant

current_image_ref
current_image_identity
target_manifest_identity
target_image_ref
target_archive_sha256
target_archive_size

usb_device_identity_public_fingerprint
usb_filesystem_uuid
usb_measured_usable_bytes
usb_mount_authority

target_artifact_verified
predecessor_recovery_verified
ha_data_backup_verified

authorization_id_sha256
authorization_claimed
authorization_consumed

failure_code
recovery_required
created_at_unix
updated_at_unix
```

Do not persist passwords, MQTT secrets, raw private configuration, SSH targets, raw device serial numbers, or backup encryption keys in public evidence.

The active transaction and USB `transaction/phase.json` must be durably updated before every destructive phase transition. A phase advancement is not accepted until required files and parent directories are fsynced.

## 8. State-machine mapping

Frozen product phases:

```text
U0  DISCOVERED / READONLY_ADMISSION
U1  PREPARE_REQUESTED
U2  USB_QUALIFIED_FORMATTED_BOUND
U3  TARGET_DOWNLOADING_VERIFYING
U4  READY_TO_INSTALL

U5  INSTALL_REQUESTED_REVALIDATING
U6  PREDECESSOR_RECOVERY_PREPARING
U7  HA_QUIESCED_DATA_BACKUP_PREPARING
U8  RECOVERY_ADMISSION_COMPLETE
U9  LIVE_AUTHORIZATION_CLAIMED
U10 INTERNAL_PREDECESSOR_CAPACITY_RELEASED
U11 TARGET_INSTALLED_STARTED
U12 TARGET_ACCEPTANCE
U13A COMMITTED
U13B ROLLED_BACK
```

No internal predecessor-image deletion is permitted before U9.

U9 requires all of:

```text
same bound USB UUID
target artifact exact and verified
predecessor recovery package exact and verified
HA_DATA_BACKUP exact and verified
production prestate exact
transaction capacity still PASS
new live authorization eligible and unconsumed
```

The user pressing "开始升级" enters U5. It does not itself consume the one-shot authorization.

## 9. PREPARE contract

Preparation is a product mutation only to the user-confirmed USB device and updater transaction metadata. It must not interrupt the running production HA.

Order:

```text
approved manifest read-only admission
-> user PREPARE intent
-> exact removable-device selection
-> destructive USB confirmation
-> format GPT/ext4
-> bind UUID
-> measured capacity >= 14 GiB
-> full transaction-capacity PASS
-> download exact target directly to USB
-> verify size/hash/platform/provenance contract
-> fsync target + transaction metadata
-> READY_TO_INSTALL
```

At READY_TO_INSTALL:

```text
HOMEASSISTANT_RUNNING=true
INTERNAL_PREDECESSOR_IMAGE_UNCHANGED=true
PRODUCTION_CONFIG_UNCHANGED=true
PREDECESSOR_RECOVERY_CREATED=false
HA_DATA_BACKUP_CREATED=false
LIVE_INSTALL_AUTHORIZATION_CLAIMED=false
```

Ordinary users do not copy files to the USB and do not use a computer.

## 10. INSTALL contract

After explicit user INSTALL intent:

```text
revalidate same USB UUID
-> revalidate target artifact
-> revalidate current predecessor/runtime
-> export predecessor image directly to USB
-> verify predecessor recovery package
-> quiesce Home Assistant through production owner
-> create consistent pre-upgrade HA_DATA_BACKUP directly to USB
-> verify backup + fsync
-> U8 final recovery admission
-> U9 claim fresh one-shot live authorization
-> remove only exact predecessor HA runtime/image objects required for capacity
-> load exact target archive from USB
-> publish target binding
-> start target with preserved production /config
-> target health acceptance
-> COMMIT or automatic image+data rollback
```

No `docker system prune`, `docker image prune -a`, wildcard image deletion, or unrelated Manager/Broker deletion is allowed.

## 11. HA_DATA_BACKUP contract

Minimum required recovery scope:

- complete persistent production `/config`;
- default SQLite history/database when used;
- `.storage` and integration state under `/config`;
- all product-owned Home Assistant persistent files required to reproduce the pre-upgrade state;
- metadata required to restore safe ownership/mode semantics.

Consistency:

```text
TARGET_VERIFIED
+ PREDECESSOR_RECOVERY_VERIFIED
-> QUIESCE_HA
-> SNAPSHOT
-> VERIFY
-> FSYNC
-> ONLY_THEN_U8
```

If an external database or unsupported external persistent state is detected and no exact snapshot adapter exists:

```text
INSTALL=STOP_BEFORE_U9
UNSUPPORTED_EXTERNAL_STATE=FAIL_CLOSED
```

Success path:

```text
RESTORE_PREUPGRADE_BACKUP=false
TARGET_MIGRATED_PRODUCTION_CONFIG=CANONICAL
```

Rollback path:

```text
RESTORE_PREDECESSOR_IMAGE=true
RESTORE_PREUPGRADE_HA_DATA=true
ROLLBACK_PASS_REQUIRES_BOTH=true
```

Backup confidentiality/authenticity is mandatory. Exact encryption/key recovery remains a separate implementation decision and may not be replaced by permanent plaintext storage as the final product design.

## 12. Removable-media safety contract

Formatting is permitted only after the media module proves all of:

```text
exactly_one_eligible_removable_device=true
selected_device_is_root_device=false
selected_device_backs_production_mount=false
selected_device_read_only=false
displayed_identity_matches_selected_device=true
explicit_destructive_confirmation=true
```

After format:

```text
partition_table=GPT
filesystem=ext4
label=N3W-UPDATE
filesystem_uuid_bound=true
measured_usable_bytes>=15032385536
full_transaction_capacity_pass=true
bounded_write_fsync_read_hash_selftest=PASS
```

A different USB UUID cannot inherit an active transaction. After U9, missing recovery media must stop and request reinsertion of the same bound filesystem UUID; no replacement disk may be auto-formatted or substituted.

## 13. OTA manifest and MQTT Update contract

The approved-manifest provider is an interface, not a hard-coded CDN implementation.

Minimum normalized manifest result supplied to the OTA control plane:

```text
manifest_schema_supported=true
approval_status=APPROVED
component=homeassistant
version
platform=linux/arm64
target_archive_size_bytes
target_archive_sha256
target_image_identity
release_identity
verification_status=PASS
```

Unsigned/unapproved/expired/unsupported or ambiguous provider results fail closed and must not become an installable update.

MQTT Update projection must expose at minimum:

```text
installed_version
latest_approved_version
update_available
ota_phase
progress_percent_or_null
ready_to_install
in_progress
error_code_or_null
```

The entity/state payload must never expose private host paths, USB serial numbers, credentials, backup filenames containing user identity, raw authorization IDs, or private evidence locators.

## 14. Control-plane -> privileged-executor boundary

No MQTT payload may directly become a root shell command, block-device path, Docker argument or filesystem path.

The future implementation must use an enumerated request schema such as:

```text
action=PREPARE | INSTALL | STATUS
target_release_id=<validated manifest-owned identifier>
transaction_token=<opaque bounded identifier>
```

The privileged side independently resolves:

- the approved target manifest;
- the eligible block device;
- all host paths;
- all Docker image refs;
- the current transaction;
- the exact production owner.

Unknown fields/actions fail closed.

The exact IPC mechanism may be selected during implementation, but it must not require mounting the Docker socket into greenhouse-manager or giving the container block-device/root privileges.

## 15. Power-loss recovery contract

Boot/re-entry classification must use the durable HA-USB transaction plus the bound USB transaction copy.

Before U9:

- predecessor remains the runtime authority;
- if HA was quiesced during U7, restart predecessor only after proving pre-U9 state and transaction authority;
- no destructive predecessor image deletion has occurred.

After U9:

- normal HA activation must not race transaction recovery;
- recovery first verifies the same bound USB UUID;
- if USB is present, classify forward-resume versus rollback using the last durable phase;
- if USB is absent, stop with `RECOVERY_MEDIA_REQUIRED`;
- never claim success from stale internal tags alone.

## 16. RootFS layer overlap

```text
DOCKER_SYSTEM_DF_SHARED_SIZE_ZERO_IS_NOT_ROOTFS_LAYER_PROOF=true
ROOTFS_LAYER_OVERLAP_IS_DIAGNOSTIC_ONLY_FOR_V1_1=true
NO_USB_ROUTE_DOES_NOT_RETURN_EVEN_IF_LAYER_OVERLAP_IS_HIGH=true
```

A future read-only diagnostic may compare exact `RootFS.Layers` digest lists for 2026.10.0 and 2026.10.4. The result may improve capacity understanding but cannot relax mandatory-USB policy.

## 17. Source implementation slices

To keep the implementation bounded, use sequential slices.

### R1 — pure transaction/media/backup interfaces

- transaction schema/store;
- removable-media classifier and destructive-confirmation boundary;
- capacity formula;
- target/predecessor/backup artifact records;
- no real block formatting;
- no live T1.

### R2 — simulated USB transaction

- loopback/synthetic block devices only;
- ext4 format/mount/UUID tests in CI where supported;
- target preparation and READY_TO_INSTALL;
- predecessor export/restore adapters against synthetic Docker host;
- backup create/verify/restore against synthetic HA data;
- power-loss injection.

### R3 — greenhouse-manager OTA control plane

- approved-manifest provider interface;
- MQTT Update discovery/state;
- bounded PREPARE/INSTALL intent;
- no host privilege;
- no real T1.

### R4 — host integration package

- connect control plane request to privileged HA-USB executor through a narrow validated IPC;
- preserve three-container stack;
- add required host-runtime installation assets only if review proves necessary;
- exact-source CI and package binding.

### R5 — real-T1 read-only preflight

Only after R1-R4 source/CI closure:

- removable-media inventory read-only;
- current HA data/database topology;
- current image identities;
- transaction-state absence/terminality;
- no format or service stop.

Real USB format/install remains a separately authorized physical/live gate.

## 18. Required tests

At minimum:

1. internal/root disk can never be selected for formatting;
2. multiple eligible USB devices fail closed;
3. read-only USB fails closed;
4. explicit destructive confirmation required before any partition write;
5. marketed 16GB value is never used as capacity authority;
6. exactly 14 GiB measured boundary PASS and one-byte-below FAIL;
7. full transaction formula may reject media even when 14 GiB floor passes;
8. UUID binding mismatch fails closed;
9. target corruption before READY_TO_INSTALL fails with production HA unchanged;
10. READY_TO_INSTALL occurs before predecessor export/HA stop;
11. INSTALL intent does not itself consume live authorization;
12. predecessor export corruption stops before U7/U9;
13. backup corruption stops before U9;
14. unsupported external DB/state stops before U9;
15. U8 requires target + predecessor + HA backup simultaneously verified;
16. no predecessor image deletion before U9;
17. no broad Docker prune command appears in product path;
18. successful target keeps migrated production `/config`;
19. target failure restores predecessor image and pre-upgrade HA data;
20. image-only rollback is not accepted as rollback PASS;
21. power loss at every U0-U11 phase has deterministic recovery classification;
22. USB removal before U9 leaves predecessor recoverable internally;
23. USB removal after U9 requires same UUID reinsertion;
24. no second authorization claim/replay;
25. Generic V2 Manager/Broker regression suite unchanged;
26. MQTT Update state does not expose private values;
27. control-plane payload cannot inject shell/path/Docker args;
28. no fourth Docker product service is introduced;
29. greenhouse-manager never receives Docker socket/block-device/root privilege;
30. exact RootFS overlap diagnostic, if added, does not alter mandatory-USB admission.

## 19. Current source-design closure

```text
P5_EXECUTION_PACKAGE_DISPOSITION=RETIRED_FOR_PRODUCT_EXECUTION
P5_AUTHORIZATION_DISPOSITION=SUPERSEDED_UNCLAIMED

GENERIC_V2_REWRITE_REQUIRED=false
GENERIC_V2_DIRECT_HA_USB_APPLY_REUSE=false
GENERIC_V2_PRIMITIVE_REUSE=true

THREE_CONTAINER_CORE_STACK_PRESERVED=true
GREENHOUSE_MANAGER_PRIVILEGED_HOST_ACCESS=false
BROAD_DOCKER_PRUNE=false

USB_RECOMMENDED_MARKET_SIZE=16GB_OR_LARGER
USB_MEASURED_USABLE_CAPACITY_MIN=14_GiB

SOURCE_IMPLEMENTATION_REQUIRED=true
EXECUTABLE_SOURCE_MUTATION_THIS_GATE=false
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R1_20261106_01
AUTO_EXECUTE_NEXT_GATE=false
```
