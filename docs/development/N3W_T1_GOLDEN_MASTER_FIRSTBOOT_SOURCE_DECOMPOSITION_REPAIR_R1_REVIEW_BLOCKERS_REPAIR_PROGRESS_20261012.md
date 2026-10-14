# N3-W T1 R1 independent-review blockers repair progress

Date: 2026-10-12

TASK=
`N3W_T1_GOLDEN_MASTER_FIRSTBOOT_SOURCE_DECOMPOSITION_REPAIR_R1_REVIEW_BLOCKERS_REPAIR`

## 0. Current status

~~~text
PRE_REPAIR_BRANCH_HEAD=75aedf67b2a48820243eccba0c3db7e42893ebf3
R1_REVIEW_REPAIR_SOURCE_HEAD=3dbd9723063e1f5f14605b1bcf13bee4c54c84ab

A1_LEGACY_COMMIT_COMPATIBILITY=REPAIRED_SOURCE
A2_FIRSTBOOT_RECORD_OWNERSHIP=REPAIRED_SOURCE
A3_FIRSTBOOT_ATOMIC_WRITE=REPAIRED_SOURCE
A4_FIRSTBOOT_BINDING=REPAIRED_SOURCE

CI=PENDING
T1_ACCESS=false
T1_MUTATION=false
R3_CLEANUP=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
AUTHORIZATION_08_GRANTED=false
MERGE=false
~~~

This gate is limited to the four blockers from the R1 independent source review.
It does not implement real Armbian machine-id/SSH identity, Seal, firstboot systemd,
factory acceptance, clone physical acceptance, or R2 master-build execution.

## 1. Exact repair delta

Compared with pre-repair branch head
`75aedf67b2a48820243eccba0c3db7e42893ebf3`,
the repair changes exactly four source/test files:

~~~text
MOD tools/n3w_t1_fresh_product_bootstrap.py
MOD tests/tools/test_n3w_t1_fresh_product_bootstrap.py
MOD host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py
MOD host/greenhouse-manager/tests/bootstrap/test_device_firstboot.py
~~~

No staging-host transport, `fresh_installer.py`, firmware, Compose topology,
production activation unit, R8 authorization ID, T1 runtime, or board source is changed.

## 2. A1 — legacy R8 commit compatibility

Independent review found that R1 changed the old commit behavior from:

~~~text
preflight ALL final targets
→ begin first rename
~~~

to:

~~~text
preflight instance targets
→ move instance targets
→ preflight public targets
→ move public targets
~~~

This could write instance final paths before discovering a conflicting public final
path such as `/opt/HomeAssistant`.

Repair:

- added `_validate_commit_targets_absent()`;
- added `_move_commit_targets()`;
- split public/instance commit methods still preflight their own ownership;
- legacy `commit_candidate()` now:
  1. preflights `FINAL_DIRS + FINAL_FILES` as one set;
  2. only then moves targets in the original `FINAL_DIRS`, then `FINAL_FILES` order;
  3. then performs daemon-reload and candidate cleanup.

Regression test proves a later public-target collision leaves the earlier instance
source unmoved.

Result:

~~~text
A1=REPAIRED_SOURCE
LEGACY_ALL_TARGET_PREFLIGHT_RESTORED=true
LEGACY_MOVE_ORDER_RESTORED=true
~~~

## 3. A2 — transaction/record ownership authority

The firstboot transaction is an execution authority and must not trust a
mode-correct file owned by an unexpected account.

Repair now requires:

- transaction root: directory, non-symlink, owner == current privileged executor,
  mode `0700`;
- transaction and complete records: regular non-symlink file,
  owner == current privileged executor, mode `0600`;
- candidate root, when present: directory, non-symlink,
  owner == current privileged executor, mode `0700`.

Existing unsafe metadata fails closed; the code does not silently normalize an
existing untrusted transaction authority into a trusted one.

Result:

~~~text
A2=REPAIRED_SOURCE
OWNER_BINDING_REQUIRED=true
~~~

## 4. A3 — atomic write hardening

Previous R1 used a fixed `*.tmp` path with create/truncate behavior.

Repair:

- temporary name includes a fresh random suffix;
- open flags use:
  `O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW(where available)`;
- temporary file owner is checked;
- temporary file is forced to `0600`;
- data is fsync'd before replace;
- existing target metadata is validated before replacement;
- final record metadata is revalidated;
- parent directory is fsync'd after replace;
- a pre-existing temporary symlink fails closed and cannot truncate its target.

Result:

~~~text
A3=REPAIRED_SOURCE
EXCLUSIVE_TEMP_CREATE=true
NOFOLLOW_TEMP_CREATE=true
PARENT_FSYNC=true
~~~

## 5. A4 — candidate/host/system binding

Repair adds/strengthens:

### Candidate-root binding

The transaction records:

~~~text
candidate_root
candidate_dev
candidate_ino
~~~

Rules:

- candidate path must be absolute and non-symlink;
- when materialized it must be private and correctly owned;
- after PRODUCT_IDENTITY the transaction binds the candidate directory device/inode;
- later stages reject candidate replacement;
- a different candidate path with the same transaction root is rejected;
- completed-state validation also requires the same candidate-root path.

### Host binding

Once transaction stage is `OS_IDENTITY` or later:

- `host_instance_id` must be a non-empty persisted value;
- missing persisted host binding fails closed;
- a different current host identity fails closed.

### SYSTEM_ID hash binding

`FIRSTBOOT_COMPLETE.json` now includes
`system_id_sha256`.

Completed-state validation requires:

~~~text
complete.system_id_sha256 == SHA256(complete.system_id)
transaction.system_id == complete.system_id
transaction.system_id_sha256 == complete.system_id_sha256
transaction.stage == VERIFY
~~~

Result:

~~~text
A4=REPAIRED_SOURCE
CANDIDATE_PATH_BINDING=true
CANDIDATE_INODE_BINDING=true
HOST_BINDING_FAILCLOSED=true
COMPLETE_SYSTEM_HASH_BINDING=true
~~~

## 6. Added review-blocker regression coverage

New tests include:

- legacy all-target commit preflight before first move;
- transaction-root owner drift rejection;
- pre-existing atomic temp symlink rejection without victim modification;
- candidate-root symlink rejection;
- transaction candidate-root path drift rejection;
- missing persisted host binding rejection;
- completed transaction SYSTEM_ID hash drift rejection;
- completed transaction candidate-root drift rejection.

Existing R1 tests remain in place for release binding, host drift,
marker-last completion and idempotence.

## 7. Scope intentionally still open

Not part of this repair:

~~~text
SB4_REAL_HOST_FIRSTBOOT_ADAPTER=OPEN
SB5_SEAL_IMPLEMENTATION=OPEN
SB6_OS_IDENTITY_ADAPTER=OPEN
SB7_FACTORY_CLONE_UNIQUENESS_HARNESS=OPEN

MACHINE_ID_LIVE_IMPLEMENTATION=false
SSH_HOST_KEY_LIVE_IMPLEMENTATION=false
FIRSTBOOT_SYSTEMD=false
SEAL_LIVE_IMPLEMENTATION=false
T1_ACCESS=false
~~~

## 8. CI checkpoint

Exact repair source head:

~~~text
3dbd9723063e1f5f14605b1bcf13bee4c54c84ab
~~~

At the time this progress record was created, GitHub Actions had started and
Public repository safety CI had already passed. The required focused/extended
R1 regression set was still queued/running.

No PASS closure is claimed until the exact repair source head reaches the
required CI terminal state.

## 9. STOP / next decision

After CI terminal success, perform a focused closure review of A1–A4.

Only if:

~~~text
A1=CLOSED
A2=CLOSED
A3=CLOSED
A4=CLOSED
NEW_R1_BLOCKERS=0
~~~

may the project close R1 and enter R2 master-build/Seal source design or repair.
