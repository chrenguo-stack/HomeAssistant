# N3-W T1 U7 Home Assistant quiesce / HA_DATA_BACKUP source design and independent review
# 2026-11-14

STATUS=SOURCE_DESIGN_REVIEW_IMPLEMENTED_REVIEW_COMPLETE_CI_PENDING
LIVE_T1_MUTATION=false
SERVICE_STOP=false
USB_WRITE=false
TRANSACTION_MUTATION=false
U8_PLUS=false
MERGE=false

## 1. Fresh rebind authority

REPOSITORY=chrenguo-stack/HomeAssistant
MAIN_AT_REBIND=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
PR=807
PR_STATE=OPEN_DRAFT
PR_HEAD_AT_REBIND=bf85ad74b8c310760fa9594adff437491d640b52
PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
WORKING_CONTEXT_VERSION=7.7
CURRENT_DURABLE_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING
POST_REBOOT_RUNTIME_BASELINE=UNKNOWN_FRESH

R26_STATUS=CLOSED_PASS
R26_AUTHORIZATION=CONSUMED_NO_REPLAY
R26_REPLAY=false

This document starts from the R26 closure. It does not replay R26 and does not
infer any post-reboot live runtime, mount, container, owner-unit or IPC state.

## 2. Frozen authorities

U7 keeps the non-media-identity safety rules of the V1.1 mandatory-USB
architecture and P5 source-design delta.

Removable-media continuity follows the later frozen V1.2 removable-media
content-authority architecture.

USB_DEVICE_NODE_CONTINUITY_REQUIRED=false
USB_FILESYSTEM_UUID_CONTINUITY_REQUIRED=false
USB_PUBLIC_FINGERPRINT_CONTINUITY_REQUIRED=false
EXACT_CONTENT_IDENTITY_IS_RECOVERY_AUTHORITY=true
INTERNAL_TRANSACTION_IS_PRIMARY_AUTHORITY=true

"same USB reopen after reboot" means safe rediscovery of current compatible
media plus exact target/predecessor/backup content verification. It does not
mean /dev/sdX, MAJ:MIN, UUID or session fingerprint equality.

## 3. Independent source review findings

### 3.1 Existing media reopen path

SubprocessPrepareBackend.resolve_transaction_media():

- freshly enumerates USB/removable media;
- rejects root-backed storage;
- rejects incompatible partition shape;
- requires ext4 and N3W-UPDATE;
- rejects unsafe foreign mounts;
- mounts an unmounted compatible partition at the transaction runtime mount;
- does not gate on historical transaction UUID/fingerprint.

_stable_fingerprint() is explicitly a session observation, not cross-session
recovery authority.

RESULT=ALIGNED_WITH_V1_2

### 3.2 Existing U7 state primitive

record_predecessor_recovery_and_ha_quiesced():

- requires durable U6;
- requires exact verified predecessor recovery identity;
- requires quiesce=true;
- advances to durable U7;
- does not create or verify HA_DATA_BACKUP.

RESULT=PARTIAL_ONLY

### 3.3 Missing production backup implementation

n3w_t1_core_updater_ha_backup.py previously contained only the backup record,
protocol surface and validation.

Search found no real production create_consistent_backup implementation.
R2 used a synthetic backup and R4 explicitly deferred the real HA backup
security/restore path.

RESULT=SOURCE_GAP_CONFIRMED

### 3.4 Existing production owner semantics

n3wfc4-services-activation.service owns Manager + Home Assistant together.
Its ExecStop stops Home Assistant and Manager; Broker is separately owned.

U7 reuses that production owner. It does not stop an arbitrary raw HA
container.

RESULT=REUSE_EXISTING_OWNER_SEMANTICS

## 4. U7 source contract

Allowed source sequence:

U6
-> safe compatible media reopen
-> exact target verification
-> exact predecessor verification
-> quiesce production application owner
-> prove HA stopped + Manager stopped + Broker preserved
-> persist U7
-> create protected quiesced HA backup directly to recovery media
-> verify archive identity + authentication + decryptability + tar manifest
-> persist verified backup identity while remaining in U7
-> STOP

Forbidden in this gate:

- U7 -> U8;
- live authorization claim;
- predecessor image deletion;
- target load/start;
- rollback mutation;
- live IPC wiring that auto-executes U7;
- live T1 execution.

U7_BACKUP_COMPLETION_IMPLICIT_U8=false

## 5. Quiesce consistency

Quiesce is valid only when:

PRODUCTION_OWNER_INACTIVE=true
HOMEASSISTANT_RUNNING_COUNT=0
MANAGER_RUNNING_COUNT=0
BROKER_RUNNING_COUNT=1
BROKER_CONTAINER_CONTINUITY=true
BROKER_OWNER_ACTIVE=true

Manager is intentionally stopped because it shares the production application
owner with Home Assistant. The host-side updater, not Manager, must own long
U7 progress.

Before backup:

- if home-assistant_v2.db exists, read-only PRAGMA quick_check must return ok;
- recorder db_url in product or persistent YAML fails closed because no external
  snapshot adapter exists;
- special persistent filesystem objects and symlinks escaping the HA data root
  fail closed.

## 6. Backup security and key recovery

Do not add a second device-specific backup master secret.

KEY_AUTHORITY=/var/lib/greenhouse-manager/identity/system-root.key
KEY_AUTHORITY_SIZE=32_BYTES
KEY_AUTHORITY_EXISTING_H0_H1_SYSTEM_IDENTITY=true

The existing SYSTEM_ROOT_KEY is already part of H0/H1 system identity and its
portable recovery model. U7 derives transaction-scoped encryption and MAC
subkeys with HMAC-SHA256 domain separation.

The root key and derived keys are never written to USB, transaction JSON,
progress evidence, GitHub, process argv or environment.

On-media format:

PLAINTEXT_FULL_BACKUP_ON_USB=false
ARCHIVE_STREAM=tar.gz
ENCRYPTION=AES-256-CTR_via_OpenSSL_PBKDF2_SHA256
AUTHENTICATION=encrypt_then_HMAC_SHA256
MANIFEST_IDENTITY=SHA256_of_decrypted_numeric_owner_tar_listing
PUBLIC_SIDECAR=hash_size_algorithms_auth_tag_only

AES-CTR alone is not treated as authenticated encryption. Independent
encrypt-then-MAC HMAC is mandatory and is verified before decrypted content is
accepted.

The full plaintext archive is streamed from the quiesced HA data root into the
encryption process; no complete plaintext archive is staged on internal or
removable storage.

Immediately after creation and while the source remains quiesced, GNU tar
--compare checks the decrypted archive against the source tree. This binds
accepted U7 evidence to the exact quiesced pre-upgrade point. Later integrity
is protected by ciphertext SHA-256 + HMAC + decrypted manifest identity.

## 7. Integrity acceptance

U7 verification requires:

CIPHERTEXT_SHA256_MATCH=true
CIPHERTEXT_SIZE_MATCH=true
HMAC_MATCH=true
DECRYPT_STREAM_SUCCESS=true
MANIFEST_SHA256_MATCH=true
SOURCE_COMPARE_AT_CREATION=true
SQLITE_QUICK_CHECK=true_IF_SQLITE_EXISTS
UNSUPPORTED_EXTERNAL_STATE=false

The archive is created with numeric ownership metadata and normal tar mode
metadata, preserving the persistent /config tree for later rollback work.

Actual production restore remains a later rollback/destructive gate. The U7
provider deliberately refuses production restore so this source gate cannot
cross into U9+/rollback execution.

## 8. Failure and resume

Before U9, the internal predecessor remains authoritative.

Failure before quiesce:
- no service mutation;
- durable phase remains U6/U7;
- fail closed.

Failure after quiesce but before verified U7 completion:
- never enter U8;
- never claim authorization;
- attempt to restart the predecessor application owner with existing HA
  readiness budget;
- retain durable U6/U7;
- surface original backup failure if restart succeeds;
- if restart fails, surface ha_usb_u7_failure_recovery_failed.

Re-entry from durable U7:
- quiesce again because reboot/prior failure may have restarted HA;
- recreate and reverify the backup rather than assuming an older backup still
  represents the latest pre-cutover state.

Media after reboot:
- rediscover current safe compatible media;
- old path/MAJ:MIN/UUID/fingerprint are not continuity gates;
- exact target and predecessor contents are verified before quiesce;
- missing/corrupt content fails before HA is stopped.

## 9. Timeout and progress contract

KF-154 applies.

A long U7 backup must not be represented by one opaque SSH/client timeout.

Core source exposes progress callbacks for media reopen, quiesce, source
validation, archive encryption, source comparison, ciphertext hashing/MAC,
plaintext verification and the U7 durable stop. Long hash/MAC paths report at
64 MiB intervals.

Future live executor requirements:
- private host-side durable progress ledger;
- no secrets in heartbeat/progress;
- transport timeout greater than bounded remote operation OR reconnect/status
  protocol;
- post-start client timeout means UNCERTAINTY, not failure;
- reconcile durable internal transaction + USB mirror + remote result ledger
  before any successor;
- consumed authorization is never replayed.

No live executor is created or run in this source gate.

## 10. Source scope

Modify:
- tools/n3w_t1_core_updater_ha_backup.py
- tools/n3w_t1_core_updater_ha_usb.py
- tools/n3w_t1_core_updater_ha_install.py
- tools/n3w_t1_core_updater_host.py
- focused U7 backup tests

Do not wire HaUsbU7BackupController into current live IPC in this gate.

## 11. Acceptance

Required focused proof includes:
- U6 -> U7 success remains U7;
- authorization remains unclaimed/unconsumed;
- no U8 transition;
- post-quiesce backup failure resumes predecessor owner;
- external recorder fails closed;
- SQLite integrity failure fails closed;
- known plaintext is absent from USB archive;
- ciphertext tamper is rejected;
- backup root key is absent from USB archive/metadata;
- production owner evidence requires HA+Manager stopped and Broker preserved;
- same-media reopen uses content authority, not historical /dev/UUID/fingerprint;
- restore is unavailable in the U7 gate.

## 12. Stop boundary

SOURCE_ONLY_U7_DESIGN_ALLOWED=true
SOURCE_ONLY_U7_IMPLEMENTATION_ALLOWED=true
SOURCE_TESTS_ALLOWED=true
CI_ALLOWED=true
GITHUB_ARCHIVE_ALLOWED=true

U7_LIVE_EXECUTION=false
SERVICE_STOP=false
USB_WRITE=false
LIVE_TRANSACTION_MUTATION=false
U8_PLUS=false
MERGE=false

The next live phase remains separately gated after source review/CI closure
and a fresh post-reboot read-only baseline.


## 13. Post-implementation independent review repairs

The first implementation review found one false-stop recovery defect: the
quiesce call itself was outside the failure-recovery try block. A production
owner could therefore already have stopped Manager/Home Assistant and then
fail Broker-continuity proof without restarting the predecessor application
owner.

This was repaired before source closure. Quiesce + evidence validation now run
inside the same pre-U9 recovery envelope as backup creation and verification,
and a focused regression proves that a quiesce-proof failure triggers
predecessor-owner resume.

A second compatibility review found that importing the U7 backup module from
the shared LocalHost module would expand the dependency closure of historical
P4 read-only execution bundles. The host adapter therefore returns a small
validated public evidence mapping; the U7 controller converts that mapping to
the typed U7 evidence contract. Historical read-only bundles do not gain a new
module dependency.

The HA target-binding workflow now includes the focused U7 backup tests in its
explicit source test set.

The Current State Index top entry also restates the current Core Stack
authority bindings required by the existing repository authority checker.
This is documentation/CI authority alignment only; it does not advance the
durable U6 transaction or live lifecycle phase.

FINAL_SOURCE_REVIEW=PASS_PENDING_FRESH_CI
NEW_U7_SOURCE_BLOCKER_COUNT=0
U7_LIVE_EXECUTION=false
U8_PLUS=false
MERGE=false
