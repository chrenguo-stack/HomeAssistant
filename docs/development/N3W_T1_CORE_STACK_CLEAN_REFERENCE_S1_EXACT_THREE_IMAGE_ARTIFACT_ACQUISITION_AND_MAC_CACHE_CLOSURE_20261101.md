# N3-W T1_Core_Stack Clean Reference — S1 exact three-image artifact acquisition and Mac cache closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_S1_EXACT_THREE_IMAGE_ARTIFACT_ACQUISITION_AND_MAC_CACHE_20261101_01

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64

RUN_ID=41275979177
ARTIFACT_ID=13070404405
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-24382caae4a1f5d459297f86e8d18f10a848ca64
ARTIFACT_GITHUB_DIGEST=sha256:99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93

GITHUB_ARTIFACT_AUTHORITY=PASS
GITHUB_RUN_AUTHORITY=PASS
S1_LOCAL_BINDING_VERIFY=PASS
S1_LOCAL_TAR_SHA256_VERIFY=PASS
S1_MAC_EXACT_THREE_IMAGE_CACHE=PASS

T1_ACCESS=false
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

S1_RESULT=CLOSED_PASS
```

## 1. Durable Mac cache

The exact three-image artifact was downloaded into the private durable Mac cache class:

```text
~/Documents/N3W/t1-core-stack-cache/<source-head>
```

The expanded username/path remains private operational information and is not recorded in the
public repository.

The cache member set is exactly:

```text
binding.json
greenhouse-manager-arm64.tar
homeassistant-arm64.tar
broker-arm64.tar
```

## 2. Manager exact binding

```text
MANAGER_IMAGE=local/greenhouse-manager:fresh-24382caae4a1
MANAGER_IMAGE_ID=sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8
MANAGER_TAR_SIZE_BYTES=62688256
MANAGER_TAR_SHA256=4c308f192a30e628ebacad11ed3aa471554fee6c3aa9fd1c25ec647d354a5006
PLATFORM=linux/arm64
```

Manager is source-bound to:

```text
24382caae4a1f5d459297f86e8d18f10a848ca64
```

## 3. Home Assistant exact binding

```text
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
HOMEASSISTANT_TAR_SIZE_BYTES=2448553472
HOMEASSISTANT_TAR_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
HOMEASSISTANT_ARM64_MANIFEST_DIGEST=sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4
PLATFORM=linux/arm64
```

## 4. Mosquitto Broker exact binding

```text
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
BROKER_TAR_SIZE_BYTES=27556352
BROKER_TAR_SHA256=79cf713ba9118cbd54376e7e7bef7e53e9f6638659d9f0a01093d6ac6d2d8300
BROKER_ARM64_MANIFEST_DIGEST=sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
PLATFORM=linux/arm64
```

## 5. Local verification result

The operator-side verification established:

```text
source_head=24382caae4a1f5d459297f86e8d18f10a848ca64
fresh_runtime_identity_binding=true
node_credential_count=0
production_service_start=false
secret_values_included=false
t1_access=false
board_access=false
```

All three local tar files matched the sizes and SHA-256 values recorded in `binding.json`.

Therefore:

```text
MAC_EXACT_THREE_IMAGE_CACHE_VALID=true
REBUILD_REQUIRED=false
REDOWNLOAD_REQUIRED=false
```

## 6. Architecture boundary

S1 created a durable local artifact cache only.

It did not:

- access T1_B;
- mutate T1_B;
- load any Docker image onto T1_B;
- create any application container;
- start Broker, Manager or Home Assistant;
- access boards.

The next deployment must consume this verified local cache rather than pull application
images from the network.

## 7. Next route

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_FIRST_DEPLOYMENT_20261101_01
```

R1 must first perform a read-only/predeployment eligibility check on T1_B, then transfer and
verify the exact locally cached artifacts before any image load or production activation.
