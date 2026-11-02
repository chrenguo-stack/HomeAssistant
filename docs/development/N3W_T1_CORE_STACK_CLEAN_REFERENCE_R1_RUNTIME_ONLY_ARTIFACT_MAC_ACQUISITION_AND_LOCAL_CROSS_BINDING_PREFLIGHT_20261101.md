# N3-W T1_Core_Stack Clean Reference — R1 runtime-only artifact Mac acquisition and local cross-binding preflight

Date: 2026-11-01

## 0. Gate

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_RUNTIME_ONLY_ARTIFACT_MAC_ACQUISITION_AND_LOCAL_CROSS_BINDING_20261101_01

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R1_DEPLOYMENT_TOOL_SOURCE_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1

RUNTIME_RUN_ID=41286249917
RUNTIME_ARTIFACT_ID=13075576515
RUNTIME_ARTIFACT_NAME=n3w-t1-clean-reference-runtime-24382caae4a1f5d459297f86e8d18f10a848ca64
RUNTIME_ARTIFACT_DIGEST=sha256:7879bca99292829c3da55774968ea3a5a71627cca5f916d684e180898f520c91
RUNTIME_ARTIFACT_SIZE_BYTES=149421
RUNTIME_ARTIFACT_EXPIRED=false

S1_IMAGE_RUN_ID=41275979177
S1_IMAGE_ARTIFACT_ID=13070404405
S1_IMAGE_ARTIFACT_DIGEST=sha256:99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93
S1_IMAGE_ARTIFACT_EXPIRED=false

T1_ACCESS=false
T1_MUTATION=false
DOCKER_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

## 1. Purpose

Acquire the already-produced runtime-only artifact once into the durable private Mac cache and
cross-bind it against the already-verified S1 three-image Mac cache.

This gate proves only local Mac artifact continuity. It does not access T1_B and does not perform
R1 deployment.

## 2. Durable private cache classes

S1 exact image cache already exists at:

```text
~/Documents/N3W/t1-core-stack-cache/<source-head>
```

The runtime-only artifact will be stored separately at:

```text
~/Documents/N3W/t1-core-stack-runtime-cache/<source-head>
```

Expanded usernames and local absolute paths remain private operational information and are not
committed.

## 3. Runtime artifact exact set

The extracted runtime cache must contain exactly these 12 files:

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

Image tar members are forbidden in the runtime-only cache.

## 4. Frozen local cross-binding

Required exact values:

```text
SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
RUNTIME_PAYLOAD_SHA256=7c1fbc29bfcb5597f2736a9a6ce39192cd8c6bb317df6db37c9581df7efcdcfd
PAYLOAD_MANIFEST_SHA256=b5570c7e97965d5afa593721849571d62ab67a67888fb2c2ace6d4d043147fa3
CAPACITY_CONTRACT_SHA256=c350580efebf2b4dca6d0498730bd928867e14633cb9cbe68b14047464d67cc5
S1_BINDING_SHA256=3585049d9743df08975c09bc18a7351fc2775abbba0c01e3821ff22922eac39f

MANAGER_IMAGE_ID=sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8
HOMEASSISTANT_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
BROKER_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
```

Repository-owned verification uses the exact deployment-tool authority copies of:

```text
tools/n3w_t1_clean_reference_staging_host.py
tools/n3w_t1_fresh_product_staging_host.py
```

The local-only verifier invokes the existing `_materialize_local_work()` path. This checks:

- runtime cache exact file set;
- S1 cache exact file set;
- runtime-binding schema and source head;
- runtime `s1_binding_sha256` against the actual local S1 `binding.json`;
- exact image ID/tar size/tar SHA/platform equality for all three images;
- actual local S1 tar sizes and SHA-256 values;
- runtime payload outer SHA and manifest SHA;
- payload source head and embedded image bindings;
- capacity and image artifact contracts.

It creates only a temporary hardlink workspace on the same Mac filesystem and deletes it after the
check. It does not contact T1.

## 5. Operator Mac command

The operator command must:

1. fresh-check artifact metadata from GitHub;
2. fail if the durable runtime cache destination already exists;
3. download the named artifact from run 41286249917;
4. fetch the exact verifier source files from deployment-tool authority 4b0ec26e...;
5. run repository-owned local cross-binding plus frozen-hash assertions;
6. atomically move the verified runtime directory into the durable runtime cache class;
7. apply private permissions;
8. stop.

No T1 locator, SSH, Docker mutation, service start or board access is used.

## 6. PASS

```text
PASS_IF=
GITHUB_RUNTIME_ARTIFACT_METADATA_EXACT
AND_RUNTIME_CACHE_EXACT_12_FILE_SET
AND_REPOSITORY_OWNED_LOCAL_CROSS_BINDING_PASS
AND_SOURCE_HEAD_EXACT
AND_RUNTIME_PAYLOAD_SHA256_EXACT
AND_PAYLOAD_MANIFEST_SHA256_EXACT
AND_CAPACITY_CONTRACT_SHA256_EXACT
AND_S1_BINDING_SHA256_EXACT
AND_MANAGER_IMAGE_ID_EXACT
AND_HOMEASSISTANT_IMAGE_ID_EXACT
AND_BROKER_IMAGE_ID_EXACT
AND_RUNTIME_ARTIFACT_IMAGE_TAR_COUNT_0
AND_T1_ACCESS_FALSE
```

## 7. Stop boundary

```text
STOP_AFTER=MAC_RUNTIME_ONLY_CACHE_VERIFIED_AND_CROSS_BOUND_TO_S1
T1_B_PREFLIGHT=NOT_EXECUTED
R1_LIVE_APPLY=NOT_EXECUTED
AUTO_EXECUTE_NEXT_GATE=false
```

After PASS, the next gate may prepare T1_B read-only/predeployment eligibility. This document does
not authorize that access.
