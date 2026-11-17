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

Each subphase also carries cumulative durable evidence flags:

```text
rollback_recovery_content_verified
rollback_target_cleanup_verified
rollback_predecessor_image_restored
rollback_ha_data_restored
rollback_predecessor_runtime_started
rollback_health_verified
```

The state validator requires the exact cumulative evidence pattern for each U13B subphase. The public generic `transition()` also rejects every U13B edge. U13B progression is routed through rollback domain helpers, and the internal rollback transition enforces an exact per-edge update-key contract. Matching boolean fields supplied to the generic transition are therefore not accepted as rollback evidence.

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
HOST_PHASE_POWER_LOSS_CLASSIFIABLE=true
HOST_USB_SPLIT_WRITE_RECONCILIATION_PENDING=true
U13B_LIVE_EXECUTION_AUTHORIZED=false
```

## 10. Stage B production rollback backend

Stage B materializes production rollback primitives without creating or authorizing a live U13B executor.

### 10.1 Protected Home Assistant data restore

`ProtectedHaDataBackupProvider.restore_preupgrade_backup()` now requires the exact transaction identity and bound USB backup root.

The restore order is:

```text
verify encrypted archive hash
-> verify HMAC authenticity
-> verify plaintext manifest
-> validate live /config target tree
-> clear only the HA data-root contents
-> decrypt/extract pre-upgrade data
-> validate restored tree
-> SQLite quick_check
-> exact archive/source compare
-> fsync restored files/directories
```

Authentication and integrity verification happen before current HA data is deleted. A tampered backup therefore fails before live data mutation.

If extraction is interrupted, the host transaction remains at U13B2. Re-entry may safely clear the partial HA data tree and repeat restoration from the same authenticated archive.

### 10.2 Command-free controller

`tools/n3w_t1_core_updater_ha_u13b.py` owns transaction orchestration only. It executes no Docker/systemd commands.

For each subphase it follows:

```text
verify exact recovery authorities
-> perform/reconcile one bounded operation
-> verify postcondition
-> sync USB transaction metadata
-> persist host transaction
```

It resumes from the durable host U13B0..U13B4 phase without deliberately replaying already completed earlier operations.

### 10.3 Production media/runtime adapter

`tools/n3w_t1_core_updater_ha_u13b_host.py` reuses existing production primitives:

- `SubprocessPrepareBackend` for bound-media resolution and USB transaction metadata;
- portable image identity for exact target/predecessor archive validation;
- `LocalHost` for exact HA container/image cleanup;
- the already live-proven `LocalU11RuntimeOwner` HA-OTA overlay contract for predecessor runtime start;
- current listener/MQTT/HTTP readiness checks for terminal predecessor health.

The durable cross-session media authority is filesystem UUID plus exact recovery content. The session-scoped public USB fingerprint is not promoted to a cross-session recovery authority.

Target cleanup is restricted to Home Assistant target residues/image. Broker and unrelated images are not pruned.

### 10.4 Resume boundary still open for Stage C

Stage B closes operation-level restartability, but it does not claim that every split durable-write point is automatically reconciled.

The required write order remains:

```text
USB metadata durable
-> host transaction durable
```

A crash after USB persistence but before the corresponding host write can therefore leave `USB_PHASE = host successor` while `HOST_PHASE = predecessor`.

That state must not be resolved by blind execution replay.

Stage C must add a read-only reconciliation contract that can classify at minimum:

```text
HOST_USB_EXACT
USB_ONE_PHASE_AHEAD_RECONCILABLE
HOST_ONE_PHASE_AHEAD_STOP
DIVERGENT_OR_UNKNOWN_STOP
```

and prove that an observed USB-ahead phase is the exact allowed successor with matching transaction/recovery authority before host reconciliation is considered.

### 10.5 Stage B boundary

```text
U13B_PRODUCTION_RESTORE_BACKEND=true
U13B_COMMAND_FREE_CONTROLLER=true
U13B_OPERATION_RESUME_SAFE=true
U13B_USB_HOST_SPLIT_RECONCILIATION_PENDING=true
U13B_READONLY_PREFLIGHT=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

No live rollback package is created by Stage B.

## 11. Independent-review Stage A repair — 2026-11-17

Independent review rejected the earlier Stage A closure claim because the generic transaction API still accepted rollback-edge updates when a caller supplied expected evidence fields directly.

The repaired contract is:

```text
PUBLIC_GENERIC_TRANSITION_U13B_EDGES=false
ROLLBACK_DOMAIN_TRANSITION_REQUIRED=true
ROLLBACK_PER_EDGE_UPDATE_KEY_ALLOWLIST=true
SPOOFED_GENERIC_EVIDENCE_UPDATE_REJECTED=true
ROLLBACK_BRANCH_LINEAR_RANK_ASSUMPTION=false
```

The public generic transition now rejects every U13B edge. Rollback helpers use a separate internal transition path and every rollback edge has an exact update-key contract. Non-rollback transition semantics remain unchanged.

Shared prerequisite checks no longer rank U13B0..U13B after U13A. The rollback branch is anchored at U9 for forward-path prerequisite semantics, so a future U10/U11/U12-only rule is not inherited merely because a rollback phase appears later in the phase tuple.

The previous acceptance label `POWER_LOSS_RESUME_CLASSIFIABLE=true` was too broad. Only host-phase re-entry classification is closed at Stage A. USB-ahead/host-behind split-write reconciliation remains pending.

## 12. Independent-review Stage B repair — 2026-11-17

Independent review rejected the earlier Stage B closure for three reasons: terminal predecessor health was weaker than U12 target acceptance, backup verification could create a missing recovery directory, and production/synthetic rollback coverage was incomplete.

The repaired source contract requires:

```text
PREDECESSOR_RUNTIME_IMAGE_ID_EXACT=true
PREDECESSOR_HA_RESTART_COUNT_ZERO=true
BROKER_OWNER_ACTIVE=true
MANAGER_BROKER_EXACT_PEERS=true
PRODUCTION_CONFIG_MOUNT_EXACT=true

BACKUP_VERIFY_MISSING_DIRECTORY_MUTATION=false
BACKUP_CREATE_AND_VERIFY_DIRECTORY_SEMANTICS_SPLIT=true

ROLLBACK_ORIGINS_TESTED=U9,U10,U11,U12
OPERATION_LEVEL_INTERRUPTION_POINTS_TESTED=
  cleanup,image,data_quiesce,data_restore,runtime,health
```

The exact predecessor runtime image ID is derived from the durable transaction's `current_image_identity.runtime_image_id`, not merely from a Docker tag. The USB predecessor archive restore must resolve to that same runtime ID. B3/B4 re-entry validates the running Home Assistant container against that ID and requires `RestartCount==0`.

Backup verification now requires the recovery directory to already exist with private ownership/mode; it never creates a missing directory. Directory creation remains confined to the U7 backup-production path.

This repair still does not close USB-ahead/host-behind durable split-write reconciliation. That remains a later gate after Stage A/B source closure.
## 14. Final independent review repair — persistent Home Assistant binding is terminal health authority

The 2026-11-17 final independent Stage A / Stage B review found one additional Stage B false-PASS path after the previous source-repair CI closure.

A durable `U13B4_PREDECESSOR_RUNTIME_STARTED` transaction can be resumed after a crash or process restart. At that point the predecessor container may still be running with the exact predecessor image, zero restart count, the production `/config` mount, healthy Manager/Broker peers, listeners, MQTT authentication and HTTP readiness. Those runtime facts are necessary but not sufficient for terminal rollback closure: the persistent Home Assistant image binding must also still select the predecessor. Otherwise a later systemd/Compose recreate can start the target again even though the transaction was already marked `U13B_ROLLED_BACK`.

The Stage B terminal-health contract is therefore strengthened to require:

```text
RUNNING_PREDECESSOR_IMAGE_EXACT=true
PREDECESSOR_RESTART_COUNT_ZERO=true
PRODUCTION_CONFIG_MOUNTED=true
MANAGER_BROKER_PEERS_EXACT=true
HOMEASSISTANT_PERSISTENT_BINDING=PREDECESSOR
LISTENERS_EXACT=true
MANAGER_MQTT_AUTHENTICATED=true
HOMEASSISTANT_MQTT_AUTHENTICATED=true
HOMEASSISTANT_HTTP_READY=true
```

A mismatch between the running predecessor and the persistent Home Assistant binding is fail-closed as `u13b_homeassistant_binding_drift` and must never advance `U13B4 -> U13B_ROLLED_BACK`.

This repair is intentionally Stage B scoped. It does not implement Stage C USB/host split-write reconciliation, does not authorize a live rollback, and does not change the already terminal U13A production transaction.



## 15. Stage C — USB/host split-write read-only reconciliation source gate

Stage A/B final independent review is CLOSED_PASS after KF-163 repair and exact-head 16/16 CI. Stage C is repository-only and addresses the remaining durability split created by the intentionally ordered write sequence:

```text
validated successor transaction
-> USB metadata fsync
-> host transaction durable write
```

A crash between the last two steps can leave the USB exactly one U13B rollback edge ahead of the host. The existing Stage B controller would otherwise re-enter from the older host phase and repeat the bounded operation. Stage C therefore makes split classification a mandatory controller entry guard before recovery authorities or runtime operations are touched.

The read-only classifier validates all four existing USB transaction documents:

- `manifest.json`;
- `phase.json`;
- `checksums.json`;
- `content-authority.json`.

The classifier requires exact transaction ID, release, target archive identity, target image, filesystem UUID, recovery content identities and recovery-content manifest continuity. The session-scoped USB public fingerprint must remain structurally valid but is deliberately not promoted to cross-session authority.

Classification is restricted to the U13B rollback branch:

```text
HOST_USB_EXACT
USB_ONE_PHASE_AHEAD_RECONCILABLE
HOST_ONE_PHASE_AHEAD_STOP
DIVERGENT_OR_UNKNOWN_STOP
```

Only `HOST_USB_EXACT` permits the current rollback controller to continue. `USB_ONE_PHASE_AHEAD_RECONCILABLE` is a read-only classification result, not permission to write the host transaction and not permission to replay the operation. The controller stops with a dedicated reconciliation-required error. Host-ahead, multi-phase divergence, malformed metadata and authority drift all fail closed.

This stage intentionally does **not** implement automatic host reconciliation. A later source gate must re-observe the exact real-world postcondition corresponding to the USB successor before any host-only metadata repair is considered.

Production USB metadata reading is itself non-mutating: it reads existing private regular files only and rejects symlinks, ownership/mode drift, oversized metadata, malformed JSON and duplicate keys. No directory creation, USB metadata write, service action, image action or transaction write occurs in the read path.

```text
STAGE_A_CLOSED_PASS=true
STAGE_B_CLOSED_PASS=true
U13B_SPLIT_CLASSIFIER=true
U13B_USB_METADATA_READONLY=true
U13B_CONTROLLER_BLIND_REPLAY_BLOCKED=true
USB_ONE_PHASE_AHEAD_AUTO_HOST_WRITE=false
USB_ONE_PHASE_AHEAD_AUTO_OPERATION_REPLAY=false
U13B_READONLY_RECONCILIATION_SOURCE=true
U13B_LIVE_EXECUTION_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```


## 16. Stage D design discovery and D1 transaction-mirror foundation

Stage C closed the read-only phase classifier, but the next reconciliation design review found that the original four USB metadata files are insufficient to perform a safe host-only repair.

A USB-one-phase-ahead result proves the durable phase ordering, but `phase.json` does not preserve the complete successor host transaction. The first rollback edge is the clearest example:

```text
U9/U10/U11/U12
-> U13B0_ROLLBACK_IN_PROGRESS
```

That transition also persists `failure_code`, `rollback_origin_phase`, `recovery_required` and `rollback_recovery_content_verified`. Reconstructing those fields from the older host transaction after a crash would require guessing data that was already computed before the split.

D1 therefore adds a fifth private USB metadata document:

```text
n3w-update/transaction/host-transaction.json
```

It is the exact validated, public-safe host successor transaction passed to USB synchronization. The USB write order is tightened to:

```text
static authority metadata
-> exact host-transaction mirror
-> phase.json
-> fsync transaction directory
-> host transaction durable write
```

`phase.json` is deliberately written last and acts as the USB-side commit marker. For an exact host/USB state, the mirror must equal the validated host transaction. For a USB-one-phase-ahead candidate, the mirror must be an exact legal one-edge successor: only the bounded rollback fields for that edge plus `updated_at_unix` may differ. Any other mirrored field drift fails closed.

This D1 foundation still does not authorize host reconciliation. It only makes the already observed successor transaction recoverable and provable.

The remaining Stage D work is intentionally separated:

1. add read-only, per-edge real-world postcondition observers;
2. require the observer for the specific USB successor phase to pass;
3. only then permit a bounded host-only write of the exact mirrored successor transaction;
4. never replay the rollback operation merely because USB is ahead.

```text
STAGE_C_CLOSED_PASS=true
STAGE_D_D1_TRANSACTION_MIRROR=true
USB_PHASE_IS_LAST_COMMIT_MARKER=true
USB_AHEAD_EXACT_SUCCESSOR_PROVABLE=true
USB_AHEAD_HOST_AUTO_WRITE=false
USB_AHEAD_OPERATION_REPLAY=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```
