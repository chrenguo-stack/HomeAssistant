# NEW_CHAT_HANDOFF_STANDARD

> Status: authoritative project process standard candidate  
> Version: `HANDOFF_STANDARD_VERSION=1.1`  
> Scope: all future formal new-chat handoff documents for this repository

## 0. Purpose

A formal handoff must preserve enough state for a fresh high-level-model/Codex session to continue without reconstructing history, reopening closed routes, replaying consumed authorization, or inventing execution details that were never observed.

The governing principle is:

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
TEAM_SHARED_WORKSPACE=GITHUB
CHAT_AND_EXECUTOR_SESSIONS=EPHEMERAL_WORKSPACES
```

A formal handoff has two independent completeness requirements:

```text
HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS
```

The key execution change in version 1.1 is:

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODEX_ROLE=EXACT_EXECUTOR
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
```

Natural-language/DSL text may describe purpose, scope, invariants, PASS/FAIL conditions, and authorization boundaries. It is no longer executable authority for Codex to translate into ad-hoc shell/Python commands for a physical, mutating, one-shot, or evidence-critical gate.

---

## 1. Authority precedence

When authorities appear to conflict, use this order unless a stage-specific contract defines a stricter authority:

```text
1. exact repository / exact runtime / exact live evidence
2. explicit current authorization boundary
3. this NEW_CHAT_HANDOFF_STANDARD.md
4. current formal handoff document
5. versioned Execution Package bound by the handoff
6. KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
7. current-conversation inference
```

Historical handoffs remain evidence, not automatically current authority.

Every conclusion must distinguish:

```text
OBSERVED    = directly present in raw evidence, repository source, or live readback
DERIVED     = strictly derivable from OBSERVED facts without adding assumptions
HYPOTHESIS  = plausible but not proven
PROPOSED    = not authorized
AUTHORIZED  = explicitly authorized action within an exact scope
```

Never promote `HYPOTHESIS` or `PROPOSED` into a proven/current fact.

---

## 2. Team and execution roles

### 2.1 High-level model responsibilities

The high-level model owns:

- product route and architecture boundary;
- exact source/runtime/artifact authority;
- gate design, scope, authorization and rollback;
- deciding whether a source change is justified;
- designing or reviewing the Execution Package;
- defining what raw evidence must exist before an operation can be adjudicated;
- PASS / FAIL / STOP classification from source + raw evidence;
- keeping product defects separate from host/tooling/executor defects;
- refusing to infer command/code details that are not present in evidence.

The high-level model may author the exact executor directly, or may delegate executor implementation to Codex during a host-only development gate. What matters is that the executor is reviewed, tested, committed, and hash/commit-bound before it becomes execution authority.

### 2.2 Codex responsibilities

For an execution gate, Codex is the exact executor. It must:

- checkout/rebind the exact package commit;
- verify the package manifest and required files;
- execute the versioned executor exactly as specified;
- preserve raw command/stdout/stderr/result evidence before summarizing;
- stop at the first substantive mismatch unless the package explicitly permits continuation;
- return the predefined closure and evidence manifest.

Codex must not, during an exact execution gate:

- compile prose/DSL into substitute commands;
- silently modify the executor;
- improvise a missing command;
- repair the executor and continue in the same one-shot/physical authorization;
- enlarge scope;
- weaken a gate;
- replay consumed/superseded authorization;
- cross into the next gate automatically;
- install or substitute tooling unless the package explicitly authorizes it.

A separate host-only development gate may explicitly authorize Codex to implement or repair the package. That development gate ends after tests + GitHub persistence; it does not automatically consume the later physical/runtime authorization.

---

## 3. Execution Package model

### 3.1 Default rule

For formal handoff continuation, the preferred execution authority is a versioned repository package.

An Execution Package is REQUIRED when any of these is true:

- physical board / USB / serial / RF access;
- live runtime mutation;
- Flash / NVS / provisioning / credential mutation;
- one-shot or finite authorization;
- exact command ordering matters;
- a failed attempt could alter evidence or target state;
- raw stdout/stderr/argv/traceback are needed for later adjudication;
- the gate contains multiple dependent operations where ad-hoc interpretation would create ambiguity.

For trivial host-only, read-only inspection with no finite authorization and no state risk, a package may be minimal or not required. The handoff must state why.

### 3.2 Canonical package contents

Use normal readable repository paths. A typical package contains:

```text
TASK.md                    # human-readable goal/scope/PASS/STOP contract
executor.py                # exact commands, ordering, checkpoints and evidence writes
evidence_schema.json       # required raw evidence files/fields
manifest.json              # source/tool/input/hash/authorization bindings
tests/...                  # host tests for executor and failure behavior
```

The exact repository paths are stage-specific and must be recorded in the handoff.

The package must be bound by durable identifiers, preferably:

```text
EXECUTION_PACKAGE_COMMIT=
EXECUTOR_GIT_BLOB=
EXECUTOR_SHA256=<when useful>
MANIFEST_GIT_BLOB=
EVIDENCE_SCHEMA_GIT_BLOB=
TEST_COMMIT_OR_RUN=
```

### 3.3 Package readiness

Before a physical/mutating/evidence-critical authorization is requested:

```text
EXECUTION_PACKAGE_MATERIALIZED=true
EXECUTION_PACKAGE_GITHUB_SHARED=true
EXECUTION_PACKAGE_TESTS_PASS=true
EXECUTION_PACKAGE_EXACT_BINDING=PASS
```

If any of those is false, the next gate is host-only package materialization/repair, not physical execution.

### 3.4 DSL role after version 1.1

DSL/natural-language contracts remain useful for:

- goal;
- allowed/forbidden scope;
- frozen inputs;
- authorization boundaries;
- PASS/FAIL/STOP rules;
- expected closure fields.

They are NOT a command compiler contract:

```text
DSL_EXECUTION_MODEL=false
DSL_TO_COMMAND_COMPILATION=false
AD_HOC_COMMAND_SYNTHESIS_FOR_EXECUTION_GATE=false
```

If an execution detail matters, put it in the versioned executor or package manifest and test it there.

---

## 4. Raw-evidence-first rule

A closure summary is not a substitute for raw evidence.

For every external command or device operation whose details may matter later, the executor must persist the command description before starting the operation, then persist the result afterward.

A recommended per-operation evidence layout is:

```text
op_NN/
  command.json
  stdout.txt|stdout.bin
  stderr.txt|stderr.bin
  result.json
```

`command.json` should contain, as applicable:

- argv as actually executed;
- exact executable/interpreter path;
- relevant script/tool path and hash;
- UTC start timestamp;
- target logical identity/locator without publishing secrets;
- package commit/executor hash;
- authorization ID and claim state.

`result.json` should contain, as applicable:

- return code / errno;
- UTC end timestamp;
- timeout/interruption state;
- whether the command actually started;
- whether target access occurred;
- first failed operation;
- evidence file hashes.

The evidence write order must make command evidence survive even if process launch itself fails:

```text
persist command.json
→ execute
→ persist stdout/stderr/result
→ validate
→ persist validation/adjudication
```

Raw private evidence may stay outside Git, but GitHub must contain the public-safe manifest, hashes, status, and recovery locator needed for continuity.

Never commit credentials, private keys, setup secrets, or private board identities merely to satisfy evidence persistence.

---

## 5. Authorization model

Formal handoffs must contain an authorization ledger for every authorization still relevant to the current route.

Each entry must state, as applicable:

```text
AUTHORIZATION=
BOUND_EXECUTION_PACKAGE_COMMIT=
BOUND_EXECUTOR_BLOB=
CLAIMED=true|false
CONSUMED=true|false
RESULT=
REPLAY_PERMITTED=true|false
SUPERSEDED_BY=
```

Rules:

- host-only package development does not consume the later physical/live authorization;
- complete host-only prechecks before claiming a one-shot physical authorization whenever possible;
- claim a finite physical authorization immediately before the first authorized target/device action, not during package construction;
- after claim, a one-shot/finite authorization is consumed even if execution later fails, unless the authorization explicitly says otherwise;
- consumed/superseded authorization is never silently reused;
- if executor/package material changes after authorization, treat that as a new authority binding and obtain new authorization when required;
- `READY_FOR_*_AUTHORIZATION=true` is readiness only, not authorization.

---

## 6. Failure handling

Executor/tooling failure and product failure must remain separate.

If an execution package fails before the target/device operation begins:

```text
PRODUCT_FAILURE_PROVEN=false
EXECUTOR_OR_HOST_FAILURE=true
```

Do not infer the root cause from a one-line STOP summary if actual argv/source/traceback evidence is absent.

After any STOP, classify what is known as `OBSERVED`, `DERIVED`, and `HYPOTHESIS` before designing repair.

Repair is a separate gate unless the current package explicitly and safely authorizes a bounded continuation. For physical/one-shot gates, the default is:

```text
AUTO_REPAIR=false
AUTO_RETRY=false
```

---

## 7. Required handoff section order

Every formal handoff must use this top-level structure:

```text
0.  会话切换结论
1.  执行模式与首要原则
2.  Product North Star
3.  Frozen Authorities
4.  Current Live Baseline
5.  Proven Current Facts / Evidence Classes
6.  Current Root Cause / Blockers
7.  Closed / Forbidden Routes
8.  Authorization Ledger
9.  Rollback Authority
10. Next ONE Gate
11. Hard Allowed / Forbidden Scope
12. Versioned Execution Package Contract
13. Expected Closure + Raw Evidence Contract
14. After PASS / FAIL
15. KNOWN_FAILURES Updates
16. New Chat Start Prompt
17. Final Frozen State
18. Handoff Compliance Audit
```

If a section is not applicable, retain it and write `NOT_APPLICABLE:<reason>`.

---

## 8. Frozen authorities and live baseline

Record only authorities needed for continuation. Prefer the authority closest to the thing being proven:

```text
source authority → exact commit/tree
executor authority → exact commit/blob/hash
OCI image → digest/image ID
live runtime → docker/process/live evidence
board identity → fresh silicon/ROM identity, not USB path
```

The handoff must explicitly say what is live now and what requires a fresh read-only rebind in the new session.

Historical evidence is not automatically a current live fact.

---

## 9. Rollback authority

For a gate that can mutate live state, state:

- exact prechange rollback authority;
- fresh snapshot requirement;
- rollback order;
- maximum restart/reload scope;
- rollback success condition;
- `ROLLBACK_INCOMPLETE` condition;
- whether a second attempt is prohibited.

The Execution Package must implement only the rollback behavior actually authorized by the gate. It must not invent rollback from prose.

---

## 10. Next ONE Gate

Every handoff exposes exactly one next executable logical gate:

```text
NEXT_ONE_GATE=<name>
```

The gate must include purpose, frozen inputs, allowed/forbidden operations, PASS/FAIL/STOP conditions, package readiness/binding, expected raw evidence, and expected closure.

If the required package is not yet materialized/tested, `NEXT_ONE_GATE` must be the host-only package materialization/repair gate.

Codex never auto-enters the next gate.

---

## 11. Expected closure and evidence manifest

Every execution gate defines a stable closure before execution starts.

The closure is a compact adjudication surface, not a replacement for raw evidence. It must include at least:

```text
EXECUTION_ID=
EXECUTION_PACKAGE_COMMIT=
EXECUTOR_BLOB=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=
RAW_EVIDENCE_COMPLETE=
EVIDENCE_MANIFEST_PATH_OR_HASH=
FIRST_FAILED_OPERATION=
TARGET_ACCESS_OCCURRED=
<GATE_RESULT>=
NEXT_ROUTE=
STOP_REASON=
```

Never use closure fields to claim command/code details the executor did not persist.

---

## 12. GitHub team-workspace requirement

This standard inherits `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`.

Formal handoffs must include:

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=<n>
TEAM_SHARE_COMPLETENESS=PASS|FAIL
```

Source/tests/execution packages with ongoing engineering value are not durably complete until pushed to GitHub and commit/hash-bound.

Raw private evidence may remain private if GitHub contains a safe locator/hash/status sufficient for future recovery.

---

## 13. Handoff generation discipline

When producing a handoff:

1. Start from `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`.
2. Read this standard, `TEAM_COLLABORATION_WORKSPACE_STANDARD.md`, and `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`.
3. Carry forward only current authorities and relevant closed-route guards.
4. Preserve exact consumed/replay states.
5. Define one next gate.
6. Bind the exact Execution Package, or make package materialization the next gate.
7. Include raw-evidence requirements before execution.
8. Include a self-contained new-chat start prompt.
9. Run the compliance audit before calling the handoff formal.

---

## 14. Handoff compliance audit

Every formal handoff ends with this block, with all applicable fields `PASS` before `HANDOFF_READY_FOR_NEW_CHAT=true`:

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.1

PRIMARY_EXECUTION_PRINCIPLE_EXPLICIT=PASS
EXECUTION_MODEL_EXPLICIT=PASS
EXECUTION_PACKAGE_MODEL_EXPLICIT=PASS
CODEX_EXACT_EXECUTOR_ROLE_EXPLICIT=PASS
DSL_NOT_COMMAND_AUTHORITY=PASS
RAW_EVIDENCE_FIRST_EXPLICIT=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS

OBSERVED_DERIVED_HYPOTHESIS_SEPARATED=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
AUTHORIZATION_PACKAGE_BINDING_EXPLICIT=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS
EXECUTION_PACKAGE_READY_OR_MATERIALIZATION_GATE=PASS

ALLOWED_FORBIDDEN_SCOPE_EXPLICIT=PASS
RAW_EVIDENCE_CONTRACT_PRESENT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

TEAM_SHARED_WORKSPACE_EXPLICIT=PASS
TEAM_SHARE_COMPLETENESS_CLASSIFIED=PASS
KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS
HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```

If any applicable item cannot be `PASS`, the handoff remains draft/incomplete.

---

## 15. Maintenance

Changes to this standard must:

- be committed through normal repository review;
- explain the concrete process regression or need being addressed;
- update the handoff template when required structure changes;
- avoid stage-specific runtime values;
- preserve explicit live/physical authorization boundaries.

Current standard candidate:

```text
HANDOFF_STANDARD_VERSION=1.1
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODEX_ROLE=EXACT_EXECUTOR
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
NEXT_ONE_GATE_ONLY=true
COMPLIANCE_AUDIT_REQUIRED=true
```
