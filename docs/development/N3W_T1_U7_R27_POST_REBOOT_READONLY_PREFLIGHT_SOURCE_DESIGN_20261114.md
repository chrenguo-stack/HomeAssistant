# N3W T1 U7 R27 Post-Reboot Read-Only Preflight Source Design — 2026-11-14

## 1. Purpose

R27 is the first gate after U7 critical-node source review closed at
d973136d05054ce6a547b4e1b43b596f8eb46d60 with 16/16 fresh CI SUCCESS.

R27 does not execute U7. It re-establishes the real T1 baseline after the
planned reboot and determines whether a separate U7 source-activation gate may
be prepared.

## 2. Frozen entry authority

- R26 is CLOSED_PASS, claimed + consumed, and permanently no-replay.
- durable transaction phase must remain U6_PREDECESSOR_RECOVERY_PREPARING.
- durable transaction SHA-256 must remain
  7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe.
- product U9 authorization fields must remain false/false/null.
- exact predecessor recovery content remains:
  - archive SHA-256 34cec37ab021e1081e236502bfd06760894f6bca93bd8d6bf99d8d90bb89848d
  - archive size 743074537 bytes
  - portable identity SHA-256
    8b4d4376e2ab339347abb4aa554d3a5cc6f93ea20b0ee3c22ca8e29ae14b16c3.

## 3. Read-only checks

R27 verifies:

1. current boot observation and R26 durable success ledger, requiring R26 success to predate the current boot epoch;
2. exact durable U6 transaction and no product authorization claim;
3. host/services-owner/broker-owner health after reboot;
4. exact Manager/Home Assistant/Broker runtime image binding and restart count;
5. Manager IPC still reports PREDECESSOR_RECOVERY_PREPARING;
6. exact installed U6 source set, including the pre-U7 host.py Git blob identity, proving U7 source has not been partially or silently activated;
7. one safe ext4 N3W-UPDATE removable medium, excluding the root device;
8. V1.2 content authority, with no historical device-node, UUID or fingerprint continuity gate;
9. exact target archive and exact predecessor archive;
10. no HA backup residue before U7;
11. HA data root presence, metadata, logical measured bytes, no external symlink/special file, and no unsupported db_url;
12. SQLite file shape is inspected without opening the live database; quick_check is deferred until mandatory quiesce so R27 cannot create/update WAL shared-memory state;
13. SYSTEM_ROOT_KEY path/owner/mode/length metadata only. Key bytes are never read or emitted by R27;
14. OpenSSL AES-256-CTR/PBKDF2-related CLI capability and GNU tar feature availability;
15. current USB free capacity for remaining U7 work: HA backup budget + working budget + reserve.

If the USB is not mounted after reboot, R27 may temporarily mount the one
eligible partition with ro,noload,nodev,nosuid,noexec (accepting the kernel-reported norecovery alias), inspect it, then unmount
and remove only the temporary /run directory. This is not USB data mutation.

## 4. Source activation decision

R27 intentionally expects the exact R26/U6 installed source set. The reviewed
U7 candidate changes the backup/controller/state path and production-owner
quiesce support. Therefore a clean PASS reports:

U7_SOURCE_ACTIVATION_REQUIRED=true
U7_SOURCE_ACTIVATION_ELIGIBLE=true
U7_LIVE_EXECUTION_ELIGIBLE=false

The next gate after a real R27 PASS is a separate U7 source-activation design
and authorization. Source activation must not stop Home Assistant, create the
HA backup, enter U7, or claim product U9 authorization.

## 5. KF-154 boundary

R27 is read-only and has no one-shot mutation claim. Its SSH budget is sized
for full target/predecessor hashing. KF-154 durable progress/result-ledger
requirements remain mandatory for the later live U7 executor; R27 does not
weaken or satisfy that future requirement.

## 6. Stop boundary

R27_READ_ONLY=true
SOURCE_DEPLOYMENT=false
SERVICE_STOP=false
SERVICE_RESTART=false
USB_DATA_MUTATION=false
TRANSACTION_MUTATION=false
U7_TRANSITION=false
U8_PLUS=false
BOARD_ACCESS=false
MERGE=false

STATUS=SOURCE_AND_TEST_PREPARED_FRESH_CI_PENDING
NEXT_IF_SOURCE_CI_PASS=REAL_T1_R27_READONLY_PREFLIGHT
NEXT_AFTER_REAL_R27_PASS=DEFINE_U7_SOURCE_ACTIVATION_GATE


## 7. Review-discovered U7 live capacity blocker and repair

R27 source review found that a read-only preflight capacity PASS cannot be the
actual U7 write-safety boundary. HA data and USB free space may change after
R27.

The U7 controller is therefore repaired so that after production-owner
quiesce, and before any new HA backup bytes are written, it freshly measures
the quiesced HA data tree and current USB free space. It requires the current
HA backup budget plus transaction working budget plus removable-media reserve.
A capacity failure creates no new backup and resumes the predecessor
application owner.

For U7 re-entry, a prior verified encrypted backup may be counted only as
reclaimable space and only when the current on-media regular-file size matches
its durable backup identity. Missing prior backup bytes simply count as zero
reclaimable bytes.

U7_FRESH_BACKUP_CAPACITY_GATE=MANDATORY
R27_CAPACITY_PASS_IS_ADVISORY_ONLY=true
R27_SQLITE_QUICK_CHECK=DEFERRED_UNTIL_QUIESCE
LIVE_U7_EXECUTION=false


POST_REBOOT_EPOCH_PROOF_REQUIRED=true


U7_RECLAIMABLE_BACKUP_ACCOUNTING=ALLOCATED_BLOCKS_ONLY
U7_RECLAIMABLE_BACKUP_HARDLINK_ALLOWED=false
U7_ORPHAN_FIXED_BACKUP_PATH_RECLAIMABLE=true

A stale fixed-path encrypted backup left by an earlier failed U7 re-entry may
be treated only as bytes that the provider is about to unlink. Reclaimable
capacity uses allocated filesystem blocks, not logical file length, and rejects
multi-link files. This prevents both retry deadlock and sparse/hard-link
capacity overestimation.
