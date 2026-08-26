# NEW_CHAT_HANDOFF_STANDARD

> Status: authoritative project process standard  
> Version: `HANDOFF_STANDARD_VERSION=1.0`  
> Scope: all future formal new-chat handoff documents for this repository

## 0. Purpose

A formal handoff must preserve enough state for a fresh high-level-model/Codex session to continue the project without reconstructing history, re-opening closed routes, replaying consumed authorization, or inventing a new execution framework.

The handoff has two independent completeness requirements:

```text
HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS
```

A document that preserves facts but does not explain how the next session is allowed to execute is incomplete.

The governing principle remains:

```text
test product, not the test framework
```

Do not create a new executor/preclaim/manifest/framework merely because a new chat started.

---

## 1. Authority precedence

When authorities appear to conflict, use this order unless a stage-specific contract explicitly defines a stricter authority:

```text
1. exact repository / exact runtime / exact live evidence
2. this NEW_CHAT_HANDOFF_STANDARD.md
3. current formal handoff document
4. KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
5. current-conversation inference
```

Historical handoffs remain evidence, not automatically current authority.

A handoff must clearly distinguish:

```text
PROVEN_FACT
INFERENCE
PROPOSED_NEXT_ACTION
AUTHORIZED_ACTION
```

Never promote an inference or proposed authorization into a proven/current fact.

---

## 2. Execution model

Every formal handoff must explicitly restate:

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
```

### 2.1 High-level model responsibilities

The high-level model owns:

- architecture and product route;
- exact-main/image/successor authority;
- gate design and scope;
- authorization design and replay classification;
- rollback contract;
- PASS / FAIL / STOP classification from Codex closure;
- distinction between product, runtime/config, infrastructure, CI, and physical-harness defects;
- deciding when source changes are actually justified;
- preventing acceptance/tooling complexity from becoming a parallel product architecture.

The high-level model must not default to writing a large Bash/Python executor when a bounded DSL execution contract is sufficient.

### 2.2 Codex responsibilities

Codex is the low-order executor. It owns mechanical execution of the exact contract, including:

- Git / Docker / SSH / Compose / shell / test commands;
- read-only preflight and authority recovery;
- mutation only inside an explicitly granted authorization;
- mechanical parsing and evidence capture;
- structured closure output;
- fail-closed STOP at the first substantive mismatch unless the contract explicitly permits continuation.

Codex must not:

- enlarge scope;
- weaken a gate;
- invent a repair;
- replay consumed/superseded authorization;
- cross into the next gate automatically;
- change frozen input authority;
- install tooling unless specifically authorized;
- access boards/USB/serial/Flash/NVS/RF without the relevant physical authorization.

---

## 3. DSL execution semantics

Every new Codex execution session must be given this semantic rule, either directly in the handoff or by explicit reference to this standard:

```text
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true
```

An exact DSL execution protocol is itself executable authority for the operations explicitly allowed by that protocol.

Codex must mechanically translate each DSL operation into the minimum necessary commands using tools already available in the execution environment.

Examples:

```text
"docker inspect"
→ construct and run the minimum docker inspect command.

"derive active DynSec path from running Mosquitto config"
→ perform the minimum read-only shell/Python parsing required to prove that path.

"resolve container target -> host source"
→ inspect current Compose/Docker metadata and derive the exact mapping.

"create fresh rollback snapshot"
→ construct only the mkdir/copy/hash/metadata operations explicitly required by the snapshot contract.
```

This mechanical translation is classified as:

```text
DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false
```

Codex may choose between equivalent already-installed read-only tools, shell primitives, and bounded Python supplied from stdin when parsing is necessary.

Absence of a prewritten Bash/Python script is **not** a valid blocker when the DSL contains sufficient frozen inputs, allowed operations, gates, and terminal outputs.

`MISSING_EXECUTOR` is valid only when the protocol explicitly requires an exact supplied implementation, byte sequence, script, or artifact and that exact material is absent.

### 3.1 When an exact executor is appropriate

A prewritten executor should be supplied only when at least one of these is true:

- byte-level/protocol semantics require an exact fixed implementation;
- atomicity depends on a specifically audited sequence that must not be recompiled by the executor;
- a previously proven environment/tooling defect requires a bounded successor executor repair;
- the contract explicitly names an exact executor artifact as authority.

Do not create a general executor merely because a DSL could also be expressed as Python.

---

## 4. Authorization model

Formal handoffs must contain an authorization ledger for every authorization still relevant to the current route.

Each entry must state, as applicable:

```text
AUTHORIZATION=
CLAIMED=true|false
CONSUMED=true|false
RESULT=
REPLAY_PERMITTED=true|false
SUPERSEDED_BY=
```

Rules:

- read-only reasoning/preflight does not consume a live/physical authorization unless an explicit contract says otherwise;
- mutation requires explicit user approval of the exact authorization scope;
- after claim, one-shot/finite authorization is consumed even if execution fails;
- consumed or superseded authorization must never be silently reused;
- a successor that changes material runtime authority must receive a new authorization binding where required;
- `READY_FOR_*_AUTHORIZATION=true` means only that design/approval may proceed; it is not itself authorization.

---

## 5. Required handoff section order

Every formal handoff must use the following top-level structure. Sections may contain stage-specific subsections, but must not be silently omitted.

```text
0.  会话切换结论
1.  执行模式
2.  Product North Star
3.  Frozen Authorities
4.  Current Live Baseline
5.  Proven Current Facts
6.  Current Root Cause / Blockers
7.  Closed / Forbidden Routes
8.  Authorization Ledger
9.  Rollback Authority
10. Next ONE Gate
11. Hard Allowed / Forbidden Scope
12. Codex DSL Execution Contract
13. Expected Closure
14. After PASS / FAIL
15. KNOWN_FAILURES Updates
16. New Chat Start Prompt
17. Final Frozen State
18. Handoff Compliance Audit
```

If a section is genuinely not applicable, keep the section and write `NOT_APPLICABLE` plus the reason.

---

## 6. Frozen-authority rules

`Frozen Authorities` must record only values required to continue correctly, such as:

- repository and exact-main commit/tree;
- exact candidate image/artifact ID;
- successor path/hash where relevant;
- target host/platform;
- exact service/container authority;
- exact state/credential path authority where relevant.

Do not flood the handoff with every historical SHA.

For every frozen value, prefer the authority closest to the thing being proven. Examples:

```text
OCI image identity → image ID / digest
current runtime → docker inspect/live process evidence
active DynSec path → running Broker config + mount binding
source authority → exact repository commit/tree
```

---

## 7. Current live baseline

The handoff must explicitly say what is live *now*, not only what was live before the previous action.

Record only safe metadata needed by the next gate, including relevant:

- running/stopped service state;
- exact image/container binding;
- restart state/count where important;
- active listener/owner state;
- rollback-restored state;
- board/USB/serial/Flash/NVS status.

If the state was proven only historically and requires rebind in the new chat, say so.

---

## 8. Proven facts, blockers, and closed routes

Separate three concepts:

### Proven Current Facts

Facts directly established by exact evidence.

### Current Root Cause / Blockers

Only blockers still on the current product route.

### Closed / Forbidden Routes

Previously explored or disproven branches that must not re-enter without new direct counter-evidence.

Use concise classifications such as:

```text
SOURCE_DEFECT_PROVEN=false
TLS_IDENTITY_BLOCKER=CLOSED
STATE_MIGRATION_REQUIRED=false
```

A handoff must not re-open a closed route merely to be comprehensive.

---

## 9. Rollback authority

For any next gate that could mutate live state, the handoff must state:

- what exact prechange state is the rollback authority;
- what must be snapshotted immediately before mutation;
- rollback order;
- maximum allowed restart/reload scope;
- what constitutes rollback success;
- what constitutes `ROLLBACK_INCOMPLETE` / manual recovery;
- whether a second attempt is prohibited.

Historical rollback evidence is not automatically a valid fresh rollback snapshot for a later live mutation.

---

## 10. Next ONE Gate rule

Every handoff must expose exactly one next executable logical gate.

```text
NEXT_ONE_GATE=<name>
```

It may name the stage after that gate, but must not package several speculative successors into the next execution request.

The next gate must include:

- purpose;
- frozen inputs;
- allowed operations;
- forbidden operations;
- PASS conditions;
- FAIL conditions;
- STOP boundary;
- expected closure.

A failure in the next gate returns to the high-level model. Codex does not automatically design or execute the successor.

---

## 11. Hard scope rules

Every handoff must explicitly state defaults:

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

Then list stage-specific `ALLOWED` and `FORBIDDEN` operations.

Do not rely on vague phrases such as "be careful" or "read-only where possible".

When a bounded evidence/snapshot write is allowed while live runtime remains read-only, distinguish:

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
```

Do not label such a transaction globally read-only without explaining the exception.

---

## 12. Expected closure rules

Every next gate must define a stable structured closure before execution starts.

The closure must be sufficient for the high-level model to decide the next step without asking Codex to reinterpret raw logs.

At minimum include:

- execution/gate identity;
- authorization claimed/consumed state;
- exact binding results;
- mutation flags;
- rollback/snapshot result when applicable;
- terminal PASS/FAIL classification;
- `NEXT_ROUTE` or equivalent;
- explicit STOP.

Never use a closure field to claim a fact the execution did not prove.

---

## 13. Handoff-generation discipline

When producing a new handoff:

1. Start from `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`.
2. Read this standard and `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`.
3. Carry forward only current authorities and relevant closed-route guards.
4. Preserve exact consumed/replay states.
5. Define one next gate.
6. Include a self-contained new-chat start prompt.
7. Run the compliance audit below before calling the document formal.

Do not rewrite the template structure simply because a particular stage feels simpler.

---

## 14. Handoff compliance audit

Every formal handoff must end with this block, with all applicable fields resolved to `PASS` before `HANDOFF_READY_FOR_NEW_CHAT=true`:

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.0

EXECUTION_MODEL_EXPLICIT=PASS
HIGH_LEVEL_CODEX_ROLE_BOUNDARY=PASS
DSL_EXECUTION_SEMANTICS_EXPLICIT=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS

PROVEN_FACTS_SEPARATED_FROM_INFERENCE=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS

ALLOWED_FORBIDDEN_SCOPE_EXPLICIT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS

HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```

If any applicable item cannot be `PASS`, the document is a draft/incomplete handoff and must not be presented as the formal new-chat authority.

---

## 15. CI/linter policy

Do **not** add a handoff CI framework merely because this standard exists.

For now the process guard is:

```text
STANDARD + TEMPLATE + COMPLIANCE_AUDIT
```

Only add a small static linter later if repeated real handoffs prove that manual/template enforcement is insufficient.

---

## 16. Maintenance

Changes to this standard must:

- be made in Git history;
- explain the concrete regression or process need being addressed;
- update the template if the required structure changes;
- update `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` when the change originates from an actual failure;
- avoid stage-specific runtime values in this file.

Current standard authority:

```text
HANDOFF_STANDARD_VERSION=1.0
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
COMPLIANCE_AUDIT_REQUIRED=true
```
