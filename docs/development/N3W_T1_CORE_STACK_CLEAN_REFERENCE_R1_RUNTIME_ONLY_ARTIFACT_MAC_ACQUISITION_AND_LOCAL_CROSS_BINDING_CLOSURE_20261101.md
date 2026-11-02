# N3-W T1_Core_Stack Clean Reference — R1 runtime-only artifact Mac acquisition and local cross-binding closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_RUNTIME_ONLY_ARTIFACT_MAC_ACQUISITION_AND_LOCAL_CROSS_BINDING_20261101_01

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R1_DEPLOYMENT_TOOL_SOURCE_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1

RUNTIME_RUN_ID=41286249917
RUNTIME_ARTIFACT_ID=13075576515
RUNTIME_ARTIFACT_DIGEST=sha256:7879bca99292829c3da55774968ea3a5a71627cca5f916d684e180898f520c91

MAC_RUNTIME_CACHE_CLASS=~/Documents/N3W/t1-core-stack-runtime-cache/<source-head>
MAC_RUNTIME_CACHE_FILE_COUNT=12
MAC_RUNTIME_CACHE_EXACT_FILE_SET=PASS

SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
RUNTIME_PAYLOAD_SHA256=7c1fbc29bfcb5597f2736a9a6ce39192cd8c6bb317df6db37c9581df7efcdcfd
PAYLOAD_MANIFEST_SHA256=b5570c7e97965d5afa593721849571d62ab67a67888fb2c2ace6d4d043147fa3
S1_BINDING_SHA256=3585049d9743df08975c09bc18a7351fc2775abbba0c01e3821ff22922eac39f

MANAGER_IMAGE_ID=sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8
HOMEASSISTANT_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
BROKER_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b

LOCAL_EXACT_IMAGE_CACHE=true
RUNTIME_ARTIFACT_IMAGE_TAR_COUNT=0
T1_ACCESS=false
T1_MUTATION=false
DOCKER_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false

MAC_RUNTIME_ONLY_ARTIFACT_ACQUISITION_AND_LOCAL_CROSS_BINDING=PASS
RESULT=CLOSED_PASS
```

## 1. Operator result

The operator executed the repository-authority local verification package on Mac.

The verifier returned:

```json
{
  "status": "PASS",
  "source_head": "24382caae4a1f5d459297f86e8d18f10a848ca64",
  "runtime_payload_sha256": "7c1fbc29bfcb5597f2736a9a6ce39192cd8c6bb317df6db37c9581df7efcdcfd",
  "payload_manifest_sha256": "b5570c7e97965d5afa593721849571d62ab67a67888fb2c2ace6d4d043147fa3",
  "s1_binding_sha256": "3585049d9743df08975c09bc18a7351fc2775abbba0c01e3821ff22922eac39f",
  "manager_image_id": "sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8",
  "homeassistant_image_id": "sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879",
  "broker_image_id": "sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b",
  "runtime_artifact_image_tar_count": 0,
  "local_exact_image_cache": true,
  "t1_access": false,
  "docker_mutation": false,
  "production_service_start": false,
  "board_access": false
}
```

The expanded user-specific local path is intentionally omitted from public GitHub evidence.

## 2. Durable Mac runtime cache

The runtime-only artifact now exists in the durable private cache class:

```text
~/Documents/N3W/t1-core-stack-runtime-cache/<source-head>
```

The verified cache contains exactly 12 files:

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

No `*-arm64.tar` file exists in the runtime cache.

## 3. Local S1 cross-binding

The existing S1 private image cache was used as the local image authority.

The runtime bundle was cross-bound to the actual local S1 `binding.json`, and all three image
records matched the already-accepted S1 image IDs. The repository-owned verifier also rechecked
the actual local image tar sizes and SHA-256 values before returning PASS.

Therefore:

```text
RUNTIME_TO_S1_LOCAL_BINDING=PASS
INDEPENDENT_MANAGER_REBUILD_ELIGIBLE=false
REBUILD_REQUIRED=false
REDOWNLOAD_REQUIRED=false
```

## 4. Safety boundary

This gate was Mac-only.

It did not:

- access T1_B or T1_A;
- transfer runtime payload or images to T1;
- mutate Docker on T1;
- load application images on T1;
- start Manager, Home Assistant or Mosquitto;
- access any board;
- merge PR #705.

```text
T1_B_PREFLIGHT=NOT_EXECUTED
R1_LIVE_APPLY=NOT_EXECUTED
AUTO_EXECUTE_NEXT_GATE=false
```

## 5. Next route

The runtime artifact and exact S1 image cache are now both durably present and locally
cross-bound on Mac.

The next bounded stage is T1_B predeployment eligibility/read-only preflight. That stage must
freshly confirm the clean R0H host baseline and storage/transport eligibility before any payload
transfer, Docker image load or stopped-state application staging.

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_PREDEPLOYMENT_READONLY_PREFLIGHT_20261101_01
AUTO_EXECUTE_NEXT_GATE=false
```
