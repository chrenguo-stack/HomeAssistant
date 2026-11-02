# N3-W T1_Core_Stack Clean Reference — R1 local exact image-cache deployment source design

Date: 2026-11-01

## 0. Gate

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_LOCAL_EXACT_IMAGE_CACHE_DEPLOYMENT_SOURCE_DESIGN_20261101_01

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
S1_RESULT=CLOSED_PASS

R1_LIVE_APPLY=false
SOURCE_DESIGN=true
SOURCE_REPAIR_ALLOWED=true
T1_ACCESS=false
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

## 1. Problem

S1 successfully froze and cached the exact three ARM64 images, but the existing fresh deployable
workflow independently rebuilds Manager. The second build has a different image ID despite using
the same repository source head.

Therefore R1 cannot use a deployable payload that contains newly rebuilt images.

## 2. Frozen authority hierarchy

R1 uses two separate authorities:

```text
SOURCE_AUTHORITY
= 24382caae4a1f5d459297f86e8d18f10a848ca64

IMAGE_AUTHORITY
= S1 binding.json
+ exact three local tar SHA256 values
+ exact image IDs
```

The runtime payload may be regenerated from exact source, but image tar files must never be
regenerated inside the R1 path.

## 3. Required data flow

```text
S1 exact-three-image artifact
        |
        +-> durable Mac image cache
        |
        +-> CI/runtime-payload builder consumes the same exact image artifact
              |
              +-> validates source head
              +-> validates exact image binding
              +-> loads image tars only for inspection if required
              +-> NEVER docker build
              +-> emits runtime-only payload bundle

Mac:
  exact runtime-only payload
  + S1 exact local image cache
        |
        +-> host wrapper cross-verifies both authorities
        +-> T1_B read-only preflight
        +-> one-at-a-time image transfer/load
        +-> Clean Reference stopped-state apply
```

## 4. Runtime-only builder

Add repository-owned builder:

```text
tools/n3w_t1_clean_reference_runtime_payload_builder.py
```

Inputs:

```text
--repository <exact source checkout>
--source-head <40-hex>
--image-root <exact-three-image artifact directory>
--destination <empty output directory>
```

Expected image-root files:

```text
binding.json
greenhouse-manager-arm64.tar
homeassistant-arm64.tar
broker-arm64.tar
```

The builder must fail closed if:

- source checkout is not exact source head;
- binding source head differs;
- file set differs;
- any tar size/SHA differs from binding.json;
- image platform is not linux/arm64;
- Manager image/ref/source binding differs;
- HA/Broker fixed digest identities differ;
- Docker archive config digest does not equal image_id;
- archive/config/rootfs binding cannot be proven.

The builder may `docker load` exact tar files in CI solely to obtain the same runtime image size
semantics used by the accepted deployable workflow. It must not build or pull an application
image.

Output directory contains only runtime/control material:

```text
runtime-payload.tar.gz
runtime-payload.sha256
payload-manifest.sha256
capacity-contract.json
capacity-contract.sha256
executor.sha256
host-wrapper.py
host-wrapper.sha256
host-baseline.py
host-baseline.sha256
image-set.json
runtime-binding.json
```

No image tar is duplicated into this runtime-only output.

`runtime-binding.json` and `image-set.json` bind the runtime payload to the exact S1 image
tar SHA/size/image IDs.

## 5. Runtime-only CI producer

Add manual/source-test workflow:

```text
.github/workflows/n3w-t1-clean-reference-runtime-payload-ci.yml
```

Manual production of the runtime bundle requires the exact S1 image artifact run/id.

For the current Clean Reference:

```text
IMAGE_RUN_ID=41275979177
IMAGE_ARTIFACT_ID=13070404405
SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
```

Workflow must prove the image artifact belongs to the same source head and is successful before
using it.

The workflow must not call `docker build` for Manager.

## 6. Host transport convergence

Extend:

```text
tools/n3w_t1_fresh_product_staging_host.py
```

with a Clean Reference local-split source mode.

Required operator inputs:

```text
--runtime-bundle-root <verified runtime-only bundle>
--image-cache-root <S1 durable image cache>
```

The host wrapper must:

1. verify runtime bundle exact file set and sidecars;
2. verify image cache exact file set and S1 binding;
3. cross-bind source head and three image records;
4. materialize the existing in-memory F3 work layout without copying/rebuilding images;
5. execute current transport/capacity checks;
6. preserve one-at-a-time image transfer;
7. never perform GitHub large-artifact download in local-split mode.

## 7. Clean Reference target entry point

Extend:

```text
tools/n3w_t1_fresh_product_bootstrap.py
```

with a separate Clean Reference phase, or add a thin dedicated wrapper around its existing
business primitive.

The target-side R1 apply must call:

```text
fresh_installer.run_fresh_staging()
```

and must not call production V2 claim/marker validation.

It requires an explicit Clean Reference confirmation value, but that confirmation is not
production authority and must not create or satisfy a production V2 marker.

Required output:

```text
fresh_product_staged=true
node_credential_count=0
product_listener_count=0
production_service_start=false
activation_authorized=false
board_access=false
```

## 8. Production separation

Production V2 behavior is frozen:

- `apply` still requires V2 run-context;
- production STARTED marker still required;
- production authorization ledger remains unchanged;
- Clean Reference confirmation cannot satisfy production checks;
- Clean Reference R1 cannot activate services.

This separation must be regression-tested.

## 9. R1 target end state

On R1 PASS:

```text
DOCKER_IMAGE_COUNT=3
T1_CORE_STACK_IMAGE_IDENTITY_EXACT=true

PRODUCT_RUNTIME_FILES_STAGED=true
FRESH_SYSTEM_ID_CREATED=true
FRESH_STATE_CREATED=true
BROKER_DYNSEC_CREATED=true
NODE_CREDENTIAL_COUNT=0

PRODUCT_CONTAINER_COUNT=0
PRODUCT_LISTENER_COUNT=0
PRODUCTION_SERVICE_START=false
ACTIVATION_AUTHORIZED=false
```

R1 stops here. R2/R3 later decide how controlled start/reboot/workload acceptance is performed.

## 10. Test requirements

Minimum tests:

1. runtime builder rejects source mismatch;
2. builder rejects image binding/tar SHA mismatch;
3. builder uses exact cached Manager image and never invokes build;
4. runtime output contains no image tar;
5. local split host mode rejects runtime/image source mismatch;
6. local split host mode rejects image tar SHA mismatch;
7. local split mode performs no GitHub large artifact download;
8. Clean Reference preflight is read-only;
9. Clean Reference apply calls stopped-state staging and never production activation;
10. production apply still requires V2 run-context/marker;
11. Clean Reference confirmation cannot satisfy production apply;
12. failure cleanup retains existing transaction-owned semantics.

## 11. Stop boundary

```text
SOURCE_DESIGN=FROZEN
SOURCE_REPAIR_ALLOWED=true
CI_ALLOWED=true

R1_LIVE_APPLY=false
T1_ACCESS=false
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_LOCAL_EXACT_IMAGE_CACHE_DEPLOYMENT_SOURCE_REPAIR_20261101_01
```
