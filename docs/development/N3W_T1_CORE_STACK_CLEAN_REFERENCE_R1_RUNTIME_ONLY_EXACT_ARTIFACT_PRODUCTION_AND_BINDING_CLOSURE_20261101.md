# N3-W T1_Core_Stack Clean Reference — R1 runtime-only exact artifact production and binding closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_RUNTIME_ONLY_EXACT_ARTIFACT_PRODUCTION_AND_BINDING_20261101_01

R0H=CLOSED_PASS
S0=CLOSED_PASS
S1=CLOSED_PASS
R1_LOCAL_EXACT_IMAGE_CACHE_SOURCE_REPAIR=CLOSED_PASS

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R1_DEPLOYMENT_TOOL_SOURCE_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1

WORKFLOW_RUN_ID=41286249917
WORKFLOW_EVENT=workflow_dispatch
WORKFLOW_RUN_HEAD_SHA=d377446acda59fd1f3327c5093a0e6f0286b7a5d
INPUT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
IMAGE_RUN_ID=41275979177
IMAGE_ARTIFACT_ID=13070404405
BASE_RUN_ID=41275979325
BASE_ARTIFACT_ID=13071308834

SOURCE_TEST_JOB=SUCCESS
BUILD_RUNTIME_JOB=SUCCESS

RUNTIME_ONLY_ARTIFACT_ID=13075576515
RUNTIME_ONLY_ARTIFACT_NAME=n3w-t1-clean-reference-runtime-24382caae4a1f5d459297f86e8d18f10a848ca64
RUNTIME_ONLY_ARTIFACT_DIGEST=sha256:7879bca99292829c3da55774968ea3a5a71627cca5f916d684e180898f520c91
RUNTIME_ONLY_ARTIFACT_SIZE_BYTES=149421
RUNTIME_ONLY_ARTIFACT_EXPIRED=false

RUNTIME_PAYLOAD_SHA256=7c1fbc29bfcb5597f2736a9a6ce39192cd8c6bb317df6db37c9581df7efcdcfd
PAYLOAD_MANIFEST_SHA256=b5570c7e97965d5afa593721849571d62ab67a67888fb2c2ace6d4d043147fa3
CAPACITY_CONTRACT_SHA256=c350580efebf2b4dca6d0498730bd928867e14633cb9cbe68b14047464d67cc5
S1_BINDING_SHA256=3585049d9743df08975c09bc18a7351fc2775abbba0c01e3821ff22922eac39f

MANAGER_IMAGE_ID=sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8
HOMEASSISTANT_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
BROKER_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b

IMAGE_REBUILD_PERFORMED=false
REGISTRY_PULL_PERFORMED=false
RUNTIME_ARTIFACT_IMAGE_TAR_COUNT=0

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false

RUNTIME_ONLY_EXACT_ARTIFACT_PRODUCTION_AND_BINDING=PASS
NEXT_ROUTE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_RUNTIME_ONLY_ARTIFACT_MAC_ACQUISITION_AND_LOCAL_CROSS_BINDING_20261101_01
STOP=true
```

## 1. Manual workflow run identity

The previously dispatched manual run was freshly identified as GitHub Actions run
`41286249917`.

Fresh GitHub run metadata proved:

```text
workflow=N3W T1 Clean Reference runtime payload CI
event=workflow_dispatch
status=completed
conclusion=success
head_branch=test/n3w-r8-full-simulated-e2e-safety-20261028
head_sha=d377446acda59fd1f3327c5093a0e6f0286b7a5d
```

This is distinct from PR-triggered run `41285628034`, where `build-runtime` was SKIPPED.

## 2. Run-head / source-authority separation

The workflow run head is the branch revision used to execute the CI workflow. It is not the
T1_Core_Stack component source authority.

Comparison of:

```text
R1_DEPLOYMENT_TOOL_SOURCE_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1
WORKFLOW_RUN_HEAD_SHA=d377446acda59fd1f3327c5093a0e6f0286b7a5d
```

showed exactly three later commits and only these documentation files changed:

- `docs/development/N3W_CURRENT_STATE.md`
- `docs/development/N3W_CURRENT_STATE_INDEX.md`
- `docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_LOCAL_EXACT_IMAGE_CACHE_DEPLOYMENT_SOURCE_REPAIR_CLOSURE_20261101.md`

Therefore:

```text
R1_DEPLOYMENT_TOOL_SOURCE_DRIFT=false
T1_CORE_STACK_COMPONENT_SOURCE_DRIFT=false
RUN_HEAD_POST_AUTHORITY_DRIFT=DOCS_ONLY
```

## 3. Exact input provenance

The `build-runtime` job received exactly:

```text
SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
IMAGE_RUN_ID=41275979177
IMAGE_ARTIFACT_ID=13070404405
BASE_RUN_ID=41275979325
BASE_ARTIFACT_ID=13071308834
```

Its provenance step independently queried GitHub and required both input workflow runs to be
completed/successful at the exact source head, both artifacts to be unexpired, and both artifact
names/IDs to match the expected source head.

The exact-image artifact was downloaded with GitHub digest:

```text
sha256:99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93
```

The runtime-base artifact was downloaded with GitHub digest:

```text
sha256:90ad34008a733dc58638b3617f70f7393b556c0f336264db1b52b0302d84a45f
```

Both match the previously frozen R1 inputs.

## 4. Runtime-only artifact independent inspection

GitHub produced exactly one runtime-only artifact:

```text
ID=13075576515
NAME=n3w-t1-clean-reference-runtime-24382caae4a1f5d459297f86e8d18f10a848ca64
SIZE_BYTES=149421
DIGEST=sha256:7879bca99292829c3da55774968ea3a5a71627cca5f916d684e180898f520c91
EXPIRED=false
```

The artifact ZIP was downloaded and independently inspected.

Exact top-level member set contained 12 files:

```text
build-report.json
capacity-contract.json
capacity-contract.sha256
executor.sha256
host-baseline.py
host-baseline.sha256
host-wrapper.py
host-wrapper.sha256
payload-manifest.sha256
runtime-binding.json
runtime-payload.sha256
runtime-payload.tar.gz
```

No `*-arm64.tar` image member exists.

```text
RUNTIME_ARTIFACT_IMAGE_TAR_COUNT=0
```

The artifact ZIP itself recomputed to the same GitHub digest.

## 5. Hash and manifest verification

Independent byte-level verification proved:

```text
runtime-payload.tar.gz_SHA_MATCH=true
capacity-contract.json_SHA_MATCH=true
host-wrapper.py_SHA_MATCH=true
host-baseline.py_SHA_MATCH=true
executor_SHA_MATCH=true
payload-manifest.json_SHA_MATCH=true
```

The runtime payload tar contains 48 tar members. Its manifest lists 25 controlled file entries;
all 25 file sizes and SHA-256 values were recomputed from the tar and matched exactly.

```text
MANIFEST_FILE_HASH_MISMATCH_COUNT=0
RUNTIME_TAR_IMAGE_TAR_COUNT=0
```

The runtime binding and build report agree on:

```text
source_head=24382caae4a1f5d459297f86e8d18f10a848ca64
runtime_payload_sha256=7c1fbc29bfcb5597f2736a9a6ce39192cd8c6bb317df6db37c9581df7efcdcfd
payload_manifest_sha256=b5570c7e97965d5afa593721849571d62ab67a67888fb2c2ace6d4d043147fa3
s1_binding_sha256=3585049d9743df08975c09bc18a7351fc2775abbba0c01e3821ff22922eac39f
image_rebuild_performed=false
registry_pull_performed=false
production_service_start=false
t1_access=false
board_access=false
```

## 6. S1 exact image binding

`runtime-binding.json` records the same exact three image identities and tar hashes already
accepted by S1:

```text
Manager:
image_id=sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8
tar_sha256=4c308f192a30e628ebacad11ed3aa471554fee6c3aa9fd1c25ec647d354a5006

Home Assistant:
image_id=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
tar_sha256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663

Mosquitto:
image_id=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
tar_sha256=79cf713ba9118cbd54376e7e7bef7e53e9f6638659d9f0a01093d6ac6d2d8300
```

The workflow postbuild verifier also recomputed the SHA-256 of the downloaded S1 `binding.json`
and required it to equal `runtime-binding.json.s1_binding_sha256`.

Therefore the independently rebuilt Manager image remains excluded from R1; no second Manager
build or registry pull was used.

## 7. Boundary and next route

This gate performed no T1 or board access and no production service start.

```text
MAC_RUNTIME_ARTIFACT_ACQUISITION=NOT_EXECUTED
T1_B_PREFLIGHT=NOT_EXECUTED
R1_LIVE_APPLY=NOT_EXECUTED
MERGE=false
```

The next route is prepared but is not automatically entered:

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_RUNTIME_ONLY_ARTIFACT_MAC_ACQUISITION_AND_LOCAL_CROSS_BINDING_20261101_01
AUTO_EXECUTE_NEXT_GATE=false
```
