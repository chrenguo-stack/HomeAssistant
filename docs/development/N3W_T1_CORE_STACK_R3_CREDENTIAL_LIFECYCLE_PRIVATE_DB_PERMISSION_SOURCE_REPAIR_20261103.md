# N3-W T1_Core_Stack R3 credential lifecycle private DB permission source repair — 2026-11-03

TASK=N3W_T1_CORE_STACK_R3_CREDENTIAL_LIFECYCLE_PRIVATE_DB_PERMISSION_SOURCE_REPAIR_20261103_01
KF=KF-139
STATE=SOURCE_REPAIR_IN_PROGRESS

## 1. Exact live failure evidence

The real T1 R3 first-registration attempt reached Manager B and created a second durable
first-registration transaction, then failed before the identity-bound 47112 pairing
window became available.

Observed Manager B binding:

- image ref: `local/greenhouse-manager:fresh-3539c8f871e2`
- image id: `sha256:9dd128f0700840d46d300f9a434e2d3fbf5abba7abbd03c7dd432e9f497be035`
- restart count: `0`
- network mode: `host`

Observed transaction:

- opened_at: `2026-11-03T04:47:55.725Z`
- state: `ACTIVE`
- phase: `BOOTSTRAP_ACCEPTED`
- cleanup_state: `NONE`
- registrations: `0`
- pairing sessions: `0`
- node leases: `0`

Observed pairing-window state after the failure:

- `pairing_window_state=CLOSED`
- `close_reason=open_failure`
- `failure_type=SimplifiedProductRuntimeError`
- TCP 47112: closed

The exact Manager log at `2026-11-03T04:47:55.773Z` records
`First-registration window open unavailable failure_type=DynamicPairingWindowError`.

## 2. Proven root cause

The live credential lifecycle database was:

`/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3`

with mode `0644`, owner uid/gid `999:999`.

The Manager registration startup path creates/opens that database through
`CredentialLifecycleStore`. Before this repair, writable creation delegated directly
to `sqlite3.connect()`, so a new file inherited the process umask and could be created
as `0644`.

Later, first-registration 47112 composition executes
`_ensure_private_database(lifecycle_path)`. Existing databases with any group/other
permission are rejected with `SimplifiedProductRuntimeError("private_database_permissions_invalid")`.

Therefore the same Manager could create or accept a `0644` credential lifecycle
database during registration startup and later reject it when opening the 47112
pairing window.

ROOT_CAUSE=PROVEN

## 3. Source repair contract

The repair is intentionally narrow:

1. when `CredentialLifecycleStore` creates a database that does not yet exist, it
   creates the inode with mode `0600` before SQLite opens it;
2. `fchmod(0600)` makes the newly-created file exact even under an unusual umask;
3. an already-existing file is not silently chmod-normalized;
4. the existing dynamic pairing private-database gate remains fail-closed for unsafe
   pre-existing files;
5. no live T1 database, pairing window, credential, DynSec state or board state is
   changed by this source-repair gate.

## 4. Regression coverage

Focused regression coverage proves both sides of the contract:

- a credential DB created by the Manager-style store path is exactly `0600` even
  with process umask `000`, and then passes the same private-database gate used by
  first-registration pairing composition;
- a pre-existing `0644` credential DB remains `0644` after store open and is still
  rejected by the private-database gate.

## 5. Live migration boundary

This source repair prevents recurrence on clean/future creation. It does not silently
repair the already-existing real-T1 `0644` file.

The current real T1 must remain untouched in this gate. After source CI and review
close, any repair of the existing T1 state requires a separate explicit live-mutation
gate with fresh read-only preflight and transaction-state reconciliation first.

LIVE_MUTATION=false
BOARD_ACCESS=false
SECOND_REGISTRATION_RETRY=false
MERGE=false

## 6. Source authority

BASE_HANDOFF_PR=768
BASE_HANDOFF_HEAD=7be27ab4c372376537d3de3350a716c7aa920ccb
SOURCE_REPAIR_BRANCH=fix/n3w-r3-credential-lifecycle-private-db-permission-20261103

The exact repair head and CI closure are appended only after fresh GitHub CI completes.
