# N3W T1 U13B Stage D D3 — Host-only reconciliation writer source design

Date: 2026-11-17  
Scope: repository/source design only  
Authority baseline: `e92ed76c04ce753d6c12320af93a19f6c99fdf2f`  
PR: #807  
Status: DESIGN_ONLY

## 1. Purpose

Stage C classifies the durable USB/host split. D1 persists the exact successor host
transaction to USB before the phase commit marker. D2 proves the real-world
postcondition for each legal USB-ahead rollback edge.

D3 may repair **only the host transaction document** after all of those proofs
still hold. It must never reconstruct successor fields, replay a rollback
operation, rewrite USB metadata, or treat USB phase alone as write authority.

## 2. Independent design findings

### 2.1 Host state write is durable but is not compare-and-swap

`HaUsbStateStore.write()` validates the document, writes a private temporary
file, fsyncs it, atomically replaces the active file, and fsyncs the state
directory. This is suitable for the final durable host write.

However, `write()` does not compare the current active transaction with an
expected predecessor. A stale caller could therefore overwrite a newer host
transaction if D3 simply performed:

```text
observe -> write(usb_mirror)
```

D3 must use the existing global `HaUsbStateStore.lock()` / `V2StateStore.lock()`
directory flock and re-read the active host transaction inside that lock before
any reconciliation write.

### 2.2 Existing write_required=false media resolution is not strict read-only

`SubprocessPrepareBackend.resolve_transaction_media(..., write_required=False)`
still creates host runtime mount directories and, when the USB is unmounted,
uses a normal ext4 mount. That can allow journal replay or other filesystem
metadata writes and therefore is not a sufficient contract for a feature named
"host-only reconciliation".

D3 requires a dedicated reconciliation media path:

```text
UNMOUNTED USB
  -> mount ro,noload,nodev,nosuid,noexec
  -> read only

ALREADY MOUNTED RO AT EXACT EXPECTED PATH
  -> verify exact source/path/options
  -> read only

ALREADY MOUNTED RW
  -> STOP
  -> no automatic remount

MOUNTED ELSEWHERE / WRONG UUID / AMBIGUOUS DEVICE
  -> STOP
```

No D3 path may call USB metadata sync or any USB atomic-json writer.

## 3. Proposed source components

### 3.1 Dedicated read-only reconciliation media resolver

Add a narrowly named API rather than extending the ambiguous
`write_required: bool` contract, for example:

```python
resolve_transaction_media_for_reconciliation(
    transaction
) -> PreparedUsbMedia | None
```

Required behavior:

- bind to the transaction ID and filesystem UUID already present in the host transaction;
- accept exactly one eligible removable USB device and one partition;
- reject root-device or production-mount backing devices;
- never format, fsck-repair, self-test, or write USB data;
- if unmounted, mount with `ro,noload,nodev,nosuid,noexec`;
- if already mounted, require the exact expected mount path and read-only state;
- reject an existing read-write mount instead of remounting it;
- create only private host-side runtime mount directories when needed;
- return no write authority.

### 3.2 U13BHostOnlyReconciliationWriter

Introduce a separate orchestrator. It must not be folded into
`HaUsbU13BRollbackController._persist()`, because normal rollback persistence
intentionally writes USB first and Host second, while D3 must write **Host only**.

Suggested result states:

```text
RECONCILED
ALREADY_EXACT
```

All other classifications raise a fail-closed error.

## 4. Commit algorithm

An optional preflight may resolve/read/observe before the lock for diagnostics,
but it grants no write authority.

The authoritative commit pass is:

```text
with transaction_store.lock():

  1. current = transaction_store.read()
     - missing/invalid => STOP

  2. validate current transaction

  3. resolve the same bound USB through the dedicated strict read-only resolver
     - unavailable/ambiguous/RW/wrong binding => STOP

  4. snapshot = backend.read_transaction_metadata(current, media)
     - existing private regular-file and schema checks apply

  5. split = classify_u13b_usb_host_split(current, media, snapshot)

  6. if split == HOST_USB_EXACT:
       require snapshot.host_transaction == current
       return ALREADY_EXACT
       - no host write
       - no observer operation replay

  7. require split == USB_ONE_PHASE_AHEAD_RECONCILABLE
     - HOST_ONE_PHASE_AHEAD_STOP => STOP
     - DIVERGENT_OR_UNKNOWN_STOP => STOP

  8. successor = validate(snapshot.host_transaction)
     - use exact mirrored successor
     - do not rebuild transition fields
     - do not alter updated_at_unix

  9. rerun the phase-specific D2 read-only postcondition observer
     inside the same host transaction lock
     - literal True only
     - false/error => STOP

 10. recheck the in-memory successor is still the exact snapshot mirror

 11. transaction_store.write(successor)
     - ONLY mutation authorized by D3
     - no backend.sync_transaction_metadata()
     - no rollback runtime operation

 12. confirmed = transaction_store.read()
     require confirmed == successor

 13. reclassify confirmed vs the same USB snapshot
     require HOST_USB_EXACT

 14. return RECONCILED
```

The existing atomic host write provides file + directory durability. The global
transaction lock prevents cooperating updater/IPC writers from changing the
active transaction between the authoritative re-read and host write.

## 5. Why the observer is rerun under the lock

A D2 preflight result is advisory only. It may become stale before commit.

D3 therefore reruns the exact observer immediately before host persistence.
There is no updater-controlled state mutation between the successful observer
and `transaction_store.write(successor)`.

This does not claim to freeze arbitrary external Docker/systemd actors forever.
It gives D3 the same point-in-time evidence model already used by durable U13B
phase transitions, while removing the stale-host overwrite race.

## 6. Edge-specific write authority

The mirrored successor and the D2 observer must match exactly:

| Host predecessor | USB successor | Required D2 proof before host-only write |
|---|---|---|
| U9/U10/U11/U12 | U13B0 | exact target/predecessor/backup recovery authorities |
| U13B0 | U13B1 | target cleanup complete; services quiesced; Broker exact |
| U13B1 | U13B2 | exact predecessor image present; services quiesced |
| U13B2 | U13B3 | exact restored HA tree + authenticated backup + immutable SQLite check |
| U13B3 | U13B4 | exact predecessor runtime/binding/peers/config mount |
| U13B4 | U13B | predecessor terminal health, MQTT, HTTP, persistent binding |

No edge may be inferred from phase rank alone.

## 7. Crash / retry semantics

### Crash before host write

Host remains predecessor; USB remains exact successor. Next D3 invocation reruns
all classification and postcondition checks.

### Crash during atomic host write

The host state is either the old valid transaction or the new valid successor.
No partially written JSON is accepted.

### Crash after host write but before response

Next invocation observes `HOST_USB_EXACT` and returns `ALREADY_EXACT` without
another write or rollback operation.

### Host advances before D3 acquires the lock

The authoritative read inside the lock wins. The stale preflight is discarded.

### USB disappears or changes before commit

The locked pass cannot prove the same bound media and stops without host write.

## 8. Required failure codes

At minimum keep distinct fail-closed categories for:

```text
u13b_reconciliation_transaction_missing
u13b_reconciliation_usb_unavailable
u13b_reconciliation_usb_not_readonly
u13b_reconciliation_host_ahead_stop
u13b_reconciliation_divergent_stop
u13b_reconciliation_postcondition_failed
u13b_reconciliation_write_verify_failed
u13b_reconciliation_postwrite_split_invalid
upgrade_transaction_busy
```

Exact names may be normalized during implementation, but failures must remain
diagnostically distinguishable and must not be converted into retry-with-operation.

## 9. Source tests required before D3 can close

### 9.1 Six-edge success matrix

Parameterize all six legal predecessor/successor edges and prove:

- exact USB mirror selected;
- correct D2 observer called exactly once in the commit pass;
- exactly one host write;
- no USB metadata sync;
- no rollback operation call;
- post-write classification is `HOST_USB_EXACT`.

### 9.2 Negative split matrix

For each of:

- HOST_USB_EXACT;
- HOST_ONE_PHASE_AHEAD_STOP;
- DIVERGENT_OR_UNKNOWN_STOP;
- two-or-more-phase USB lead;
- invalid/tampered mirror;
- wrong transaction ID;
- wrong filesystem UUID;
- wrong recovery authority;

prove either safe no-op (only exact) or STOP with zero host writes.

### 9.3 Stale-state / locking tests

Prove:

- busy global lock => zero writes;
- host changes between optional preflight and lock => commit uses fresh state and stops/no-ops as appropriate;
- no stale expected transaction can overwrite a newer host transaction;
- concurrent new-upgrade preparation remains serialized by the same root-directory lock.

### 9.4 Crash idempotence tests

Inject failure:

- before write;
- after atomic write / before readback;
- after readback / before return.

The next invocation must converge to either a fresh reconciliation attempt or
`ALREADY_EXACT`, never operation replay.

### 9.5 Strict read-only USB tests

Prove:

- unmounted USB uses `ro,noload,nodev,nosuid,noexec`;
- existing exact RO mount is accepted;
- existing RW mount is rejected;
- mount elsewhere is rejected;
- no `_atomic_json`, sync metadata, fsync-to-USB writer, format, self-test,
  image load, HA restore, service stop/start, or binding rewrite is reachable.

### 9.6 Exact transaction tests

Prove host result equals the mirrored successor document exactly:

- preserved `failure_code`;
- preserved `rollback_origin_phase`;
- preserved all rollback evidence;
- preserved `updated_at_unix`;
- terminal status/recovery_required exact at U13B.

## 10. Explicit non-goals

D3 does not:

- authorize real T1 rollback;
- start or resume rollback operations;
- repair Host-one-phase-ahead state;
- repair divergent/unknown state;
- rewrite USB transaction metadata;
- reconstruct a successor from phase.json;
- merge PR #807;
- define Stage E.

## 11. Acceptance boundary

D3 source implementation may be considered CLOSED_PASS only after:

```text
D2_CLOSED_PASS=true
STRICT_READONLY_USB_RESOLVER=true
GLOBAL_TRANSACTION_LOCK_USED=true
LOCKED_HOST_REREAD=true
LOCKED_USB_REREAD=true
LOCKED_POSTCONDITION_REOBSERVATION=true
EXACT_USB_MIRROR_ONLY=true
HOST_ONLY_WRITE=true
USB_METADATA_WRITE=false
ROLLBACK_OPERATION_REPLAY=false
POSTWRITE_HOST_READBACK_EXACT=true
POSTWRITE_SPLIT=HOST_USB_EXACT
SIX_EDGE_TEST_MATRIX=PASS
STALE_STATE_TESTS=PASS
CRASH_IDEMPOTENCE_TESTS=PASS
EXACT_HEAD_CI=PASS
INDEPENDENT_SOURCE_REVIEW=PASS
U13B_LIVE_EXECUTION_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## 12. Next source gate

```text
NEXT_ONE_GATE=U13B_STAGE_D_D3_HOST_ONLY_RECONCILIATION_WRITER_SOURCE_IMPLEMENTATION
```


## 13. Implementation review delta — serialization and RO mount lifetime

D3 implementation review found two additional operational requirements.

First, the normal U13B rollback controller must hold the same
`HaUsbStateStore.lock()` as the Host-only reconciliation writer. Otherwise a
normal rollback could advance Host between D3's final guard read and atomic Host
replacement. The controller is therefore serialized through the shared
root-directory flock without changing rollback phase semantics.

Second, a D3 RO+noload mount cannot remain mounted after reconciliation because
the next normal rollback step must persist new USB transaction metadata. D3
therefore releases the product-owned reconciliation mount in a `finally` path
for success, ALREADY_EXACT, and failure. It never remounts the USB read-write.

```text
ROLLBACK_CONTROLLER_SHARED_TRANSACTION_LOCK=true
D3_RECONCILIATION_RO_MOUNT_TEMPORARY=true
D3_RECONCILIATION_RO_MOUNT_RELEASE_FINALLY=true
USB_REMOUNT_RW_BY_D3=false
```
