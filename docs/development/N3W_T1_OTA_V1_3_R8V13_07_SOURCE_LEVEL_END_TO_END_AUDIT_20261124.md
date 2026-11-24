# N3-W T1 Core Stack OTA V1.3 — R8V13-07 Source-Level End-to-End Audit

Date: 2026-11-24  
Scope: R8V13-07 fresh transaction A, exact 2026.10.4 -> 2026.10.0 physical acceptance  
Repository: chrenguo-stack/HomeAssistant / PR #824

## 1. Audit decision

Physical retry is suspended.

The two physical stops were both safe pre-mutation executor failures:

- Attempt 01: embedded Python argv wiring mismatch.
- Attempt 02: stale fixed /tmp work-directory collision.

Both defects escaped the then-current focused CI. This is sufficient evidence that the R8V13-07 outer executor and its CI need an end-to-end source audit before another physical attempt.

The audit does **not** find an unknown or drifting core OTA state machine. The weak point is the newly composed operator executor and its validation strategy.

## 2. Exact live source authority

Spare T1 live recovery archive:

```text
LIVE_HA_RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
LIVE_HA_RECOVERY_SOURCE_HEAD=90ce32ce4b6c329fd38c2771e352d129d6d00a86
```

The core files used by the live pyz are byte-identical to the current PR source:

```text
n3w_t1_core_updater_ha_recovery_startup.py
  blob=a10c4727bd68b311ec2074ef49f714889ffd8d39
n3w_t1_core_updater_ha_ipc.py
  blob=3fd778d99c347bf911683ae82c3bb4d270e3e4d9
n3w_t1_core_updater_ha_usb.py
  blob=7f48e9355f646e125baf8db2f38f9bb42ff9d5e2
n3w_t1_core_updater_ha_usb_state.py
  blob=bc9926c366b08374421ee524933ee89ac58c8524
n3w_t1_core_updater_v2_common.py
  blob=2703d4f24f21eca1e07d44f1c429a036eaf7a4b6

CORE_SOURCE_DRIFT=false
```

Therefore all R8V13-07 execution/recovery reasoning must use source head `90ce32ce...` as the live execution authority. Current PR source is acceptable only because these core blobs are identical.

## 3. Exact U4 -> U13 call graph

### 3.1 U4 -> U5: INSTALL intent

Operator entry:

```text
ha-recovery.pyz
  --maintenance-submit-approved-release INSTALL
```

Source chain:

```text
maintenance_submit_approved_release()
  -> LocalApprovedHaRelease.resolve_homeassistant_release()
  -> HaUsbIpcExecutor.submit("INSTALL")
  -> require_same_admission()
  -> request_install()
  -> HaUsbStateStore.write()
```

Durable result:

```text
ACTIVE / U5_INSTALL_REQUESTED_REVALIDATING
authorization_claimed=false
authorization_consumed=false
authorization_id_sha256=null
predecessor_start absent
```

No application stop or destructive image action occurs at U5.

### 3.2 U5/U6 -> install authority

Operator authority request binds:

- transaction_id_sha256
- requested_install_binding_sha256(document)
- authorization_id
- expiry

`requested_install_binding_sha256()` covers:

- transaction_id_sha256
- usb_filesystem_uuid
- usb_mount_authority
- prepared_image_materials

`LocalHaPredecessorRuntime.issue_candidate_authority(..., "install", ...)` additionally:

- resolves the approved release pin and manifest;
- requires the same release admission;
- captures the exact current launch binding;
- verifies the recovery startup/retry units and active retry timer;
- verifies the predecessor launch is unchanged before publishing;
- rejects already-consumed authorization;
- atomically publishes schema-v3 install authority.

The product authority publisher already defines replacement semantics:

- different binding: replaceable;
- same binding + active conflicting grant: rejected;
- same binding + identical effective grant: reusable through the existing file;
- expired authority: replaceable.

An outer hard-coded historical authority-binding gate is therefore not authoritative and must not duplicate these semantics.

### 3.3 Product execution owner

The product package contains:

```text
n3w-t1-ha-recovery-retry.service
  Type=oneshot
  PrivateMounts=yes
  ExecStart=/usr/bin/python3 -I /opt/n3w-t1-core-updater/ha-recovery.pyz --resume-pending
  TimeoutStartSec=45min
```

and:

```text
n3w-t1-ha-recovery-retry.timer
  OnCalendar=*-*-* *:*:00,30
  WantedBy=timers.target
```

`capture_start_binding()` calls `require_recovery_install()`, which verifies:

- recovery startup unit exact ExecStart;
- recovery retry unit exact ExecStart;
- recovery startup enabled;
- retry timer enabled and active;
- required live pyz CLI options present.

Therefore the product architecture explicitly makes the systemd recovery worker/timer the durable owner of pending install/recovery work.

A long-running SSH shell is not the intended owner of U5 -> U13.

### 3.4 --resume-pending dispatch

`main(pending_only=True)` first calls `resume_host_recovery()`.

If no recovery path is already active, it calls `_dispatch_pending_candidate()`.

For:

```text
ACTIVE
phase in {U5, U6}
predecessor_start absent
install authority present
```

it calls:

```text
LocalHaPredecessorRuntime.install_requested()
```

### 3.5 Install/recovery state machine

```text
U5
  -> verify authority
  -> verify bound target/predecessor archives
  -> verify exact production prestate
  -> measure action-time internal capacity
  -> U6
  -> capture acceptance baseline

U6
  -> persist predecessor_start
  -> stop application writers
  -> U7

U7
  -> measure protected-data backup capacity at action time
  -> create + verify protected backup
  -> reverify install materials
  -> U8

U8
  -> capture exact predecessor-release intent
  -> reverify backup/materials/prestate/capacity
  -> claim + consume live authorization
  -> U9

U9
  -> remove exact predecessor container/image
  -> prove predecessor release
  -> U10

U10
  -> record target-load intent
  -> load exact target
  -> bind target
  -> mark WRITES_POSSIBLE
  -> start exact target
  -> U11

U11
  -> target acceptance observations
  -> U12

U12
  -> persist acceptance receipt
  -> U13A_COMMITTED
```

Acceptance failure routes to data/image rollback and U13B.

## 4. Recovery / interruption matrix

### U4

Application is still healthy.

A product install revalidation/baseline failure may transition back to U4 with a failure_code and without predecessor_start.

This is safe operationally. It is not a destructive cutover state.

### U5

INSTALL intent is durable, but no application stop has occurred.

If authority issuance or the operator process is interrupted here, the transaction is safely resumable. A valid install authority can be issued/reused and the product worker can continue.

**A U4-only outer executor is therefore incorrect for safe re-entry.**

### U6 without predecessor_start

The install worker has entered U6, but first-stop ownership has not yet been persisted.

Product dispatch explicitly allows U6 without predecessor_start to re-enter `install_requested()`.

This is forward-resumable.

### U6/U7/U8 with predecessor_start

`_can_resume_pre_cutover()` is true.

`resume_host_recovery()`:

- marks recovery_required if needed;
- starts the predecessor if needed;
- verifies predecessor health;
- closes the attempt as rolled back.

This is pre-cutover automatic recovery.

### U9/U10 with predecessor_release_intent

`resume_host_recovery()` uses `_reconcile_predecessor_release()`.

It reconciles whether the predecessor was actually released, restores the predecessor image from bound media when needed, restores the launch binding, verifies health, and closes U13B.

### U10/U11/U12 with target writes/data restore responsibility

`ha_data_rollback_required()` selects durable data rollback.

The product:

- quiesces writers;
- verifies bound rollback materials;
- restores protected HA data through the restore journal;
- reloads the predecessor;
- resumes predecessor runtime;
- verifies predecessor health;
- closes U13B.

### U12 with persisted acceptance receipt

Before selecting rollback, `resume_host_recovery()` checks whether the exact current target runtime still matches the acceptance receipt.

If yes, it performs forward commit to U13A.

If not, the rollback path is selected.

### U13A / U13B

Terminal, no replay.

## 5. Authorization boundary

The destructive authorization is **not** consumed by U5 INSTALL intent.

It is consumed only at `claim_live_authorization()`, during the U8 -> U9 transition, after:

- target/predecessor archives have been reverified;
- exact production prestate has been reverified;
- protected-data backup has been created and verified;
- action-time internal capacity has been proven;
- predecessor release intent has been captured.

At U9:

```text
authorization_claimed=true
authorization_consumed=true
authorization_id_sha256=SHA256(authorization_id)
```

From U9 onward, the attempt is no-replay and recovery ownership is product-controlled.

## 6. Capacity model

The live source implements the V1.3 dynamic action-time model.

Before authorization claim:

`HaMountedInstallMaterialVerifier._capacity()` measures current internal free space and computes:

```text
install_required_bytes = unpacked target bytes
recovery_required_bytes = unpacked predecessor bytes + HA restore workspace
required_bytes =
  max(install_required_bytes, recovery_required_bytes)
  when single-image workspace reuse is available
```

Protected-data backup capacity is independently measured immediately before the backup write.

Target load and rollback paths re-check internal free space at their own action boundaries.

Therefore no outer static "two complete versions must fit simultaneously" gate is required.

## 7. Audit findings

### F1 — Core source drift: PASS

The live pyz source authority and current core source are byte-identical for the five critical modules.

No evidence supports reopening the core OTA architecture as unknown.

### F2 — Existing product recovery design: PASS

The core state machine contains explicit durable recovery for:

- pre-cutover interruption;
- predecessor release interruption;
- target import/activation interruption;
- protected-data rollback;
- acceptance failure;
- commit interruption.

Existing source tests already fault-inject these paths, including:

- after_target_import
- after_target_binding
- before_target_start
- after_target_start
- target_start_failed
- accept_failed
- accept_unavailable
- commit_interrupted
- commit_runtime_drift
- single-image rollback variants

### F3 — Outer executor validation strategy: FAIL

Two basic executor defects escaped focused CI:

1. shell/Python argv mismatch;
2. fixed /tmp workdir stale collision.

The current focused executor tests rely too heavily on:

- string presence;
- bash syntax;
- static source-contract assertions.

They do not prove the executor's runtime control flow.

### F4 — Local shell mutation flags are not durable authority: FAIL

Variables such as:

```text
MUTATION_STARTED
INSTALL_INTENT_SUBMITTED
INSTALL_AUTHORITY_ISSUED
```

are process-local.

If a called program persists state and then terminates before the shell updates its local flag, the flag can be false while durable mutation already occurred.

STOP/replay decisions must be derived from:

- transaction file;
- authority file;
- product runtime state;

not from shell-local booleans.

### F5 — Direct SSH-owned --resume-pending: FAIL

The fresh executor directly invokes:

```text
/usr/bin/python3 -I "$LIVE" --resume-pending
```

The product package explicitly provides a systemd retry service and timer for this action.

Direct execution unnecessarily couples the OTA transaction to the SSH session and loses the intended PrivateMounts/systemd ownership.

Historical R8V13-07 continuation already used:

```text
systemctl start n3w-t1-ha-recovery-retry.service
```

before any bounded recovery continuation.

The fresh executor regressed from that mature pattern.

### F6 — U4-only entry contract: FAIL

The fresh executor requires:

```text
ACTIVE / U4_READY_TO_INSTALL
```

at every invocation.

Source proves that these states are also safe, supported entry points:

- U5 with no predecessor_start;
- U6 with no predecessor_start.

Rejecting them turns a safe partial operator interruption into a new bespoke repair task.

### F7 — One-shot recovery dispatch: FAIL

The fresh executor makes one direct `--resume-pending` call and classifies any remaining ACTIVE state as STOPPED_NONTERMINAL.

Source proves that a first worker failure can intentionally leave durable recovery responsibility for the retry worker/timer.

The outer gate must hand recovery back to the product worker, not treat every nonterminal ACTIVE state as an unrecoverable executor failure.

### F8 — Hard-coded old install-authority binding: REMOVE

The fresh executor binds a historical authority residue to:

```text
EXPECTED_OLD_INSTALL_BINDING=f012b3ed...
```

This duplicates and narrows product `_publish_authority()` semantics.

It can false-block a state that the product correctly classifies as replaceable.

The product authority validator/publisher must be the authority.

### F9 — Preinstall monitoring self-test: REMOVE FROM OUTER GATE

The fresh executor performs a separate monitoring self-test before submitting INSTALL.

The product install path already:

- captures exact start binding;
- validates recovery service/timer installation;
- verifies install materials/prestate;
- captures the acceptance baseline before stopping services.

The outer monitoring test duplicates product admission and created extra embedded-Python complexity.

It should not be a correctness gate.

### F10 — Target-already-present protection: CORE ALREADY OWNS IT

Initially this appeared to be an outer-only guard.

Full call-graph review shows `capture_predecessor_release()` calls `observe_predecessor_released()` **before** deleting the predecessor. That check rejects a target image that exists without this transaction's target-load intent.

Therefore target ownership safety is already core-owned.

An outer target-absent observation may remain only as diagnostic evidence, not as a second safety state machine.

## 8. Required executor convergence

Before another physical command, the R8V13-07 operator executor should be reduced to a thin orchestration layer.

### Required behavior

1. Verify exact live pyz/manifest/transaction identity.
2. Classify durable transaction state.
3. U4:
   - validate exact current launch through product runtime;
   - refresh release pin **only if expiry is the only invalid field**;
   - submit exactly one INSTALL intent.
4. U5/U6 without predecessor_start:
   - reuse a valid same-binding/same-authorization install authority;
   - otherwise issue a fresh schema-v3 authority through product code.
5. U6+ with recovery responsibility:
   - do not submit another INSTALL intent;
   - do not issue a new destructive authorization;
   - hand execution to the product recovery worker.
6. Dispatch through:
   `systemctl start n3w-t1-ha-recovery-retry.service`.
7. If the first worker exits with a durable recoverable ACTIVE state, permit one bounded product-worker continuation; thereafter leave recovery ownership to the armed timer.
8. Classify only from durable transaction state.
9. U13A:
   - verify exact acceptance receipt/current runtime.
10. U13B:
   - verify predecessor runtime health.
11. Stop before R8V13-08.

### Must be removed

- fixed temporary work directory;
- shell-local mutation flags as replay authority;
- hard-coded historical authority binding gate;
- outer monitoring self-test as a correctness gate;
- direct Docker image/container mutation;
- direct application stop/start;
- direct USB format/unmount/history deletion;
- duplicate product recovery logic.

## 9. Required CI convergence

Another physical retry is not admitted by source review alone.

The executor CI must add execution-path validation that covers at least:

1. clean U4 -> U5 -> authority -> worker -> U13A;
2. U5 re-entry before authority;
3. U5 re-entry with an already-valid same-binding authority;
4. U6/no-predecessor_start re-entry;
5. U6/U7/U8 pre-cutover interruption -> U13B;
6. U9/U10 release interruption -> U13B;
7. U10/U11/U12 data rollback -> U13B;
8. U12 accepted-runtime forward commit -> U13A;
9. worker failure leaving recoverable ACTIVE state -> second product-worker dispatch / timer ownership;
10. terminal transaction -> no replay;
11. repeat executor invocation does not fail because of local temporary residue;
12. executor failure reporting is based on durable transaction state rather than local flags.

The existing core fault-injection tests should be reused as product-state-machine evidence; the new tests should focus on orchestration/re-entry rather than reimplementing those core tests.

## 10. Current physical boundary

```text
CURRENT_TRANSACTION_ID=d86669e6d16bb9420191920bc2b02583e7f7207eff0b51ed3f9e6321f99389d4
CURRENT_STATUS=ACTIVE
CURRENT_PHASE=U4_READY_TO_INSTALL
RECOVERY_REQUIRED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_ID_SHA256=null
PREDECESSOR_START_PRESENT=false
TARGET_LOADED_IMAGE_ID=null
TARGET_ACTIVATION=null
```

Attempts 01 and 02 did not consume the install authorization or cross a destructive boundary.

However no further physical retry is admitted until the thin executor and execution-path CI are closed.

```text
R8V13_07=NOT_PASS
R8V13_08=BLOCKED
LIVE_T1_EXECUTION=BLOCKED_PENDING_EXECUTOR_CONVERGENCE
BROKER_OTA=false
HOST_REBOOT=false
MERGE=false
RELEASE=false
```
