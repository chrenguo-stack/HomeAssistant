# PR #437 telemetry reliability branch decision

Updated: 2026-09-20  
Status: `ARCHITECTURE_BRANCH_DECISION`

## Authority

```text
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
PR=437
DECISION_PARENT_HEAD=913c51c5ef01840abb7a72aceff18194077d1f1a
PR437_MERGE=false
BOARD_MUTATION=false
T1_RUNTIME_MUTATION=false
```

This document records a deliberate reliability branch point discovered while
reviewing the PR #437 transition-telemetry repair. It does not replace the
accepted Phase 1 periodic-telemetry contract. It separates the current product
repair from a possible future reliable-history product upgrade.

## Existing product contract

The accepted N3-W simplification contract defines ordinary periodic telemetry
as a latest-state stream rather than guaranteed delivery of every sample:

- one authenticated application frame per sample;
- no application receipt ACK for ordinary periodic telemetry;
- no periodic resend/retry cache;
- a missing sample may recover naturally at the next higher sequence;
- a late lower sequence must not roll canonical state backward.

Therefore `missing_sequence_count > 0` remains an important diagnostic, but
is not by itself proof that the current product contract failed. Likewise,
`missing_sequence_count == 0` does not prove end-to-end reliable delivery.

## Three reliability options

### Option A — original minimal latest-state transport

```text
sample
  -> one transport attempt
  -> success or loss
  -> next sample continues
```

Advantages: minimum state, minimum RAM/flash/network coupling, highest
simplicity. Disadvantage: telemetry generated while the radio is temporarily
owned by recovery logic can be discarded before it ever receives a transport
opportunity.

### Option B — bounded transition hold buffer

```text
sample generated while no business transport opportunity exists
  -> hold in bounded RAM FIFO
  -> when Direct or Relay becomes usable, attempt that sample once
  -> transport attempt succeeds: release local ownership
  -> transport attempt fails: record failure and release; do not resend
```

This preserves the Phase 1 one-attempt architecture while preventing the
specific class of transition loss where business telemetry never received a
send opportunity at all.

Selected for PR #437.

The queue is a `transition hold buffer`, not a reliable-delivery retry queue.
Its capacity is a bounded RAM budget. Overflow remains explicit and rejects
the newest sample while preserving already-held older samples.

Direct semantics:

- `DIRECT` with MQTT not connected: no transport opportunity; retain the
  sample. A newly generated business sample may still contribute one Direct
  path-health failure observation so failover is not frozen.
- MQTT connected and publish is attempted: this is the sample's one Direct
  transport attempt. Accepted submission releases local ownership; a rejected
  submission is recorded and not retried.

Relay semantics:

- Discovery / Direct probe / Relay restore / no authenticated Relay path:
  no transport opportunity; retain the sample.
- `esp_now_send()` synchronous failure: the one Relay transport attempt has
  failed; record it and do not resend that sample.
- synchronous submit success: retain the sample only as `RELAY_IN_FLIGHT`
  until the ESP-NOW MAC completion arrives.
- MAC completion success: release the sample.
- MAC completion failure: record the failure and release the sample; do not
  put it back into the queue.

Backlog drain is `TRANSPORT_ONLY` for path-health accounting. It must not
compress Direct/Relay failure hysteresis merely because several held samples
are drained quickly. New business telemetry remains the normal cadence for
`RECORD_PATH_RESULT`.

Option B does not add Manager ACK, Manager reorder buffering, persistent
telemetry storage, history replay, or application-level resend.

## Option C — future durable every-sample delivery

Future version candidate:

```text
sample
  -> durable device outbox
  -> Direct or Relay transport
  -> Manager durable acceptance
  -> application ACK
  -> remove from outbox
```

A correct Option C would also require:

- idempotent `boot_id + seq` retransmission and deduplication;
- Manager acceptance of late historical samples without rolling canonical
  latest-state backward;
- bounded persistent storage and explicit overflow policy;
- flash-wear/write-amplification control such as append/batched or
  wear-levelled storage rather than repeatedly rewriting one NVS key;
- retry/backoff that is independent from Direct/Relay path hysteresis;
- reboot and power-loss recovery tests.

Technically this is achievable with the current ESP32-C6 / ESP-NOW / MQTT /
Manager stack, but it is a separate reliable-data architecture. Coupling its
ACK/retry state directly into the radio failover state machine would increase
risk of retry storms, queue head blocking, path oscillation, watchdog pressure,
and flash wear.

Option C is therefore reserved for a later version iteration and is explicitly
outside PR #437.

## Current decision

```text
OPTION_A=BASELINE_REFERENCE
OPTION_B=SELECTED_FOR_PR437
OPTION_C=FUTURE_VERSION_CANDIDATE

PR437_MANAGER_DURABLE_ACK=false
PR437_MANAGER_REORDER_BUFFER=false
PR437_PERSISTENT_TELEMETRY_OUTBOX=false
PR437_POST_FAILURE_RESEND=false
PR437_TRANSITION_HOLD_BUFFER=true
```

The next PR #437 source change must narrow the current retry-capable queue to
the Option B transition-hold semantics above before additional physical
validation or merge-readiness review.
