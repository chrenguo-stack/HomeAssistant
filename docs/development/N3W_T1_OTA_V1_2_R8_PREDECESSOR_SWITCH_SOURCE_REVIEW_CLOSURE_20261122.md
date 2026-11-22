# N3-W T1 OTA V1.2 R8 predecessor-switch independent source review closure

DATE=2026-11-22
PR=823
HEAD=847e1231981a60c0738cda6de1f223b0ae1bf0d0
BASE_PR=822
BASE_HEAD=ba01d2d6d65d71cfbbb5cd54c397646dfee0cc63
STATUS=SOURCE_REVIEW_PASS
LIVE_WRITE_AUTHORIZATION=NONE

## 1. Physical authority entering this review

R8 bound-USB Attempt 03 is PASS.

Current runtime:
- Home Assistant version: 2026.10.4
- image ref: local/n3w-homeassistant:2026.10.4-5881590f
- image ID: sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
- running baseline: PASS
- HA restart count: 0
- Manager/HA MQTT authenticated
- HTTP 401 expected
- exact 2026.10.0 absent

Current exact rollback point freshly verified from bound USB:
- transaction SHA-256: a427bef98d2886234bf706eb1347f09148429e44c79ab08f01e1071dd0722492
- USB: /dev/sda1 / 8:1 / ext4
- image archive SHA-256: 31108a725e6b6530c68834218d9e41579055d7fe2718b3f42902b71237dc8e5f
- image archive size: 743051918
- image portable identity SHA-256: efcf67bd4ff40cd902b43fc531aa9dce58d115ececc8ebd4e324a15e0f4952f3
- protected backup archive SHA-256: b6f7ad3803c1ae954d2d946562b5ae1db8725786e4c457db8a1deff7b10623e2
- protected backup size: 2090112
- protected backup manifest SHA-256: 1cf39dad34b36b8901c24151cc7d4b3ec6fa09b25264f6812c3a9e51569409ac
- host USB mount unchanged/unmounted after verification
- ext4 journal replay disabled by ro/noload
- errors: none

Pre-release internal free space remains evidence only and is not an R8 capacity decision.

## 2. Exact predecessor authority

Mac cache:
- ref: local/n3w-homeassistant:2026.10.0-0c73235a
- expected image ID: sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
- archive size: 2448553472
- archive SHA-256: e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
- platform: linux/arm64

The operator source-check parses the exact archive and derives the actual Docker layer import worst case from verified layer contents. It does not use the archive byte size as an import-space approximation.

## 3. Persistent-data compatibility

Exact compatibility authority:
infra/n3w-t1/upgrades/homeassistant-2026.10.4-compatibility-review.json

Canonical SHA-256:
8b02e9bb0143fc4fc7900c4c0e4c52b27f92725cd41f1f03b82ba67ffb9e0267

Frozen review proves 2026.10.0 -> 2026.10.4:
- mutation profile IMAGE_ONLY_V1
- core.config_entries: 1/5 -> 1/5
- core.device_registry: 3/4 -> 3/4
- core.entity_registry: 1/23 -> 1/23
- peer_contracts_compatible=true
- persistent_schema_compatible=true
- rollback_compatible_source_review=true

The target manifest independently binds the same review and rollback_compatible=true.

Therefore predecessor preparation uses a fresh quiesced backup of current compatible data, restores it to a separate staging directory, and atomically exchanges that copy into the production path. The original 2026.10.4 data directory is preserved by filesystem/inode identity and is not directly written by 2026.10.0.

## 4. Single-image and capacity review

Required ordering is source-enforced:

PREFLIGHT
-> QUIESCED
-> BACKUP_VERIFIED
-> DATA_EXCHANGED
-> CURRENT_RELEASE_INTENT
-> CURRENT_RELEASED
-> POST_RELEASE_CAPACITY
-> PREDECESSOR_LOADED
-> BINDING_SWITCHED
-> PREDECESSOR_HEALTHY

The durable release intent is written before exact current container/image removal.

Post-release capacity is measured from the real Docker internal filesystem and compared with:
exact 2026.10.0 import worst-case layer bytes + 1610612736-byte post-peak reserve.

No pre-release free-space reading can become capacity PASS/FAIL.

No global Docker prune exists in the package.

The 2026.10.0 archive is streamed directly from the Mac into docker load only after post-release admission. It is not first copied into T1 internal storage.

## 5. Data safety / rollback review

Before current-image release:
- application writers must be quiesced;
- a new encrypted/authenticated HA backup must be created on the bound USB;
- that backup must be immediately verified;
- a restored copy must be materialized on the same internal filesystem;
- original/staged filesystem IDs and inode IDs are journaled;
- the atomic exchange must prove which directory is original and which is staged.

Rollback:
- exact 2026.10.0 is removed only when its ownership is provable;
- original 2026.10.4 data is restored by journaled inode identity;
- exact 2026.10.4 is restored from the already verified P3 USB image archive when absent;
- exact current binding is restored;
- full converged 2026.10.4 health is required before ROLLED_BACK.

No USB recovery data is deleted.

## 6. Interrupted-process / power-loss review

A root-owned private journal records exact immutable recovery authority and phase progress.

The same source exposes status and recover.

Recover:
- does not need a new predecessor-switch grant;
- cannot advance toward 2026.10.0;
- only attempts exact restoration to healthy 2026.10.4;
- validates source head, P3 rollback transaction, USB identity, image identities, data inode identities and backup authority;
- returns RECOVERY_REQUIRED rather than guessing when exact ownership/recovery cannot be proven.

The exact recovery zipapp is cached on the operator Mac during mandatory read-only preflight.

Known explicit boundary:
an interruption inside docker load can theoretically leave storage residue without an exact 2026.10.0 image identity. If that residue prevents loading the exact 2026.10.4 rollback archive, recover returns RECOVERY_REQUIRED. It does not use global prune. This is a one-time predecessor-setup boundary and is not represented as a product-R8 guarantee.

No permanent recovery daemon is installed by predecessor setup.

## 7. Independent-review fixes

The independent review found and repaired before physical preflight:

1. Historical P3 field/layout compatibility was already closed in PR #822 Attempt 03.
2. Added journal-driven status/recover path for interrupted predecessor setup.
3. Persisted exact rollback/predecessor/USB authority in each switch-state record.
4. Added original/staged filesystem and inode evidence for atomic data exchange recovery.
5. Renamed staged_data_sha256 to staged_manifest_sha256 to avoid claiming a tree hash that was not actually computed.
6. Added exact mount-mode verification for ro/noload and rw modes.
7. Added private owner/mode/link checks for P3 rollback archive and parent directories.
8. Added real DockerRootDir/HA-data same-filesystem proof to read-only preflight.
9. Added exact recovery-package cache for post-interruption recovery without GitHub artifact dependency.
10. Removed operator.py because it could shadow Python stdlib operator during direct execution; entrypoint is now switchctl.py.
11. Fixed switchctl repository-root calculation from PACKAGE_DIR.parents[4] to PACKAGE_DIR.parents[3].
12. Corrected one focused-test fixture path; product recovery-path validation remained strict.

## 8. CI closure

Exact HEAD:
847e1231981a60c0738cda6de1f223b0ae1bf0d0

Focused workflow:
T1 R8 predecessor switch CI
run=45035261640
job=137247479946

Results:
- setup: SUCCESS
- Python setup: SUCCESS
- dependency install: SUCCESS
- compile complete predecessor-switch package: SUCCESS
- focused predecessor-switch tests: SUCCESS
- overall focused job: SUCCESS

All other workflow runs returned for this exact HEAD were also SUCCESS.

## 9. Authorization boundary

LIVE_WRITE_AUTHORIZATION=NONE
EXECUTION_PERMITTED=false

Not authorized or executed:
- stop/start/restart application services
- rw USB mount
- fresh USB backup creation
- HA data-root exchange
- current 2026.10.4 container/image release
- post-release live capacity mutation path
- docker load of 2026.10.0
- image binding switch
- predecessor runtime start
- R8 OTA
- reboot
- merge/release

The next physical gate is READ-ONLY predecessor-switch preflight only.
