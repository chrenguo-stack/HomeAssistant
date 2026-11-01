# N3-W T1_Core_Stack Clean Reference — R1 S1 image authority / deployable divergence blocker

Date: 2026-11-01

## 0. Result

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_S1_IMAGE_AUTHORITY_AND_DEPLOYABLE_DIVERGENCE_REVIEW_20261101_01

S1_RESULT=CLOSED_PASS
R1_LIVE_APPLY_AUTHORIZED=false

SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64

S1_MANAGER_IMAGE_ID=sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8
DEPLOYABLE_MANAGER_IMAGE_ID=sha256:1b97cba4a63a1c6c7f714b15f89b6859dc68cb2d6236f2eb7c52ea6689ecccd3
MANAGER_IMAGE_ID_MATCH=false

BLOCKER=INDEPENDENT_REBUILD_BREAKS_EXACT_IMAGE_CONTINUITY
SOURCE_REPAIR_REQUIRED=true
```

## 1. S1 exact image authority

S1 locally verified the exact three-image artifact produced by exact ARM64 run
`41275979177`, artifact `13070404405`.

The durable Mac cache binds Manager to:

```text
image=local/greenhouse-manager:fresh-24382caae4a1
image_id=sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8
tar_sha256=4c308f192a30e628ebacad11ed3aa471554fee6c3aa9fd1c25ec647d354a5006
tar_size_bytes=62688256
```

This exact artifact, not a later rebuild, is the Clean Reference image authority.

## 2. Same source head does not imply same Manager image

The separate fresh deployable workflow run `41275979325` also checked out exactly:

```text
24382caae4a1f5d459297f86e8d18f10a848ca64
```

but independently rebuilt Manager and produced:

```text
image=local/greenhouse-manager:fresh-24382caae4a1
image_id=sha256:1b97cba4a63a1c6c7f714b15f89b6859dc68cb2d6236f2eb7c52ea6689ecccd3
```

Therefore source-head equality alone is insufficient to prove Manager image byte identity.

For Clean Reference:

```text
SOURCE_AUTHORITY != IMAGE_ARTIFACT_AUTHORITY

SOURCE_AUTHORITY=exact repository source head
IMAGE_ARTIFACT_AUTHORITY=S1 exact binding + image ID + tar SHA256
```

## 3. Why the existing deployable artifact cannot be used for R1

The deployable workflow artifact is internally self-consistent and its CI is PASS, but it is
bound to the independently rebuilt Manager image above.

Using it for R1 would mean:

```text
S1 verifies image A
R1 deploys independently rebuilt image B
```

That violates the required Clean Reference continuity:

```text
VERIFY_EXACT_IMAGE
-> CACHE_EXACT_IMAGE
-> DEPLOY_THE_SAME_EXACT_IMAGE
```

The existing deployable artifact therefore remains valid historical/build evidence but is not
eligible for this Clean Reference R1 deployment.

## 4. Production V2 wrapper is also not the R1 authority

Current production apply requires external V2 run context and a durable production STARTED
marker. Those are production-process authorization semantics.

Clean Reference R1 is a controlled engineering baseline establishment, not a production V2 run.
It must not fabricate or weaken production marker semantics merely to reach the existing apply
entry point.

The underlying stopped-state business primitive already exists:

```text
fresh_installer.run_fresh_staging()
```

and provides:

- exact minimal-host preflight;
- offline image load;
- fresh identity/state/Broker/DynSec construction;
- runtime/source/network staging;
- atomic commit;
- stopped postcheck;
- zero node credentials;
- zero product listeners;
- production_service_start=false;
- activation_authorized=false;
- transaction-owned cleanup on failure.

R1 should expose this primitive through a separate Clean Reference entry point.

## 5. Required source convergence

The next source repair must enforce:

```text
ONE_IMAGE_BUILD
-> S1 exact image artifact
-> durable Mac image cache
-> runtime payload built around those exact image bindings
-> R1 local-cache deployment
```

It must not rebuild Manager.

Required architecture:

```text
S1 exact local image cache
  + exact S0 runtime source
  -> exact runtime-only payload
  -> Clean Reference preflight
  -> Clean Reference stopped-state apply
```

Production V2 apply remains unchanged and continues to require its own marker/run-context
authority.

## 6. Safety boundary

```text
T1_ACCESS=false
T1_MUTATION=false
R1_LIVE_APPLY=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
T1_A_MUTATION=false
```

No physical R1 command is authorized until the local-cache deployment source path is
implemented, reviewed and CI-green.
