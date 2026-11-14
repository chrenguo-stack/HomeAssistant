# N3W T1 U6 R26 Live Predecessor Recovery Closure — 2026-11-14

## Result

```text
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED
R26_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U6_PREDECESSOR_RECOVERY_R26_20261114_01
R26_EXECUTION_AUTHORITY_HEAD=d95426b15fb718e60683f75ceef36becb8038b61
R26_RESULT=PASS
R26_STATUS=U6_R26_PREDECESSOR_RECOVERY_PASS
R26_AUTHORIZATION_CLAIMED=true
R26_AUTHORIZATION_CONSUMED=true
R26_REPLAY_PERMITTED=false
```

R26 is terminal CLOSED_PASS. Do not replay it.

## Attempt history

Attempt 01 stopped before claim because the local wrapper parsed the complete SSH stdout as one JSON document and called a nonexistent SSH cleanup method. No transaction or USB mutation occurred.

Attempt 02 stopped before claim because the embedded remote script used base64 decoding without importing `base64`. No transaction or USB mutation occurred.

Both defects were repaired inside the R26 wrapper/test scope and passed fresh CI.

Attempt 03 passed embedded preflight, durably claimed/consumed the R26 one-shot authorization, entered U6 and performed predecessor recovery. The Mac-side SSH transport reached its 2400-second timeout before receiving the final remote JSON and returned `STOP_UNKNOWN`. This local result was not replayed.

A bounded read-only forensic then found the durable remote `success.json`, proving the remote action completed successfully after the client timed out.

## Durable U6 evidence

```text
LIVE_TRANSACTION_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING
LIVE_TRANSACTION_STATUS=ACTIVE
LIVE_TRANSACTION_SHA256=7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe

USB_TRANSACTION_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING
USB_TARGET_VERIFIED=true
USB_CAPACITY_VERIFIED=true

PREDECESSOR_ARCHIVE_SHA256=34cec37ab021e1081e236502bfd06760894f6bca93bd8d6bf99d8d90bb89848d
PREDECESSOR_ARCHIVE_SIZE_BYTES=743074537
PREDECESSOR_PORTABLE_IDENTITY_SHA256=8b4d4376e2ab339347abb4aa554d3a5cc6f93ea20b0ee3c22ca8e29ae14b16c3
PREDECESSOR_VERIFIED=true
PREDECESSOR_FSYNCED=true
```

The product U9 authorization fields remain unclaimed/unconsumed. The R26 execution-gate authorization is separate and is consumed/no-replay.

## Runtime preservation

The durable R26 success record proves:
- Manager, Home Assistant and Broker remained running with restart count 0;
- host, services-owner and broker-owner units remained active/running/success with zero restarts;
- Manager IPC phase is `PREDECESSOR_RECOVERY_PREPARING`;
- no service restart occurred;
- Home Assistant was not quiesced;
- no U7+ transition occurred;
- no image deletion occurred;
- rollback was not required.

## Timeout adjudication

The Attempt 03 local `STOP_UNKNOWN` is classified as a client-transport false negative. The remote operation completed later and durably recorded PASS.

For claimed one-shot actions, transport timeout never authorizes retry. Durable remote result/state must be reconciled first.

This behavior is recorded as KF-154 in `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`.

## Stop boundary

```text
CURRENT_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING
NEXT_PHASE=U7_HA_QUIESCED_DATA_BACKUP_PREPARING
U7_PLUS_AUTHORIZED=false
MERGE=false
```

Stop here. R26 is complete. The next bounded engineering task is to define/review a separate U7 HA-quiesce/data-backup gate. No U7 live mutation is authorized by this closure.
