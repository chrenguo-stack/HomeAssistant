# N3-W T1 R1 review blockers focused closure review

Date: 2026-10-13

TASK=
`N3W_T1_GOLDEN_MASTER_FIRSTBOOT_SOURCE_DECOMPOSITION_REPAIR_R1_REVIEW_BLOCKERS_FOCUSED_CLOSURE_REVIEW`

## 0. Review boundary

~~~text
READ_ONLY_SOURCE_REVIEW=true
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
R3_CLEANUP=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
AUTHORIZATION_08_GRANTED=false
MERGE=false
R2_START=false
~~~

Reviewed product source authority:

~~~text
R1_REVIEW_REPAIR_SOURCE_HEAD=3dbd9723063e1f5f14605b1bcf13bee4c54c84ab
PR541_HEAD_AT_REVIEW=5591d5e06beaeef6b50b4b2b77622db2b79f433d
~~~

The four commits after the exact product source head are documentation-only. No product source drift exists between them.

## 1. CI closure evidence

At PR head `5591d5...`, all required focused/extended workflows are terminal SUCCESS:

~~~text
N3W T1 deployment gate CI
run=38272887596
SUCCESS

greenhouse-manager CI
run=38272887259
SUCCESS

N3W T1 fresh bootstrap deployable payload CI
run=38272887237
SUCCESS

N3W T1 fresh install exact ARM64 CI
run=38272887409
SUCCESS

Public repository safety CI
run=38272887251
SUCCESS

H0 H1 initialization and portable restore CI
run=38272887359
SUCCESS

N3W T1 fresh install host-only CI
run=38272887347
SUCCESS
~~~

No completed non-success workflow exists on that PR head.

CI is necessary evidence but does not override source-review findings.

## 2. A1 — legacy commit compatibility

### Review

The repair introduces:

- `_validate_commit_targets_absent()`;
- `_move_commit_targets()`.

Legacy `commit_candidate()` now:

1. checks every target in `FINAL_DIRS + FINAL_FILES`;
2. begins no rename until the full target set is absent;
3. moves in the original `FINAL_DIRS`, then `FINAL_FILES` iteration order;
4. performs daemon-reload only after the moves.

The new public/instance-specific commit methods retain their narrower ownership contracts.

A regression test creates a later public-target collision and proves the earlier instance source remains unmoved.

### Verdict

~~~text
A1_LEGACY_COMMIT_COMPATIBILITY=CLOSED
~~~

The R1 regression identified by the independent review is repaired without removing the ownership split.

## 3. A2 — durable authority owner/mode validation

### Review

The repaired firstboot contract now fail-closes on:

- transaction root that is symlink/non-directory;
- wrong transaction-root owner;
- transaction-root mode other than 0700;
- record that is symlink/non-regular;
- wrong record owner;
- record mode other than 0600;
- existing candidate root that is symlink/non-directory;
- wrong candidate owner;
- candidate mode other than 0700.

The contract compares ownership with the current executor UID. The future production host executor must still enforce the intended privileged execution context; that is outside this R1 pure-contract closure.

### Verdict

~~~text
A2_FIRSTBOOT_RECORD_OWNERSHIP=CLOSED
~~~

No A2 blocker remains at the R1 contract layer.

## 4. A3 — atomic transaction record write

### Review

The repaired writer now uses:

~~~text
random temporary filename
O_WRONLY
O_CREAT
O_EXCL
O_NOFOLLOW where available
0600
fstat owner check
file fsync
os.replace
final metadata validation
parent-directory fsync
~~~

A targeted test precreates the exact temporary pathname as a symlink and proves:

- creation fails closed;
- the symlink target is not truncated or modified.

The transaction parent is required to be private and owned by the current executor, so the remaining pathname operations are within a protected directory.

### Verdict

~~~text
A3_FIRSTBOOT_ATOMIC_WRITE=CLOSED
~~~

No A3 blocker remains.

## 5. A4 — firstboot binding closure

### 5.1 Repaired portions that pass

The repair correctly adds:

- transaction `candidate_root` path binding;
- active-transaction candidate `st_dev/st_ino` binding after PRODUCT_IDENTITY;
- candidate symlink/owner/mode validation;
- persisted `host_instance_id` required from OS_IDENTITY onward;
- host drift rejection during an incomplete/resumed transaction;
- `system_id_sha256` in the complete marker;
- complete/transaction SYSTEM_ID SHA consistency;
- complete/transaction release/stage/host/SYSTEM_ID consistency.

These close the specific missing/null host binding and SYSTEM_ID-hash issues found in the prior review for an **incomplete/resumed transaction**.

### 5.2 Remaining blocker: completed state does not rebind to the current host

Current order is:

~~~text
validate transaction root
validate candidate path if present
_complete_report(...)
if complete:
    return already_complete=True

only after that:
    preflight_clone()
    ensure_os_identity()
    compare current host_instance_id
~~~

Therefore the completed fast path never asks the adapter for the current OS/host identity.

If an already-firstboot-completed disk is copied as a whole to another host, both:

~~~text
transaction.json
FIRSTBOOT_COMPLETE.json
~~~

are copied together. They remain mutually consistent and the current implementation can return:

~~~text
already_complete=True
~~~

without proving that the live host still equals the persisted `host_instance_id`.

This conflicts with ADR-0009 section 7.3:

~~~text
transaction binds ... the local host identity
~~~

and weakens fail-closed behavior for an accidentally or improperly cloned initialized disk.

The valid production route is still to clone only a SEALED, uninitialized master; this finding does not make that route invalid. It means the firstboot transaction contract itself is not yet strong enough to detect this class of lifecycle violation.

### 5.3 Candidate completed-state note

The active transaction binds candidate device/inode. The completed fast path binds only the candidate pathname, not current inode. This is not independently classified as a blocker in R1 because a future successful firstboot implementation may legitimately remove transaction staging after completion. The lifecycle contract should not require a transient staging inode to survive forever.

### Verdict

~~~text
A4_FIRSTBOOT_BINDING=PARTIAL
A4_COMPLETED_LIVE_HOST_BINDING=OPEN_BLOCKER
~~~

## 6. Required minimal repair

Do not broaden into real machine-id/SSH implementation.

The next source delta should only make completed-state acceptance prove the persisted host binding against current host identity through a read-only contract.

Preferred shape:

~~~text
verify_os_identity()
    -> current stable host_instance_id
    -> no identity generation
    -> no network operation
    -> no production service start
~~~

Then completed fast path requires:

~~~text
current_host_instance_id == transaction.host_instance_id
current_host_instance_id == complete.host_instance_id
~~~

Using the existing mutating/ensure-style future adapter as the only completed-state check is not preferred, because an already-complete idempotence path should verify rather than recreate host identity.

The focused repair must add a test equivalent to:

~~~text
complete firstboot on host A
copy/reuse transaction + complete state
report current host identity B
=> FAIL_CLOSED
=> never return already_complete PASS
~~~

This does not require the real Armbian machine-id/SSH implementation yet; a pure adapter/test contract is sufficient.

## 7. New blocker count / R1 status

~~~text
A1=CLOSED
A2=CLOSED
A3=CLOSED
A4=PARTIAL

NEW_R1_BLOCKER_COUNT=1
R1_SOURCE_REVIEW=NEEDS_ONE_FOCUSED_REPAIR
R1_CLOSED=false

SB1_MIXED_PUBLIC_INSTANCE_STAGE=CLOSED_SOURCE
SB2_MIXED_COMMIT_AND_CLEANUP_OWNERSHIP=CLOSED_SOURCE
SB3_MIXED_POSTCHECK=CLOSED_SOURCE
SB4_DURABLE_FIRSTBOOT_TRANSACTION=PARTIAL_CONTRACT_IMPLEMENTED
SB4_COMPLETED_LIVE_HOST_BINDING=OPEN
SB5_SEAL_IMPLEMENTATION=OPEN
SB6_OS_IDENTITY_ADAPTER=OPEN
SB7_FACTORY_CLONE_UNIQUENESS_HARNESS=OPEN
~~~

## 8. STOP

~~~text
R2_MASTER_BUILD_SEAL=HOLD
PRODUCT_SOURCE_MUTATION=false
T1_ACCESS=false
R3_CLEANUP=false
BOARD_ACCESS=false
MERGE=false
AUTHORIZATION_08_GRANTED=false
~~~

Recommended next gate:

~~~text
NEXT_ONE_GATE=
N3W_T1_GOLDEN_MASTER_FIRSTBOOT_R1_COMPLETED_HOST_BINDING_FOCUSED_REPAIR
~~~

Scope:

~~~text
add read-only completed-state host identity verification contract
bind complete fast-path to current host identity
add copied-complete-state host-drift regression
rerun same focused/extended CI
no real machine-id/SSH mutation
no Seal
no R2
no T1 access
~~~
