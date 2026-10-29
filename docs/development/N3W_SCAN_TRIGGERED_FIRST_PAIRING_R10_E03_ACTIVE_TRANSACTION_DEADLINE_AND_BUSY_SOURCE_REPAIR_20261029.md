# N3-W R10 E03 ACTIVE transaction deadline / busy source repair — 2026-10-29

## Gate

`N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_E03_ACTIVE_TRANSACTION_DEADLINE_AND_BUSY_SOURCE_REPAIR_20261029_01`

Base product source:

- `ff750b3801a282af1667b5fa63481e2333e301b3`
- PR #725 remains the product/UI integration line.

This gate authorizes source/test/archive changes only.

Not authorized:

- T1 mutation or cleanup;
- Board reset/write/NVS mutation;
- physical registration retry;
- merge.

## Physical failure evidence

The repaired R10 physical E2E reached the phone flow and displayed:

- `E03 主机忙`.

The immediately preceding T1 baseline proved:

- first-registration attempt count = 0;
- unresolved first registration = 0;
- pairing window CLOSED;
- TCP/47112 closed.

Post-failure read-only evidence proved one new Board D-owned attempt:

- runtime Board D hardware identity SHA-256 = `3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55`;
- state = `ACTIVE`;
- phase = `BOOTSTRAP_ACCEPTED`;
- cleanup_state = `NONE`;
- terminal_reason = null;
- pairing window = `CLOSED`;
- pairing-window close_reason = `manager_start`;
- pairing-window failure_type = null;
- TCP/47112 absent;
- Manager container restart count = 0.

The attempt later remained ACTIVE after its durable `expires_at` passed.

The older `3991...` write-path identity hash is not product runtime hardware-id authority and must not be used for this evidence binding.

## Confirmed blocker

The durable first-registration ACTIVE row is created before `open_first_registration()`.

The existing autonomous deadline owner is created only after the dynamic pairing window becomes OPEN.

Therefore a failure before the window takes deadline ownership can leave:

```text
durable ACTIVE / BOOTSTRAP_ACCEPTED
+ no OPEN pairing window
+ no 47112 listener
+ no autonomous deadline callback
```

The row can consequently remain ACTIVE after its absolute deadline and keep the single-registration gate busy.

This is a confirmed product blocker independent of the still-unproven instantaneous trigger of the first E03 response.

## Busy-race hardening

The HTTP bootstrap server is threaded. The transaction service previously had no transaction-level lock around:

```text
ledger lookup
-> create ACTIVE
-> activate RAM intent
-> open pairing window
```

Two concurrent confirms could therefore observe the pre-create boundary concurrently.

The repair serializes `start()` for the single-concurrent-first-registration V1 contract.

Exact duplicate confirms remain idempotent and retain the original absolute deadline.

Conflicting identity/source/secret confirms remain rejected as `registration_busy`.

## Deadline repair

The transaction service now owns a pre-window deadline timer from the moment the durable ACTIVE transaction is accepted.

Rules:

1. the timer uses the durable ledger `expires_at`;
2. exact retries do not refresh or duplicate the deadline;
3. while window establishment is unavailable, the pre-window timer remains armed;
4. once `open_first_registration()` succeeds, the pre-window timer is cancelled and the existing pairing-window deadline mechanism resumes ownership;
5. a pre-window deadline closes the RAM intent and invokes durable deadline reconciliation;
6. Manager restart semantics remain unchanged: startup reconciliation is still authoritative after process restart.

No second product TTL is introduced.

## Public-safe busy diagnostics

The wire reason remains exactly:

- `registration_busy`.

No protocol/UI change is made.

Internal Manager logs add only bounded non-secret classification strings such as:

- `active_ledger_conflict`;
- `active_intent_missing`;
- `active_intent_source_ip_mismatch`;
- `active_intent_setup_secret_mismatch`;
- `active_intent_deadline_mismatch`.

No hardware ID, pairing ID, source IP, Setup Secret, TLS pin or credential is logged by this classification.

## Regression tests

Focused transaction tests require:

- exact duplicate deadline reuse;
- source-IP conflict remains busy;
- Setup Secret conflict remains busy;
- concurrent exact confirms are serialized;
- successful window opening cancels the pre-window deadline owner;
- window-open failure leaves the original deadline owner armed;
- the pre-window deadline terminalizes and cleans an ACTIVE attempt without any follow-up request;
- a later exact retry reuses the original timer/deadline and hands ownership to the window on success.

## Physical follow-up

Source/CI PASS is not physical closure.

After source review/CI, a new Manager successor artifact and separately authorized T1 refresh are required.

The current failed ACTIVE transaction must not be manually cleaned or replayed under this source-repair gate.
