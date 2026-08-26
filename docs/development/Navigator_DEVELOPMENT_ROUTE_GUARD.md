# Navigator — Development Route Guard

> Purpose: keep the project aligned with the agreed product roadmap, detect scope drift and over-engineering early, and force a short corrective decision before more implementation work is added.

This file is a **navigation / correction index**, not a new process framework. It should stay short, readable, and actionable.

## 1. North Star

The product goal is a greenhouse environment monitoring system that is:

- reliable in real field use;
- simple for non-technical users;
- local-first and able to operate without cloud dependency;
- maintainable and reproducible;
- developed in the agreed order rather than by continuously expanding architecture.

Current product-line constraints:

- only Wi-Fi and LoRa monitoring-node SKUs are in scope;
- default node power remains battery + solar panel;
- N3-W must be completed and accepted before N3-L expansion;
- control-node work is later than monitoring-node product closure;
- optional observability/history tooling must not block the core product.

## 2. Current Route

Current main route:

```text
N3-W source convergence
-> Spare T1 current-main convergence
-> FC4 three-board final physical acceptance
-> N3-W product closure
-> N3-L
-> later control-node work
```

Current FC4 objective:

```text
exact current-main Manager image
-> production-equivalent Spare T1
-> Direct MQTT / authenticated ESP-NOW Relay / Manager canonical dedup
-> three real ESP32-C6 boards
-> direct / relay / recovery / late-add acceptance
-> N3W_THREE_BOARD_FINAL_PRODUCT_E2E=PASS
```

Anything that does not materially help complete this route is presumed **NOT NOW** unless a concrete blocker proves otherwise.

## 3. Route-Deviation Indicators

Treat any of the following as a navigation warning:

1. A new subsystem, protocol, state machine, abstraction, or authority layer appears without a direct current-product requirement.
2. A test or acceptance helper becomes larger or more complex than the product behavior it is validating.
3. One failure creates repeated successor/preclaim/executor/manifest layers instead of repairing the smallest real blocker.
4. A temporary artifact name, tag, evidence format, or workflow detail starts being treated as product architecture.
5. More effort is spent proving that execution is perfectly reproducible than proving the actual product works on the target hardware.
6. Historical mechanisms that were removed by architecture simplification are reintroduced indirectly.
7. N3-L, control-node, advanced dashboard/history, broad ESP-IDF migration, or other deferred work begins before N3-W closure.
8. A new dependency/tool is introduced when an already available tool can complete the current task safely.
9. A debugging workaround is promoted into a permanent product mechanism without a demonstrated field requirement.
10. The development path can no longer be explained in a few steps from current state to the next product acceptance result.

## 4. Over-Engineering Test

Before adding a new mechanism, answer these questions:

```text
Does it solve a current user-visible product requirement?
Does it remove a demonstrated blocker?
Will it be needed after this acceptance session ends?
Is there a simpler existing mechanism that provides the same result?
Does it reduce total system complexity rather than move complexity elsewhere?
```

If the first two answers are both **NO**, stop and classify the work as deferred or unnecessary.

If the mechanism exists only to make a one-time acceptance procedure more elaborate, prefer a bounded operator command + evidence record instead of creating another reusable framework.

## 5. Correction Rule

When route drift or over-design is detected:

```text
1. STOP adding new layers.
2. Re-state the current product objective.
3. Identify the smallest real blocker.
4. Remove steps that do not change product acceptance.
5. Reuse existing source/tools/contracts where practical.
6. Resume from the shortest safe path to the next acceptance result.
```

A correction does not require discarding useful safety boundaries. High-risk live, credential, database, board, Flash, or production-equivalent mutations still require their appropriate authorization and evidence. The goal is to simplify **unnecessary process and architecture**, not weaken necessary safety controls.

## 6. Current Navigation Warning — 2026-08-26

### Situation

During N3-W / FC4 Spare T1 current-main convergence, the local ARM64 build blocker expanded into a long sequence of Docker / Colima / binfmt capability classifiers and proposed executor/materialization layers.

The Docker/ARM64 blocker was real and the diagnosis was useful. The active technical blockers were eventually reduced to:

- recover the existing Colima Docker backend;
- restore qemu-aarch64 binfmt registration;
- use the existing legacy Docker builder with explicit process-local Docker context.

After those blockers were resolved, continuing to create a large all-in-one R1-V2B executor + manifest for build, archive, T1 transfer, UID/GID probe, resolver probe, Compose validation, and deployment-gate orchestration would add more acceptance-framework complexity than current product value.

### Correction

Do **not** create a new generalized executor framework solely for this FC4 convergence.

Return to the minimal route:

```text
1. build exact-main linux/arm64 Manager candidate
2. inspect source / architecture / version / image identity
3. transfer/load candidate to Spare T1
4. run only the isolated probes needed by known FC4 failure modes
5. converge Spare T1 under a separate live authorization
6. enter FC4 three-board physical acceptance
```

Candidate tag naming is not product authority. Prefer image ID + exact source SHA/tree + architecture/labels as evidence.

The existence of both `Dockerfile` and `Dockerfile.pairing-lab` is not by itself an architecture decision. The current production-equivalent Manager path uses the normal Manager `Dockerfile`; pairing-lab remains a lab-specific artifact unless an explicit task requires it.

### Navigation status

```text
PRODUCT_DIRECTION=ON_ROUTE
FC4_OBJECTIVE=ON_ROUTE
TOOLING_RECOVERY=NECESSARY_AND_COMPLETE
ACCEPTANCE_PROCESS_COMPLEXITY=WARNING_OVER_DESIGN
CORRECTION=RETURN_TO_MINIMAL_PRODUCT_ACCEPTANCE_PATH
```

## 7. NOT NOW

Unless a new approved roadmap decision changes the order, do not allow the current N3-W FC4 effort to expand into:

- N3-L implementation;
- LoRa gateway-election redesign;
- new telemetry ACK/resend/PATH/lease mechanisms;
- new durable pairing-recovery architecture;
- control-node implementation;
- advanced Grafana / InfluxDB / Node-RED product requirements;
- broad ESP-IDF migration without a demonstrated blocker;
- a new generic executor/evidence framework created only for one acceptance session.

## 8. Relationship to KNOWN_FAILURES

Use the two documents differently:

```text
KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
= symptom -> root cause -> fix -> regression guard

Navigator_DEVELOPMENT_ROUTE_GUARD.md
= product direction -> scope drift -> over-design warning -> correction
```

A technical incident may belong in both when it reveals both a concrete failure and a development-process/architecture lesson.

## 9. Update Rule

Update this file when any of the following occurs:

- the project phase or product north star changes;
- development starts moving into a deferred phase prematurely;
- a new design adds significant complexity;
- an acceptance/debug workflow grows disproportionately;
- a previous simplification decision is being reversed;
- a correction materially shortens or clarifies the route.

Each update should be brief and use this form:

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

Do not turn this file into a chronological evidence archive. Keep only active navigation rules and high-value historical corrections that prevent recurrence.
