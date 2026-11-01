# N3-W T1 production stack Manager-state read-only classification progress

Date: 2026-10-11

Status: RECOGNIZED_RESTORE_ROOT / NOT_YET_ACTIVATION_READY

PR: #541 OPEN DRAFT

## 1. Observed root

```text
ROOT=/var/lib/greenhouse-manager
ROOT_PRESENT=true
ROOT_SYMLINK=false
ROOT_STAT=0:0:711
ROOT_REALPATH=/var/lib/greenhouse-manager
RECURSIVE_ENTRY_COUNT=12
SYMLINK_COUNT=0
REGULAR_FILE_COUNT=9
DIRECTORY_COUNT=3
OTHER_COUNT=0
```

The root is not an unknown random directory. Its observed members strongly match the accepted H0/H1 portable-restore role layout:

```text
RESTORE_COMPLETE.json
system-identity.json
system-root.key
system-ca.pem
system-ca-key.pem
manager-identity.json
manager/manager-state.sqlite3
broker/dynamic-security.json
broker/mosquitto.db
```

The Manager state database is a regular 0600 file owned by 999:999 and independently reports:

```text
SQLITE_QUICK_CHECK=ok
TABLE_COUNT=9
```

No symlink or special-file collision was observed.

## 2. Recognized retained authority vs active production state

The `broker/` subtree under this portable root is retained H0/H1 restore material. It is not the current production Broker data root.

Current S20 production Broker authority remains:

```text
/var/lib/n3wfc4-broker/dynamic-security.json
SHA256=95d99839ec9a6b8003e1375883a3f9263a92e0dbc49c8ca5478196027081a90a
```

Therefore the restored `broker/dynamic-security.json` and `broker/mosquitto.db` must not be promoted or copied over the current S20 Broker state by inference.

## 3. Two unresolved contract deviations

### 3.1 Root mode

Accepted H0/H1 source/ADR contract freezes the portable/candidate root as mode 0700.

Observed:

```text
/var/lib/greenhouse-manager = root:root:0711
```

The current evidence does not prove whether this 0711 transition was an intentional later production-access normalization or an untracked permission drift. Do not chmod it yet.

### 3.2 Unexpected directory named as a database

Observed:

```text
manager/registration.sqlite3
TYPE=DIR
OWNER=root:root
MODE=0755
```

The accepted persistence role layout binds Manager registration, credential lifecycle, and retirement outbox to:

```text
manager/manager-state.sqlite3
```

Historical test fixtures also use `manager/registration.sqlite3` only as a regular-file database, never as an expected directory.

Therefore:

```text
MANAGER_REGISTRATION_SQLITE3_DIRECTORY=UNEXPECTED
DELETE_AUTHORIZED=false
IGNORE_AS_BENIGN=false
```

It must be classified before production Manager activation.

## 4. Ownership observations

```text
manager/manager-state.sqlite3=999:999:0600
manager-identity.json=999:999:0600
system-identity.json=999:999:0600
system-root.key=999:999:0600
system-ca.pem=999:999:0600
system-ca-key.pem=999:999:0600
broker/*=1883:1883
RESTORE_COMPLETE.json=root:root:0600
```

Mode 0600 is consistent with the accepted member-mode contract, but current authority does not yet prove the later ownership transition of all system identity/private-key members to UID/GID 999. Do not normalize ownership by inference.

## 5. Mandatory restore/identity-claim boundary

The accepted portable-restore source contract writes `RESTORE_COMPLETE.json` with:

```text
activation_enabled=false
identity_claim_required_before_activation=true
production_services_modified=false
network_operation=false
```

The observed marker proves this root originated from that lifecycle, but the current read-only output did not inspect those marker fields or a corresponding identity-claim registry.

Production activation must not proceed until the current restored identity claim state is read and classified without exposing raw SYSTEM_ID or host identity.

## 6. Current result

```text
MANAGER_STATE_ROOT_RECOGNIZED=true
MANAGER_STATE_DATABASE_QUICK_CHECK=PASS
SYMLINK_COLLISION=false
SPECIAL_FILE_COLLISION=false
ROOT_MODE_CLASSIFICATION=PENDING
SYSTEM_MEMBER_OWNER_CLASSIFICATION=PENDING
UNEXPECTED_MANAGER_REGISTRATION_DIRECTORY=PRESENT
RESTORE_MARKER_CONTRACT=PENDING_READONLY_CHECK
IDENTITY_CLAIM_STATE=PENDING_READONLY_CHECK
ACTIVATION_READY=false
LIVE_RUNTIME_MUTATION=false
```

Next gate:

```text
NEXT_ONE_GATE=N3W_T1_PRODUCTION_STACK_RESTORE_IDENTITY_AND_MANAGER_ROOT_READONLY_FORENSIC_20261011_01
```

This next gate remains read-only. It may read only marker metadata, hashes, file types/permissions, safe SQLite schema/count metadata, and identity-claim booleans/fingerprints. It must not print raw SYSTEM_ID, MANAGER_ID, private keys, passwords, or database rows.
