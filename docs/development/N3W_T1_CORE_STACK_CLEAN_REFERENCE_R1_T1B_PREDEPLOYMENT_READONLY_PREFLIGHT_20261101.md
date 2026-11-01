# N3-W T1_Core_Stack Clean Reference — R1 T1_B predeployment read-only preflight

Date: 2026-11-01

## 0. Gate

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_PREDEPLOYMENT_READONLY_PREFLIGHT_20261101_01

TARGET=T1_B

R0_RESULT=CLOSED_PASS
R0H_RESULT=CLOSED_PASS
S0_RESULT=CLOSED_PASS
S1_RESULT=CLOSED_PASS
R1_RUNTIME_ONLY_ARTIFACT_PRODUCTION_AND_BINDING=CLOSED_PASS
R1_MAC_RUNTIME_ARTIFACT_LOCAL_CROSS_BINDING=CLOSED_PASS

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R1_DEPLOYMENT_TOOL_SOURCE_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1

T1_ACCESS=READ_ONLY
T1_MUTATION=false
PAYLOAD_TRANSFER=false
IMAGE_TRANSFER=false
DOCKER_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

The private operator-side T1_B SSH locator is intentionally not recorded in the public repository.

## 1. Purpose

Before any R1 payload or image transfer, re-prove that T1_B is still the same clean-reference
host established by R0/R0H and that the exact Mac runtime/S1 caches are admissible for the later
stopped-state deployment.

This gate must fail closed if T1_B has accumulated any container/image/volume/product state,
product listener, product unit/path/firewall residue, host-runtime loss, or insufficient transport
capacity.

## 2. Authority and tool selection

Use exact deployment-tool authority:

```text
4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1
```

Read-only inventory:

```text
tools/n3w_t1_minimal_baseline_readonly_inventory.py
```

Clean Reference capacity/input preflight:

```text
tools/n3w_t1_clean_reference_staging_host.py
tools/n3w_t1_fresh_product_staging_host.py
```

The existing Clean Reference preflight alone is not sufficient to prove the host is still empty.
It checks host-runtime readiness and transport capacity but does not fail on every form of Docker
or product residue. Therefore this gate additionally requires the read-only inventory and explicit
empty-state assertions below.

## 3. Read-only proof

The selected tools execute remote probes through SSH. For this gate:

- the host-baseline Python source is executed via `python3 -c`;
- the storage probe is executed via `python3 -c`;
- the minimal-baseline inventory is executed via an encoded `python3 -c`;
- no remote script file is copied;
- no remote temporary directory is created;
- no payload/image is copied;
- no Docker object is created, loaded, removed or changed;
- no service is started/stopped/restarted/enabled/disabled.

Local Mac verification may create and delete a temporary same-filesystem hardlink workspace.

## 4. R0/R0H host continuity requirements

Expected host/runtime contract:

```text
OS_ID=ubuntu
OS_VERSION=26.04
OS_CODENAME=resolute
ARCH=aarch64|arm64

NETWORKMANAGER_ACTIVE=active
NETWORKMANAGER_ENABLED=enabled
SSH_ACTIVE=active
DEFAULT_ROUTE_PRESENT=true

SYSTEMD_STATE=running
FAILED_UNIT_COUNT=0

DOCKER_IO_PACKAGE_VERSION=29.1.3-0ubuntu4.1
DOCKER_COMPOSE_V2_PACKAGE_VERSION=2.40.3+ds1-0ubuntu1
DOCKER_SERVER_VERSION=29.1.3
COMPOSE_RUNTIME_VERSION=2.40.3+ds1-0ubuntu1
DOCKER_SERVICE_ACTIVE=active
DOCKER_SERVICE_ENABLED=enabled
```

Package versions are exact continuity evidence for this clean-reference host. They are not promoted
to permanent T1_Core_Stack product identity.

## 5. Required empty Docker state

```text
TOTAL_CONTAINER_COUNT=0
TOTAL_IMAGE_COUNT=0
TOTAL_VOLUME_COUNT=0
DOCKER_NETWORK_NAMES=bridge,host,none
ONLY_DEFAULT_DOCKER_NETWORKS=true
```

Any non-default Docker object is a STOP for this gate, even if its ownership is not proven.

## 6. Required product absence

All known product paths must be absent:

```text
/var/lib/greenhouse-manager
/var/lib/n3wfc4-homeassistant
/var/lib/n3wfc4-broker
/var/lib/n3wfc4-certificate-lifecycle
/opt/greenhouse-secrets
/opt/HomeAssistant
/etc/n3wfc4
/usr/local/sbin/n3w-broker-ingress-guard
/usr/local/sbin/n3w-t1-broker-authenticated-readiness
/usr/local/sbin/n3w-broker-certificate-lifecycle
/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
/etc/systemd/system/n3wfc4-broker-ingress-guard.service
/etc/systemd/system/n3wfc4-broker-activation.service
/etc/systemd/system/n3wfc4-services-activation.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer
```

No product-named systemd unit may exist.

No listener may exist on:

```text
1883
8883
18883
8123
47110
47111
47112
```

No N3W product firewall rule may exist. Docker's own framework such as `DOCKER-USER` is allowed.

## 7. Local exact-input and capacity requirements

Mac runtime cache class:

```text
~/Documents/N3W/t1-core-stack-runtime-cache/<source-head>
```

Mac S1 image cache class:

```text
~/Documents/N3W/t1-core-stack-cache/<source-head>
```

The existing `_materialize_local_work()` path must again cross-bind runtime/S1 inputs and
`--phase preflight` must return:

```text
status=PASS
phase=preflight
source_head=24382caae4a1f5d459297f86e8d18f10a848ca64
host_baseline=PASS
local_exact_image_cache=true
github_large_artifact_download=false
payload_transfer=false
docker_mutation=false
production_v2_authority_used=false
production_service_start=false
activation_authorized=false
board_access=false
transport.capacity_pass=true
```

The storage probe must also establish the staging/Docker/image-store filesystem contract used by
the transport planner and preserve the minimum post-peak free-space reserve.

## 8. PASS/STOP

```text
PASS_IF=
R0_R0H_HOST_CONTINUITY_PASS
AND_SYSTEMD_HEALTH_PASS
AND_DOCKER_EMPTY_STATE_PASS
AND_PRODUCT_ABSENCE_PASS
AND_LOCAL_EXACT_INPUT_CROSS_BINDING_PASS
AND_TRANSPORT_CAPACITY_PASS
AND_T1_MUTATION_FALSE

STOP_IF=
ANY_PRODUCT_OR_UNKNOWN_DOCKER_RESIDUE
OR_ANY_PRODUCT_LISTENER_OR_UNIT_OR_PATH_OR_FIREWALL_RULE
OR_HOST_RUNTIME_DRIFT
OR_FAILED_SYSTEMD_UNIT
OR_STORAGE_OR_TRANSPORT_CAPACITY_FAIL
OR_LOCAL_EXACT_BINDING_FAIL
```

## 9. Stop boundary

```text
STOP_AFTER=T1B_PREDEPLOYMENT_READONLY_PREFLIGHT_RESULT_CAPTURED_AND_ARCHIVED
R1_PAYLOAD_TRANSFER=NOT_EXECUTED
R1_IMAGE_TRANSFER=NOT_EXECUTED
R1_DOCKER_LOAD=NOT_EXECUTED
R1_STOPPED_STATE_STAGING=NOT_EXECUTED
PRODUCTION_SERVICE_START=NOT_EXECUTED
AUTO_EXECUTE_NEXT_GATE=false
```

A PASS only authorizes preparation of the next bounded R1 deployment gate. It does not authorize
payload transfer, image load, provisioning, activation or service start.
