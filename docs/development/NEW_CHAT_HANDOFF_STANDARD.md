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

The project-wide execution model is:

```text
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
HIGH_LEVEL_MODEL_WRITES_EXECUTION_CODE=true
HIGH_LEVEL_MODEL_COMMITS_CODE_TO_GITHUB=true
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
```

Natural-language/DSL text may describe purpose, scope, invariants, PASS/FAIL/STOP conditions, and authorization boundaries. It is not executable authority for Codex to translate into ad-hoc shell/Python commands.

---

## 1. Authority precedence

When authorities appear to conflict, use this order unless a stage-specific contract defines a stricter authority:

```text
1. exact repository / exact runtime / exact live evidence
2. explicit current authorization boundary
3. this NEW_CHAT_HANDOFF_STANDARD.md
4. current formal handoff document
5. exact committed Execution Package bound by the handoff
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

The high-level model owns all project and execution code authoring. It must:

- maintain product route and architecture boundaries;
- bind exact source/runtime/artifact authority;
- design gate scope, authorization, rollback, and evidence contracts;
- decide whether a source change is justified;
- design and write project code when required;
- design and write every Execution Package artifact, including executors, helpers, manifests, evidence schemas, and tests;
- commit those artifacts to GitHub before Codex execution;
- define what raw evidence must exist before an operation can be adjudicated;
- classify results as `OBSERVED / DERIVED / HYPOTHESIS`;
- decide PASS / FAIL / STOP from exact source + raw evidence;
- keep product defects separate from host/tooling/executor defects;
- refuse to infer command/code details that are not present in evidence.

The following are frozen:

```text
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
HIGH_LEVEL_MODEL_WRITES_EXECUTION_CODE=true
HIGH_LEVEL_MODEL_COMMITS_CODE_TO_GITHUB=true
```

### 2.2 Codex responsibilities

Codex is an exact executor and result reporter, not a code author.

For an execution gate, Codex may:

- checkout/rebind the exact package commit;
- verify the package manifest, file presence, and required hashes;
- run host tests already committed in the package when explicitly instructed;
- execute the committed executor exactly as specified;
- preserve and return raw command/stdout/stderr/result evidence;
- return the predefined closure and evidence manifest.

Codex must not:

- author project source code;
- author or modify an executor, helper, manifest, evidence schema, or test;
- compile prose/DSL into substitute commands;
- improvise a missing command;
- patch an executor locally and continue;
- repair a failed executor in the execution environment;
- create a temporary replacement executor/helper to bypass a package defect;
- enlarge scope or weaken a gate;
- replay consumed/superseded authorization;
- cross into the next gate automatically;
- install or substitute tooling unless the exact committed package explicitly authorizes that operation.

Frozen role:

```text
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
```

If committed execution code is wrong, incomplete, missing, or incompatible:

```text
STOP
-> RETURN_TO_HIGH_LEVEL_MODEL
-> HIGH_LEVEL_MODEL_MODIFIES_GITHUB_CODE
-> NEW_COMMIT
-> REBIND_EXACT_COMMIT_AND_TEST
-> ONLY_THEN_CONSIDER_REEXECUTION
```

Codex must never repair execution code in place and continue under the same physical/one-shot execution attempt.

---

## 3. Execution Package model

### 3.1 When a package is required

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

### 3.2 Frozen repository storage layout

Execution Packages are formal project engineering code. They are organized by project, stage, and gate, not by executor identity.

```text
EXECUTION_PACKAGE_STORAGE_MODEL=STAGE_AND_GATE_SCOPED
EXECUTION_PACKAGE_ROOT=tools/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_TEST_ROOT=tests/execution_packages/<project>/<stage>/<gate_id>/
CODEX_ONLY_FOLDER=false
```

Canonical example:

```text
tools/execution_packages/
└── n3w/
    └── kf089/
        └── id13_readonly_recovery/
            ├── TASK.md
            ├── executor.py
            ├── manifest.json
            └── evidence_schema.json

tests/execution_packages/
└── n3w/
    └── kf089/
        └── id13_readonly_recovery/
            └── test_executor.py
```

Rules:

- do not create a generic `codex/`, `for_codex/`, `executor_misc/`, or equivalent Codex-only catch-all folder;
- keep gate-specific code inside the gate package while it has only one concrete consumer;
- do not build a generic execution framework in anticipation of reuse;
- extract a helper only after actual reuse exists across at least two concrete packages and the shared contract is clear;
- helper extraction is a normal high-level-model-authored GitHub code change with tests and review;
- historical packages remain readable/reproducible unless a separate cleanup decision supersedes them.

### 3.3 Canonical package contents

A typical package contains:

```text
TASK.md                    # human-readable goal/scope/PASS/STOP contract
executor.py                # exact commands, ordering, checkpoints and evidence writes
manifest.json              # source/tool/input/hash/authorization bindings
evidence_schema.json       # required raw evidence files/fields
```

Host tests live under the mirrored test root:

```text
tests/execution_packages/<project>/<stage>/<gate_id>/
```

Additional helpers are permitted only when the gate actually needs them. Package-local helper code remains inside that gate directory unless real reuse justifies later extraction.

### 3.4 Package identity and readiness

The package must be bound by durable identifiers, preferably:

```text
EXECUTION_PACKAGE_COMMIT=
EXECUTOR_GIT_BLOB=
EXECUTOR_SHA256=<when useful>
MANIFEST_GIT_BLOB=
EVIDENCE_SCHEMA_GIT_BLOB=
TEST_COMMIT_OR_RUN=
```

Before a physical/mutating/evidence-critical authorization is requested:

```text
EXECUTION_PACKAGE_MATERIALIZED=true
EXECUTION_PACKAGE_GITHUB_SHARED=true
EXECUTION_PACKAGE_TESTS_PASS=true
EXECUTION_PACKAGE_EXACT_BINDING=PASS
RAW_EVIDENCE_CONTRACT_PASS=true
```

If any item is false, execution is not ready. The high-level model must repair the package in GitHub first.

### 3.5 DSL role

DSL/natural-language contracts remain useful for:

- goal;
- allowed/forbidden scope;
- frozen inputs;
- authorization boundaries;
- PASS/FAIL/STOP rules;
- expected closure fields.

They are not a command compiler contract:

```text
DSL_EXECUTION_MODEL=false
DSL_TO_COMMAND_COMPILATION=false
AD_HOC_COMMAND_SYNTHESIS_FOR_EXECUTION_GATE=false
```

If an execution detail matters, put it in the exact committed executor/manifest/tests.

---

## 4. Raw-evidence-first rule

A closure summary is not a substitute for raw evidence.

For every external command or device operation whose details may matter later, the executor must persist the command description before starting the operation, then persist the result afterward.

Recommended per-operation layout:

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

Evidence write order:

```text
persist command.json
-> execute
-> persist stdout/stderr/result
-> validate
-> persist validation/adjudication
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

- package authoring, repair, and host tests happen before later physical/live authorization whenever possible;
- package authoring is performed by the high-level model, not Codex;
- claim a finite physical authorization immediately before the first authorized target/device action;
- after claim, a one-shot/finite authorization is consumed even if execution later fails, unless the authorization explicitly says otherwise;
- consumed/superseded authorization is never silently reused;
- if executor/package material changes after authorization, treat that as a new authority binding and obtain a new authorization when required;
- `READY_FOR_*_AUTHORIZATION=true` is readiness only, not authorization.

---

## 6. Failure handling

Executor/tooling failure and product failure must remain separate.

If a package fails before the target/device operation begins:

```text
PRODUCT_FAILURE_PROVEN=false
EXECUTOR_OR_HOST_FAILURE=true
```

Do not infer a root cause from a compact STOP summary if actual argv/source/traceback evidence is absent.

After any STOP, classify what is known as `OBSERVED`, `DERIVED`, and `HYPOTHESIS` before repair.

For package defects:

```text
AUTO_REPAIR_BY_CODEX=false
LOCAL_EXECUTOR_PATCH_BY_CODEX=false
AD_HOC_SUBSTITUTE_COMMAND=false
```

Repair path:

```text
STOP
-> high-level model edits package source
-> commit to GitHub
-> bind new exact commit/blob/hash
-> run host tests
-> re-evaluate authorization state
```

For physical/one-shot gates, default:

```text
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
source authority -> exact commit/tree
executor authority -> exact commit/blob/hash
OCI image -> digest/image ID
live runtime -> docker/process/live evidence
board identity -> fresh silicon/ROM identity, not USB path
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

If a required package is not READY, physical/live execution is forbidden until the high-level model authors/repairs and commits the package and its host tests pass.

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

Source, tests, and execution packages with ongoing engineering value are not durably complete until pushed to GitHub and commit/hash-bound.

Raw private evidence may remain private if GitHub contains a safe locator/hash/status sufficient for future recovery.

---

## 13. Handoff generation discipline

When producing a handoff:

1. Start from `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`.
2. Read this standard, `TEAM_COLLABORATION_WORKSPACE_STANDARD.md`, and `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`.
3. Carry forward only current authorities and relevant closed-route guards.
4. Preserve exact consumed/replay states.
5. Define one next gate.
6. Bind the exact committed Execution Package, or mark execution blocked until the high-level model materializes it.
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
CODE_AUTHORING_MODEL_HIGH_LEVEL_ONLY=PASS
HIGH_LEVEL_MODEL_EXECUTION_CODE_AUTHORING_EXPLICIT=PASS
CODEX_CODE_AUTHORING_DISABLED=PASS
CODEX_EXACT_EXECUTOR_AND_RESULT_REPORTER_ROLE=PASS
EXECUTION_PACKAGE_MODEL_EXPLICIT=PASS
EXECUTION_PACKAGE_STORAGE_MODEL_EXPLICIT=PASS
CODEX_ONLY_FOLDER_DISABLED=PASS
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
EXECUTION_PACKAGE_READY_OR_EXECUTION_BLOCKED=PASS
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
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODE_AUTHORING_MODEL=HIGH_LEVEL_MODEL_ONLY
HIGH_LEVEL_MODEL_WRITES_PROJECT_CODE=true
HIGH_LEVEL_MODEL_WRITES_EXECUTION_CODE=true
HIGH_LEVEL_MODEL_COMMITS_CODE_TO_GITHUB=true
CODEX_CODE_AUTHORING=false
CODEX_ROLE=EXACT_EXECUTOR_AND_RESULT_REPORTER
REPOSITORY_VERSIONED_EXECUTOR=true
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
DSL_ROLE=GOAL_AND_BOUNDARY_ONLY
DSL_TO_COMMAND_COMPILATION=false
EXECUTION_PACKAGE_STORAGE_MODEL=STAGE_AND_GATE_SCOPED
EXECUTION_PACKAGE_ROOT=tools/execution_packages/<project>/<stage>/<gate_id>/
EXECUTION_PACKAGE_TEST_ROOT=tests/execution_packages/<project>/<stage>/<gate_id>/
CODEX_ONLY_FOLDER=false
PREMATURE_GENERIC_EXECUTION_FRAMEWORK=false
NEXT_ONE_GATE_ONLY=true
COMPLIANCE_AUDIT_REQUIRED=true
```
