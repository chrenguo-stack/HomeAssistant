# N3-W T1 U7 R30 HA quiesce / data-backup live executor source design
# 2026-11-15

STATUS=SOURCE_IMPLEMENTED_UNGRANTED_CI_PENDING
REPOSITORY=chrenguo-stack/HomeAssistant
PR=807
BASE_HEAD=1143f428cd8d861a64ff758acf1d757ca49d1f7b
R29_LIVE_CLOSURE=CLOSED_PASS
R29_REPLAY_PERMITTED=false

## 1. Gate identity

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U7_HA_QUIESCE_DATA_BACKUP_R30_20261115_01
PACKAGE=tools/execution_packages/n3w/r7a/u7_ha_quiesce_data_backup_r30
CURRENT_DURABLE_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING
TARGET_SUCCESS_PHASE=U7_HA_QUIESCED_DATA_BACKUP_PREPARING
U7_LIVE_AUTHORIZATION_GRANTED=false
REPLAY_PERMITTED=false
U8_PLUS=false
```

R30 is an execution package for the already frozen U6 -> U7 product path. It
does not introduce a new product lifecycle phase and it does not reuse the
consumed R29 grant.

## 1.1 Post-source-review dependency repair prerequisite

Independent post-commit review found one post-R29 runtime-source gap before R30 can
be preflighted:

```text
INSTALLED_PREPARE_HOST_BLOB=59b06d3aa595a6c4801b96d6b992b174a700ca31
INSTALLED_PREPARE_HOST_SHA256=0d0c96d7ae2f26c2d2ae8388e6ee75ad0616081a6cdcb98727f2131dab31c30e
INSTALLED_BACKUP_CAPACITY_REVALIDATION=false

TARGET_PREPARE_HOST_BLOB=9e3dd9180d88e354f81480458220f1c092b30aa8
TARGET_PREPARE_HOST_SHA256=72cdbc94e9e3e4694ac00ad8fb01f5a2877d8f80a4b07e9c0236b546e43874c2
TARGET_BACKUP_CAPACITY_REVALIDATION=true
```

R25 -> R29 source-delta review shows that every other U7 production source file
changed in that interval was already activated by repaired R29. The missing
runtime dependency is therefore bounded to `n3w_t1_core_updater_ha_prepare_host.py`.

Before R30 read-only preflight, a separate ungranted one-file source activation
gate is required:

```text
PREREQUISITE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U7_PREPARE_HOST_SOURCE_ACTIVATION_R30S_20261115_01
R30S_LIVE_AUTHORIZATION_GRANTED=false
R30S_ACTIVATED_SOURCE_FILE_COUNT=1
R30S_SERVICE_STOP=false
R30S_TRANSACTION_MUTATION=false
R30S_USB_MUTATION=false
R30S_U7_TRANSITION=false
```

R30 now requires durable R30S claim/success evidence plus the target
prepare-host SHA-256 before its own preflight can continue. A matching file
without R30S durable authority is not sufficient.

## 2. Current source boundary

This source commit is deliberately ungranted:

```text
live_execution_authorized=false
authorization_state.granted=false
authorization_state.claimed=false
authorization_state.consumed=false
authorization_state.replay_permitted=false
```

Repository-only source implementation, focused tests, CI, review and a later
read-only T1 preflight are allowed. HA/Manager stop, transaction mutation,
USB writes and U7 transition are not authorized by this source commit.

## 3. Read-only preflight contract

Before any future live grant, the executor requires all of the following to
match the post-R29 authority:

- exact U6 transaction SHA-256 and transaction ID;
- consumed/no-replay R26 and R29 durable ledgers;
- exact installed transitive source SHA-256 set;
- production owner units and exact Manager/Home Assistant/Broker containers;
- Broker running with restart_count=0;
- already-mounted expected recovery-media mount, ext4 and read-write;
- exact target and predecessor recovery identities;
- fresh backup-capacity revalidation;
- supported HA persistent-data tree with no unsupported external recorder;
- SQLite read-only quick_check when the recorder database exists;
- valid 32-byte system root key without exporting key material;
- required OpenSSL and tar tools.

The preflight does not mount media. The expected recovery media must already be
mounted at the frozen runtime mount before the preflight begins. This avoids a
read-only gate silently becoming a mount mutation.

```text
PREFLIGHT_SERVICE_STOP=false
PREFLIGHT_TRANSACTION_MUTATION=false
PREFLIGHT_USB_WRITE=false
PREFLIGHT_AUTHORIZATION_CLAIM=false
```

## 4. Future live execution contract

Only a separate grant-only successor may make the R30 manifest executable.
On a future explicitly authorized live run:

1. the same embedded preflight must pass;
2. R30 writes one private durable authorization claim and consumes it before
   invoking the mutation path;
3. the existing `HaUsbU7BackupController` remains the product authority;
4. the production application owner stops Manager + Home Assistant together;
5. Broker must remain running and retain exact container identity;
6. the controller records durable U7, creates the protected HA backup, verifies
   it and records the verified backup identity;
7. execution stops in U7; no U8 recovery admission is called.

Product U9 authorization fields remain untouched. R30's execution grant is an
execution-package safety grant, not the product U9 authorization.

## 5. Backup and failure safety

The existing production backup provider remains authoritative:

- encrypted HA archive;
- encrypt-then-HMAC authentication;
- transaction-scoped keys derived from the existing system root key;
- source-tree validation and SQLite integrity check;
- source comparison while HA remains quiesced;
- ciphertext checksum, manifest identity and decryptability verification.

If a failure occurs after quiesce, the existing U7 controller attempts to
restart the predecessor application owner. R30 records whether recovery was
attempted and whether the running baseline was restored. It never enters U8 on
failure.

## 6. Timeout / no-replay contract

R30 adds a private durable host ledger:

```text
authorization_claim.json
progress.json
success.json
failure.json
```

Progress records contain only bounded phase names and numeric progress values.
They contain no raw keys, backup contents or credentials.

The local wrapper invokes the remote execute path at most once. If SSH/client
transport becomes uncertain after invocation, it performs one status
reconciliation against the remote ledger and transaction state. If a terminal
result cannot be proven, the result is STOP_UNKNOWN with authorization treated
as consumed and replay forbidden. There is no blind live retry.

## 7. Focused test requirements

The source gate must prove:

- manifest remains ungranted;
- exact post-R29 U6/transitive source binding;
- executor and embedded remote script compile;
- read-only preflight cannot mount or stop services;
- R26/R29/runtime/media/backup prerequisites are bound;
- live controller is invoked only after durable execution claim;
- success stops in U7 with verified backup and Broker preserved;
- post-quiesce failure attempts predecessor-owner recovery;
- progress and terminal ledgers are durable;
- timeout path reconciles status and has one execute invocation only;
- product U9 authorization fields remain untouched;
- target-binding CI explicitly covers R30 package and focused tests.

## 8. Stop boundary

```text
SOURCE_IMPLEMENTATION_ALLOWED=true
SOURCE_TESTS_ALLOWED=true
CI_ALLOWED=true
GITHUB_ARCHIVE_ALLOWED=true
T1_READONLY_PREFLIGHT_ALLOWED_AFTER_SOURCE_CLOSURE=true

U7_LIVE_EXECUTION_AUTHORIZED=false
SERVICE_STOP_AUTHORIZED=false
TRANSACTION_MUTATION_AUTHORIZED=false
USB_WRITE_AUTHORIZED=false
U8_PLUS_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

Fresh CI and an independent exact-source review are mandatory before the R30S
T1 read-only preflight. R30 itself remains blocked until R30S live source
activation is separately authorized, consumed and closed PASS. A successful read-only preflight still does not grant live
U7 execution.
