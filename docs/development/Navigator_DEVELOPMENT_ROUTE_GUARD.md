# Navigator — Development Route Guard

> Purpose: keep the project aligned with the agreed product roadmap, detect scope drift and over-engineering early, and force a short corrective decision before more implementation or acceptance-framework work is added.

This file is a **navigation / correction index**, not a new product process framework. It should remain short, readable, and actionable.

The earlier historical version of this file was archived after FC4 route changes. This version is re-established for the current N3-W three-board regression/retest route and does not make the historical FC4 route text current authority.

## 1. Current North Star

```text
NORTH_STAR=N3W_THREE_BOARD_REGRESSION_RETEST
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
FC4_REOPEN=false
```

Current route focus:

```text
Board A R2 = FROZEN CLOSED PASS
Board B R2 = CURRENT
Board C = NOT ACCESSED BY CURRENT BOARD-B STAGE
```

The current Board-B objective is to prove normal runtime liveness after existing-identity credential recovery while preserving:

```text
stable NODE_ID
MQTT credential generation = 2
application-key epoch = 1
system-peer-trust generation = 1
pairing state = approved
pending credential generation = NONE
```

No flash, NVS erase, firmware rewrite, pairing-recovery replay, credential-recovery replay, Broker ACL relaxation, or unrelated mutation is part of this route.

## 2. Development / Validation Roles

The established execution model remains:

```text
High-level model
  -> route, authority, scope, gate design, adjudication

Codex low-order executor
  -> exact command compilation, observation, normalization, evidence output
```

Codex must not redesign the route, expand scope, repair production state, replay consumed authorization, or promote an observed failure into a product root cause without the high-level adjudication layer.

## 3. Route-Deviation / Over-Engineering Indicators

Treat any of the following as a navigation warning:

1. A test/helper becomes more complex than the product behavior being validated.
2. One read-only failure creates a long chain of tiny successor gates whose main purpose is to debug the previous gate.
3. More time is spent proving the test harness than observing Manager/Broker/Board product behavior.
4. Historical container IDs, hashes, paths, or snapshots are repeatedly promoted into current-runtime correctness authorities.
5. A read-only diagnostic stops after one ordinary observation failure even though independent read-only evidence could still be collected safely.
6. An executor makes a semantic product-failure decision when it only possesses incomplete transport/oracle evidence.
7. Already-frozen runtime facts are rediscovered from scratch in every micro-gate instead of receiving a lightweight continuity check.
8. A temporary acceptance mechanism starts becoming permanent product architecture.
9. A failure in parser/framing/namespace/path selection is treated as Manager/Broker/Board failure before the harness domain is excluded.
10. The path from the current state to the next product acceptance result can no longer be explained in a few steps.

## 4. Correction — Consolidated Read-Only Snapshot Strategy

### Trigger

During Board-B R2 runtime-liveness preparation on 2026-09-03, repeated host-only read-only stages were blocked by harness/oracle issues involving:

- current/predecessor container authority;
- Docker inspect field domains;
- deleted predecessor-container assumptions;
- Broker effective-config path discovery;
- DynSec UNKNOWN propagation;
- raw-container `docker exec` targeting;
- stdout newline/framing comparison;
- Manager socket namespace selection;
- MQTT endpoint extraction;
- resolver context and process-environment authority.

These failures were useful for safety but created a tooling-debug loop. The exact-container resolver successor eventually proved:

```text
R2B_MANAGER_EXACT_CONTAINER_RESOLVER_PROBE=PASS
MANAGER_MQTT_ENDPOINT_AUTHORITY_BOUND=true
MANAGER_IN_CONTAINER_RESOLVER_AUTHORITY_BOUND=true
MANAGER_CURRENT_DNS_FAILURE_PROVEN=false
PREDECESSOR_PROCESS_ENV_FAILURE_CLASS=PHYSICAL_HARNESS
```

This confirms that the workflow should be simplified without weakening fail-closed mutation boundaries.

### New default for host-only read-only diagnosis

Use:

```text
ONE LOGICAL GATE
ONE EXECUTOR
ONE FRESH SNAPSHOT
ONE ADJUDICATION
```

A single logical read-only runtime-baseline gate may collect, in one execution, mutually compatible facts for the same objective:

```text
Current Manager authority
  - exact container/image/source continuity
  - MQTT endpoint inputs
  - exact-container resolver result
  - process-owned established MQTT socket

Current Broker authority
  - endpoint-bound exact container/image
  - listener state
  - live mosquitto.conf
  - Dynamic Security plugin/config-file binding
  - active dynamic-security.json

Board-B Manager durable state
  - registration approved
  - current NODE_ID binding
  - credential generation 2 active
  - pending generation NONE

Stability
  - Manager/Broker identity and RestartCount
  - relevant config/DynSec hashes
  - bounded 30–60 second continuity window
```

This is still **one logical gate** because all evidence serves the same goal: establish the current Board-B runtime baseline before runtime-liveness observation.

## 5. Read-Only STOP Policy

Do not use mutation-style immediate STOP for every ordinary read-only negative observation.

### Immediate STOP remains mandatory when:

```text
exact target authority is lost or ambiguous
transport/executor integrity is not proven
a safety or redaction boundary is violated
a command would exceed read-only scope
runtime identity changes during the snapshot
```

### Otherwise, for independent read-only observations:

```text
observed false / UNKNOWN
  -> record exact fact and error class
  -> continue collecting other independent read-only evidence
  -> adjudicate once at the end
```

Example: a resolver failure does not by itself prevent read-only collection of resolver-file hashes, Manager-owned socket tables, Broker listener state, Broker config, or DynSec structural metadata, provided target authority and read-only safety remain intact.

This rule does **not** apply to mutation gates. Mutation gates remain fail-closed at the first unmet precondition.

## 6. Continuity Check Instead of Rediscovery

Once a current runtime authority has been freshly and uniquely frozen, later gates should use a small continuity check first:

```text
same container ID?
running?
RestartCount unchanged/acceptable?
exact image/source still bound?
```

If YES, reuse the frozen current authority for that bounded sequence.

If NO, return to an authority-rebind gate.

Do not repeatedly rediscover current Manager/Broker from broad heuristics when no continuity break has occurred.

## 7. Executor Evidence Policy

The low-order executor should prefer **facts over semantic verdicts**.

Preferred output:

```text
GETADDRINFO_SUCCESS=
GETADDRINFO_EXCEPTION_CLASS=
MANAGER_OWNED_MQTT_SOCKET_MATCH_COUNT=
BROKER_CONFIG_READ_RC=
DYNSEC_READ_RC=
DYNSEC_JSON_VALID=
```

Avoid premature executor-only conclusions such as:

```text
PRODUCT_FAILURE
ACTIVE_DYNSEC_DRIFT
MANAGER_DISCONNECTED
```

unless the corresponding authoritative facts were actually observed and the gate contract explicitly defines that classification.

The high-level model remains responsible for final classification into:

```text
PASS
PRODUCT
SECURITY
PHYSICAL_HARNESS
INFRASTRUCTURE
UNKNOWN_NOT_PASS
```

## 8. KNOWN_FAILURES as Pre-Gate Constraints

`KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` is not only postmortem reference. Relevant guards must be applied before a gate is issued.

For the current R2B path, especially apply:

```text
KF-009  runtime path authority
KF-035  exact Manager resolver context
KF-045  host/container path-domain separation
KF-058  process/netns socket authority
KF-069  active DynSec authority lineage
KF-070  Docker recreate / RestartCount semantics
KF-071  current-runtime/current-endpoint authority discriminator
KF-072  UNKNOWN propagation
KF-078  stdin/TTY/parameter/framing contract
KF-082  positive PASS normalization
```

If a proposed executor conflicts with an existing guard, correct the executor before execution instead of rediscovering the known failure live.

## 9. Current Optimized Route

After the exact-container resolver PASS, the preferred route is:

```text
frozen current Manager/Broker continuity check
        |
        v
R2B_CURRENT_RUNTIME_AUTHORITY_CONSOLIDATED_READONLY_SNAPSHOT
        |
        +-- Manager endpoint/resolver/process-owned socket
        +-- endpoint-bound Broker listener/config/DynSec
        +-- Board-B Manager durable-state spot check
        +-- 30–60 s stability
        |
        v
ONE high-level adjudication
        |
        +-- PASS -> Board-B security semantic binding / runtime-liveness route
        +-- HARNESS -> repair only the oracle, no product mutation
        +-- REAL DRIFT -> scoped RCA
```

Do not automatically execute the next gate after a PASS.

Any future Board/USB/serial access still requires the appropriate fresh explicit authorization; this optimization changes only host-only read-only evidence collection efficiency.

## 10. Relationship to KNOWN_FAILURES

Use the documents differently:

```text
KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
= symptom -> root cause -> fix/guard

Navigator_DEVELOPMENT_ROUTE_GUARD.md
= product direction -> scope/complexity warning -> route correction
```

A technical incident can belong in both when it reveals both a concrete failure and a development-process lesson.

## 11. Update Rule

Update this file when:

- the product phase or North Star changes;
- validation begins fragmenting into repeated harness-debug micro-gates;
- a simpler evidence-collection strategy materially shortens the route;
- a deferred architecture starts re-entering the current task;
- a previous simplification decision is being reversed.

Use this compact form:

```text
DATE=
CURRENT_OBJECTIVE=
WARNING=
WHY_IT_IS_DRIFT_OR_OVER_DESIGN=
CORRECTION=
KEEP=
DEFER_OR_REMOVE=
STATUS=
```

Do not turn Navigator into a chronological evidence archive. Keep current route rules and only high-value historical corrections that prevent recurrence.
