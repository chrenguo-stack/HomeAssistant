# N3-W T1 fresh bootstrap R4 Docker 29 cross-store image identity — Astra independent source review brief（2026-10-12）

## 1. Review mission

Please independently review the current N3-W T1 fresh-product bootstrap repair before any successor real-T1 one-shot authorization is granted.

The primary question is not merely whether the immediate Docker 28→29 image-ID failure was correctly diagnosed. The review must answer:

> Is the exact current source strong enough to justify spending the next one-shot live authorization on a real minimal-host T1, or are there still source-level blockers that should be closed first?

This review is source/CI/documentation only.

~~~text
READ_ONLY_REVIEW=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
MERGE=false
SUCCESSOR_AUTHORIZATION_GRANTED=false
~~~

## 2. Exact authority to bind first

Repository:

~~~text
chrenguo-stack/HomeAssistant
PR=541
BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010
PR_STATE=OPEN_DRAFT
~~~

Product/source authority to review:

~~~text
PRODUCT_SOURCE_HEAD=c263b9df6bac900332d27a50a66dd603d7d5e1e4
PRODUCT_SOURCE_PARENT=c117c3c65d553043ddd88ced6acccfdf5159fd36
PRE_REPAIR_EVIDENCE_HEAD=68eebb51fb9ad1db46e36bb76dfce50596119d12
~~~

The docs-only commit created by this review brief is not product execution authority. Fresh-rebind PR #541 and confirm that the product delta being reviewed is still rooted at c263b9df....

Primary files:

~~~text
tools/n3w_t1_fresh_product_bootstrap.py
tools/n3w_t1_fresh_product_staging_host.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
tests/tools/test_n3w_t1_fresh_product_bootstrap.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_clean_product_deployment_gate.py
~~~

Relevant prior project authority:

~~~text
tools/execution_packages/n3w/kf098/t1_live_cutover/TASK.md
docs/development/N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_PRECLAIM_REMOTE_EXTRACT_SOURCE_REPAIR_20261012.md
docs/development/N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_PAYLOAD_FILE_SET_INVALID_SOURCE_REPAIR_20261012.md
docs/development/N3W_T1_FRESH_BOOTSTRAP_R3_POSTCLAIM_FIRST_IMAGE_LOAD_FORENSIC_20261012.md
docs/development/N3W_T1_FRESH_BOOTSTRAP_R3_DOCKER29_CROSS_STORE_IMAGE_IDENTITY_SOURCE_REPAIR_20261012.md
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
docs/development/N3W_CURRENT_STATE.md
docs/development/N3W_CURRENT_STATE_INDEX.md
~~~

## 3. Live history that must not be reinterpreted

### 3.1 R1 / authorization _01 — remote extractor syntax failure

The first live apply stopped before claim because generated remote Python was syntactically invalid.

~~~text
AUTHORIZATION=_01
CLAIMED=false
CONSUMED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
~~~

Repair introduced a multiline remote extractor plus exact generated-program compile/execute regressions. KF-109 has subsequently been live-revalidated because a later run successfully executed the repaired extractor and reached deeper bootstrap logic.

### 3.2 R2 / authorization _02 — payload file-set invalid

The second real apply successfully passed repaired remote extraction, then stopped before claim at:

~~~text
reason=payload_file_set_invalid
HOST_STATUS=STOP_PRECLAIM
CLAIMED=false
CONSUMED=false
REMOTE_PAYLOAD_REMOVED=true
~~~

Root cause: deployable workflow froze the payload manifest, then imported the bootstrap module from the payload tree, allowing Python bytecode to create a post-manifest __pycache__/*.pyc. The archive then included an unmanifested regular file.

Repair:

~~~text
PYTHONDONTWRITEBYTECODE=1
post-rehearsal final bootstrap self-check
explicit pycache regular-file rejection before archive
~~~

### 3.3 R3 / authorization _03 — artifact transport x2, then postclaim image binding failure

Two attempts first stopped locally before claim because Mac gh run download failed following the Actions artifact blob redirect.

Both attempts proved:

~~~text
CLAIMED=false
CONSUMED=false
PAYLOAD_TRANSFER=false
DOCKER_MUTATION=false
REMOTE_PAYLOAD_PRESERVED=false
~~~

The same authorization was therefore still valid before claim.

A manual transport-only fallback then downloaded the official GitHub Actions artifact using the REST redirect plus resumable curl and proved the complete ZIP digest before extracting the exact six-file artifact set.

~~~text
ARTIFACT_DOWNLOAD=PASS
ARTIFACT_ZIP_SHA256=03098b8cf5e30a4ca485da52e9e752054226b6718f3a5bf7e26b78cc88612689
ARTIFACT_OUTER_EXTRACT=PASS
~~~

The artifact-owned exact host wrapper then executed the original apply logic.

R3 durably claimed:

~~~text
AUTHORIZATION_ID=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_03
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false
~~~

It then failed with:

~~~text
BOOTSTRAP_STATUS=STOP_PARTIAL
BOOTSTRAP_REASON=fresh_install_failed
HOST_STATUS=STOP_PARTIAL
REMOTE_PAYLOAD_PRESERVED=true
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
~~~

The authorization is permanently consumed and must never be replayed.

## 4. R3 cleanup and failure-domain proof

Independent post-failure real-T1 inventory proved rollback to the minimal-host baseline:

~~~text
STATUS=PASS
INVENTORY_SHA256=e38273381de031789fff2f5c2fb37725c328cfaa9710603b6c74ba920422842d
CONTAINERS=0
IMAGES=0
VOLUMES=0
NETWORKS=bridge,host,none
PRODUCT_PATHS_PRESENT=0
PRODUCT_UNITS=0
PRODUCT_LISTENERS=0
UNKNOWN_STOP=0
DELETE_PRODUCT_STATE_CANDIDATE=0
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
~~~

No candidate transaction directories remained.

The retained claimed payload is intentionally preserved:

~~~text
REMOTE_PAYLOAD=n3w-fresh-bootstrap.EOmzn8
SOURCE_HEAD=1f191b264f246254ac1f1cb97cd38dc942f13021
AUTHORIZATION_MARKER=true
HOMEASSISTANT_TAR_PRESENT=true
HOMEASSISTANT_TAR_SIZE=2448553472
MANAGER_TAR_PRESENT=true
MANAGER_TAR_SIZE=59296768
BROKER_TAR_PRESENT=true
BROKER_TAR_SIZE=27556352
~~~

Docker events then proved the first Home Assistant image actually loaded:

~~~text
CLAIM_UTC=2026-10-12T07:10:48.678811+00:00
HA_IMAGE_LOAD_EPOCH=1791789413
HA_IMAGE_LOAD_LOCAL≈2026-10-12T15:16:53+08:00
HA_RUNTIME_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
HA_UNTAG_DELETE_EPOCH=1791789437
HA_UNTAG_DELETE_LOCAL≈2026-10-12T15:17:17+08:00
~~~

Artifact/CI expected build/config ID:

~~~text
HA_EXPECTED_BUILD_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
~~~

No storage/OOM/kernel evidence was observed. Current storage after cleanup was healthy.

Therefore:

~~~text
DOCKER_LOAD_TIMEOUT=false
ENOSPC=false
OOM=false
FIRST_IMAGE_LOAD_COMPLETED=true
SINGLE_ID_EQUALITY_FAILED=true
CLEANUP_COMPLETED=true
~~~

## 5. Docker-store evidence

The exact R3 deployable workflow ran on:

~~~text
CI_DOCKER_SERVER=28.0.4
~~~

Real T1:

~~~text
T1_DOCKER_SERVER=29.7.1
T1_ARCH=aarch64
T1_STORAGE_DRIVER=overlayfs
~~~

Docker upstream states that image ID representation differs between the legacy graphdriver store and containerd image store: the former uses the image config hash, while containerd may expose a manifest or index/manifest-list identity.

This repository had already frozen the same engineering rule during KF-098:

~~~text
Docker's classic image store may expose the config digest as image .Id.
Docker with the containerd image store may expose the OCI manifest digest as image .Id.
Therefore the live executor must not assume one representation is universal.
~~~

KF-098 also used architecture/OS plus artifact-owned RootFS fingerprint as part of runtime binding.

## 6. Current R4 source repair at c263b9df...

Successor authorization has been rotated:

~~~text
PREDECESSOR=_03
PREDECESSOR_CLAIMED=true
PREDECESSOR_CONSUMED=true
PREDECESSOR_REPLAY=false

SUCCESSOR=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_04
SUCCESSOR_GRANTED=false
SUCCESSOR_CLAIMED=false
SUCCESSOR_CONSUMED=false
~~~

The deployable workflow now records for each exact image:

~~~text
tar_sha256
tar_size_bytes
loaded_size_bytes
image_id
platform
rootfs_layers_sha256
~~~

The RootFS fingerprint is SHA-256 of the canonical JSON serialization of the ordered docker image inspect RootFS.Layers list.

Current runtime validation:

~~~text
exact payload/manifest file binding
exact image tar SHA binding
docker load from local exact tar
exact tag inspection
runtime .Id must be syntactically sha256:<64hex>, but need not equal CI build .Id
Architecture=arm64
Os=linux
ordered RootFS.Layers fingerprint must equal artifact-frozen value
~~~

After each load, the runtime binding is stored.

Stopped postcheck now:

~~~text
requires zero containers
requires exactly three Docker images
re-inspects each exact image tag
re-validates platform + RootFS fingerprint
requires postcheck binding == binding captured immediately after load
requires zero volumes
requires only bridge/host/none networks
requires no product listeners
requires product firewall inactive
requires guard unit loaded but inactive/not-enabled
requires exact staged product paths
renders Compose
runs deployment gate
runs fresh-state isolated Manager audit with node credential counts == 0
~~~

Regression coverage added:

~~~text
accept containerd-style runtime .Id different from build/config ID when RootFS exact
reject RootFS fingerprint drift
workflow must freeze rootfs_layers_sha256
workflow emits FRESH_CROSS_STORE_IMAGE_BINDING=PASS
~~~

A stale test fixture still expected _03 on the first repair commit; that was the only failing test (55 PASS / 1 FAIL) and was corrected in c263b9df....

## 7. Current CI snapshot

At review-brief creation time:

~~~text
EXACT_HEAD=c263b9df6bac900332d27a50a66dd603d7d5e1e4
TOTAL=25
PASS=19
IN_PROGRESS=6
FAIL=0
QUEUED=0
~~~

Already PASS includes:

~~~text
N3W T1 fresh install host-only CI
Public repository safety CI
N3W T1 deployment gate CI
~~~

Still running at that snapshot includes:

~~~text
N3W T1 fresh bootstrap deployable payload CI
N3W T1 fresh install exact ARM64 CI
N3W T1 S20 production image binding CI
N3W T1 production stack staging payload CI
M2 node auth board lab CI
C-07 node retirement CI
~~~

Astra must fresh-rebind CI rather than treating this snapshot as final.

## 8. Independent review questions A1–A8

### A1 — Cross-store identity semantics

Is replacing strict CI-build .Id equality with an ordered RootFS.Layers fingerprint technically sound across the exact Docker 28 CI → Docker 29.7.1 containerd-store T1 path?

Specifically verify whether docker image inspect RootFS.Layers is a stable cross-store semantic for an exact single-platform image loaded from the same tar.

Classification required:

~~~text
A1=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

### A2 — Binding strength / config-identity gap

Does the current runtime contract become too weak by accepting any syntactically valid runtime .Id as long as tag + platform + RootFS layers match?

Consider images with identical filesystem layers but different OCI config such as:

~~~text
Entrypoint
Cmd
User
Env
WorkingDir
Labels
Healthcheck
StopSignal
~~~

The artifact tar itself is SHA-bound before load, but assess whether runtime and stopped-postcheck should additionally freeze/verify artifact-owned config digest, OCI manifest digest, selected immutable Config fields, or another portable identity.

Do not accept “the tar was exact” as sufficient without analyzing post-load/postcheck substitution or representation risks.

~~~text
A2=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

### A3 — Build-side authority and manifest/index ambiguity

The CI still asserts item["Id"] == record["image_id"] while building the artifact on Docker 28, then stores RootFS fingerprint.

Review whether the artifact should explicitly freeze:

~~~text
config digest
single-platform manifest digest
index/list digest when applicable
RootFS fingerprint
~~~

for all three images.

Check Home Assistant and Broker source pinning versus Manager local build semantics.

~~~text
A3=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

### A4 — load_images / stopped_postcheck completeness

Search the entire fresh-install path for residual assumptions that Docker runtime image IDs equal build/config IDs.

At minimum review:

~~~text
LiveFreshInstallerAdapters.load_images()
LiveFreshInstallerAdapters.stopped_postcheck()
image-lock handling
clean product deployment gate
Compose rendering
manager/broker/HA references
cleanup image removal
~~~

Also verify whether “exactly three images” has identical meaning under the real Docker 29 containerd store and whether the exact tags are sufficient to rule out unwanted additional runtime content.

~~~text
A4=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

### A5 — Failure/cleanup/no-replay safety

Verify that the cross-store repair did not weaken:

~~~text
durable authorization claim
one-shot consume semantics
no replay after claim
transaction-owned cleanup only
rollback to minimal host
production_service_start=false
board_access=false
~~~

R3 empirically proved cleanup after the first image binding failure. Check source paths for failures later in:

~~~text
identity
state
broker material
DynSec
runtime staging
commit
stopped postcheck
~~~

~~~text
A5=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

### A6 — Unexercised downstream blockers before another one-shot

R3 never progressed beyond first-image binding.

Perform a source-level adversarial review of every later fresh staging step to identify blockers that can be found without spending _04.

Pay special attention to real T1 differences that host-only/Docker-28 CI may not model:

~~~text
UID/GID ownership
Docker 29 containerd behavior
isolated docker run --network none
Mosquitto DynSec temporary container
systemd daemon-reload
atomic rename/same-filesystem commit
Compose v5.4.0 rendering
stopped postcheck
Manager isolated audit
Armbian OS 26.05 / Ubuntu resolute
~~~

If another live-only blocker is foreseeable, classify it before authorizing _04.

~~~text
A6=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

### A7 — Failure observability before spending another authorization

The R3 underlying image-binding exception was collapsed by fresh_installer.py into generic:

~~~text
fresh_install_failed
~~~

The root cause had to be reconstructed from retained payload + Docker events.

Assess whether R4 should add stage-safe structured failure diagnostics before the next live run, for example:

~~~text
failed_stage
bounded non-secret failure class
cleanup_result
~~~

without exposing generated secrets or compromising transaction safety.

The review should answer whether this is:

~~~text
required before _04
recommended but nonblocking
not needed
~~~

### A8 — Artifact download reliability and execution-path integrity

The repository host wrapper still uses:

~~~text
gh run download
~~~

R3 experienced two consecutive local failures while following the GitHub Actions artifact blob redirect.

The successful third path used an out-of-band transport-only fallback:

~~~text
GitHub REST artifact endpoint
→ temporary redirect
→ curl IPv4/http1.1
→ complete artifact ZIP SHA256 exact match
→ safe exact six-file extraction
→ artifact-owned host-wrapper execution
~~~

Review whether the official R4 source must incorporate a bounded, integrity-preserving fallback before another one-shot authorization, instead of relying on a manual wrapper substitution.

Any proposed fallback must preserve:

~~~text
artifact ID/name/source binding
whole ZIP digest binding when available
exact outer file set
host-wrapper SHA binding
payload archive SHA binding
payload manifest SHA binding
no T1 mutation before all local validation passes
~~~

~~~text
A8=CLOSED | OPEN_BLOCKER | OPEN_NONBLOCKER
~~~

## 9. Required Astra output

Please return a concise but complete independent review in this structure:

~~~text
REVIEW_SOURCE_HEAD=
PR_HEAD_AT_REVIEW=
CI_STATE=

A1=
A2=
A3=
A4=
A5=
A6=
A7=
A8=

MERGE_RECOMMENDATION=NO_MERGE | SOURCE_OK_BUT_LIVE_PENDING
R4_LIVE_APPLY_RECOMMENDATION=BLOCK | PROCEED_AFTER_LISTED_REPAIRS | PROCEED_AFTER_CI_AND_PREFLIGHT

BLOCKERS=
NONBLOCKING_FINDINGS=
REQUIRED_SOURCE_REPAIRS=
REQUIRED_TESTS=
REQUIRED_PRELIVE_STEPS=
~~~

For every OPEN finding, cite exact file/function/line or a precise source fragment and explain the concrete failure mode.

Do not treat passing CI as proof of Docker 29 live compatibility.

Do not recommend replaying _03.

Do not authorize or perform T1 mutation.

Do not merge PR #541.

## 10. Desired decision threshold

The target is not “the patch probably fixes the observed failure.”

The threshold for allowing the next one-shot real-T1 attempt is:

> No source-visible blocker remains in artifact identity, Docker-29 compatibility, transaction safety, failure observability required for recovery, or artifact acquisition; exact CI and fresh read-only T1 preflight must pass after all required repairs.

The next live authorization remains:

~~~text
N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_04
GRANTED=false
CLAIMED=false
CONSUMED=false
~~~
