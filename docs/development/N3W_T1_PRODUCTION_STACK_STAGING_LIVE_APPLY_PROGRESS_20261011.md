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


## 6. Independent review after Codex handoff

The remote PR state was independently rebound before continuation.

Verified remote starting point:

```text
PR541_HEAD=0fbcd9c544f8783faaacec174ad113f6025a23e7
RUN20=38125209251
RUN20_CONCLUSION=success
RUN20_SCOPE=pre-hardening_executor
```

The reported local commit `f5b9f300...` was not present on GitHub and therefore
could not be treated as repository authority.

Independent source review of the archived executor confirmed both reported
rollback gaps in the remote pre-hardening version:

1. `mutated=True` was set only after both legacy-directory deletion and N3-W
   root creation. A failure between those two operations could leave the first
   mutation outside rollback.
2. rollback used recursive deletion of `/opt/HomeAssistant` without first
   proving that the tree contained only transaction-owned paths.

The remote executor was hardened directly on PR #541:

```text
71e778a40d31706b2dd08227d15a6b53d37c8823
fix(n3w): harden staging rollback boundaries

b9305b5fff1d046ebbc86530d12521ea227681a6
test(n3w): cover staging rollback hardening
```

The hardening additionally makes rollback re-prove:

```text
containers=0
docker volume set=exact frozen baseline
project network container counts=0
production listeners=0
guard contract=exact
DynSec SHA=exact
secret bundle aggregate=unchanged
Manager DB SHA=unchanged
legacy empty registration directory=restored
N3-W state root=absent
HA staging root=absent
/opt/HomeAssistant staging root=absent unless unknown content is preserved
activation units=not-found
production image references=absent
dispatcher=absent
```

Unknown content under `/opt/HomeAssistant` is now preserved and forces rollback
FAIL instead of recursive deletion.

The first destructive action, removal of the exact empty legacy registration
directory, now marks the transaction mutated immediately so any subsequent
failure enters rollback.

A fresh exact-head CI was triggered:

```text
PR541_HEAD=b9305b5fff1d046ebbc86530d12521ea227681a6
RUN_ID=38125884756
RUN_NUMBER=22
STATUS=in_progress
LIVE_T1_MUTATION=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
```

Run #20 remains useful only as evidence for the pre-hardening executor. It is
not valid as exact-head authority for the hardened executor.

No payload may be rebuilt and no T1 apply may begin until run #22 passes.


## 7. Exact hardened executor CI closure and payload build entry

The hardened executor source/test boundary is now CI-closed.

```text
EXECUTOR_SOURCE_HEAD=b9305b5fff1d046ebbc86530d12521ea227681a6
RUN_ID=38125884756
RUN_NUMBER=22
CONCLUSION=success

FOCUSED_SOURCE_TESTS=PASS
RENDER_AND_VALIDATE_PRODUCTION_COMPOSE=PASS
DOWNLOAD_EXACT_FROZEN_MANAGER_ARTIFACT=PASS
LOAD_EXACT_FROZEN_ARM64_MANAGER_IMAGE=PASS
PREPARE_SYNTHETIC_RESTORED_MANAGER_BASELINE=PASS
EXACT_IMAGE_MANAGER_STATE_PREPARE_AND_AUDIT=PASS
```

The following documentation-only head also passed the same dedicated workflow:

```text
DOCUMENTED_HEAD=7f54561cb74fface14660010b2c18fe34ba5f522
RUN_ID=38125935452
RUN_NUMBER=23
CONCLUSION=success
```

The superseded local payload reported in the Codex handoff remains forbidden for
T1 use.

A repository-owned payload builder has now been added:

```text
.github/workflows/n3w-t1-production-stack-staging-payload-ci.yml
COMMIT=96113b82e3b69cdc6d2f35293e67a2b7873e9bdc
```

It builds a new content-addressed staging payload only after:

- running the staging executor focused tests;
- downloading artifact `11665219740` from frozen binding run `38040433177`;
- verifying Manager tar SHA256
  `2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081`;
- checking the executor's internal payload source hash contract;
- generating a manifest containing source head, executor SHA256, file hashes and
  the authorization ID with claimed/consumed both false;
- uploading only public source/configuration plus the frozen Manager image tar;
- including no secret values.

Current boundary:

```text
HARDENED_EXECUTOR_CI=PASS
PAYLOAD_BUILD_CI=PENDING
T1_MUTATION=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

Fresh T1 preflight and staging apply remain blocked until the new payload build
CI has passed and the resulting artifact hashes are rebound.


## 8. Exact payload binding closure

The first payload workflow run was successful as a build, but its manifest bound
to GitHub's pull-request synthetic merge SHA rather than the PR branch head:

```text
SUPERSEDED_RUN_ID=38126385865
SUPERSEDED_ARTIFACT_ID=11697706589
SYNTHETIC_MERGE_SHA=21727a26b8d19f1014215112c00a159618e0c065
MERGE_MESSAGE=Merge bf000858c64f5a4f4e6ff15cb1ebb5a8ab88c06e into d423211b6196c2f2f0f01dff072c4f877fbe58ee
SUPERSEDED_FOR_T1_USE=true
```

The payload workflow was repaired to explicitly check out and bind
`github.event.pull_request.head.sha` on pull-request runs.

Repair commit:

```text
ea6738551e583a14ad5685e181109b7e57f8fb1b
ci(n3w): bind staging payload to PR head
```

The replacement exact-head payload CI passed:

```text
RUN_ID=38126850777
RUN_NUMBER=5
CONCLUSION=success
SOURCE_HEAD=ea6738551e583a14ad5685e181109b7e57f8fb1b
ARTIFACT_ID=11697172862
ARTIFACT_NAME=n3w-t1-production-stack-staging-payload-ea6738551e583a14ad5685e181109b7e57f8fb1b
ARTIFACT_ZIP_SHA256=371b7affdf9503c93396762c278bee5bc749f25b55fdb5826d498ba06adb72ce
PAYLOAD_ARCHIVE_SHA256=35e9b7e2594ff1b90b84a2d78a9f4dff885e68c67c597227ad48352ecd7cc3d7
PAYLOAD_MANIFEST_SHA256=3e73fbf62482c660eac67de8db047a76ebd0c8f2897e6bbcff54f42a68e6241e
EXECUTOR_SHA256=3f82a52db85290abf7a0ab0b9c407e74c40202598e0c41292ffe06ceeffdd2ef
MANAGER_TAR_SHA256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081
```

The downloaded artifact was independently unpacked and rebound. Its manifest
reports:

```text
schema=gh.n3w-t1-production-stack-staging-payload/1
source_head=ea6738551e583a14ad5685e181109b7e57f8fb1b
authorization_id=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01
authorization_claimed=false
authorization_consumed=false
secret_values_included=false
production_service_start=false
board_access=false
file_count=14
```

The executor, manifest, payload archive, Manager tar and GitHub artifact ZIP all
match their recorded SHA256 values.

Current safe boundary:

```text
PAYLOAD_BINDING=PASS
FRESH_T1_PREFLIGHT=NEXT
T1_PRODUCTION_MUTATION=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

The fresh T1 preflight must use only artifact ID `11697172862` and executor
SHA256 `3f82a52d...`. Any earlier payload is forbidden.
