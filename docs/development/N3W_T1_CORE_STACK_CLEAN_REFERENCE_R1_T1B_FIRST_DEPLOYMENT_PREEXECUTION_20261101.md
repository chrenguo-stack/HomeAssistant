# N3-W T1_Core_Stack Clean Reference — R1 T1_B first deployment preexecution

Date: 2026-11-01

## 0. Gate

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_FIRST_DEPLOYMENT_20261101_01
TARGET=T1_B

USER_ENTERED_GATE=true

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R1_DEPLOYMENT_TOOL_SOURCE_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1
READONLY_INVENTORY_AUTHORITY=ca849ed8565504529e2e39c823172ec2070cb5a8

R1_T1B_PREDEPLOYMENT_READONLY_PREFLIGHT=CLOSED_PASS

T1_ACCESS=true
T1_MUTATION=true
PAYLOAD_TRANSFER=true
IMAGE_TRANSFER=true
DOCKER_IMAGE_LOAD=true

PRODUCTION_SERVICE_START=false
PRODUCTION_V2_AUTHORITY_USED=false
ACTIVATION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false

AUTO_EXECUTE_NEXT_GATE=false
```

The operator-specific T1_B SSH locator and private Mac absolute paths are not recorded in public evidence.

## 1. Exact inputs

Runtime cache class:

```text
~/Documents/N3W/t1-core-stack-runtime-cache/<source-head>
```

S1 image cache class:

```text
~/Documents/N3W/t1-core-stack-cache/<source-head>
```

Frozen source:

```text
SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
```

Exact image authority:

```text
MANAGER_IMAGE_ID=sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8
HOMEASSISTANT_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
BROKER_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
```

Exact runtime authority:

```text
RUNTIME_PAYLOAD_SHA256=7c1fbc29bfcb5597f2736a9a6ce39192cd8c6bb317df6db37c9581df7efcdcfd
PAYLOAD_MANIFEST_SHA256=b5570c7e97965d5afa593721849571d62ab67a67888fb2c2ace6d4d043147fa3
S1_BINDING_SHA256=3585049d9743df08975c09bc18a7351fc2775abbba0c01e3821ff22922eac39f
```

No image rebuild or registry pull is allowed.

## 2. Entry eligibility

The immediately preceding T1_B predeployment read-only gate closed PASS with:

```text
SYSTEMD_STATE=running
FAILED_UNIT_COUNT=0

TOTAL_CONTAINER_COUNT=0
TOTAL_IMAGE_COUNT=0
TOTAL_VOLUME_COUNT=0
DOCKER_NETWORK_NAMES=bridge,host,none

PRODUCT_PATH_RESIDUAL_COUNT=0
PRODUCT_UNIT_RESIDUAL_COUNT=0
PRODUCT_LISTENER_RESIDUAL_COUNT=0
UNKNOWN_STOP_COUNT=0

TRANSPORT_REMOTE_FREE_BYTES=11859628032
TRANSPORT_WORST_IMAGE_REQUIRED_FREE_BYTES=10135822686
MINIMUM_POST_PEAK_FREE_BYTES=5368709120
TRANSPORT_CAPACITY_PASS=true
```

The apply wrapper re-runs host baseline and storage/capacity checks before mutation.

## 3. Authorized mutation

This gate authorizes only the repository-owned Clean Reference R1 apply path:

```text
tools/n3w_t1_clean_reference_staging_host.py
--phase apply
--confirmation N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_FIRST_DEPLOYMENT_20261101_01
```

The path may:

1. create one transaction-owned temporary remote staging directory;
2. transfer and verify the exact runtime payload;
3. transfer the Clean Reference executor and verify its SHA-256;
4. transfer one exact image tar at a time;
5. verify each tar SHA/size before load;
6. load exactly Home Assistant, Manager and Broker images;
7. delete each staged image tar after successful load;
8. generate fresh system identity;
9. generate fresh state with zero node credentials;
10. generate Broker materials and initialize DynSec service identities;
11. stage runtime/configuration and required stopped-state units;
12. commit only transaction-owned Clean Reference targets;
13. perform the internal stopped-state postcheck;
14. remove the transaction-owned temporary payload directory after success.

The Clean Reference confirmation is isolated from production V2 authority. It does not create,
consume or satisfy the production V2 authorization ledger/marker.

## 4. Required internal apply sequence

```text
preflight
load_images
identity
state
broker
dynsec
runtime
commit
postcheck
```

Image transport/load order is frozen by the payload contract and must be observed exactly.

## 5. Required R1 end state

```text
DOCKER_IMAGE_COUNT=3
T1_CORE_STACK_IMAGE_IDENTITY_EXACT=true

PRODUCT_RUNTIME_FILES_STAGED=true
FRESH_SYSTEM_ID_CREATED=true
FRESH_STATE_CREATED=true
BROKER_DYNSEC_CREATED=true
NODE_CREDENTIAL_COUNT=0

PRODUCT_CONTAINER_COUNT=0
PRODUCT_VOLUME_COUNT=0
PRODUCT_LISTENER_COUNT=0

PRODUCTION_V2_AUTHORITY_USED=false
PRODUCTION_SERVICE_START=false
ACTIVATION_AUTHORIZED=false
BOARD_ACCESS=false
```

The internal stopped postcheck must also prove:

- exact image runtime binding for all three images;
- only default Docker networks;
- no product listener;
- no production firewall activation;
- expected product paths exist;
- fresh state and DynSec contain zero node credentials;
- production activation units are not enabled.

## 6. Failure semantics

Before mutation, any preflight/input/capacity failure is a STOP with no R1 mutation.

After mutation starts:

- the fresh installer attempts transaction-owned cleanup on failure;
- if cleanup is proven PASS, the result remains a failed deployment with cleanup evidence;
- if cleanup is not proven, STOP immediately and preserve evidence;
- do not replay blindly after an ambiguous or partially cleaned failure;
- do not run ad-hoc cleanup outside a separately reviewed recovery step.

No production service start is authorized even as a recovery action.

## 7. Post-apply independent read-only acceptance

After apply returns PASS, perform a separate read-only external probe that checks:

```text
TOTAL_CONTAINER_COUNT=0
TOTAL_IMAGE_ID_COUNT=3
MANAGER_IMAGE_ID=exact S1 authority
HOMEASSISTANT_IMAGE_ID=exact S1 authority
BROKER_IMAGE_ID=exact S1 authority
TOTAL_VOLUME_COUNT=0
DOCKER_NETWORK_NAMES=bridge,host,none
TARGET_PRODUCT_LISTENER_COUNT=0

PRODUCTION_ACTIVATION_UNITS_ENABLED=false
PRODUCTION_SERVICE_START=false
```

The internal executor remains the authority for the fresh-state/DynSec/node-credential semantic
postcheck because it audits those structures before returning PASS without publishing secrets.

## 8. Stop boundary

```text
STOP_AFTER=R1_FIRST_DEPLOYMENT_RESULT_AND_POST_APPLY_READONLY_ACCEPTANCE_CAPTURED

R2_START_OR_REBOOT=NOT_EXECUTED
CUSTOMER_NODE_PAIRING=NOT_EXECUTED
BOARD_ACCESS=NOT_EXECUTED
PRODUCTION_SERVICE_START=NOT_EXECUTED

AUTO_EXECUTE_NEXT_GATE=false
```

A PASS in this gate establishes the stopped-state R1 Clean Reference. It does not authorize
R2 controlled start/reboot or R3 workload.
