# Development Handoff Document Contract

```text
HANDOFF_CONTRACT_VERSION=1.0
CANONICAL_TEMPLATE=
docs/development/templates/N3W_FC4_DEVELOPMENT_HANDOFF_TEMPLATE_V1.0.md
CANONICAL_TEMPLATE_BLOB_SHA=e26ff3329e52e6e56b16b865c19649feabbb09b7
LINTER=
tools/check_development_handoff.py
```

## Purpose

This contract makes development handoffs a repeatable, machine-checkable project artifact instead of an ad-hoc narrative. It applies to every new handoff that declares `HANDOFF_SCHEMA_VERSION`.

Historical handoffs that predate this contract remain historical records and are not silently rewritten as schema-compliant documents.

## Mandatory principles

```text
NEW_SESSION_HANDOFF_REQUIRES_TEMPLATE=true
HANDOFF_LINT_REQUIRED=true
HANDOFF_LINT_PASS_REQUIRED_BEFORE_CLOSEOUT=true
PUBLIC_REPOSITORY_SAFETY_REQUIRED=true

UNKNOWN_IS_NOT_FAIL=true
UNOBSERVED_IS_NOT_FALSE=true
ONE_GATE_ONE_ROUTE_DECISION=true

EXECUTION_MODEL=
HIGH_LEVEL_REASONING_PLUS_BOUNDED_CODEX_EXECUTION

HIGH_LEVEL_REASONING_ROLE=CHATGPT
BOUNDED_EXECUTION_ROLE=CODEX

DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING=true
CONSUMED_AUTHORIZATION_REPLAY_FORBIDDEN=true
```

## Required sections

Every schema-compliant handoff must retain all sections below, in this order. A section that does not apply must stay present and declare `SECTION_STATE=NOT_APPLICABLE`.

1. Document Identity / Schema
2. North Star / Route
3. Execution Model
4. Repository / Branch Authority
5. Frozen Product Source
6. Worktree / Workspace Guard
7. Runtime Authority
8. Product State / Proven Facts
9. Active Blocker / Root Cause
10. Failure Classification / Fuse
11. Authorization Ledger
12. Mutation State
13. Known Failures / Regression Guards
14. Forbidden Actions / Non-goals
15. Next Route Action
16. Physical State
17. Source Repair / Changed-file Allowlist
18. Tests / CI / Artifact Authority
19. Next-Session Read-Only Recovery
20. New Conversation Startup Prompt
21. Handoff Terminal

## Required machine-readable fields

At minimum:

```text
HANDOFF_SCHEMA_VERSION
HANDOFF_TEMPLATE_ID
HANDOFF_TEMPLATE_VERSION
HANDOFF_TEMPLATE_BLOB_SHA
HANDOFF_DOCUMENT_VERSION
HANDOFF_DATE

NORTH_STAR
CURRENT_ROUTE_NODE
ACTIVE_DETOUR
RETURN_TO_ROUTE
NEW_BRANCH_ALLOWED

EXECUTION_MODEL
HIGH_LEVEL_REASONING_ROLE
BOUNDED_EXECUTION_ROLE
ONE_GATE_ONE_ROUTE_DECISION
UNKNOWN_IS_NOT_FAIL
UNOBSERVED_IS_NOT_FALSE
DSL_OR_EXECUTION_CONTRACT_IS_NOT_SELF_EXECUTING

REPOSITORY
HANDOFF_BRANCH
HANDOFF_PREDECESSOR_HEAD
HANDOFF_BRANCH_HEAD_POLICY

FROZEN_PRODUCT_SOURCE_HEAD
FROZEN_PRODUCT_SOURCE_TREE

PRIVATE_WORKTREE_PATH_EXPOSED
DIRTY_WORKTREE_MUTATION_ALLOWED

RUNTIME_AUTHORITY_STATE
PRODUCT_STATE

PRODUCT_BLOCKER_PROVEN
FAIL_CLASS
CURRENT_EXECUTOR_FAILURE_STREAK
ROUTE_AUDIT_REQUIRED

CONSUMED_AUTHORIZATION_COUNT
REPLAY_OF_CONSUMED_AUTHORIZATION_ALLOWED

SOURCE_MUTATION_EXECUTED
PHYSICAL_MUTATION_EXECUTED
RUNTIME_MUTATION_EXECUTED

KNOWN_FAILURES_UPDATED
KNOWN_FAILURES_STATE

FORBIDDEN_ACTIONS_STATE
NEXT_ROUTE_ACTION

PHYSICAL_STATE
SOURCE_REPAIR_STATE
TEST_PLAN_STATE
NEXT_SESSION_RECOVERY_STATE
STARTUP_PROMPT_PRESENT

HANDOFF_LINT_REQUIRED
HANDOFF_LINT_RESULT
PUBLIC_REPOSITORY_SAFETY_REQUIRED
PUBLIC_REPOSITORY_SAFETY_RESULT
```

## Authorization ledger format

Every authorization entry must use a bounded block:

```text
AUTHORIZATION_LEDGER_BEGIN
AUTHORIZATION_ID=<id-or-NONE>
AUTHORIZATION_STATE=<NOT_APPLICABLE|CANDIDATE|GRANTED|CLAIMED|CONSUMED>
REPLAY_PERMITTED=<true|false|NOT_APPLICABLE>
AUTHORIZATION_SCOPE=<scope-or-NOT_APPLICABLE>
AUTHORIZATION_LEDGER_END
```

If `AUTHORIZATION_STATE=CONSUMED`, `REPLAY_PERMITTED` must be `false`.

A candidate authorization is not a granted authorization.

## Public repository rules

Schema-compliant public handoffs must never expose:

- Setup Secret bodies or hashes;
- raw Board hardware identifiers;
- raw pairing identifiers;
- raw NODE_ID values;
- private Board IP addresses;
- private evidence paths;
- developer absolute home paths;
- credentials, private keys, tokens, passwords, or embedded URL credentials.

Use public-safe placeholders such as:

```text
<PRIVATE_EXACT_WORKTREE_PATH>
<PRIVATE_EVIDENCE_PATH>
<REDACTED_BOARD_AUTHORITY>
```

The existing `tools/check_public_repository_safety.py` remains authoritative for repository-wide leak detection. The handoff linter adds handoff-specific fail-closed checks.

Because the repository-safety step scans the whole tracked repository, a handoff closeout may expose a pre-existing safety violation outside the handoff files. Such a finding is a real closeout blocker: fix the originating tracked fixture/document with the smallest public-safe change, preserve its product/test semantics, and rerun the same gate. Do not weaken or scope down the safety checker merely to make the handoff pass.

## Template versioning

The canonical template is versioned. A handoff must record:

```text
HANDOFF_TEMPLATE_VERSION=<version>
HANDOFF_TEMPLATE_BLOB_SHA=<40-hex Git blob SHA>
```

Changing required sections, required keys, authorization semantics, or safety semantics requires a template/contract version change.

Editorial changes that do not alter semantics may keep the same schema version only when explicitly reviewed.

## Validation

For one file:

```bash
python3 tools/check_development_handoff.py \
  --file docs/development/<handoff>.md
```

For all schema-declared handoffs:

```bash
python3 tools/check_development_handoff.py --all
```

Linter self-test:

```bash
python3 tools/check_development_handoff.py --self-test
```

A new development boundary must not start until the current schema-compliant handoff reports:

```text
HANDOFF_LINT_RESULT=PASS
PUBLIC_REPOSITORY_SAFETY_RESULT=PASS
```

and the corresponding commands have actually passed. A field claiming PASS does not replace running the check.

## Migration policy

Legacy handoffs without `HANDOFF_SCHEMA_VERSION` are reported as legacy/skipped by `--all`. Do not bulk-edit historical handoffs merely to satisfy the new schema.

When a live lineage needs a new handoff after this contract, generate a new version from the canonical template and make it the current recovery authority.
