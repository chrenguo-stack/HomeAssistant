# N3-W T1 U13A live commit pre-authorization review — 2026-11-17

## Authority

```text
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED
SOURCE_HEAD=e56eb75f02857b1b150accf371e91d852ee08709
SOURCE_CI=16_OF_16_SUCCESS

U13A_READONLY_RESULT=U13A_COMMIT_READONLY_PREFLIGHT_PASS
FORWARD_COMMIT_ELIGIBLE=true
ROLLBACK_REQUIRED=false

U13A_LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
```

## Focused source review

The exact live executor, manifest, focused tests, product transition source and durable transaction state machine were independently re-read at the source head.

Review result:

```text
ENTRY_PHASE=U12_TARGET_ACCEPTANCE
ONLY_FORWARD_TERMINAL=U13A_COMMITTED
ROLLBACK_CALL_PRESENT_IN_LIVE_PATH=false

FRESH_U13A_READONLY_REQUIRED_PRECLAIM=true
FORWARD_COMMIT_CLASSIFICATION_REQUIRED=true
ONE_SHOT_OUTER_AUTHORIZATION=true
POSTCLAIM_REPLAY_FORBIDDEN=true

USB_METADATA_WRITE_BEFORE_HOST_TRANSACTION=true
PARTIAL_USB_ONLY_FAIL_CLOSED=true
PARTIAL_HOST_ONLY_FAIL_CLOSED=true
TRANSPORT_AMBIGUITY_READONLY_RECONCILIATION=true

SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_RESTORE=false
PREDECESSOR_IMAGE_RESTORE=false
BOARD_ACCESS=false
MERGE=false
```

## Authorization identity boundary

The existing transaction retains the original destructive-cutover authorization identity recorded at U9.

U13A uses a separate outer one-shot execution authorization ledger:

```text
U13A_AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U13A_LIVE_20261117_01
U13A_CONFIRMATION=EXECUTE U13A LIVE COMMIT: YES
```

This outer authorization does not overwrite the transaction's historical U9 authorization identity.

## Durable transition

If later explicitly authorized, the intended bounded mutation is:

```text
U12_TARGET_ACCEPTANCE
-> record_commit()
-> U13A_COMMITTED

status=COMMITTED
recovery_required=false
```

Write order:

```text
1. U13A USB transaction metadata
2. U13A host transaction
3. terminal read-only verification
4. U13A success ledger
```

The predecessor recovery package and pre-upgrade HA backup remain on USB.

## Pre-authorization verdict

```text
SOURCE_REVIEW=PASS
NEW_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false
LIVE_AUTHORIZATION_READY=true

U13A_LIVE_EXECUTION_AUTHORIZED=false
REAL_T1_MUTATION=false
```

## Explicit boundary

No live U13A mutation may occur until the user explicitly grants:

```text
EXECUTE U13A LIVE COMMIT: YES
```

After explicit authorization, the manifest must be advanced to a separate exact authorized package and fresh CI must pass before real execution.
