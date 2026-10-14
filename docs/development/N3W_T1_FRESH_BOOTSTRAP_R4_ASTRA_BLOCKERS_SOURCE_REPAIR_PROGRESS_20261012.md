# N3-W T1 fresh bootstrap R4 Astra blockers source repair progress（2026-10-12）

## Gate

~~~text
TASK=N3W_T1_FRESH_BOOTSTRAP_R4_ASTRA_FINDINGS_SOURCE_REPAIR_20261012_01
STATUS=SOURCE_REPAIR_CI_PENDING
PR=541
PR_STATE=OPEN_DRAFT
MERGE=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
~~~

## Review authority

~~~text
ASTRA_REVIEW_SOURCE_HEAD=c263b9df6bac900332d27a50a66dd603d7d5e1e4
ASTRA_RESULT=BLOCK
ASTRA_BLOCKERS=F1,F2,F3,F4,F5,F6
~~~

## Current repaired product source

~~~text
PRODUCT_SOURCE_HEAD=3e88e41aa19d6612226205aba3be5e696b01b835
PREDECESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_04
PREDECESSOR_GRANTED=false
PREDECESSOR_STATUS=SUPERSEDED_UNGRANTED

SUCCESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_05
SUCCESSOR_GRANTED=false
SUCCESSOR_CLAIMED=false
SUCCESSOR_CONSUMED=false
~~~

## Repair mapping

### F1 — portable exact image identity

The payload now freezes and validates exact image tar SHA256, Docker-archive manifest SHA256, selected Docker-archive record SHA256, artifact config digest, selected runtime Config contract SHA256, ordered RootFS.Layers SHA256, arm64/linux, and exact image tag.

The build step proves the saved config bytes hash to the build/config image identity and proves RootFS/Config semantic equality between the archive and build-side inspect. Runtime no longer treats one Docker .Id representation as cross-store authority; it must reproduce the artifact-owned runtime Config and RootFS contract.

### F2 — DynSec and Broker log volume lifecycle

The temporary DynSec Broker now uses an explicit /mosquitto/log tmpfs and removal includes -v. The production fresh Compose also declares /mosquitto/log as tmpfs. Rehearsal asserts the Docker volume set is unchanged.

### F3 — credential bundle immutability

The repository no longer appends GH_MANAGER_IMAGE into the manifest-bound credential bundle.

The untouched credential runtime environment remains at:

~~~text
/opt/greenhouse-secrets/mqtt/manager/runtime.env
~~~

A separate deployment/Compose environment is staged at:

~~~text
/etc/n3wfc4/docker-compose.env
~~~

The precommit rehearsal invokes the exact Manager-side credential verifier after staging and asserts the bundle remains valid.

### F4 — durable no-replay authority

Claim state is moved outside the disposable payload directory:

~~~text
/var/lib/n3w-fresh-bootstrap-authorizations/<sha256(authorization_id)>.json
~~~

The record is atomic, mode 0600, under a mode-0700 ledger directory, fsynced, and binds authorization_id, source_head, and payload_manifest_sha256. A second payload directory using the same authorization is rejected. The host wrapper probes this durable record as claim/consume authority.

### F5 — Docker 29/containerd capacity admission

The capacity model no longer treats Docker-28 image inspect Size as the entire load peak. It conservatively accounts for current extracted payload + imported content-store bytes estimated from exact tar sizes + unpacked snapshot bytes estimated from loaded image sizes + 5 GiB post-peak reserve.

Preflight also verifies staging, Docker root and detected containerd root reside on the same filesystem and uses the minimum reported free space.

This may intentionally reject the current small T1 storage before any live claim. A capacity STOP is preferable to spending a one-shot authorization with an unproven reserve.

### F6 — safe failure observability

The fresh-installer contract now tracks a bounded stage and emits safe failed_stage, failure_code, cleanup_result, authorization_consumed and replay_allowed fields. Raw secret-bearing subprocess detail is not promoted into the structured live result.

## Artifact download reliability

The host wrapper now requires exact artifact metadata including ID and ZIP SHA-256. It tries the normal GitHub CLI download first. If that transport fails, it uses the GitHub artifact endpoint, obtains the temporary redirect without forwarding the GitHub token to the blob host, downloads with curl, verifies the complete ZIP SHA-256, rejects unsafe ZIP members, requires the exact six-file outer set, then continues through the existing wrapper/archive/manifest binding.

No T1 operation occurs before local artifact verification.

## Current stop condition

~~~text
EXACT_HEAD_CI=RUNNING
REPLACEMENT_ARTIFACT=NOT_YET_AUTHORITY
T1_PREFLIGHT=NOT_RUN_FOR_THIS_SOURCE
ASTRA_REVIEW_R2=NOT_RUN
LIVE_AUTHORIZATION=_05_NOT_GRANTED
~~~

Do not clean the preserved R3 payload or touch T1 until exact source CI is understood and a bounded cleanup/preflight plan is frozen.
