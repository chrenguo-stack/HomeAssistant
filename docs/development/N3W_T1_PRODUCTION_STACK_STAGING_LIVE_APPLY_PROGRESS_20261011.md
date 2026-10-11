# N3-W T1 production stack staging live apply progress

Date: 2026-10-11

Status: AUTHORIZATION_GRANTED / EXECUTOR_ARCHIVED / CI_PENDING / LIVE_NOT_CLAIMED

PR: #541 OPEN DRAFT

## 1. Authorization state

The operator explicitly approved:

```text
AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01
AUTHORIZATION_STATE=GRANTED_PENDING_CLAIM
ONE_SHOT=true
REPLAY_FORBIDDEN=true
```

No live staging mutation has been made at this checkpoint. A read-only SSH
reachability check reported `aarch64`; it did not change T1 state.

## 2. Frozen execution artifact

The staging transaction is now implemented as a repository-owned executor:

```text
tools/n3w_t1_production_stack_staging.py
SHA256=400ab67a03b9f166d6d2e8faf6eb837fdc9a24cfbb75a1606beb512a69b55d7a
```

The executor:

- repeats the complete fail-closed T1 preflight before mutation;
- validates exact payload source hashes and the frozen Manager tar hash;
- refuses target collisions and pre-existing production image references;
- removes only the exact empty legacy registration directory;
- creates and prepares only the empty N3-W runtime state;
- loads/pulls only the three frozen production images;
- stages only the approved production source, env, readiness and two activation
  unit files;
- performs `daemon-reload` without enabling or starting either unit;
- renders Compose, runs the deployment gate, and performs the final stopped-state
  audit;
- automatically rolls back staging-created files, empty state roots and image
  references on any post-mutation failure;
- never installs the NetworkManager dispatcher or starts a production service.

Focused tests are in:

```text
tests/tools/test_n3w_t1_production_stack_staging.py
```

The dedicated Manager state-binding workflow now includes the executor and its
tests in both path routing and focused test execution.

## 3. Frozen Manager artifact verification

Artifact `11665219740` from run `38040433177` was downloaded through the GitHub
artifact API and verified locally:

```text
ARTIFACT_ZIP_SHA256=90d72f6eadc85c7ff56156f2f65c149785cdcabc11082b3e8fa275e486b29615
MANAGER_TAR_SHA256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081
MANAGER_TAR_SIZE=59183104
```

No secret material is present in the artifact or executor package.

## 4. Local validation

```text
RUFF=PASS
FOCUSED_PYTEST=36 passed
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

## 5. Next safe entry point

Push this source/test/document boundary, wait for the dedicated CI at the exact
PR head, then build a content-addressed payload. Only after exact CI success may
the granted authorization be claimed by starting the executor's `apply` phase.

Any fresh-preflight drift is STOP and leaves the authorization unclaimed.

```text
ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=not-required
PRIVATE_RAW_EVIDENCE_PRESENT=false
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=not-required
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
REGRESSION_GUARD_ARCHIVED=true
UNTRACKED_CRITICAL_ARTIFACTS=0
UNARCHIVED_CRITICAL_KNOWLEDGE=0
NEXT_SAFE_ENTRY_POINT=exact-head CI then fresh T1 preflight and one-shot apply
```
