# N3-W T1 U13B automatic rollback source design V1 — 2026-11-17

## 1. Context and boundary

U13A normal-success live execution is CLOSED_PASS and durably terminal at `U13A_COMMITTED`.
That successful production transaction is not a rollback test fixture and must not be mutated merely to exercise U13B.

U13B development therefore starts repository-only, using source contracts, synthetic fault injection and later a separately authorized clean-OTA failure scenario.

```text
CURRENT_LIVE_PHASE=U13A_COMMITTED
CURRENT_LIVE_HEALTH=PASS
CURRENT_U13A_AUTHORIZATION_CONSUMED=true
CURRENT_U13A_REPLAY_PERMITTED=false

U13B_SOURCE_DESIGN=true
U13B_SOURCE_DEVELOPMENT=true
U13B_LIVE_EXECUTION_AUTHORIZED=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

Architecture authority remains
`docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_AND_DATA_ROLLBACK_ARCHITECTURE_V1.1_20261106.md`.

## 2. Existing gap

The architecture requires:

```text
target failure after destructive claim
-> transaction=ROLLBACK_IN_PROGRESS
-> target cleanup
-> predecessor image restore from USB
-> HA_DATA_BACKUP restore
-> predecessor runtime activation
-> health verification
-> transaction=ROLLED_BACK
```

Before this source delta, the repository had only a direct logical transition from U9/U10/U11/U12 to terminal `U13B_ROLLED_BACK`.
The synthetic R2 test executed restore actions outside the transaction and then called one terminal helper.

That was insufficient for production because power loss or process death between restore steps could not be represented durably.
It also allowed no public `ROLLBACK_IN_PROGRESS` phase for IPC/status consumers.

## 3. U13B durable subphases

U13B remains one architectural phase but is implemented with durable subphases:

```text
U9/U10/U11/U12
-> U13B0_ROLLBACK_IN_PROGRESS
-> U13B1_TARGET_CLEANUP_COMPLETE
-> U13B2_PREDECESSOR_IMAGE_RESTORED
-> U13B3_HA_DATA_RESTORED
-> U13B4_PREDECESSOR_RUNTIME_STARTED
-> U13B_ROLLED_BACK
```

Public IPC maps U13B0..U13B4 to `ROLLBACK_IN_PROGRESS` and only the terminal phase to `ROLLED_BACK`.

The transaction records `rollback_origin_phase` when rollback starts. Valid origins are U9/U10/U11/U12 only.
U13A is terminal and is deliberately not a U13B entry point.

During U13B0..U13B4:

```text
status=ACTIVE
recovery_required=true
failure_code=<bounded public code>
```

At terminal U13B:

```text
status=ROLLED_BACK
recovery_required=false
```

## 4. Entry admission

Rollback start is permitted only after the destructive U9 authorization is already claimed/consumed and the transaction is still in U9/U10/U11/U12.

Before entering U13B0 the implementation must revalidate all three bound recovery identities:

- exact target artifact;
- exact predecessor recovery archive;
- exact protected HA_DATA_BACKUP.

Their recomputed recovery-content manifest must match the durable transaction.

Wrong/missing USB or wrong recovery content must stop before a rollback mutation and remain `RECOVERY_MEDIA_REQUIRED`.

## 5. Per-step contracts

### U13B0 -> U13B1: target cleanup

Required evidence:

```text
services_quiesced=true
target_runtime_absent=true
target_image_absent=true
```

For origins U9/U10, target runtime/image may already be absent; exact observed absence satisfies the contract.
For U11/U12, the production owner must quiesce Manager/Home Assistant as required and remove the failed target runtime/image using bounded exact-image operations.

Broker must not be pruned or replaced.

### U13B1 -> U13B2: predecessor image

The exact predecessor archive identity must still equal the U8 recovery authority.
The predecessor image must be exact-present internally after either:

- observation that the exact image is already present, or
- loading/restoring the exact USB predecessor archive.

No unrelated image cleanup is allowed.

### U13B2 -> U13B3: Home Assistant data

The protected pre-upgrade backup identity must still equal the durable transaction.
Restore is valid only after cryptographic/authenticity verification and while the target runtime is quiesced.

The production restore backend is a separate implementation gate because the current `ProtectedHaDataBackupProvider.restore_preupgrade_backup()` intentionally fails closed.

### U13B3 -> U13B4: predecessor runtime

Before phase advance, prove:

- predecessor runtime started;
- production `/config` mounted;
- Manager running;
- Broker running;
- Home Assistant running.

Compose/systemd production ownership remains authoritative; U13B must not introduce a parallel manual container lifecycle.

### U13B4 -> terminal U13B

Terminal rollback requires predecessor health acceptance, Manager MQTT authentication, Home Assistant MQTT authentication and Home Assistant HTTP readiness.

Only then may status become `ROLLED_BACK`.

## 6. Durability and power-loss rule

The future production controller must persist every subphase in this order:

```text
perform/reconcile one bounded operation
-> verify exact postcondition
-> sync USB transaction metadata
-> fsync USB metadata
-> persist host transaction
-> proceed to next subphase
```

After a crash, the controller resumes from the durable subphase and observes the real host state before deciding whether the operation is already complete or needs bounded continuation.

There is no blind replay of the original U9 install authorization.

U13B is recovery of the already-consumed destructive transaction, not a second destructive authorization.

## 7. Failure semantics

A U13B intermediate failure remains non-terminal with `recovery_required=true`.
It must never be rewritten as `ROLLED_BACK` merely because some recovery actions succeeded.

If recovery media disappears after U9:

```text
RECOVERY_MEDIA_REQUIRED=true
AUTO_FORMAT_OTHER_USB=false
AUTO_REPLAY=false
```

The same filesystem UUID and exact recovery content remain mandatory.

If predecessor runtime cannot pass final health verification, the transaction remains a recovery failure and requires a separate forensic/recovery gate.

## 8. Source implementation stages

### Stage A — state/contract layer

This change set implements:

- durable U13B0..U13B4 subphases;
- rollback origin binding;
- exact recovery-content validation before U13B0;
- staged transition helpers;
- IPC `ROLLBACK_IN_PROGRESS` mapping;
- synthetic tests for staged rollback, required evidence, wrong recovery content and power-loss classification.

### Stage B — production restore backend

Next source gate will implement and test:

- exact predecessor archive load/verification using existing LocalHost image primitives;
- target cleanup bounded to Home Assistant only;
- protected HA_DATA_BACKUP restore;
- exact predecessor Compose binding restoration;
- systemd-owned predecessor runtime activation;
- reusable predecessor health/readiness verification.

### Stage C — U13B read-only preflight/executor

Only after Stage B source review and CI:

- build exact source-bound U13B read-only preflight;
- prove a legitimate rollback starting state without mutation;
- build an initially unauthorized U13B execution package;
- run independent source review and exact-head CI.

Any real T1 rollback mutation requires a separate explicit authorization and must not use the already successful U13A production transaction merely as a destructive test.

## 9. Acceptance for Stage A

```text
DIRECT_U9_U12_TO_TERMINAL_U13B=false
ROLLBACK_IN_PROGRESS_DURABLE=true
ROLLBACK_ORIGIN_BOUND=true
RECOVERY_CONTENT_REVERIFIED_BEFORE_ROLLBACK=true
TARGET_CLEANUP_EVIDENCE_REQUIRED=true
PREDECESSOR_IMAGE_EVIDENCE_REQUIRED=true
HA_DATA_RESTORE_EVIDENCE_REQUIRED=true
PREDECESSOR_RUNTIME_EVIDENCE_REQUIRED=true
FINAL_HEALTH_EVIDENCE_REQUIRED=true
POWER_LOSS_RESUME_CLASSIFIABLE=true
U13B_LIVE_EXECUTION_AUTHORIZED=false
```
