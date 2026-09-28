# N3-W KF-098 Dynamic Discovery Real-Traffic Acceptance Closure — 2026-09-28

Status: `CLOSED_PASS`

## Scope

This document closes KF-098 after the already-completed Manager source repair and exact T1 live cutover were exercised by a real Board B discovery/HTTP flow.

No Board flash/NVS mutation, registration mutation, pairing repair authorization, Broker mutation, firewall mutation, or second Manager cutover was performed for this acceptance.

## Pre-existing closure authority

```text
SOURCE_REPAIR=PASS
T1_LIVE_CUTOVER=PASS
MANAGER_RUNTIME=PASS
MANAGER_PAIRING_ADVERTISED_HOST=auto
BROKER_CONTINUITY=PASS
R5_CONTINUITY=PASS
```

The accepted design required six live conditions after source deployment:

1. Manager UDP/47111 and TCP/47112 are bound;
2. Board discovery request reaches T1;
3. discovery response host equals the current route-selected T1 IPv4;
4. response host no longer equals the predecessor stale value;
5. Board initiates TCP/47112 to the current T1;
6. expected next pairing disposition is observed.

## Real Board evidence

The earlier zero-traffic windows were not product evidence because Board B was powered off at that time. Board B was then powered by USB and left otherwise unmodified.

A fresh 60 s passive capture observed:

```text
DISCOVERY_QUERY_COUNT=12
DISCOVERY_RESPONSE_COUNT=12
CANDIDATE_HOST_EQUALS_ROUTE_SELECTED_T1_IPV4=true
CANDIDATE_HOST_DIFFERS_FROM_PREDECESSOR=true
TCP47112_TRAFFIC_PRESENT=true
BOARD_TO_CURRENT_T1_TCP_SYN=true
T1_TO_BOARD_TCP_SYN_ACK=true
TCP47112_HANDSHAKE_OBSERVED=true
```

The current candidate address is intentionally not recorded as a raw private locator in public-safe documentation. Its secret-safe hash differs from the frozen predecessor stale-value hash.

## Expected next pairing disposition

A second passive 30 s application-level capture observed the actual HTTP pairing sequence:

```text
REQUEST_PATH=/v2/pairing/hello
REQUEST_SCHEMA=gh.pair.hello/1

HELLO_HTTP_STATUS=200
HELLO_RESPONSE_SCHEMA=gh.pair.simple-hello-result/1
HELLO_STATUS=rejected
HELLO_REASON=repair_intent_required
HELLO_TRANSACTION_DISPOSITION=continue

NEXT_REQUEST_PATH=/v2/pairing/begin
NEXT_REQUEST_SCHEMA=gh.pair.simple-begin/1
BEGIN_HTTP_STATUS=403
BEGIN_RESPONSE_SCHEMA=gh.pair.simple-error/1
```

This is the expected existing-identity security boundary. The Board reached the current T1 over the repaired discovery/HTTP path, but the Manager refused to replace the durable registered identity because no fresh one-shot repair intent had been authorized.

The 403 on `/v2/pairing/begin` therefore does not reopen KF-098. Identity-preserving repair remains a separate later gate.

## Closure

```text
KF098_SOURCE_REPAIR=PASS
KF098_T1_LIVE_CUTOVER=PASS
KF098_MANAGER_RUNTIME=PASS
KF098_REAL_BOARD_DISCOVERY_ACCEPTANCE=PASS
KF098_REAL_BOARD_HTTP47112_ACCEPTANCE=PASS
KF098_EXPECTED_NEXT_PAIRING_DISPOSITION=PASS

PAIRING_REPAIR_AUTHORIZATION=false
REGISTRATION_DATABASE_MUTATION=false
BOARD_FLASH_MUTATION=false
BOARD_NVS_MUTATION=false
T1_RECUTOVER=false

KF098_ROUTE_STATUS=CLOSED_PASS
KF098_KNOWN_FAILURE_STATUS=GUARDED
```

KF-098 is closed. The next pairing-identity recovery activity, if needed, must use its own explicit identity-preserving repair gate and must not be represented as unfinished KF-098 work.


## Independent Astra review

Astra independently reviewed the source, repository-versioned deployment executor, tests, and archived live evidence at `main=5e695213866258457096f3b1a584997e1ffb3aa0`.

```text
KF098_SOURCE_REVIEW=PASS
KF098_DEPLOYMENT_REVIEW=PASS
KF098_LIVE_EVIDENCE_REVIEW=PASS
BLOCKER_COUNT=0

KF098_ROUTE_STATUS=CLOSED_PASS
KF098_KNOWN_FAILURE_STATUS=GUARDED
```

This review did not access T1 or replay the physical pairing flow. It independently confirmed that the archived evidence and current source/executor behavior are sufficient for KF-098 closure. The three review follow-ups are recorded in `docs/development/N3W_KF098_ASTRA_INDEPENDENT_REVIEW_ALIGNMENT_20260928.md` and are non-blocking.
