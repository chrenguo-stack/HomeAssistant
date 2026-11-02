# N3-W T1_Core_Stack Clean Reference — R1 T1_B predeployment read-only preflight closure

Date: 2026-11-01

## 0. Final result

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_PREDEPLOYMENT_READONLY_PREFLIGHT_20261101_01
TARGET=T1_B

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R1_DEPLOYMENT_TOOL_SOURCE_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1
READONLY_INVENTORY_AUTHORITY=ca849ed8565504529e2e39c823172ec2070cb5a8

READONLY_PREFLIGHT_SCHEMA=gh.n3w-t1-clean-reference-r1-t1b-readonly-preflight/2
READONLY_PREFLIGHT_STATUS=PASS

T1_ACCESS=READ_ONLY
T1_MUTATION=false
PAYLOAD_TRANSFER=false
IMAGE_TRANSFER=false
DOCKER_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false

RESULT=CLOSED_PASS
```

## 1. Fresh host continuity

Operator evidence:

```text
OS_ID=ubuntu
OS_VERSION=26.04
OS_CODENAME=resolute
ARCHITECTURE=aarch64

SYSTEMD_STATE=running
FAILED_UNIT_COUNT=0

NETWORKMANAGER_ACTIVE=active
NETWORKMANAGER_ENABLED=enabled

DOCKER_IO_PACKAGE_VERSION=29.1.3-0ubuntu4.1
DOCKER_COMPOSE_V2_PACKAGE_VERSION=2.40.3+ds1-0ubuntu1
DOCKER_SERVER_VERSION=29.1.3
COMPOSE_RUNTIME_VERSION=2.40.3+ds1-0ubuntu1
DOCKER_SERVICE_ACTIVE=active
DOCKER_SERVICE_ENABLED=enabled
```

This re-proves the R0/R0H host-runtime continuity needed before R1 mutation.

## 2. Empty Docker and product-absence proof

```text
TOTAL_CONTAINER_COUNT=0
TOTAL_IMAGE_COUNT=0
TOTAL_VOLUME_COUNT=0
DOCKER_NETWORK_NAMES=bridge,host,none
ONLY_DEFAULT_DOCKER_NETWORKS=true

PRODUCT_PATH_RESIDUAL_COUNT=0
PRODUCT_UNIT_RESIDUAL_COUNT=0
PRODUCT_LISTENER_RESIDUAL_COUNT=0
UNKNOWN_STOP_COUNT=0
```

No product container, image, volume, path, systemd unit or target listener was found.

## 3. Firewall visibility

The repaired read-only observer accepted the absent optional nft CLI only after both iptables
read views were complete.

```text
NFT_OPTIONAL_CLI_ABSENT_ACCEPTED=true
IPTABLES_FILTER_VISIBILITY=PASS
IPTABLES_NAT_VISIBILITY=PASS
UNKNOWN_STOP_COUNT=0
```

This follows the separately closed source repair:

```text
N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_PREFLIGHT_NFT_VISIBILITY_FALSE_STOP_SOURCE_REPAIR_20261101_01
RESULT=CLOSED_PASS
CI_RUN_ID=41290538736
CI_RESULT=SUCCESS
```

No nft package was installed and no T1_B firewall mutation occurred.

## 4. Exact local input and transport-capacity proof

```text
SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
LOCAL_EXACT_IMAGE_CACHE=true
GITHUB_LARGE_ARTIFACT_DOWNLOAD=false

STAGING_FREE_BYTES=11859628032
DOCKER_FREE_BYTES=11859628032
IMAGE_STORE_FREE_BYTES=11859628032

TRANSPORT_REMOTE_FREE_BYTES=11859628032
TRANSPORT_WORST_IMAGE_REQUIRED_FREE_BYTES=10135822686
MINIMUM_POST_PEAK_FREE_BYTES=5368709120
TRANSPORT_CAPACITY_PASS=true
```

The exact Mac runtime/S1 inputs remain admissible for the frozen R1 transport plan.

## 5. Evidence identity

```text
INVENTORY_SHA256=8dca28c99dfb2ad90dd26f7f6562d99e8164a60f77d657262b1c11bf965fc897
```

The operator-specific SSH target and any private local absolute paths are intentionally omitted
from public repository evidence.

## 6. Safety boundary

This gate did not:

- transfer runtime payload to T1_B;
- transfer any application image tar to T1_B;
- load any Docker image;
- create or remove any Docker object;
- create product runtime/state;
- start Broker, Manager or Home Assistant;
- authorize production activation;
- access any board.

```text
R1_PAYLOAD_TRANSFER=NOT_EXECUTED
R1_IMAGE_TRANSFER=NOT_EXECUTED
R1_DOCKER_IMAGE_LOAD=NOT_EXECUTED
R1_STOPPED_STATE_STAGING=NOT_EXECUTED
PRODUCTION_SERVICE_START=NOT_EXECUTED
BOARD_ACCESS=NOT_EXECUTED
```

## 7. Next route

S1 already froze the next deployment gate as:

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_FIRST_DEPLOYMENT_20261101_01
AUTO_EXECUTE_NEXT_GATE=false
```

The next gate may authorize exact local runtime/image transfer, verification, image load and
Clean Reference stopped-state staging only within its own bounded mutation authority.

The frozen R1 target end state remains:

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

R1 first deployment must stop at stopped-state staging. It must not start the production services.
