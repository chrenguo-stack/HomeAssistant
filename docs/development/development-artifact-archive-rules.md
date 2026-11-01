# Development artifact archive rules

These rules apply to all N3-W, N3-L, Manager, Broker, Home Assistant,
firmware, FC4, diagnostic, validation, and acceptance work.

## Boundary contract

Every meaningful boundary must close the following chain before another
development or live boundary begins:

```text
LOCAL_ARTIFACT_AUDIT
-> CLASSIFY
-> PUBLIC_ARCHIVE
-> PRIVATE_EVIDENCE_BINDING
-> GIT_STATUS_CHECK
-> COMMIT
-> LOCAL_VALIDATION
-> REMOTE_PUSH
-> REMOTE_EXACT_BINDING
```

Meaningful boundaries include a new root cause, source fix, regression guard,
environment constraint, deployment change, useful failed physical attempt,
test result, diagnostic/executor tool, or acceptance result.

If a completed boundary reports `UNARCHIVED_CRITICAL_RESULT_COUNT != 0`, stop.
Do not start a new development or physical boundary. An explicitly approved
archive-recovery boundary may proceed, but it must not claim or consume a
pending physical authorization.

## Required local audit

Inspect all of the following before closure:

- staged, modified, untracked, and valuable ignored files in the worktree;
- relevant artifacts in `/tmp`, `/private/tmp`, Downloads, build, validation,
  evidence, and private-package directories;
- terminal-only facts such as exact SHA/tree, test counts, errors, versions,
  Docker/Compose resolution, network mode, ports, ARM64 results, service
  state, USB/serial/board identity, firmware hashes, registration/replay
  state, state transitions, and consumed authorization status;
- helper scripts, executors, parsers, validators, and diagnostic tools.

Anything useful for later reproduction, diagnosis, acceptance, or handoff that
has no equivalent durable record sets `ARCHIVE_REQUIRED=true`.

## Classification

Classify every valuable artifact before archiving it.

### `PUBLIC_SAFE`

Source, tests, CI, deployment gates, executors, documentation, sanitized
summaries, hashes, sizes, non-sensitive environment facts, state-machine
results, and public-safe reproducers belong in GitHub.

### `PRIVATE_REQUIRED`

Passwords, Setup Secrets, POP values, LMK/application keys, private keys,
tokens, production credentials, private packet captures, and raw evidence that
may contain them remain in the approved private evidence root. Never copy raw
values into source, commit messages, PRs, issues, or public logs.

GitHub must instead contain a sanitized binding where available:

```text
PRIVATE_EVIDENCE_PRESENT=true
PRIVATE_EVIDENCE_PATH_CLASS=<sanitized class>
PRIVATE_EVIDENCE_SHA256=<sha256>
PRIVATE_EVIDENCE_SIZE=<bytes or documented legacy-unavailable marker>
PRIVATE_EVIDENCE_CREATED_AT=<timestamp or documented legacy-unavailable marker>
PRIVATE_EVIDENCE_PURPOSE=<purpose>
SECRET_VALUES_INCLUDED=false
```

### `EPHEMERAL_DISCARDABLE`

Caches, reproducible build intermediates, superseded source archives, rejected
diagnostic candidates, and stale worktrees may be discarded only after their
useful knowledge and required bindings are archived. Superseded commits and
worktrees must never be used as exact-source authority.

## Failure and environment records

Every confirmed new fault, false oracle, executor trap, or environment-specific
behavior must be checked against
`KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`. Add or update a KF entry when no
equivalent record exists. Keep unresolved or not-yet-live-accepted fixes OPEN.

Persist only environment facts that affect behavior or reproducibility.
Prefer, in order:

1. a machine-checkable regression or deployment gate;
2. a sanitized evidence summary;
3. a private raw evidence binding.

Raw logs must never be the only knowledge carrier when a test or gate can
express the same contract.

## Push readiness and final report

Before every push, report source/test/doc/untracked counts, valuable local
artifact counts, public/private archive requirements, KF/environment/guard
requirements, and:

```text
UNARCHIVED_CRITICAL_RESULT_COUNT=0
```

Any non-zero value means `STOP` and `PUSH_NOT_READY`.

Every completed development boundary reports at least:

```text
ARCHIVE_AUDIT=PASS/FAIL
PUBLIC_SOURCE_ARCHIVED=true/false
PUBLIC_TESTS_ARCHIVED=true/false
PUBLIC_DOCS_ARCHIVED=true/false
KNOWN_FAILURES_UPDATED=true/false/not-required
PRIVATE_RAW_EVIDENCE_PRESENT=true/false
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=true/false/not-required
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true/false/not-required
REGRESSION_GUARD_ARCHIVED=true/false/not-required
UNTRACKED_CRITICAL_ARTIFACTS=0
UNARCHIVED_CRITICAL_KNOWLEDGE=0
LOCAL_HEAD=<sha>
LOCAL_TREE=<tree>
REMOTE_HEAD=<sha>
REMOTE_EXACT_BINDING=PASS/FAIL
WORKTREE_CLEAN=true/false
NEXT_SAFE_ENTRY_POINT=<description>
```

Do not upload every local file mechanically. Preserve reusable knowledge,
private-evidence provenance, and exact bindings; explicitly quarantine or
classify uncertain artifacts instead of silently ignoring them.
