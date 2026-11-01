# N3-W KF-098 Astra Independent Review Alignment — 2026-09-28

Status: `INDEPENDENT_REVIEW_PASS`

## Review scope

Astra independently reviewed KF-098 against repository source, the repository-versioned cutover executor, tests, and archived public-safe field evidence at:

```text
REVIEW_MAIN=5e695213866258457096f3b1a584997e1ffb3aa0

KF098_SOURCE_REVIEW=PASS
KF098_DEPLOYMENT_REVIEW=PASS
KF098_LIVE_EVIDENCE_REVIEW=PASS

BLOCKER_COUNT=0

KF098_ROUTE_STATUS=CLOSED_PASS
KF098_KNOWN_FAILURE_STATUS=GUARDED
```

Astra did not access T1, rerun deployment/pairing, or directly re-capture the original live packets. The live-evidence conclusion is therefore a source/executor/test/archive cross-review, not a new physical execution.

## Review conclusions

Astra reported PASS for all requested review items:

- A1 root cause: the durable predecessor IPv4 was directly propagated into `candidate.host`, which explains discovery success followed by HTTP targeting the wrong T1 address.
- A2 dynamic resolution: each accepted request re-resolves the route-selected local IPv4, constructs a request-local candidate, does not cache a prior address, and emits no response if resolution fails.
- A3 configuration boundary: production product pairing rejects durable concrete IPv4 while retaining `auto` and hostname as separate supported modes; hostname support does not claim B2 closure.
- A4 recreate authority: a Compose definition representing only three mounts cannot safely reproduce the six-mount live Manager; running-container runtime contract is the correct recreate authority.
- A5 Docker-default normalization: only proven-equivalent DNS/OOM default representations are normalized; non-default policy changes remain visible and fail-closed.
- A6 readiness/rollback: the first failed live apply crossed the mutation boundary and rolled back; waiting for bounded health before listener checks is a valid readiness fix and still rejects real TCP/UDP listener failure. The prior failure remains a reasonable readiness-race explanation, not a uniquely proven root cause.
- A7 post-rollback reacquire: lifecycle/default-representation differences are narrowly accepted while the complete frozen runtime/security contract must otherwise match.
- A8 physical closure: archived discovery request/response counts, current-address match, predecessor exclusion, and Board-to-current-T1 TCP handshake cover the KF-098 product failure chain.
- A9 pairing rejection: `repair_intent_required` proves entry into the existing-identity protection path. The subsequent HTTP 403 does not reopen KF-098, but 403 alone does not establish the exact internal begin rejection reason.
- A10 closure disposition: `CLOSED_PASS` / `GUARDED` is supported.

## Additional isolated checks reported by Astra

Astra also reported isolated behavior checks beyond string/source inspection:

- one UDP client and one server instance exercised resolver success, resolver failure, then changed-address success; observed behavior was new-address response -> no response -> updated-address response, with no stale-address reuse;
- snapshot reacquire accepted the documented default-value normalization while rejecting 13 frozen-field or policy drifts;
- `postcheck()` rejected health failure, missing TCP listener, and missing UDP listener.

These isolated checks were not represented as a full project CI rerun or a real DHCP/LAN migration test.

## Non-blocking follow-ups

The three review follow-ups were accepted for immediate cleanup rather than being left as long-term debt:

1. formal regression coverage was added for the same request source across success -> route-resolution failure -> changed-address success, proving no stale-address reuse, and for postcheck rejection on health/TCP47112/UDP47111 failure;
2. stale manifest wording that implied Compose/temporary-overlay recreate authority was removed or replaced by the live-container-contract authority;
3. a fresh private passive capture was bound by SHA-256, byte count, UTC observation window, hashed Board/pairing identity, and exact Manager image. The application payload explicitly reported `error=setup_secret_unavailable` for the observed `/v2/pairing/begin` 403, so the reason is no longer inferred from HTTP status alone.

Public-safe evidence authority: `docs/development/N3W_KF098_PRIVATE_EVIDENCE_TRACEABILITY_ALIGNMENT_20260928.md`.

The traceability capture also exposed a client-side control-flow defect outside the original KF-098 address root cause: firmware treated `status=rejected + transaction_disposition=continue` as immediate permission to call `/begin`. PR #500 repairs this by mapping rejected/continue to a wait-and-retry action that preserves the pairing ID and suppresses `/begin` until a later hello is accepted.

## Final disposition

```text
KF098_INDEPENDENT_REVIEW=PASS
KF098_BLOCKER_COUNT=0
KF098_ROUTE_STATUS=CLOSED_PASS
KF098_KNOWN_FAILURE_STATUS=GUARDED

KF098_REOPEN=false
IDENTITY_REPAIR_REMAINS_SEPARATE=true
B2_REMAINS_OUT_OF_SCOPE=true
B3_REMAINS_OUT_OF_SCOPE=true
```
