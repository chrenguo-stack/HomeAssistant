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


## 9. Fresh T1 preflight STOP: H0/H1 provenance fingerprint width

The exact payload reached T1 and executed only the read-only preflight phase.

Observed result:

```text
phase=preflight
status=STOP
reason=manager_database_provenance_drift
authorization_id=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01
production_service_start=false
board_access=false
```

No `--authorization-id` was passed to the executor and the apply phase was not
entered.

```text
T1_PRODUCTION_MUTATION=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
```

Independent source review found a precise contract mismatch.

The accepted H0/H1 authority defines:

```python
def system_id_fingerprint(system_id: str) -> str:
    return hashlib.sha256(system_id.encode("utf-8")).hexdigest()[:24]
```

The production Manager database provenance therefore stores a 24-character
SYSTEM_ID fingerprint. The staging executor and Manager-state preparer instead
compared that column with the complete 64-character public-safe SYSTEM_ID
SHA-256. The synthetic CI fixture also inserted 64 characters, so the incorrect
assumption was self-consistent in CI and escaped detection.

Root classification:

```text
KF=KF-105
FAILURE_CLASS=PHYSICAL_HARNESS_SOURCE_CONTRACT_MISMATCH
PRODUCT_RUNTIME_FAILURE_PROVEN=false
H0H1_RESTORE_DRIFT_PROVEN=false
LIVE_MUTATION=false
```

Source repair:

```text
6202f5409dfc0bbd04cac8143b38e2dbeafe1e39
fix(n3w): honor H0H1 24-char system fingerprint

63a98496e72db6530a3ced1a37c7c5277b0ff85f
test(n3w): enforce H0H1 provenance fingerprint width

06e1c155351efff34b9f82a9eabd6fe5853b4c99
ci(n3w): model H0H1 provenance fingerprint correctly

b4d8548e32604f2adc08e496f5d72af6e53dcc6e
fix(n3w): align staging provenance with H0H1 fingerprint

2cd22205675da00d8fc5a5078f392d7c1bd1c3a7
test(n3w): guard staging provenance fingerprint semantics
```

The complete 64-character SYSTEM_ID SHA-256 remains the public-safe identity
authority. Only the H0/H1 provenance column uses its defined 24-character
fingerprint prefix.

The replacement source CI and replacement payload must pass before another T1
preflight. The prior payload artifact is now superseded and forbidden for
further T1 use.


## 10. Replacement fresh T1 preflight PASS

The KF-105-repaired exact payload was transferred to T1 and executed in
`preflight` mode only. No authorization ID was supplied to the executor.

Observed exact result:

```text
status=PASS
phase=preflight
docker_container_count=0
docker_volume_count=45
docker_volume_set_sha256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
project_network_container_counts=n3wfc4-private:0,n3wfc4-services:0
tcp_1883=0
tcp_8883=0
tcp_18883=0
tcp_8123=0
tcp_47112=0
udp_47111=0
guard_active=true
guard_enabled=true
guard_exact=true
dynsec_sha256=95d99839ec9a6b8003e1375883a3f9263a92e0dbc49c8ca5478196027081a90a
identity_claim_count=1
legacy_collision=empty_root_root_0755_directory
manager_database_quick_check=ok
manager_database_business_rows=0
manager_database_provenance_rows=1
manager_database_sha256=6db7069f2134be3b178d3238da2dfc199463d812dd6be318531611eaddc4c971
n3w_state_root=absent
production_images=absent
production_services=stopped
secret_file_count=11
root_available_bytes=6420983808
manager_tar_sha256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081
source_file_count=12
production_service_start=false
board_access=false
live_mutation=false
```

The exact replacement payload authority remains:

```text
SOURCE_HEAD=8a7bd74cc1cc009e198faf715adae26696777107
PAYLOAD_CI_RUN=38127849103
ARTIFACT_ID=11698220067
ARTIFACT_ZIP_SHA256=779d221da3f85b431a7a99601c44de070a818dc04273677aed9b0064feb8b9d2
PAYLOAD_ARCHIVE_SHA256=6ab2816a02d3b2ce90ba94d57e41b347051881bc5c2c4a2fa8016aca8f7445f3
PAYLOAD_MANIFEST_SHA256=145c22de3810046851b7414eb953fd1fc2098681084fcda5e213ac6f4ed6c2ce
EXECUTOR_SHA256=3cfc30043bb6ad81e9a6ef4cad11a3bddc9155099f2d6f5a1024d3e2363070d1
```

Disposition:

```text
KF105=CLOSED_GUARDED
FRESH_T1_PREFLIGHT=PASS
AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01
AUTHORIZATION_STATE=GRANTED_PENDING_CLAIM
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
LIVE_STAGING_APPLY=READY
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

Starting the executor's `apply` phase with the exact authorization ID is the
claim point. From that moment the authorization is one-shot and must never be
replayed, even if transport is interrupted or the executor rolls back.


## 11. One-shot staging apply consumed with rollback PASS

The exact payload apply phase was started under the granted one-shot authorization.

Observed execution:

```text
fresh_preflight=PASS
state_root_prepare=PASS
manager_image_load=START
manager_image_load=STOP
reason=image_binding_drift:local/greenhouse-manager:s20-511db028
rollback_status=PASS
rollback_errors=[]
production_service_start=false
board_access=false
```

By the frozen authorization contract, entering `--phase apply` permanently claims
and consumes the authorization, regardless of rollback outcome.

```text
AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_RESULT=FAILED_ROLLBACK_PASS
REPLAY_FORBIDDEN=true
```

The failure occurred after the exact empty legacy collision directory was
removed and the empty N3-W root was created, then after `docker load`. The
executor's rollback reported PASS with zero errors. Its rollback postcheck
therefore re-proved the production baseline and removed the loaded Manager image
reference before returning STOP.

No Broker, Manager or Home Assistant production service was started.

### Image identity oracle defect

The frozen Manager tar itself is exact:

```text
MANAGER_TAR_SHA256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081
MANAGER_CONFIG_DIGEST=sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1
MANAGER_OCI_TARGET_DIGEST=sha256:abd9560c978b69429eea734df216664ea643ed762a77777dcb816f5d537afad6
```

The staging executor incorrectly required Docker image inspect `.Id` to equal
the config digest only. Docker's containerd image-store implementation instead
uses the image target descriptor digest as the inspect ID. The same portability
problem would also affect the digest-pinned Home Assistant and Broker images.

Source repair now treats both storage models as exact, without weakening the
content lock:

- classic image store: image ID must equal the exact config digest;
- containerd image store: image ID must equal the exact OCI target/manifest
  digest;
- if an OCI Descriptor is present, its digest must equal the exact expected
  target digest;
- OS/architecture must remain exactly `linux/arm64`;
- any other ID or descriptor still fails closed.

Source repair commits:

```text
bb0be92dbffcb86536c71ab59114cae7e63540c9
fix(n3w): support Docker containerd image identity

1b7a610499e4f6586536d3c2d968353f1a98ec52
test(n3w): cover classic and containerd image identities

d136bdbde8df9fcf38330ef8afa3957016c6eeb3
fix(n3w): complete cross-store image identity wiring

80ecf3048b1cf138b2a3d7412eed846777136b77
ci(n3w): bind Manager config and OCI target digests
```

### Mac wrapper transport defect

After the executor had already returned its STOP + rollback PASS result, the Mac
wrapper itself failed at:

```text
zsh: PIPESTATUS[0]: parameter not set
```

That is a separate host-wrapper defect: `PIPESTATUS` is Bash-specific while the
operator shell is zsh. It did not cause the executor failure and did not change
the rollback result. Future live wrappers must capture the SSH return code
without a shell-specific pipeline array; the next version must be repository
owned and tested before another live authorization is requested.

Current boundary:

```text
KF106=OPEN_SOURCE_REPAIR_CI_PENDING
KF078=OPEN_HOST_WRAPPER_RECURRENCE
PRODUCTION_ROLLBACK=PASS
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_FORBIDDEN=true
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```


## 12. Repository-owned host transport repair

A repository-owned Mac-to-T1 transport wrapper now replaces the ad-hoc zsh
pipeline used by the consumed failed apply:

```text
tools/n3w_t1_production_stack_staging_host.py
01b7538cb0a5ee118368c49c31f0970f0f3af7cf
feat(n3w): add repository-owned staging host transport

tests/tools/test_n3w_t1_production_stack_staging_host.py
b1889ef1dc26249265169eda08a961a504204370
test(n3w): guard staging host transport semantics

6c821a88d1291c10220f2efd7b0e218e10935e2b
ci(n3w): test and publish staging host wrapper
```

The wrapper:

- uses subprocess argument arrays instead of shell pipelines;
- uses `ssh -n` for commands that do not own stdin;
- verifies payload archive, executor and manifest hashes before transport;
- verifies them again after transfer;
- emits an explicit one-shot claim event immediately before remote apply;
- captures SSH return codes directly, with no Bash/zsh pipeline-status variable;
- retains local and remote evidence on failed/unknown apply transport;
- cleans temporary material automatically after successful completion;
- never silently converts an apply transport error into a replayable state.

The payload workflow now runs the host-wrapper focused tests and publishes the
exact wrapper plus its SHA256 alongside the content-addressed payload.

Current replacement CI:

```text
PR541_HEAD=6c821a88d1291c10220f2efd7b0e218e10935e2b
MANAGER_STATE_BINDING_RUN=38129717751
STAGING_PAYLOAD_RUN=38129717780
STATUS=PENDING
```

No new live authorization exists. The consumed authorization
`N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_01` remains permanently
non-replayable.


## 13. KF-106 / host-wrapper CI closure and successor rotation

The image-identity repair and repository-owned host transport both passed their
dedicated exact-head CI at repository head
`d92bdbb3a84bfe2403f42e69612ae1196824c743`.

```text
MANAGER_STATE_BINDING_RUN=38129756566
MANAGER_STATE_BINDING_RUN_NUMBER=57
MANAGER_STATE_BINDING_CONCLUSION=success

STAGING_PAYLOAD_RUN=38129756547
STAGING_PAYLOAD_RUN_NUMBER=34
STAGING_PAYLOAD_CONCLUSION=success
```

Run #34 proved and published:

```text
SOURCE_HEAD=d92bdbb3a84bfe2403f42e69612ae1196824c743
ARTIFACT_ID=11698238759
ARTIFACT_ZIP_SHA256=7ff1cb440078dc9e1d64df442166b477109d46d2d2e4044a01c73883ef8ecfec
PAYLOAD_ARCHIVE_SHA256=f487075537c63df9407e5b78aa9ff2c16f1066ce4b0ce5c861c99fe98d406f0f
PAYLOAD_MANIFEST_SHA256=74a6a4562345bc358ad4c9a3ec14247bba0ab8cbc9b03aab8948ddc3fe65a823
EXECUTOR_SHA256=7954915bb709123f55334eb5da3f504039b1ea81d3298aaf11c4eec84ad60c2c
HOST_WRAPPER_SHA256=30ca74ec1a46f5de6252adf2663bcce4607ac2e7768f5e31fd5ca14ac0338a4b
MANAGER_TAR_SHA256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081
MANAGER_CONFIG_DIGEST=sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1
MANAGER_OCI_TARGET_DIGEST=sha256:abd9560c978b69429eea734df216664ea643ed762a77777dcb816f5d537afad6
```

That artifact is source-valid evidence for the repair, but it still embeds the
already consumed predecessor authorization ID `..._01`. It is therefore
**not eligible for a second live apply**.

The live authorization identity has now been rotated in source and payload
metadata to:

```text
N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
```

The successor is currently **NOT_GRANTED**. The predecessor remains permanently
consumed and non-replayable.

Current boundary:

```text
KF106_SOURCE_CI=PASS
KF078_HOST_WRAPPER_CI=PASS
PREDECESSOR_AUTHORIZATION=CONSUMED_NO_REPLAY
SUCCESSOR_AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
SUCCESSOR_AUTHORIZATION_STATE=NOT_GRANTED
SUCCESSOR_PAYLOAD_CI=PENDING
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```


## 14. Successor payload binding PASS

The successor-authorization exact payload completed CI and was independently
downloaded and rebound.

```text
SOURCE_HEAD=161253205a9b8d3af8aa345808f231add9bd5723
MANAGER_STATE_BINDING_RUN=38130333275
MANAGER_STATE_BINDING_RUN_NUMBER=65
MANAGER_STATE_BINDING_CONCLUSION=success
PUBLIC_REPOSITORY_SAFETY_RUN=38130333328
PUBLIC_REPOSITORY_SAFETY_RUN_NUMBER=4047
PUBLIC_REPOSITORY_SAFETY_CONCLUSION=success
STAGING_PAYLOAD_RUN=38130333387
STAGING_PAYLOAD_RUN_NUMBER=42
STAGING_PAYLOAD_CONCLUSION=success

AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

ARTIFACT_ID=11697988392
ARTIFACT_NAME=n3w-t1-production-stack-staging-payload-161253205a9b8d3af8aa345808f231add9bd5723
ARTIFACT_ZIP_SHA256=da0aa461fe9f69cf4da0a019f5f91cf9195837f3fd90ec172e4c49a3f639c5aa
PAYLOAD_ARCHIVE_SHA256=1a788d9c77034dda6c99f1e82d17564c062fa0687b3f7483924a99d845df90a3
PAYLOAD_MANIFEST_SHA256=cead5f2c35d28ae695f70195850b7964d4f72826d013eba7b043022abb2d7068
EXECUTOR_SHA256=5ff02f68ebca832c57698084a837233db3863c32301b26ec114c61eb51156918
HOST_WRAPPER_SHA256=30ca74ec1a46f5de6252adf2663bcce4607ac2e7768f5e31fd5ca14ac0338a4b

MANAGER_TAR_SHA256=2ef0421d483334f6ef81c92beb1b6784174f069a4bde179ba615ce0b70435081
MANAGER_CONFIG_DIGEST=sha256:ef0f28c2fd339430a85acb6cb65158c71c61cd8fc3c6330c375da27d0f2440f1
MANAGER_OCI_TARGET_DIGEST=sha256:abd9560c978b69429eea734df216664ea643ed762a77777dcb816f5d537afad6
```

Independent artifact verification confirmed that the published
`host-wrapper.sha256` equals the actual `host-wrapper.py` SHA256 and that the
archive/executor/manifest sidecars match the CI-emitted values.

The predecessor payloads and authorization `..._01` remain permanently
superseded and non-replayable.

Current gate:

```text
SUCCESSOR_PAYLOAD_BINDING=PASS
SUCCESSOR_FRESH_T1_PREFLIGHT=NEXT
SUCCESSOR_AUTHORIZATION_STATE=NOT_GRANTED
SUCCESSOR_AUTHORIZATION_CLAIMED=false
SUCCESSOR_AUTHORIZATION_CONSUMED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

The next operation is read-only T1 preflight using the repository-owned
host-wrapper from artifact ID `11697988392`. A PASS does not itself grant
`..._02`; explicit user approval is still required before apply.


## 15. Successor fresh T1 preflight PASS

The repository-owned host wrapper executed the successor exact payload against T1
in read-only preflight mode.

Observed result:

```text
phase=preflight
status=PASS
transport_completion=KNOWN_SUCCESS
HOST_WRAPPER_RC=0

authorization_id=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
authorization_claimed=false
authorization_consumed=false

docker_container_count=0
docker_volume_count=45
docker_volume_set_sha256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
project_network_container_counts=n3wfc4-private:0,n3wfc4-services:0
tcp_1883=0
tcp_8883=0
tcp_18883=0
tcp_8123=0
tcp_47112=0
udp_47111=0
guard_active=true
guard_enabled=true
guard_exact=true
dynsec_sha256=95d99839ec9a6b8003e1375883a3f9263a92e0dbc49c8ca5478196027081a90a
identity_claim_count=1
legacy_collision=empty_root_root_0755_directory
manager_database_quick_check=ok
manager_database_business_rows=0
manager_database_provenance_rows=1
manager_database_sha256=6db7069f2134be3b178d3238da2dfc199463d812dd6be318531611eaddc4c971
n3w_state_root=absent
production_images=absent
production_services=stopped
secret_file_count=11
secret_bundle_sha256=ce8700835c8b4e4aa86a6c0bacda4785122dd3971b858c9279200ff9399fb929
root_available_bytes=6420955136
live_mutation=false
production_service_start=false
board_access=false
```

The terminal's later shell-session-save warning occurred after the wrapper had
already returned `HOST_WRAPPER_RC=0`. It is outside the staging executor and
host-wrapper transaction and does not alter the preflight result.

Current authorization boundary:

```text
SUCCESSOR_FRESH_T1_PREFLIGHT=PASS
SUCCESSOR_AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
SUCCESSOR_AUTHORIZATION_STATE=NOT_GRANTED
SUCCESSOR_AUTHORIZATION_CLAIMED=false
SUCCESSOR_AUTHORIZATION_CONSUMED=false
LIVE_STAGING_APPLY=READY_AFTER_EXPLICIT_USER_APPROVAL
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

The next permitted mutation is a single staging-only apply under `..._02`.
Starting that apply permanently claims and consumes the successor authorization,
regardless of success, rollback, transport interruption, or operator terminal
failure. It may never be replayed.


## 16. Successor authorization explicitly granted

After the exact successor payload binding and fresh T1 read-only preflight both
passed, the operator explicitly approved:

```text
N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
```

Current state before apply invocation:

```text
AUTHORIZATION_STATE=GRANTED_PENDING_CLAIM
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
LIVE_STAGING_APPLY=AUTHORIZED
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR_MERGE=false
```

Only the repository-owned host wrapper and exact successor artifact may be used.
The predecessor authorization and all predecessor payloads remain permanently
forbidden.


## 17. Successor apply claimed / live execution in progress

The repository-owned host wrapper emitted the one-shot claim event:

```text
HOST_WRAPPER_BINDING=PASS
AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
authorization_claimed=true
do_not_replay=true
event=apply_transport_invoked
```

Per the frozen contract, the successor authorization is now permanently claimed
and consumed. It must never be replayed, regardless of the eventual transaction
result or host transport outcome.

At the time of this update the host wrapper had not yet returned a final
executor result. This is not itself a failure signal: the repository-owned host
wrapper invokes the remote executor with `subprocess.run(...,
capture_output=True)` and only forwards the captured remote stdout/stderr after
that SSH command exits. Long-running remote steps such as image pulls can
therefore make the operator terminal appear silent while the transaction is
still active.

Current state:

```text
AUTHORIZATION_STATE=CLAIMED_IN_PROGRESS
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_FORBIDDEN=true
FINAL_TRANSACTION_RESULT=UNKNOWN
PRODUCTION_SERVICE_START=NOT_YET_OBSERVED
BOARD_ACCESS=false
PR_MERGE=false
```

The correct operator action is to leave the original terminal/process running.
Any parallel observation must be strictly read-only.


## 18. Successor apply #02 consumed: external image pull timeout / rollback PASS

The successor staging apply was invoked through the repository-owned host wrapper
under authorization:

```text
N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
```

Observed exact execution:

```text
HOST_WRAPPER_BINDING=PASS
apply_transport_invoked=true
authorization_claimed=true

fresh_preflight=PASS
state_root_prepare=PASS
manager_image_load=PASS
manager_state_prepare=PASS
production_image_pull=START

STOP:
TimeoutExpired:
docker pull --platform linux/arm64
ghcr.io/home-assistant/home-assistant:2026.10.0@
sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4
timed out after 1200 seconds

rollback_status=PASS
rollback_errors=[]
production_service_start=false
board_access=false

host_transport=FAILED_OR_UNKNOWN
ssh_returncode=2
HOST_WRAPPER_RC=2
```

The executor itself returned a structured STOP with rollback PASS, so the
transaction result is known even though the host wrapper conservatively labels
all nonzero SSH exits as `FAILED_OR_UNKNOWN`.

Authorization disposition:

```text
AUTHORIZATION_ID=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
AUTHORIZATION_STATE=CONSUMED_FAILED_ROLLBACK_PASS
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_FORBIDDEN=true
```

No production service was started.

### KF-107 classification

The immediate failure is an external registry pull timeout. The lower-level
network cause is not proven.

A separate design defect is proven: the one-shot post-claim staging transaction
contained required Internet registry pulls. Therefore a transient registry or
network delay could consume the one-shot authorization after local staging
mutation had already begun.

```text
KF107=OPEN_SOURCE_REPAIR
DOMAIN=INFRASTRUCTURE
NETWORK_ROOT_CAUSE=TBD
PRODUCT_RUNTIME_FAILURE_PROVEN=false
ROLLBACK=PASS
```

### Source repair direction

The live staging transaction must no longer depend on external image registry
access.

The payload CI now materializes the exact digest-pinned ARM64 Home Assistant and
Broker images before T1 execution, saves both as image tar files, removes their
local refs, reloads the tars, and re-verifies the exact digest/platform contract.
The content-addressed staging payload then carries:

```text
artifact/greenhouse-manager-arm64.tar
artifact/homeassistant-arm64.tar
artifact/broker-arm64.tar
```

The T1 executor replaces live `docker pull` with local `docker load` for all
three images and verifies the same exact image identity contract after load.

Source repair commits:

```text
6c7bedf7aa99f51a7c03a5dedc7fd6c1321dff36
fix(n3w): remove live registry pulls from staging apply

1e7c934d3b5a955fb23f551b95dfe1009048b495
test(n3w): guard offline staging image payload

07ad3a561997d5e0065770248ca4b4b606dd1d28
ci(n3w): freeze external images into staging payload
```

The authorization identity is rotated again:

```text
PREDECESSOR=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_02
PREDECESSOR_STATE=CONSUMED_FAILED_ROLLBACK_PASS

SUCCESSOR=N3W_T1_PRODUCTION_STACK_STAGING_LIVE_APPLY_20261011_03
SUCCESSOR_STATE=NOT_GRANTED
```

No `..._03` live execution is allowed until the new large payload CI, exact
artifact binding, fresh T1 read-only preflight, and explicit operator approval
all pass.
