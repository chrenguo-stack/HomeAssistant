# N3-W T1 fresh bootstrap R6 — Astra R2 closure review brief（2026-10-12）

## 1. Mission

Perform an independent closure review of the exact repaired fresh-bootstrap source after the first Astra review blocked live progression.

The decision is limited to whether the project may move to:

~~~text
replacement exact artifact binding
→ real-T1 read-only preflight
~~~

It is NOT permission to perform a live apply.

~~~text
READ_ONLY_REVIEW=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
MERGE=false
LIVE_AUTHORIZATION_GRANTED=false
~~~

## 2. Fresh authority

~~~text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=541
BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010
PR_STATE=OPEN_DRAFT
PRODUCT_SOURCE_HEAD=dec88fdc19daf50185d09acf4a38db8c18816ef2
ASTRA_R1_SOURCE_HEAD=c263b9df6bac900332d27a50a66dd603d7d5e1e4
ASTRA_R1_RESULT=BLOCK
ASTRA_R1_BLOCKERS=F1,F2,F3,F4,F5,F6
~~~

The docs-only commit containing this brief is not product execution authority. Fresh-rebind PR #541, then review the product delta rooted at PRODUCT_SOURCE_HEAD.

Relevant files:

~~~text
tools/n3w_t1_fresh_product_bootstrap.py
tools/n3w_t1_fresh_product_staging_host.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py
host/greenhouse-manager/src/greenhouse_manager/ops/t1_clean_service_credential_bundle.py
infra/n3w-t1/production/docker-compose.fresh.yml
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
tests/tools/test_n3w_t1_fresh_product_bootstrap.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_clean_product_deployment_gate.py
tools/execution_packages/n3w/kf098/t1_live_cutover/TASK.md
docs/development/N3W_T1_FRESH_BOOTSTRAP_R4_DOCKER29_CROSS_STORE_IMAGE_IDENTITY_ASTRA_SOURCE_REVIEW_BRIEF_20261012.md
docs/development/N3W_T1_FRESH_BOOTSTRAP_R4_ASTRA_BLOCKERS_SOURCE_REPAIR_PROGRESS_20261012.md
docs/development/N3W_T1_FRESH_BOOTSTRAP_R3_DOCKER29_CROSS_STORE_IMAGE_IDENTITY_SOURCE_REPAIR_20261012.md
docs/development/N3W_T1_FRESH_BOOTSTRAP_R3_POSTCLAIM_FIRST_IMAGE_LOAD_FORENSIC_20261012.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
~~~

## 3. Exact CI state

~~~text
EXACT_HEAD=dec88fdc19daf50185d09acf4a38db8c18816ef2
TOTAL=25
PASS=25
FAIL=0
IN_PROGRESS=0
QUEUED=0
~~~

Critical PASS:

~~~text
N3W T1 fresh bootstrap deployable payload CI
N3W T1 fresh install exact ARM64 CI
N3W T1 fresh install host-only CI
N3W T1 production stack staging payload CI
N3W T1 S20 production image binding CI
N3W T1 deployment gate CI
greenhouse-manager CI
M2 manager runtime secret ownership CI
Public repository safety CI
~~~

CI green is necessary but must not be treated as Docker 29 live proof.

## 4. Authorization state

~~~text
_03=CLAIMED_CONSUMED_NO_REPLAY
_04=SUPERSEDED_UNGRANTED
_05=SUPERSEDED_UNGRANTED
_06=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_06
_06_GRANTED=false
_06_CLAIMED=false
_06_CONSUMED=false
~~~

R2 closure review must not authorize _06.

## 5. F1 — portable exact image identity

Previous blocker: RootFS-only runtime identity was too weak because identical filesystem layers can have behavior-changing Config differences.

Current source binds:

~~~text
exact image tar SHA256
Docker archive manifest.json SHA256
selected Docker archive record SHA256
saved config-object digest
ordered RootFS diff-id fingerprint
normalized behavior-relevant Config contract
exact image tag
Architecture=arm64
Os=linux
~~~

Behavior-relevant Config fields:

~~~text
Entrypoint
Cmd
User
Env
WorkingDir
Labels
Healthcheck
StopSignal
Volumes
ExposedPorts
~~~

The archive and build-side inspect must agree before payload freeze. Target runtime does not require runtime .Id == Docker-28 build/config .Id. It instead requires exact RootFS + normalized Config contract + platform/tag binding. Docker null/empty representation differences are normalized only for semantically empty field forms.

The exact deployable-payload CI passes this path.

R2 question:

~~~text
F1=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

If OPEN, identify the exact unbound behavior or identity surface.

## 6. F2 — DynSec/Broker volume lifecycle

Previous blocker: the Mosquitto image-declared /mosquitto/log path could create an anonymous volume that survived temporary container removal.

Current source:

~~~text
temporary DynSec Broker: --tmpfs /mosquitto/log
temporary container removal: docker rm -f -v
production fresh Compose: tmpfs /mosquitto/log
precommit rehearsal: Docker volume set must remain unchanged
~~~

R2 question: verify all temporary Broker/Manager paths relevant to fresh bootstrap have bounded storage lifecycle and no path can recreate the anonymous-volume leak before stopped postcheck.

~~~text
F2=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

## 7. F3 — credential-bundle immutability

Previous blocker: staging appended GH_MANAGER_IMAGE to the manager credential runtime.env, mutating a manifest-bound credential artifact.

Current source preserves:

~~~text
/opt/greenhouse-secrets/mqtt/manager/runtime.env
~~~

Compose-only runtime selection is separately staged at:

~~~text
/etc/n3wfc4/docker-compose.env
~~~

Precommit rehearsal invokes the exact Manager credential verifier after staging and requires node_credential_count=0, credential bundle valid, GH_MANAGER_IMAGE absent from credential runtime.env, and the compose env equal to credential env plus GH_MANAGER_IMAGE only.

R2 question: verify no other fresh-bootstrap path mutates credential-manifest-bound files after creation and all Compose/deployment-gate consumers use the new env consistently.

~~~text
F3=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

## 8. F4 — durable one-shot no-replay authority

Previous blocker: the old claim marker lived only inside the temporary payload directory, so the same authorization ID could be claimed again in a new payload directory.

Current source creates:

~~~text
/var/lib/n3w-fresh-bootstrap-authorizations/
<sha256(authorization_id)>.json
~~~

Properties:

~~~text
directory mode 0700
record mode 0600
owner = executing root user on real apply
O_EXCL creation
O_NOFOLLOW when available
file fsync
directory fsync
binds authorization_id
binds source_head
binds payload_manifest_sha256
~~~

The apply path checks the durable ledger before mutation. The host wrapper uses the durable record as the post-error claim/consume oracle. A regression test proves that payload directory B cannot reuse an authorization already claimed by payload directory A.

R2 must inspect crash/error windows and answer:

1. durable ledger is established before mutation;
2. duplicate authorization cannot create a second record;
3. host wrapper cannot classify a durable claim as replayable;
4. cleanup never removes the ledger record;
5. payload-local marker is not the sole postclaim authority.

~~~text
F4=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

## 9. F5 — Docker 29/containerd capacity admission

Previous blocker: the old budget used Docker-28 image inspect Size as if it completely described target disk amplification.

Current admission model conservatively accounts for:

~~~text
extracted payload
+ imported content-store bytes estimated from exact tar sizes
+ unpacked snapshot bytes estimated from loaded image sizes
+ 5 GiB minimum post-peak reserve
~~~

It also checks /var/tmp, DockerRootDir and detected DockerRootDir/containerd device identity and free bytes, requires the same filesystem, and uses the minimum free-space authority.

A capacity failure must stop before payload transfer, mutation or claim.

R2 question: determine whether this is conservative enough for the exact Docker 29.7.1/containerd target. Rejecting the current T1 is acceptable if reserve is insufficient.

~~~text
F5=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

If OPEN, state the exact under-count, double-count or missing store component.

## 10. F6 — safe postclaim failure observability

Previous blocker: R3 exposed only generic fresh_install_failed.

Current source tracks the active stage and exposes bounded structured fields:

~~~text
failed_stage
failure_code
cleanup_result
authorization_claimed
authorization_consumed
replay_allowed
~~~

Human-readable compatibility remains:

~~~text
fresh_install_failed
fresh_install_failed_and_cleanup_not_proven
~~~

Preclaim FreshInstallerError specificity is preserved. Raw subprocess stdout/stderr is not promoted into the structured result.

R2 question: verify this is sufficient to classify a failed one-shot without leaking generated passwords, setup material, private broker data or arbitrary subprocess text.

~~~text
F6=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

## 11. A8 — artifact download reliability

R3 had two Mac-side gh run download failures before payload transfer. The previous manual fallback is now repository-owned.

The host wrapper requires:

~~~text
artifact run ID
artifact name
artifact ID
GitHub artifact ZIP SHA256
~~~

It validates artifact metadata, tries gh run download, and on transport failure uses the GitHub artifact endpoint to obtain a temporary HTTPS redirect, downloads the ZIP, verifies whole ZIP SHA256, safely extracts the exact six-file outer set, then continues through the existing wrapper/archive/manifest binding.

The GitHub bearer token is sent only to api.github.com, not the redirected blob URL.

No T1 operation occurs before local artifact verification.

R2 question: confirm the fallback changes transport only and cannot weaken source/artifact/executor identity.

~~~text
A8=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

## 12. Downstream fresh-staging scan

R3 never got beyond first image binding on the real T1. Re-scan current exact source for source-visible blockers in:

~~~text
load all three images
identity creation
fresh state creation
Broker materials
DynSec provisioning
credential verification
runtime staging
same-filesystem commit
systemd daemon-reload
Compose v5.4 rendering
deployment gate
stopped postcheck
isolated Manager audit
cleanup after failures in every stage
~~~

Do not call something a blocker solely because real-T1 live revalidation is still pending. Distinguish source-visible blocker from live-revalidation-required.

~~~text
DOWNSTREAM_SOURCE_BLOCKER=YES | NO
~~~

If YES, give exact path/function and concrete failure mode.

## 13. Required output

Return this exact decision structure, then concise evidence:

~~~text
REVIEW_SOURCE_HEAD=
PR_HEAD_AT_REVIEW=
CI_STATE=

F1=
F2=
F3=
F4=
F5=
F6=
A8=
DOWNSTREAM_SOURCE_BLOCKER=

NEW_BLOCKERS=

R6_PRELIVE_RECOMMENDATION=
BLOCK
or
PROCEED_TO_ARTIFACT_BINDING_AND_READONLY_PREFLIGHT

R6_LIVE_APPLY_RECOMMENDATION=
NOT_YET_AUTHORIZED

MERGE_RECOMMENDATION=
NO_MERGE

REQUIRED_SOURCE_REPAIRS=
REQUIRED_TESTS=
REQUIRED_PRELIVE_STEPS=
~~~

For every OPEN finding, cite the exact file/function/source fragment and explain whether it blocks the next prelive stage.

## 14. Closure threshold

Recommend PROCEED_TO_ARTIFACT_BINDING_AND_READONLY_PREFLIGHT only if:

1. F1-F6 are all CLOSED;
2. A8 has no blocker;
3. no new source-visible downstream blocker exists;
4. exact-head CI remains 25/25 PASS;
5. _06 remains ungranted.

Even with closure PASS, the only next steps are:

~~~text
bind replacement exact artifact
→ define bounded cleanup of retained R3 payload
→ real T1 minimal-baseline read-only inventory
→ real T1 transport/capacity preflight
→ review evidence
~~~

Only after those steps may a separate decision consider granting _06.
