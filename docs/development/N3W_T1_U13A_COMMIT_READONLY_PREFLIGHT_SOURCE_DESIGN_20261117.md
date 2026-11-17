# N3-W T1 U13A commit read-only preflight source design — 2026-11-17

## 1. Entry authority

```text
PR=807
U12_EXECUTION_SOURCE_HEAD=dc5a5cce3d4b6221c0ea64b58bd5e5bd2d802e94
U12_EXECUTION_ID=u12-live01-20261117T005801Z
U12_RESULT=U12_LIVE_ACCEPTANCE_PASS
U12_ALIGNMENT_HEAD=547216aa9ba803dd621fe31a1fff4c2563f42e4f
U12_ALIGNMENT_CI=16_OF_16_SUCCESS

LIVE_TRANSACTION_PHASE=U12_TARGET_ACCEPTANCE
LIVE_TRANSACTION_SHA256=32a92edcd9fbdad1356b874a55d40f6e919518363c5740b495f9b5fa08a56071
USB_TRANSACTION_PHASE=U12_TARGET_ACCEPTANCE
USB_PHASE_SHA256=ca5cbcaa0d915f9a0fe590d2beeeace846ce7029bdf6dcb8b46331d205212283

U13A_LIVE_EXECUTION_AUTHORIZED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
```

U12 is durably accepted. The next source-only gate decides whether the existing U12 state is still eligible for the normal terminal path:

```text
U12_TARGET_ACCEPTANCE
-> U13A_COMMITTED
```

No U13 terminal transition is executed by this package.

## 2. Architecture decision

The existing architecture defines two terminal outcomes:

```text
U13A_COMMITTED
U13B_ROLLED_BACK
```

For a healthy, exact U12 runtime with intact bound recovery media, the normal route is U13A.

U13B is not selected merely because rollback remains technically possible. Rollback is the recovery route after target failure or a recovery-required condition. The current durable U12 acceptance evidence does not establish such a failure.

Therefore the read-only gate must prove:

```text
POWER_LOSS_REENTRY_CLASSIFICATION=FORWARD_COMMIT_ELIGIBLE
ROLLBACK_REQUIRED=false
```

before any future U13A live commit can be considered.

## 3. Read-only verification contract

The real-T1 U13A preflight revalidates, in order:

1. exact installed product source hashes;
2. exact durable U12 host transaction;
3. U12 one-shot live ledger:
   - claim exists;
   - claimed + consumed;
   - replay forbidden;
   - failure ledger absent;
   - success status is `U12_LIVE_ACCEPTANCE_PASS`;
   - supplemental U12 performance evidence is present and structurally valid;
4. same bound USB filesystem UUID and exact U12 transaction mirror;
5. exact recovery assets:
   - target archive;
   - predecessor recovery archive;
   - protected Home Assistant data backup;
   - recovery capacity still passes;
6. exact target runtime identity and production `/config` RW bind;
7. Broker/Manager/Home Assistant continuity;
8. required listener contract;
9. current Manager + Home Assistant MQTT authentication;
10. Home Assistant HTTP readiness;
11. power-loss reentry classification with recovery media present and exact recovery content verified.

Expected PASS classification:

```text
FORWARD_COMMIT_ELIGIBLE=true
ROLLBACK_REQUIRED=false
```

## 4. Why recovery assets are re-read here

U12 performance design forbids re-reading large archives merely to manufacture timing numbers.

U13A preflight has a different purpose: this is the final safety check before a terminal `COMMITTED` decision after which the product may tell the user that the update is complete and the USB can be removed.

Therefore the final U13A preflight intentionally re-verifies the target archive, predecessor recovery archive and protected data backup for correctness, not for benchmarking.

The resulting recovery verification elapsed time may be recorded diagnostically, but:

```text
NORMAL_OTA_BASELINE_AVAILABLE=false
```

remains true.

## 5. Read-only mutation boundary

The preflight must not call:

- `record_commit()`;
- `record_rollback_complete()`;
- host transaction write;
- USB transaction metadata sync;
- service start/stop/restart;
- image load/delete/prune;
- board operations;
- merge.

Required result flags:

```text
TRANSACTION_MUTATION=false
USB_MUTATION=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
U13A_LIVE_EXECUTION_AUTHORIZED=false
U13A_TRANSITION=false
U13B_TRANSITION=false
BOARD_ACCESS=false
MERGE=false
```

## 6. Future U13A live path

A later separately authorized U13A live executor should remain minimal:

```text
fresh U13A read-only preflight
-> one-shot U13A execution claim
-> lock transaction
-> revalidate exact U12
-> record_commit(U12)
-> sync U13A USB transaction metadata
-> persist host U13A transaction
-> terminal read-only verification
-> durable success ledger
-> STOP
```

Expected terminal state:

```text
PHASE=U13A_COMMITTED
STATUS=COMMITTED
RECOVERY_REQUIRED=false
```

The predecessor recovery package and pre-upgrade data backup remain on USB. U13A must not restore the old backup.

## 7. U13B separation

U13B rollback remains a separate recovery gate.

It requires concrete rollback evidence and must verify both:

```text
PREDECESSOR_IMAGE_RESTORED=true
HA_DATA_BACKUP_RESTORED=true
```

before `U13B_ROLLED_BACK` may be persisted.

This U13A read-only gate neither authorizes nor executes U13B.

## 8. Stop boundary

```text
NEXT_ONE_GATE=REAL_T1_U13A_COMMIT_READONLY_PREFLIGHT_ONLY
STOP_AFTER_U13A_READONLY_PREFLIGHT_BEFORE_ANY_U13_TERMINAL_MUTATION=true

U13A_LIVE_EXECUTION_AUTHORIZED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```
