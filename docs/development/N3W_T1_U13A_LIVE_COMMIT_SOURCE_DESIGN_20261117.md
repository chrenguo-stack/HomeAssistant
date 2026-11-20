# N3-W T1 U13A live commit source design — 2026-11-17

## 1. Entry authority

```text
U13A_READONLY_SOURCE_HEAD=fee2e1f4bb5d724e6821eb9e6534038e9646457d
U13A_READONLY_SOURCE_CI=16_OF_16_SUCCESS
U13A_READONLY_RESULT=U13A_COMMIT_READONLY_PREFLIGHT_PASS

ENTRY_PHASE=U12_TARGET_ACCEPTANCE
ENTRY_TRANSACTION_SHA256=32a92edcd9fbdad1356b874a55d40f6e919518363c5740b495f9b5fa08a56071
ENTRY_USB_PHASE_SHA256=ca5cbcaa0d915f9a0fe590d2beeeace846ce7029bdf6dcb8b46331d205212283

FORWARD_COMMIT_ELIGIBLE=true
ROLLBACK_REQUIRED=false
```

The current transaction is eligible for the normal terminal success route.

## 2. Terminal operation

The live gate performs only:

```text
U12_TARGET_ACCEPTANCE
-> record_commit()
-> U13A_COMMITTED
```

Expected terminal fields:

```text
phase=U13A_COMMITTED
status=COMMITTED
recovery_required=false
```

No service or image operation is part of U13A commit.

## 3. Preclaim safety

Before consuming the U13A authorization, the executor must run the full U13A read-only preflight again.

Required result:

```text
STATUS=U13A_COMMIT_READONLY_PREFLIGHT_PASS
FORWARD_COMMIT_ELIGIBLE=true
ROLLBACK_REQUIRED=false
```

This includes exact recovery asset verification.

If preflight fails, no U13A authorization is claimed or consumed.

## 4. One-shot authorization

A real U13A transition requires a separate exact authorization.

The source-preparation manifest remains:

```text
U13A_LIVE_EXECUTION_AUTHORIZED=false
```

until explicit user authorization is granted.

After authorization is granted, the exact execution package must require:

```text
granted=true
claimed=false
consumed=false
replay_permitted=false
```

On remote execution start, the authorization claim is persisted once and immediately becomes:

```text
claimed=true
consumed=true
replay_permitted=false
```

No postclaim blind replay is permitted.

## 5. Postclaim revalidation

After claim and under the transaction lock, revalidate:

- exact U12 host transaction;
- same bound USB UUID;
- exact U12 USB mirror;
- intact U12 live success ledger;
- exact target runtime;
- production /config RW bind;
- Broker/Manager/Home Assistant health;
- current Manager + HA MQTT authentication;
- Home Assistant HTTP readiness;
- `FORWARD_COMMIT_ELIGIBLE` classification.

The large recovery archives do not need a third full rehash inside the lock because the full read-only preflight completed immediately before the claim. The bound media identity and transaction mirror are rechecked after claim.

## 6. Durable write order

The terminal metadata write order remains consistent with prior mandatory-USB transitions:

```text
1. sync U13A transaction metadata to bound USB
2. persist host transaction U13A
3. verify both sides terminal
4. persist U13A success ledger
```

A power loss between steps 1 and 2 is fail-closed:

```text
USB=U13A_COMMITTED
HOST=U12_TARGET_ACCEPTANCE
-> STOP_PARTIAL_U13A_USB_ONLY
-> no blind replay
-> separate reconciliation/repair gate
```

A host-only terminal mismatch is also fail-closed.

## 7. Terminal verification

PASS requires:

```text
HOST_PHASE=U13A_COMMITTED
HOST_STATUS=COMMITTED
HOST_RECOVERY_REQUIRED=false
USB_PHASE=U13A_COMMITTED
TARGET_RUNTIME_HEALTHY=true
MANAGER_MQTT_AUTH=true
HA_MQTT_AUTH=true
HA_HTTP_READY=true
```

The predecessor recovery archive and pre-upgrade HA data backup remain on the USB. They are not restored or deleted by U13A.

Only after durable terminal verification may product-level UX state say the update is complete and the USB may be removed.

## 8. Mutation boundary

Allowed by a future authorized U13A live execution:

```text
TRANSACTION_MUTATION=true
USB_TRANSACTION_METADATA_MUTATION=true
```

Forbidden:

```text
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_RESTORE=false
PREDECESSOR_IMAGE_RESTORE=false
BOARD_ACCESS=false
MERGE=false
```

## 9. Transport ambiguity

If SSH/client transport becomes ambiguous after the authorization claim:

1. never invoke execute again;
2. perform read-only status reconciliation;
3. return PASS only if both host and USB show durable U13A;
4. otherwise fail closed with consumed/no-replay authorization state.

## 10. Current stop boundary

```text
SOURCE_PREPARATION_ALLOWED=true
SOURCE_TEST_AND_CI_ALLOWED=true

U13A_LIVE_EXECUTION_AUTHORIZED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false

STOP_BEFORE_REAL_U13A_COMMIT=true
```
