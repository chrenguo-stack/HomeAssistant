# N3-W T1 OTA V1.2 R8 spare-T1 read-only preflight physical evidence

DATE=2026-11-22
PR=822
STACKED_ON_PR=821
SOURCE_HEAD=eac5794afbeef265dee0f5f60d5e5223de111e35
PREFLIGHT_HEAD=decbb0cf5f3b16b90f4d324796cc701e84260191
STATUS=R8_SPARE_READONLY_PREFLIGHT_COLLECTED
EXIT_CODE=0

## Exact local/cloud bindings

RECOVERY_ARTIFACT_ID=14755286389
RECOVERY_ARTIFACT_ZIP_SHA256=3e8d9be4100392403aef5af15c9782fe866db77be159dbe5c53814eda486c15e
RECOVERY_ARTIFACT_DOWNLOAD=PASS
PREDECESSOR_MAC_CACHE=PASS
PREDECESSOR_MAC_TAR_SIZE_BYTES=2448553472
PREDECESSOR_MAC_TAR_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663

SSH_TARGET_CLASS=SPARE_T1
SSH_HOST_KEY_BINDING=PASS
SSH_HOST_KEY_SHA256=2e6cae2b43ba5d7d0818fa53b4175a6bf58442077b32caf44b0bf886e6e4a901

## Fresh spare-T1 runtime evidence

ARCHITECTURE=aarch64
OTA_RUNNING_BASELINE=RUNNING_BASELINE_PASS
DIAGNOSTIC_ONLY=false
HOMEASSISTANT_VERSION=2026.10.4
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
HOMEASSISTANT_IMAGE_SIZE_BYTES=2447072066
HOMEASSISTANT_RESTART_COUNT=0
HOMEASSISTANT_HTTP_STATUS=401
HOMEASSISTANT_MQTT_AUTHENTICATED=true
MANAGER_MQTT_AUTHENTICATED=true
LISTENERS_MATCH=true
REFERENCES_MATCH_COMPOSE=true

PREDECESSOR_2026_10_0_PRESENT=false
PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

STACK_TRANSACTION_STATUS=COMMITTED
STACK_TRANSACTION_SHA256=39c076050122402f93b4956523129e4555df210d8e45caea1ababd88f1ee3d0b
HOMEASSISTANT_USB_TRANSACTION_STATUS=ROLLED_BACK
HOMEASSISTANT_USB_TRANSACTION_PHASE=U13B_ROLLED_BACK
HOMEASSISTANT_USB_TRANSACTION_SHA256=a427bef98d2886234bf706eb1347f09148429e44c79ab08f01e1071dd0722492
TRANSACTIONS_STABLE=true
LEGACY_MANAGER_TRANSACTION=null

RECOVERY_PACKAGE_PRESENT=false
RECOVERY_IPC_SOCKET=inactive
RECOVERY_STARTUP_SERVICE=inactive
RECOVERY_RETRY_TIMER=inactive

## Bound USB evidence

BOUND_USB_STATUS=BOUND_USB_PRESENT
BOUND_USB_DEVICE=/dev/sda1
BOUND_USB_MAJOR_MINOR=8:1
BOUND_USB_FILESYSTEM=ext4
BOUND_USB_MOUNTS=0
BOUND_USB_TRANSACTION_STATUS=ROLLED_BACK
BOUND_USB_TRANSACTION_PHASE=U13B_ROLLED_BACK
BOUND_USB_TRANSACTION_SHA256=a427bef98d2886234bf706eb1347f09148429e44c79ab08f01e1071dd0722492
ROLLBACK_MATERIALS_STATUS=BOUND_USB_PRESENT_UNMOUNTED

No USB mount was performed by this preflight. Therefore the recovery archives and protected HA backup have not yet been freshly revalidated from media.

## Capacity evidence and rule

ROOT_TOTAL_BYTES=14453903360
PRE_RELEASE_AVAILABLE_BYTES=4754677760
CAPACITY_DECISION_POINT=AFTER_RELEASE_BEFORE_NEXT_IMPORT
POST_RELEASE_AVAILABLE_BYTES=UNKNOWN
CAPACITY_DECISION=DEFER_UNTIL_POST_RELEASE_MEASUREMENT

The 4,754,677,760-byte free-space observation is pre-release evidence only. It must not be used as a PASS/FAIL capacity decision for R8. The decisive measurement is the actual internal free space after the released Home Assistant image/container has been removed and immediately before the next exact image import.

## Interpretation

1. The spare T1 is freshly proven healthy on exact Home Assistant 2026.10.4.
2. Exact 2026.10.0 is not resident on the T1 and must be imported from the already verified Mac cache when a separately authorized predecessor switch is eventually executed.
3. The bound USB is physically present and exact-transaction-bound but currently unmounted.
4. Current rollback materials cannot yet be claimed as freshly verified because this gate deliberately did not mount the USB.
5. Historical P3 U6/U7 evidence is a 2026.10.4-predecessor recovery point, not a 2026.10.0 data baseline. The archived values are:
   - predecessor image ref local/n3w-homeassistant:2026.10.4-5881590f
   - predecessor archive size 743051918 bytes
   - predecessor archive SHA-256 31108a725e6b6530c68834218d9e41579055d7fe2718b3f42902b71237dc8e5f
   - protected backup archive SHA-256 b6f7ad3803c1ae954d2d946562b5ae1db8725786e4c457db8a1deff7b10623e2
   - protected backup manifest SHA-256 1cf39dad34b36b8901c24151cc7d4b3ec6fa09b25264f6812c3a9e51569409ac
   These historical materials are useful for restoring the current 2026.10.4 state, but they must not be reused as the 2026.10.0 predecessor data baseline.
6. A safe 2026.10.0 predecessor switch must not run 2026.10.0 directly against data already migrated/written by 2026.10.4. It requires either a freshly verified historical 2026.10.0-compatible backup or a separately constructed and validated isolated 2026.10.0 test baseline.
7. The next media check should therefore do two independent things: reverify the current 2026.10.4 rollback point from the bound USB, and search only-read historical USB material for a genuine 2026.10.0-compatible backup without treating absence as permission to downgrade current data.

## Authorization boundary

LIVE_WRITE_AUTHORIZATION=NONE
T1_PERSISTENT_MUTATION=false
SERVICE_MUTATION=false
DOCKER_MUTATION=false
USB_WRITE=false
USB_FORMAT=false
HOST_USB_MOUNT=false
PREDECESSOR_SWITCH=false
R8_OTA=false
REBOOT=false
MERGE=false

Next source-only work may prepare:
- an isolated read-only bound-USB verifier that prevents ext4 journal replay and does not alter the host mount namespace;
- the independent 2026.10.0 predecessor-switch execution package in fail-closed / unauthorized-by-default form.

No persistent T1 mutation may execute until the exact corresponding live authorization is checked.


## Isolated bound-USB verification Attempt 01

ATTEMPT=01
RESULT=STOP_READONLY_COMPATIBILITY
T1_MUTATION=false
SERVICE_MUTATION=false
DOCKER_MUTATION=false
USB_WRITE=false
USB_FORMAT=false
HOST_NAMESPACE_USB_MOUNT_REQUESTED=false
ISOLATED_NAMESPACE_USB_MOUNT=true
ISOLATED_MOUNT_OPTIONS=ro,nosuid,nodev,noexec,relatime,norecovery
EXT4_JOURNAL_REPLAY=false

Fresh observations:
- bound USB remained exact `/dev/sda1`, `8:1`, ext4;
- isolated mount was read-only;
- USB available bytes: `28132188160`;
- current Home Assistant remained exact `2026.10.4`;
- runtime baseline remained `RUNNING_BASELINE_PASS`;
- transactions remained stable;
- pre-release internal available bytes: `4754538496`;
- capacity decision remained `DEFER_UNTIL_POST_RELEASE_MEASUREMENT`.

The material verifier stopped before any archive/hash failure with:
`ha_usb_prepared_image_materials_invalid`.

Interpretation:
- this is not evidence that the USB recovery bytes are corrupt;
- the historical terminal U13B transaction predates the newer `prepared_image_materials` read path used by the first R8 diagnostic;
- the diagnostic incorrectly required the newer field instead of accepting the already-bound legacy terminal `install_recovery_materials` representation and revalidating it.

Because the verifier raised before its original post-validation host-mount probe, Attempt 01 does not claim a fresh post-run host-namespace mount observation. The USB mount itself existed only inside a private `unshare --mount --propagation private` namespace and that remote process exited. Attempt 02 must still begin by proving the host namespace is unmounted before creating any new isolated mount.

Source repair:
- `e2e49077aa66ee4e4f280a600070876492bdc912`: accept legacy terminal recovery-record representation only as an alternate source of records, while independently validating record kind, image refs, target archive SHA/size, predecessor portable identity, predecessor archive bytes and protected backup authentication;
- `33d717f84a263fa004c0a41106630598cdfdd30b`: always perform the host mount-leak probe before returning a validation failure;
- `5c594ca9cdd3dbc038dfbae24dad0971be64480b`: deterministic compatibility tests;
- `0824b4fa3e5833b295dca68870c06704610a183a`: focused CI definition corrected to run pytest explicitly.

ATTEMPT02_REQUIRED=true
LIVE_WRITE_AUTHORIZATION=NONE


## Isolated bound-USB verification Attempt 02

ATTEMPT=02
RESULT=STOP_READONLY_HISTORICAL_FIELD_MAPPING
T1_MUTATION=false
SERVICE_MUTATION=false
DOCKER_MUTATION=false
USB_WRITE=false
USB_FORMAT=false
HOST_NAMESPACE_USB_MOUNT_BEFORE=false
HOST_NAMESPACE_USB_MOUNT_AFTER=false
HOST_USB_MOUNT_STATE=UNCHANGED_UNMOUNTED
ISOLATED_NAMESPACE_USB_MOUNT=true
ISOLATED_MOUNT_OPTIONS=ro,nosuid,nodev,noexec,relatime,norecovery
EXT4_JOURNAL_REPLAY=false

Fresh observations:
- exact bound USB remained `/dev/sda1`, `8:1`, ext4;
- isolated USB available bytes: `28132188160`;
- current Home Assistant remained exact `2026.10.4`;
- runtime baseline remained `RUNNING_BASELINE_PASS`;
- transactions remained stable;
- pre-release internal available bytes: `4754456576`;
- capacity decision remained `DEFER_UNTIL_POST_RELEASE_MEASUREMENT`.

The material verifier stopped with:
`recovery_material_records_unavailable`.

Exact historical-source review against commit
`48292d4c8c3da82574f63761a4ed9a62fc8ce338`
proved that the P3 transaction predates both later record representations:
- `prepared_image_materials` did not exist;
- `install_recovery_materials` did not exist;
- P3 persisted `target_artifact_identity`;
- P3 persisted `predecessor_recovery_identity`;
- P3 persisted `ha_data_backup_identity`;
- P3 bound them with `recovery_content_manifest_sha256`.

The exact P3 removable-media layout was also re-established from its execution package:
- target: `n3w-update/target/homeassistant-arm64.tar.gz`;
- predecessor: `n3w-update/predecessor/homeassistant-predecessor.tar.gz`;
- protected HA backup directory: `n3w-update/ha-data`.

Therefore Attempt 02 is another diagnostic compatibility stop, not evidence of recovery-byte corruption.

Source repair after Attempt 02:
- `1efdc4454aae9843fa424c4c077abf90a815ba5c`: add original P3 identity fields and original removable-media layout;
- `f30a5125035c8d3788a1b70bc32785174846cbce`: keep historical recovery-manifest recomputation standalone and byte-compatible with the original canonical JSON contract;
- `8007716a42d1a5e09645984a1ef18007c17c20d1`: add focused tests for the original P3 recovery authority.

The compatibility path remains fail-closed. It must verify the historical recovery-content manifest, exact predecessor archive record and bytes, protected backup record, ciphertext hash, HMAC authentication, decrypted manifest, transaction stability, and private path metadata. It does not authorize a downgrade or any T1 mutation.

ATTEMPT03_REQUIRED=true
LIVE_WRITE_AUTHORIZATION=NONE


## Isolated bound-USB verification Attempt 03

ATTEMPT=03
RESULT=PASS
T1_MUTATION=false
SERVICE_MUTATION=false
DOCKER_MUTATION=false
USB_WRITE=false
USB_FORMAT=false
HOST_NAMESPACE_USB_MOUNT_BEFORE=false
HOST_NAMESPACE_USB_MOUNT_AFTER=false
HOST_USB_MOUNT_STATE=UNCHANGED_UNMOUNTED
ISOLATED_NAMESPACE_USB_MOUNT=true
ISOLATED_MOUNT_OPTIONS=ro,nosuid,nodev,noexec,relatime,norecovery
EXT4_JOURNAL_REPLAY=false

Fresh runtime observations:
- current Home Assistant version: `2026.10.4`;
- runtime image: `local/n3w-homeassistant:2026.10.4-5881590f`;
- runtime baseline: `RUNNING_BASELINE_PASS`;
- Home Assistant restart count: `0`;
- Home Assistant and Manager MQTT authenticated: `true`;
- HTTP status: `401` as expected;
- transactions stable: `true`;
- exact 2026.10.0 image resident on T1: `false`.

Fresh storage observations:
- pre-release internal available bytes: `4754415616`;
- capacity decision point: `AFTER_RELEASE_BEFORE_NEXT_IMPORT`;
- capacity decision: `DEFER_UNTIL_POST_RELEASE_MEASUREMENT`;
- USB total bytes: `31332343808`;
- USB available bytes: `28132188160`;
- USB filesystem: ext4;
- USB read-only observation: `true`.

Fresh recovery-material verification:
- status: `CURRENT_2026_10_4_ROLLBACK_MATERIALS_VERIFIED`;
- record source: `p3_terminal_identity_fields`;
- media layout: `p3_n3w_update_layout`;
- predecessor image ref: `local/n3w-homeassistant:2026.10.4-5881590f`;
- predecessor archive size: `743051918`;
- predecessor archive SHA-256: `31108a725e6b6530c68834218d9e41579055d7fe2718b3f42902b71237dc8e5f`;
- predecessor portable identity SHA-256: `efcf67bd4ff40cd902b43fc531aa9dce58d115ececc8ebd4e324a15e0f4952f3`;
- predecessor record verified/fsynced: `true/true`;
- protected backup archive size: `2090112`;
- protected backup archive SHA-256: `b6f7ad3803c1ae954d2d946562b5ae1db8725786e4c457db8a1deff7b10623e2`;
- protected backup manifest SHA-256: `1cf39dad34b36b8901c24151cc7d4b3ec6fa09b25264f6812c3a9e51569409ac`;
- backup verified/fsynced: `true/true`;
- consistent pre-upgrade point: `true`;
- storage integrity verified: `true`;
- confidentiality protected: `true`;
- authenticity protected: `true`.

The historical target record was also recovered and validated:
- target image ref: `local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1`;
- target archive size: `835299595`;
- target archive SHA-256: `be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d`;
- target portable identity SHA-256: `2077dd39fb38a5264b34c824978643c985b32913893dabd75328d4b86ac187d8`.

Attempt 03 closed both prior diagnostic compatibility stops. The currently bound USB therefore contains a freshly reverified, authenticated and transaction-bound rollback point for the current 2026.10.4 runtime.

This PASS does not prove the existence of a 2026.10.0-compatible HA data baseline. It only proves safe rollback to the current 2026.10.4 state.

ATTEMPT03_STATUS=PASS
CURRENT_2026_10_4_ROLLBACK_POINT=VERIFIED
PREDECESSOR_2026_10_0_DATA_BASELINE=UNRESOLVED
LIVE_WRITE_AUTHORIZATION=NONE
