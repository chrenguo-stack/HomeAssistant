# TEAM_COLLABORATION_WORKSPACE_STANDARD

> Status: project-wide development process standard  
> Scope: all future development work in this repository  
> Principle owner: project team (`user + high-level model + Codex/executors`)

## 0. Core rule

The user, the high-level model, Codex, and other bounded executors are treated as members of one development team.

GitHub is the team's durable shared workspace and the primary persistence/channel for development artifacts that other team members or future sessions may need.

```text
TEAM_MODEL=USER_PLUS_HIGH_LEVEL_MODEL_PLUS_CODEX
TEAM_SHARED_WORKSPACE=GITHUB
CHAT_AND_EXECUTOR_SESSIONS=EPHEMERAL_WORKSPACES
GITHUB_PERSISTENCE_REQUIRED_FOR_DURABLE_COMPLETION=true
```

A useful artifact must not be considered durably complete while it exists only in a ChatGPT conversation, Codex session, temporary directory, local scratch path, or another member-private workspace.

```text
ARTIFACT_CREATED=true
GITHUB_SHARED=false
=> WORK_NOT_DURABLY_COMPLETE

ARTIFACT_CREATED=true
GITHUB_SHARED=true
COMMIT_OR_HASH_BOUND=true
=> TEAM_SHARE_COMPLETE
```

## 1. What must be shared through GitHub

Persist to GitHub as soon as practical when an artifact has continuing engineering value, including:

- source code and tests;
- scripts and project-owned tools;
- design/architecture decisions that affect later implementation;
- debugging/forensic conclusions that change the current route;
- handoff documents and current-state records;
- known-failure/regression guards;
- reusable execution contracts;
- important artifact manifests, hashes, and reconstruction instructions;
- review candidates that another team member may need before they are production-ready.

Large/private/raw evidence may remain outside Git when appropriate, but GitHub must contain the durable locator, hash, provenance, status, and recovery instructions needed by the team.

Secrets, private credentials, setup secrets, private keys, passwords, or other prohibited sensitive material must never be committed merely to satisfy this rule.

## 2. Review work is still team work

An artifact does not need to be production-ready before it is shared.

Use a review/archive branch or PR and label its status explicitly, for example:

```text
STATUS=REVIEW_ONLY
PHYSICAL_USE_READY=false
PRODUCTION_AUTHORITY=false
```

This is preferred over keeping review code only in chat or a local worktree.

When review passes, the reviewed normal repository path should supersede any temporary archive/bundle as implementation authority.

## 3. Normal repository paths are preferred

For source and tests that are actively being reviewed or developed, prefer directly materialized repository paths over opaque archives:

```text
tools/<tool>.py
tests/.../<test>.py
```

Archives/base64 bundles may be retained as recovery snapshots, but should not be the primary collaboration surface when readable source can be committed directly.

## 4. Commit / hash binding

Every shared engineering artifact that matters to continuation should be bound by at least one durable identifier:

- Git commit SHA / tree SHA;
- Git blob SHA;
- SHA256 for generated/binary artifacts;
- PR number plus exact head SHA where review is in progress.

Do not describe a chat attachment, temporary file, or unpushed local commit as repository authority.

## 5. Handoff requirement

Every formal new-chat handoff must state the current team-workspace status and identify any important artifact that has not yet been shared to GitHub.

Required fields:

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=<n>
TEAM_SHARE_COMPLETENESS=PASS|FAIL
```

A formal handoff should normally require:

```text
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

If a material artifact cannot yet be committed, the handoff must name it, explain why, provide the strongest available recovery locator/hash, and mark team-share completeness accordingly.

## 6. Execution principle relationship

This standard is subordinate to the project's primary execution principle:

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
```

GitHub persistence is a means to correctness, continuity, recoverability, and team coordination. Do not create unnecessary bureaucracy, duplicate artifacts, or meaningless commits merely to satisfy a ritual.

Conversely, do not use speed or convenience as a reason to leave valuable project state trapped in a private session.

## 7. Safety / authorization boundaries remain binding

This standard does not grant mutation authorization for product/runtime/boards, and it does not weaken:

- repository branch protection / PR requirements;
- explicit live or physical authorization;
- mutation scope;
- rollback contracts;
- fail-closed rules;
- secret-handling requirements.

Repository writes themselves must follow repository policy (for example, protected `main` changes through PRs).

## 8. Gate-close checklist

Before calling a meaningful development unit complete, ask:

```text
VALUABLE_ARTIFACT_CREATED=
GITHUB_SHARED=
NORMAL_REPOSITORY_PATH_USED_WHEN_APPROPRIATE=
REVIEW_OR_PRODUCTION_STATUS_EXPLICIT=
COMMIT_OR_HASH_BOUND=
SECRETS_EXCLUDED=
TEAM_SHARE_COMPLETE=
```

If `VALUABLE_ARTIFACT_CREATED=true` and `GITHUB_SHARED=false`, the default classification is:

```text
TEAM_SHARE_COMPLETE=false
WORK_NOT_DURABLY_COMPLETE=true
```

## 9. Maintenance

This standard applies to all future development work unless explicitly superseded by a newer project-wide standard committed to GitHub.

Future handoff standards/templates should reference this file so the rule survives chat/session changes.

```text
TEAM_COLLABORATION_WORKSPACE_STANDARD_VERSION=1.0
TEAM_SHARED_WORKSPACE=GITHUB
CHAT_ONLY_VALUABLE_ARTIFACT_IS_INCOMPLETE=true
```
