# N3-W T1 Explicit Device Provisioning P1 独立源码复核闭环（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_SINGLE_INITIALIZER_REPAIR_FINAL_CI_AND_INDEPENDENT_SOURCE_REVIEW`

## 0. Closure

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=541
PR_STATE=OPEN_DRAFT
PR_MERGED=false
PR_BASE_HEAD=d423211b6196c2f2f0f01dff072c4f877fbe58ee
REVIEW_BASE=43809801862541a0b310424b2c8a1685f53ad733
ORIGINAL_P1_SOURCE_HEAD=e906d3d836fefe2bc2cafc0ff7877232974b5211
REVIEW_HEAD=e464c103c9c5cbc2aa2d57d9e853d9e85e73596d

P1_INDEPENDENT_SOURCE_REVIEW=PASS
P1_BLOCKER_COUNT=0
READY_FOR_P2=true

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
ACTIVATION_TOPOLOGY_LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## 1. Fresh rebind

Fresh repository/PR rebind at review start proved:

- PR #541 remains OPEN_DRAFT and unmerged;
- branch `plan/n3w-t1-full-fresh-install-from-zero-20261010` exactly equals `e464c103...`;
- main remains `d423211b...`;
- delta from P1 prechange head still contains only the four P1 source/test files plus documentation alignment;
- no firmware, live deployment, systemd installation, activation topology or board path entered this review.

## 2. Prior blocker

The previous independent review correctly found that atomic creation of `transaction.json` did not serialize later execution of an already-existing transaction. Two processes could enter `_run_existing_transaction()` with different in-memory copies, perform duplicate side effects, and a stale writer could overwrite a newer durable stage.

This was a real P1 correctness blocker because ADR-0009 requires:

```text
UNPROVISIONED / CLONE_VERIFIED
→ acquire single initializer lock
→ create durable transaction
→ ...
```

and durable transaction rule 1 requires exactly one initializer at a time.

## 3. Repair review

Current source adds a persistent `.initializer.lock` inside the private transaction root and uses `flock(LOCK_EX|LOCK_NB)`.

The lock is held:

```text
start:
  preflight
  → private root
  → acquire exclusive initializer
  → create durable transaction
  → run complete provisioning engine
  → release

resume:
  require existing private root
  → acquire exclusive initializer
  → reject completion
  → load existing transaction
  → run remaining provisioning engine
  → release
```

The lock object is fail-closed on type, owner, mode and hard-link count. It is not deleted after use, avoiding pathname/inode replacement as a normal lifecycle step. Kernel lock ownership is released automatically when the descriptor/process exits.

Therefore a second authorized start/resume path cannot enter the transaction engine while another initializer owns it. The previously demonstrated stale-copy stage-regression path is closed.

## 4. Regression review

Focused tests now cover:

- start holds the exclusive lock during transaction execution;
- a simultaneous resume is rejected with no adapter calls and no transaction-byte change;
- initializer failure releases the lock while preserving resumability;
- unsafe/symlink lock state fails closed;
- prior duplicate-start, interrupted-resume, host-drift and durable-record regressions remain.

Exact review-head GitHub Actions state:

```text
TOTAL_WORKFLOWS=25
COMPLETED=25
SUCCESS=25
FAILURE=0
IN_PROGRESS=0
QUEUED=0
```

The earlier `5766aad...` failures were Ruff import ordering before relevant tests. The style-only follow-up `e464c103...` has the same product logic and all workflows pass.

## 5. Authority-by-authority result

```text
INSPECT_AUTHORITY=CLOSED
START_AUTHORITY=CLOSED
RESUME_AUTHORITY=CLOSED
VERIFY_AUTHORITY=CLOSED

UNPROVISIONED_AUTO_START_BLOCKED=true
NEW_TRANSACTION_SINGLE_CLAIM_SEMANTICS=CLOSED
SINGLE_INITIALIZER_EXECUTION=CLOSED
RESUME_REQUIRES_EXISTING_TRANSACTION=true
DEVICE_READY_CURRENT_HOST_BINDING=CLOSED_SOURCE
EXPLICIT_CONFIRMATION_BOUNDARY=CLOSED
PRODUCTION_ACTIVATION_SEPARATION=CLOSED_P1_SOURCE
LEGACY_R8_COMPATIBILITY=CLOSED_WITH_INTENTIONAL_NO_AUTO_START_SEMANTICS
TEST_COVERAGE=CLOSED_FOR_P1

A1_STATUS=CLOSED_FROM_PRIOR_REVIEW
A2_STATUS=CLOSED_FROM_PRIOR_REVIEW
A3_STATUS=CLOSED_FROM_PRIOR_REVIEW
A4_STATUS=CLOSED_SOURCE
```

## 6. Non-blocking observations

Two implementation details remain worth keeping visible but do not block P1:

- unsafe lock-path open may surface a raw `OSError` rather than normalizing every case to `DeviceFirstbootError`; the product CLI already catches both and remains fail-closed;
- there is no dedicated process-level duplicate-start-during-the-small-pre-claim-window test, but both race outcomes are source-closed: an existing transaction is rejected before preflight, while a contender that reaches the lock loses before transaction creation.

Neither observation reopens the single-initializer correctness issue.

## 7. Structured closure

```text
=== N3W_T1_EXPLICIT_DEVICE_PROVISIONING_COMMAND_AUTHORITY_SPLIT_SOURCE_REPAIR_P1_INDEPENDENT_SOURCE_REVIEW CLOSURE ===

EXECUTION_ID=N3W_T1_EXPLICIT_DEVICE_PROVISIONING_SINGLE_INITIALIZER_REPAIR_FINAL_CI_AND_INDEPENDENT_SOURCE_REVIEW_20261013_01
AUTHORIZATION=NOT_APPLICABLE_SOURCE_REVIEW
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

REVIEW_BASE=43809801862541a0b310424b2c8a1685f53ad733
REVIEW_HEAD=e464c103c9c5cbc2aa2d57d9e853d9e85e73596d
PR_HEAD_AT_REVIEW=e464c103c9c5cbc2aa2d57d9e853d9e85e73596d
POST_P1_PRODUCT_SOURCE_DRIFT=EXPECTED_SINGLE_INITIALIZER_REPAIR_ONLY
P1_CHANGED_FILE_ALLOWLIST_MATCH=true

INSPECT_AUTHORITY=CLOSED
START_AUTHORITY=CLOSED
RESUME_AUTHORITY=CLOSED
VERIFY_AUTHORITY=CLOSED

UNPROVISIONED_AUTO_START_BLOCKED=true
NEW_TRANSACTION_SINGLE_CLAIM_SEMANTICS=CLOSED
RESUME_REQUIRES_EXISTING_TRANSACTION=true
DEVICE_READY_CURRENT_HOST_BINDING=CLOSED_SOURCE
EXPLICIT_CONFIRMATION_BOUNDARY=CLOSED
PRODUCTION_ACTIVATION_SEPARATION=CLOSED_P1_SOURCE
LEGACY_R8_COMPATIBILITY=CLOSED_WITH_INTENTIONAL_NO_AUTO_START_SEMANTICS
TEST_COVERAGE=CLOSED_FOR_P1

A1_STATUS=CLOSED_FROM_PRIOR_REVIEW
A2_STATUS=CLOSED_FROM_PRIOR_REVIEW
A3_STATUS=CLOSED_FROM_PRIOR_REVIEW
A4_STATUS=CLOSED_SOURCE

P1_BLOCKER_COUNT=0
P1_BLOCKERS=NONE
P1_INDEPENDENT_SOURCE_REVIEW=PASS
READY_FOR_P2=true

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
SOURCE_MUTATION_DURING_REVIEW=false
MERGE=false

NEXT_ROUTE=P2_HOST_RESUME_AND_ACTIVATION_GUARD_SOURCE_ONLY
STOP=false

=== END ===
```

P1 source correctness is closed. Real Armbian OS-identity behavior, systemd installation, factory acceptance, golden-image capture and T1 live acceptance remain separate later evidence gates.
