# N3-W / FC4 Development Handoff

## 1. Document Identity / Schema

```text
HANDOFF_SCHEMA_VERSION=1.0
HANDOFF_TEMPLATE_ID=N3W_FC4_DEVELOPMENT_HANDOFF_TEMPLATE
HANDOFF_TEMPLATE_VERSION=1.0
HANDOFF_TEMPLATE_BLOB_SHA=<TEMPLATE_GIT_BLOB_SHA>

HANDOFF_DOCUMENT_VERSION=<VERSION>
HANDOFF_DATE=<YYYY-MM-DD>

HANDOFF_LINT_REQUIRED=true
HANDOFF_LINT_RESULT=<PASS|PENDING>
PUBLIC_REPOSITORY_SAFETY_REQUIRED=true
PUBLIC_REPOSITORY_SAFETY_RESULT=<PASS|PENDING>
```

## 2. North Star / Route

```text
NORTH_STAR=<VALUE>
CURRENT_ROUTE_NODE=<VALUE>
ACTIVE_DETOUR=<VALUE|NONE>
RETURN_TO_ROUTE=<VALUE|NONE>
NEW_BRANCH_ALLOWED=<true|false>
```

## 3. Execution Model

```text
EXECUTION_MODEL=HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION
HIGH_LEVEL_REASONING_ROLE=CHATGPT
BOUNDED_EXECUTION_ROLE=CODEX

ONE_GATE_ONE_ROUTE_DECISION=true
UNKNOWN_IS_NOT_FAIL=true
UNOBSERVED_IS_NOT_FALSE=true
DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING=true

CODEX_MUST_NOT_INFER_AUTHORIZATION=true
CODEX_MUST_NOT_EXPAND_SCOPE=true
CODEX_MUST_STOP_ON_PRECLAIM_FAILURE=true
CHATGPT_MUST_REVIEW_EACH_GATE_RESULT_BEFORE_NEXT_GATE=true
```

ChatGPT owns reasoning, route control, gate/authorization design, result classification, failure-fuse enforcement, and archive/handoff control. Codex executes exact bounded commands/scripts and returns raw or machine-readable results.

## 4. Repository / Branch Authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
HANDOFF_BRANCH=<BRANCH>
HANDOFF_PREDECESSOR_HEAD=<40-HEX-SHA|NOT_APPLICABLE>
HANDOFF_BRANCH_HEAD_POLICY=READ_CURRENT_BRANCH_HEAD_ON_RECOVERY
```

Do not encode a self-referential “this file's own commit SHA” as immutable authority. The next session must read the live branch HEAD.

## 5. Frozen Product Source

```text
FROZEN_PRODUCT_SOURCE_HEAD=<40-HEX-SHA|NOT_APPLICABLE>
FROZEN_PRODUCT_SOURCE_TREE=<40-HEX-SHA|NOT_APPLICABLE>
```

## 6. Worktree / Workspace Guard

```text
PRIVATE_WORKTREE_PATH_EXPOSED=false
DIRTY_WORKTREE_MUTATION_ALLOWED=false
```

Public handoffs must use placeholders such as `<PRIVATE_EXACT_WORKTREE_PATH>` rather than developer home paths.

## 7. Runtime Authority

```text
RUNTIME_AUTHORITY_STATE=<PASS|UNKNOWN|NOT_APPLICABLE>
SECTION_STATE=<APPLICABLE|NOT_APPLICABLE>
```

Record exact runtime authority facts or `UNKNOWN`. Do not serialize unobserved facts as `false`.

## 8. Product State / Proven Facts

```text
PRODUCT_STATE=<STATE>
SECTION_STATE=<APPLICABLE|NOT_APPLICABLE>
```

List only proven product facts. Distinguish durable state, runtime state, source facts, and inferred hypotheses.

## 9. Active Blocker / Root Cause

```text
PRODUCT_BLOCKER_PROVEN=<true|false>
ROOT_CAUSE=<VALUE|UNKNOWN|NONE>
SECTION_STATE=<APPLICABLE|NOT_APPLICABLE>
```

A product blocker requires independent product evidence. Executor/oracle/harness failure alone is insufficient.

## 10. Failure Classification / Fuse

```text
FAIL_CLASS=<CLASS|NONE>
CURRENT_EXECUTOR_FAILURE_STREAK=<INTEGER>
ROUTE_AUDIT_REQUIRED=<true|false>
```

Allowed primary classes:

```text
PRODUCT_BLOCKER
INFRASTRUCTURE_BLOCKER
SECURITY_AUTHORITY_BLOCKER
PHYSICAL_HARNESS_DEFECT
EXECUTOR_OR_ORACLE_DEFECT
EVIDENCE_GAP
TRANSIENT_INFRASTRUCTURE_FAILURE
NONE
```

## 11. Authorization Ledger

```text
CONSUMED_AUTHORIZATION_COUNT=<INTEGER>
REPLAY_OF_CONSUMED_AUTHORIZATION_ALLOWED=false
```

Repeat one block per authorization:

```text
AUTHORIZATION_LEDGER_BEGIN
AUTHORIZATION_ID=<ID|NONE>
AUTHORIZATION_STATE=<NOT_APPLICABLE|CANDIDATE|GRANTED|CLAIMED|CONSUMED>
REPLAY_PERMITTED=<true|false|NOT_APPLICABLE>
AUTHORIZATION_SCOPE=<SCOPE|NOT_APPLICABLE>
AUTHORIZATION_LEDGER_END
```

Consumed authorizations must always use `REPLAY_PERMITTED=false`.

## 12. Mutation State

```text
SOURCE_MUTATION_EXECUTED=<true|false>
PHYSICAL_MUTATION_EXECUTED=<true|false>
RUNTIME_MUTATION_EXECUTED=<true|false>
```

State what mutated in the completed boundary and what did not.

## 13. Known Failures / Regression Guards

```text
KNOWN_FAILURES_UPDATED=<true|false|NOT_APPLICABLE>
KNOWN_FAILURES_STATE=<STATE>
```

List relevant KF entries and their current status. Never guess a KF number.

## 14. Forbidden Actions / Non-goals

```text
FORBIDDEN_ACTIONS_STATE=DECLARED
```

Explicitly list actions the next session must not take without new authority.

## 15. Next Route Action

```text
NEXT_ROUTE_ACTION=<EXACT_NEXT_ACTION>
```

One route action only.

## 16. Physical State

```text
PHYSICAL_STATE=<STATE|NOT_APPLICABLE>
SECTION_STATE=<APPLICABLE|NOT_APPLICABLE>
```

When physical work is relevant, include Board power/USB/serial/reset/flash/NVS state and replay status. Keep raw identifiers private.

## 17. Source Repair / Changed-file Allowlist

```text
SOURCE_REPAIR_STATE=<STATE|NOT_APPLICABLE>
SECTION_STATE=<APPLICABLE|NOT_APPLICABLE>
```

When source mutation is pending or completed, record exact base, changed-file allowlist, hunk boundaries, and forbidden unrelated edits.

## 18. Tests / CI / Artifact Authority

```text
TEST_PLAN_STATE=<STATE|NOT_APPLICABLE>
SECTION_STATE=<APPLICABLE|NOT_APPLICABLE>
```

Record focused tests, full CI, build/artifact hashes, and which validations remain physical/live.

## 19. Next-Session Read-Only Recovery

```text
NEXT_SESSION_RECOVERY_STATE=DEFINED
```

Provide an ordered read-only recovery procedure. It must re-read live repository/branch authority and consumed authorization state before any mutation.

## 20. New Conversation Startup Prompt

```text
STARTUP_PROMPT_PRESENT=true
```

Include a copy-paste startup prompt containing North Star, route, execution model, frozen source, blockers, consumed authorization replay constraints, forbidden actions, and the single next route action.

## 21. Handoff Terminal

```text
HANDOFF_SCHEMA_VERSION=1.0
HANDOFF_TEMPLATE_ID=N3W_FC4_DEVELOPMENT_HANDOFF_TEMPLATE
HANDOFF_TEMPLATE_VERSION=1.0

NORTH_STAR=<VALUE>
CURRENT_ROUTE_NODE=<VALUE>
ACTIVE_DETOUR=<VALUE|NONE>
RETURN_TO_ROUTE=<VALUE|NONE>
NEW_BRANCH_ALLOWED=<true|false>

EXECUTION_MODEL=HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION

PRODUCT_BLOCKER_PROVEN=<true|false>
FAIL_CLASS=<CLASS|NONE>

CURRENT_EXECUTOR_FAILURE_STREAK=<INTEGER>
ROUTE_AUDIT_REQUIRED=<true|false>

NEXT_ROUTE_ACTION=<EXACT_NEXT_ACTION>

HANDOFF_LINT_REQUIRED=true
HANDOFF_LINT_RESULT=<PASS|PENDING>
PUBLIC_REPOSITORY_SAFETY_REQUIRED=true
PUBLIC_REPOSITORY_SAFETY_RESULT=<PASS|PENDING>
```
