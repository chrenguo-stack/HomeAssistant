# N3-W KF-096 PR #431 Pre-Merge Progress Alignment

Updated: 2026-09-18  
Status: `CURRENT_PROGRESS_ALIGNMENT`

## Scope

This document aligns repository-visible progress with the current local/conversation state without changing PR #431 product source.

```text
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
DEFECT=KF-096
KF096_STATUS=OPEN

REPOSITORY_MAIN=dcea3b33d7204679966b88e7fdfad46ae7b54a4b
PR431_NUMBER=431
PR431_STATE=OPEN_DRAFT
PR431_MERGED=false
PR431_MERGEABLE=true
PR431_BASE=dcea3b33d7204679966b88e7fdfad46ae7b54a4b
PR431_EXACT_HEAD=88812e0cab7103367e02bd89d3e1c0585c188696
```

PR #431 remains a finite successor repair to merged PR #428. It does not redesign the N3-W radio architecture.

## Why PR #428 is no longer the deployable candidate

PR #428 is merged and its exact artifact was successfully built/bound, but the later source review found additional deterministic recovery defects before Board B deployment.

Therefore:

```text
PR428_ARTIFACT_BUILD=PASS
PR428_ARTIFACT_BINDING=PASS
PR428_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR428_ARTIFACT_DISPOSITION=FROZEN_HISTORICAL_NOT_FOR_DEPLOYMENT
```

Board B remains on the frozen PR #425 artifact. No PR #428 or PR #431 physical write has occurred.

## PR #431 finite repair scope

The current successor repair is intentionally limited to:

1. stale Direct AP/BSSID hint invalidation without overriding an explicitly configured BSSID;
2. a bounded ESP-NOW unicast-completion wait with a safe abnormal exit;
3. a bounded Relay restore / callback-quiesce wait with an explicit failure exit;
4. behavior-level regression tests for those exit paths.

Explicitly excluded from this repair:

- a new generic radio scheduler;
- pairing/encryption redesign;
- Manager receive-protocol redesign;
- end-to-end delivery ACK/history replay;
- non-blocking Wi-Fi scan rewrite;
- persistent/history telemetry buffering.

The existing synchronous AP-presence scan remains a later physical measurement boundary. FIFO semantics remain "buffer then submit in order", not an end-to-end delivery guarantee.

## Astra review round 1 and source repair

Astra reviewed prior PR #431 HEAD:

```text
PR431_PRIOR_REVIEW_HEAD=9e134963e6e03386ea0387dc787544a52da0f635
ASTRA_REVIEW_ROUND_1=REQUEST_CHANGES
```

Three review findings were treated as merge blockers/evidence gaps.

### 1. Explicit BSSID provenance

The prior implementation used IDF runtime `config.sta.bssid_set`. ESPHome 2026.4.3 can set this field from the selected scan result even when the user's configured network did not explicitly lock a BSSID.

Current exact HEAD instead derives the restriction from the ESPHome selected configuration:

```text
BSSID_LOCK_SOURCE=wifi::global_wifi_component->get_sta().has_bssid()
IDF_RUNTIME_BSSID_SET_AS_CONFIG_AUTHORITY=false
```

A normal scan-selected BSSID therefore does not become a permanent user lock. A BSSID explicitly present in the selected ESPHome configuration remains authoritative.

The 5-minute hint age is evaluated when a confirmed `NOT_FOUND` result is processed; it is not an independent wall-clock expiry event. Scan errors are not counted as confirmed misses.

### 2. Callback quiesce total deadline

The prior 25 ms retry interval could repeat indefinitely because the restore budget was checked only after callback quiescence.

Current exact HEAD uses an explicit decision:

```text
callbacks_idle=true AND teardown_confirmed=true
  -> PROCEED

callbacks_idle=false AND restore_budget_not_exhausted
  -> WAIT

callbacks_idle=false AND restore_budget_exhausted
  -> REBOOT

teardown_confirmed=false
  -> REBOOT
```

The 25 ms interval is therefore only a retry cadence. The total Relay restore/quiesce budget remains bounded by 30 seconds.

### 3. Old ESP-NOW event-source isolation

ESP-IDF 5.5.4 exposes callback unregister and `esp_now_deinit()`, but its public API contract does not state that a send event that has not yet entered the user callback can never appear after a later same-boot callback re-registration.

The abnormal missing-completion path therefore does not create another ESP-NOW session in the same boot.

```text
UNicast_COMPLETION_TIMEOUT=2s
TIMEOUT_ACTION=
  detach callback target
  -> unregister callbacks
  -> esp_now_deinit()
  -> record teardown confirmation
  -> App.safe_reboot()
  -> fresh boot before any new ESP-NOW session
```

Normal Direct/Relay transitions with no pending completion retain the existing same-boot architecture.

Driver teardown now has explicit semantics:

```text
ESP-NOW stopped + owned Wi-Fi stopped + callbacks idle
  -> teardown_confirmed=true

ESP-NOW teardown failure
  -> teardown_confirmed=false
  -> keep non-reusable initialized state

owned Wi-Fi teardown failure
  -> teardown_confirmed=false

callbacks still in flight
  -> teardown_confirmed=false
```

An unconfirmed teardown blocks driver reinitialization. The abnormal path escalates to a safe reboot rather than attempting to prove same-boot generation isolation.

## Exact-head CI

Current PR #431 exact HEAD:

```text
PR431_EXACT_HEAD=88812e0cab7103367e02bd89d3e1c0585c188696

CI_TOTAL=11
CI_SUCCESS=11
CI_FAILURE=0
CI_INCOMPLETE=0

PHASE4_SIMPLIFIED_PRODUCT_RUNTIME=PASS
ESP32_C6_CHILD_COMPILE=PASS
ESP32_C6_RELAY_COMPILE=PASS
ESP32_C6_PHYSICAL_HARNESS_COMPILE=PASS
```

CI/source success is not physical acceptance and does not close KF-096.

## Current review gate

The current gate is a second Astra review bound strictly to the exact PR #431 HEAD above.

```text
NEXT_ONE_GATE=N3W_KF096_PR431_ASTRA_FINAL_REVIEW_20260918_01

BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
T1_MUTATION=false
PR431_MERGE=false
```

The second review is focused on:

1. BSSID configuration provenance and multi-network selected-config semantics;
2. finite callback-quiesce exit;
3. teardown confirmation / safe-reboot boundary and absence of same-boot abnormal-session reuse;
4. any bypass around `teardown_confirmed`;
5. distinction between behavior tests and source-string contracts.

If no new merge blocker remains, PR #431 may proceed to an explicit merge authorization. It must not be merged automatically by this alignment task.

## Physical acceptance remains pending

After a future merge, a new exact artifact must be built and bound to the merged successor source. The older PR #428 artifact cannot silently become the PR #431 candidate.

Future physical validation still needs to measure:

- Direct -> Relay initial takeover;
- Relay steady-state continuity;
- recovery-probe disturbance;
- Relay -> Direct failback;
- synchronous scan duration and main-loop stall;
- actual sampling cadence and Manager arrival cadence;
- send-time current channel, peer channel, and raw ESP-NOW errors;
- callback-timeout abnormal recovery without a stale session;
- cold-boot Relay behavior.

Until that evidence exists:

```text
KF096_STATUS=OPEN
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

## Authority boundaries

- PR #431 exact source review authority is `88812e0cab7103367e02bd89d3e1c0585c188696`.
- Repository `main`, candidate source, frozen artifact, and deployed Board B source are distinct authorities.
- Board B still runs PR #425.
- No Board/T1/serial/flash activity is authorized by this document.
- PR #428 artifact hashes remain historical evidence only; they are not a deployable successor artifact.
- KF-092 remains `CLOSED_PASS` and is not reopened by KF-096 successor work.
