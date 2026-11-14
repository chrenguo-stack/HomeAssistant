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

1. current boot observation and R26 durable success ledger;
2. exact durable U6 transaction and no product authorization claim;
3. host/services-owner/broker-owner health after reboot;
4. exact Manager/Home Assistant/Broker runtime image binding and restart count;
5. Manager IPC still reports PREDECESSOR_RECOVERY_PREPARING;
6. exact installed U6 source set, proving U7 source has not been silently activated;
7. one safe ext4 N3W-UPDATE removable medium, excluding the root device;
8. V1.2 content authority, with no historical device-node, UUID or fingerprint continuity gate;
9. exact target archive and exact predecessor archive;
10. no HA backup residue before U7;
11. HA data root presence, metadata, logical measured bytes, no external symlink/special file, and no unsupported db_url;
12. live read-only SQLite quick_check when available; busy/locked may be deferred until the mandatory quiesced check;
13. SYSTEM_ROOT_KEY path/owner/mode/length metadata only. Key bytes are never read or emitted by R27;
14. OpenSSL AES-256-CTR/PBKDF2-related CLI capability and GNU tar feature availability;
15. current USB free capacity for remaining U7 work: HA backup budget + working budget + reserve.

If the USB is not mounted after reboot, R27 may temporarily mount the one
eligible partition with ro,noload,nodev,nosuid,noexec, inspect it, then unmount
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
