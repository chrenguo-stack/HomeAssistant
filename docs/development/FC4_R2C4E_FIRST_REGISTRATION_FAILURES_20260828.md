# FC4 R2C4E First-Registration Failures — 2026-08-28

> Public-safe engineering archive. Raw hardware identifiers, pairing IDs, Setup Secret, Wi-Fi credentials, MQTT credentials, private IP addresses and private evidence paths are intentionally excluded.

## Scope

This note records the failure chain discovered during N3-W / FC4 Board C current-main first-registration acceptance on Spare T1. It supplements `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`; private evidence remains outside the public repository.

Frozen source authority at the start of this sequence:

- current-main commit: `1f80d54ff5f84056e0559a7d8cc80427c5e0bb14`
- tree: `f3b8095c62e8a4838eb1b614f05c932f54f5226d`
- Manager version: `0.4.99`

## 1. Pairing source-order correction

The first R2C4E planning pass assumed the Board C Setup Secret could be imported into Manager before STA provisioning / first network hello. Exact current-main source review disproved this ordering.

The supported order is:

```text
Board C normal application boot
  -> operator STA provisioning
  -> Board C Manager discovery
  -> POST /v2/pairing/hello
  -> Manager creates/refreshes PENDING registration
  -> exact Setup Secret import through Manager-owned local IPC
  -> /begin retry
  -> fresh first-registration transaction
```

`import_setup_secret()` requires the exact registration to already exist in `PENDING`; therefore pre-hello import is invalid. Because the PENDING pairing pointer has a finite TTL and may renew after expiration, a preclaim pairing-material hash must not be treated as permanent mutation authority. Future mutable gates must perform a final read-only claim-boundary pairing rebind after authorization is granted but before CLAIM.

## 2. Operator/network evidence capture gap

During the first R2C4E execution, the operator did perform a cold-power boot, submitted Wi-Fi credentials through the setup flow, and observed Board C online in the router. The machine closure nevertheless reported boot / captive portal / STA connection as `NOT_CONFIRMED` because the executor had not captured those manual checkpoints as machine evidence.

Subsequent read-only packet tracing proved:

- Board C UDP Manager discovery reached Spare T1 repeatedly;
- Spare T1 sent valid discovery responses;
- Board C HTTP `/hello` reached current-main Manager repeatedly.

Therefore the failure was not a Board C Wi-Fi or discovery failure. Future mixed operator/automation gates must explicitly record operator checkpoints and router/network authority instead of interpreting missing automated evidence as proof that the action did not occur.

## 3. Registration SQLite single-file bind failure

The first `/hello` requests reached Manager but no PENDING registration was created. Read-only RCA proved:

```text
sqlite3.OperationalError
message class: unable to open database file
failure actor: Manager /hello handler
```

The registration database file itself was present, private, owned by Manager UID/GID, and open read-write. The actual failure was the deployment topology:

```text
Manager rootfs: read-only
registration.sqlite3: writable single-file bind
parent directory inside container: not writable
SQLite mode: DELETE / rollback journal
required side-file: registration.sqlite3-journal
result: journal creation cannot open -> transaction fails
```

The repair changed only the registration state topology: the same canonical database object is exposed through a dedicated private writable directory bind and `GH_PAIRING_DB_PATH` is rebound to the database inside that directory. The repaired registration database subsequently accepted writes.

## 4. Systemic SQLite mount defect discovered after registration repair

After registration storage was repaired, Board C advanced to first credential staging. The next failure occurred in application-key staging with the same SQLite `unable to open database file` class.

A complete read-only write-path sweep proved the pattern is systemic. Five write-capable SQLite roles were checked:

| Role | Current topology after registration repair | Write-safe |
|---|---|---|
| registration | dedicated writable directory bind | yes |
| application-key authorization | writable single-file bind under non-writable parent | no |
| system peer trust | writable single-file bind under non-writable parent | no |
| credential lifecycle | writable single-file bind under non-writable parent | no |
| replay state | writable single-file bind under non-writable parent | no |

The application-key file directory itself is already a private writable directory bind and does not require repair.

The remaining four SQLite objects must be repaired together, not serially one failure at a time. Each repair must preserve the existing canonical database object, expose a private writable parent directory, avoid masking `/var/lib/greenhouse-manager/n3w` or the relay-key directory, and retain the read-only Manager root filesystem.

## 5. R4 partial-state rollback semantics

The failed first-registration attempt temporarily provisioned a DynSec node credential and then removed it during rollback. DynSec ChangeIndex therefore advanced legitimately; it must not be manually rewound.

Frozen post-R4 security baseline:

- DynSec ChangeIndex: `19`
- no durable Board C DynSec credential
- no Board C credential-lifecycle record
- no active/staged Board C application key
- no Board C application-key file
- no active Board C node binding

The failed automatic NODE_ID allocation leaves a `RETIRED` lease tombstone and closed node-history entry. Source review proved this is expected first-registration rollback behavior: historical NODE_ID leases, including `RETIRED`, remain permanently reserved and are not reused by automatic allocation. This is not Board C hardware retirement and must not be deleted as “stale” state.

Board C later renewed its PENDING pairing pointer after the previous pairing session expired. Source and event evidence proved this renewal is valid. The current pairing pointer remains a short-lived runtime authority and must be rebound again at the mutation claim boundary.

## 6. Regression / deployment rules

The following rules are now required for FC4 successors and should become machine-checkable regression guards:

1. Every SQLite database that current-main can mutate must be audited as a database-plus-parent-directory object, not merely as a writable file.
2. A writable SQLite single-file bind is forbidden when the container parent is not writable and the journal mode can require sibling side-files.
3. Rendered Compose and live mount preflight must enumerate all write-capable SQLite roles and require a writable private parent for each.
4. Directory-bind repairs must preserve the exact existing DB object and must not mask unrelated Manager state mounts.
5. Pairing Setup Secret import must follow `hello -> PENDING`; it is not valid before first hello.
6. Preclaim pairing hashes are snapshots only. Mutable pairing gates must rebind the current PENDING pairing pointer after authorization and before CLAIM.
7. Mixed manual/automated provisioning gates must record operator completion checkpoints explicitly; missing automated observation is not evidence that the operator action did not occur.
8. DynSec ChangeIndex is monotonic audit state. A transient provision/deprovision rollback may legitimately advance it even when no durable node credential remains.
9. A RETIRED NODE_ID lease produced by failed fresh automatic approval is a non-reusable tombstone, not an active binding and not a hardware-retirement marker.

## 7. Current continuation point

At archive time:

- registration DB directory-bind repair is retained and must not be rolled back;
- four SQLite roles remain proven write-unsafe: application-key authorization, peer trust, credential lifecycle and replay;
- Board C partial state is clean for fresh first-registration resume;
- Board C remains STA-configured; no reset, re-provisioning, flash or NVS erase is required;
- next planned gate is the consolidated four-database directory-bind repair mutation preclaim, followed by one bounded first-registration resume transaction.

The detailed raw closures, exact private pairing material and private host paths remain private evidence and are not reproduced here.
