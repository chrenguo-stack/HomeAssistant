# N3-W T1 U13B read-only preexecution source design — 2026-11-17

## 1. Entry authority and scope

Fresh rebind before this design established:

```text
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED
DEFAULT_MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
PR_HEAD_AT_DESIGN_ENTRY=c0fa1d22dfbeb8a7fdb8202de10e739ce95499f7
STAGE_D_SOURCE_HEAD=a47fc818eaea84a7357d158e2c4f92b2367d8d44
STAGE_D_SOURCE_CI=16_OF_16_SUCCESS
DOCS_ONLY_ADVANCE_FROM_STAGE_D_SOURCE=true
NEXT_CHAT_LIVE_RUNTIME=UNKNOWN_FRESH

T1_ACCESS=false
T1_MUTATION=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

`a47fc818... -> c0fa1d22...` is exactly one commit and changes only three
`docs/development/**` files. No product source changed after Stage D closure.

This gate designs and implements the **repository-side read-only admission
contract only**. It does not create a live-bound T1 execution manifest and does
not access T1. A real-T1 read-only package must be generated later from fresh
runtime evidence and separately authorized scope.

## 2. Purpose

Stage D proved that a legal USB-one-phase-ahead split can be classified,
observed and reconciled safely. Before any future live U13B rollback, the system
still needs one stable read-only gate that answers only:

```text
What durable Host/USB state exists now?
Does it belong to the U13B rollback domain?
Are exact recovery assets still valid?
Does the real machine state match the durable rollback phase?
Is Host-only reconciliation required before normal rollback?
```

The gate must not perform reconciliation or rollback work itself.

## 3. Source component

Add:

```text
tools/n3w_t1_core_updater_ha_u13b_preexecution.py
```

The component is intentionally composed from already-closed Stage D
primitives:

- `classify_u13b_usb_host_split()`;
- the strict reconciliation USB resolver (`ro,noload,nodev,nosuid,noexec` when
  an ext4 device must be mounted);
- `U13BProductionReadOnlyObserver`;
- `verify_u13b_usb_ahead_postcondition_readonly()`.

It does **not** invoke `U13BHostOnlyReconciliationWriter` or
`U13BAutomaticRollbackCoordinator`.

## 4. Authoritative read-only algorithm

Under the shared transaction lock:

```text
1. Read + validate the current Host transaction.
2. Resolve the exact bound USB through the strict read-only reconciliation path.
3. Read the complete USB transaction metadata snapshot.
4. Classify Host/USB.
5. If HOST_USB_EXACT:
   a. reverify exact recovery assets;
   b. if already in U13B progress/terminal state, re-observe the real-world
      postcondition represented by the current durable phase.
6. If USB_ONE_PHASE_AHEAD_RECONCILABLE:
   a. use the exact mirrored successor transaction;
   b. reverify exact recovery assets;
   c. run the Stage D per-edge read-only postcondition observer;
   d. report HOST_RECONCILIATION_REQUIRED only; do not repair Host.
7. HOST_ONE_PHASE_AHEAD_STOP or DIVERGENT_OR_UNKNOWN_STOP => STOP.
8. Re-read Host and USB metadata after observation; any drift => STOP.
9. Release any temporary reconciliation media before returning.
10. Emit only a structured PASS result or a fail-closed error.
```

The Host lock is an observation-consistency guard, not mutation authority.

## 5. Recovery-assets rule

Recovery content is not assumed valid merely because an earlier U8/U9/U12 gate
verified it. Every U13B preexecution PASS must freshly re-observe:

- exact target recovery identity;
- exact predecessor recovery identity;
- exact pre-upgrade HA data backup identity.

For later U13B progress phases, recovery assets are checked first and then the
phase-specific real-world postcondition is checked. This prevents a valid
runtime postcondition from hiding damaged or replaced rollback media.

## 6. PASS classifications

### 6.1 Exact entry/progress state

```text
STATUS=U13B_READONLY_PREEXECUTION_PASS
ACTION=ROLLBACK_ELIGIBLE
RECONCILIATION_REQUIRED=false
ROLLBACK_EXECUTION_REQUIRED=true
```

This is still not live rollback authorization.

### 6.2 Legal USB-one-phase-ahead state

```text
STATUS=U13B_READONLY_PREEXECUTION_PASS
ACTION=HOST_RECONCILIATION_REQUIRED
RECONCILIATION_REQUIRED=true
ROLLBACK_EXECUTION_REQUIRED=true
```

A future authorized live gate may enter D3/D4; this read-only gate itself does
not write Host.

### 6.3 Exact terminal rollback state

```text
STATUS=U13B_READONLY_PREEXECUTION_PASS
ACTION=ALREADY_ROLLED_BACK
RECONCILIATION_REQUIRED=false
ROLLBACK_EXECUTION_REQUIRED=false
TERMINAL_ROLLED_BACK=true
```

No rollback replay is permitted.

## 7. Mandatory STOP conditions

At minimum:

- missing or invalid Host transaction;
- phase outside U9/U10/U11/U12/U13B0..U13B4/U13B;
- missing, ambiguous, wrong or read-write bound USB;
- filesystem UUID/content authority drift;
- Host one phase ahead;
- multi-phase or unknown divergence;
- recovery asset mismatch;
- real-world postcondition false/error/non-literal-`True`;
- Host drift during observation;
- USB metadata drift during observation;
- inability to release temporary reconciliation media.

A historical `U13A_COMMITTED` live state is outside the U13B rollback domain and
must STOP rather than being treated as a rollback fixture.

## 8. Zero-production-mutation contract

The source component may only:

- take/release the shared transaction lock;
- read Host transaction state;
- resolve/read the bound USB through the strict read-only path;
- run existing read-only recovery/runtime observers;
- release the temporary read-only mount.

It must never:

```text
HOST_TRANSACTION_WRITE=false
USB_METADATA_WRITE=false
ROLLBACK_OPERATION_REPLAY=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_MUTATION=false
U13B_TRANSITION=false
```

The future T1 executor must also prove these fields in structured output.

## 9. Why no real-T1 execution package is generated in this gate

The latest durable live evidence is historical `U13A_COMMITTED`, while the
handoff explicitly marks current live runtime as `UNKNOWN_FRESH`. There is no
fresh rollback-start transaction or separately authorized clean OTA failure
scenario to bind.

Creating a runnable physical package now would either hard-code stale live facts
or make the package under-bound. Both are false-PASS risks.

Therefore this gate produces the reusable source contract and tests only. A
future live-bound package must, after separate authorization to perform fresh
T1 read-only binding, pin at least:

- exact preexecution source head and package file hashes;
- exact installed product source authority;
- fresh Host transaction ID/hash/phase;
- exact USB filesystem UUID and transaction metadata hashes;
- expected recovery identities;
- expected manager/broker/runtime identities required by the observer;
- explicit `read_only=true` and all mutation flags false;
- explicit `u13b_live_execution_authorized=false`.

Only after that package passes real-T1 read-only execution may a separate live
rollback authorization be considered.

## 10. Source acceptance

Focused tests must prove:

- exact entry state is admitted read-only;
- exact progress state rechecks recovery assets + its current postcondition;
- USB-one-phase-ahead is observed but never reconciled by preexecution;
- exact terminal rollback is idempotent/no-replay;
- non-literal-`True` observations fail closed;
- Host/USB drift after observation fails closed;
- host-ahead/divergent state never becomes PASS;
- the preexecution module contains no mutating rollback entrypoint.

```text
READONLY_PREEXECUTION_SOURCE_DESIGN=true
READONLY_PREEXECUTION_SOURCE_IMPLEMENTATION=true
REAL_T1_READONLY_PACKAGE_CREATED=false
T1_ACCESS=false
T1_MUTATION=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```
