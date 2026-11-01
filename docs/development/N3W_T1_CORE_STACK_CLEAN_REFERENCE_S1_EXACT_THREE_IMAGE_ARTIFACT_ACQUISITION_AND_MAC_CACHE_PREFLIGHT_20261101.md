# N3-W T1_Core_Stack Clean Reference — S1 exact three-image artifact acquisition and Mac cache preflight

Date: 2026-11-01

## 0. Gate

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_S1_EXACT_THREE_IMAGE_ARTIFACT_ACQUISITION_AND_MAC_CACHE_20261101_01

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64

SOURCE_REBUILD_REQUIRED=false
PREFERRED_EXISTING_ARTIFACT=true

RUN_ID=41275979177
ARTIFACT_ID=13070404405
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-24382caae4a1f5d459297f86e8d18f10a848ca64
ARTIFACT_SIZE_BYTES=2538800086
ARTIFACT_DIGEST=sha256:99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93
ARTIFACT_EXPIRED=false

TARGET_CACHE=MAC_PRIVATE_DURABLE_CACHE
T1_ACCESS=false
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

## 1. Required download result

The S1 Mac cache must retain the exact GitHub artifact payload for the S0 source authority.

The expected extracted artifact set is exactly:

```text
binding.json
greenhouse-manager-arm64.tar
homeassistant-arm64.tar
broker-arm64.tar
```

No other artifact member is accepted.

## 2. Binding requirements

The downloaded `binding.json` must prove:

```text
source_head=24382caae4a1f5d459297f86e8d18f10a848ca64

manager.image=local/greenhouse-manager:fresh-24382caae4a1
manager.platform=linux/arm64

homeassistant.image=local/n3w-homeassistant:2026.10.0-0c73235a
homeassistant.manifest_digest=sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4
homeassistant.platform=linux/arm64

broker.image=local/n3w-mosquitto:2.1.2-3184566d
broker.manifest_digest=sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
broker.platform=linux/arm64

fresh_runtime_identity_binding=true
node_credential_count=0
production_service_start=false
secret_values_included=false
t1_access=false
board_access=false
```

## 3. Local byte verification

S1 must verify every tar file against the SHA-256 recorded in `binding.json`:

```text
greenhouse-manager-arm64.tar -> manager.tar_sha256
homeassistant-arm64.tar      -> homeassistant.tar_sha256
broker-arm64.tar             -> broker.tar_sha256
```

The local artifact must also preserve the source-head and image identity bindings above.

## 4. Durable cache layout

Recommended private Mac cache class:

```text
~/Documents/N3W/t1-core-stack-cache/
  24382caae4a1f5d459297f86e8d18f10a848ca64/
    binding.json
    greenhouse-manager-arm64.tar
    homeassistant-arm64.tar
    broker-arm64.tar
```

The expanded username/path is private operational information and must not be committed to the
public repository.

## 5. GitHub artifact identity

Before local acquisition, GitHub authority must still report:

```text
artifact_id=13070404405
expired=false
workflow_run.head_sha=24382caae4a1f5d459297f86e8d18f10a848ca64
digest=sha256:99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93
```

If any of those fields drift, STOP and reassess rather than silently rebuilding or accepting a
different artifact.

## 6. Stop point

```text
STOP_AFTER=MAC_EXACT_THREE_IMAGE_CACHE_VERIFIED
AUTO_T1_DEPLOYMENT=false
```

S1 ends with a durable, exact, locally verified three-image cache on Mac. No Docker image is
loaded to T1_B during this gate.
