# N3-W T1 Home Assistant mandatory-USB OTA R4 closure — 2026-11-06

## 1. Gate result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R4_20261106_01
GATE_RESULT=CLOSED_PASS
R4_SCOPE=HOST_INTEGRATION_PACKAGE_AND_NARROW_VALIDATED_MANAGER_TO_PRIVILEGED_UPDATER_IPC

R4_EXECUTABLE_SOURCE_HEAD=506136a8f1fc42bb8788f8a3c0fae9220d689af4
R4_EXECUTABLE_HEAD_CI=20/20_APPLICABLE_SUCCESS
R4_EXECUTABLE_HEAD_FAILURE_COUNT=0
R4_EXPECTED_SKIPPED_WORKFLOW_COUNT=2

LIVE_T1_ACCESS=false
PRODUCTION_DEPLOYMENT=false
REAL_USB_FORMAT=false
REAL_BLOCK_DEVICE_MUTATION=false
REAL_DOCKER_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

R4 is CLOSED_PASS at executable source head `506136a8f1fc42bb8788f8a3c0fae9220d689af4`.

## 2. Implemented R4 boundary

R4 connects the already closed Manager OTA control plane to the privileged host-side Home Assistant USB transaction through a narrow local Unix domain socket.

Manager side:

- fixed-path approved-manifest provider;
- fixed-path AF_UNIX/SOCK_STREAM client;
- exact PREPARE / INSTALL / STATUS request schema;
- existing single MQTT client only;
- public OTA state refresh through the existing Manager maintenance loop;
- OTA disabled by default.

Host side:

- exact-schema dispatcher;
- bounded response schema;
- Linux SO_PEERCRED peer-UID admission;
- independent privileged-side release/admission resolution;
- PREPARE creates/advances only to U1 PREPARE_REQUESTED;
- INSTALL requires the exact previously admitted release at U4 READY_TO_INSTALL and advances only to U5 INSTALL_REQUESTED_REVALIDATING;
- no USB format/download/export/HA stop/backup/image delete/load occurs at the IPC boundary.

## 3. Manager production baseline non-drift

Independent R3-to-R4 review proved the accepted Manager production baseline did not change.

```text
CURRENT_MANAGER_IMAGE=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_MANAGER_IMAGE_ID=sha256:80d34358094638ce9c8ce5fb2635fe0a5c75ee7cc5e8c628b38ab223134e585f
CURRENT_MANAGER_TAR_SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa

CURRENT_AUTHORITY_MANIFEST_CHANGED=false
PRODUCTION_COMPOSE_CHANGED=false
PRODUCTION_MANAGER_IMAGE_REBUILT=false
LIVE_MANAGER_MUTATION=false
PRODUCTION_OTA_ENV_PRESENT=false
```

The following production blobs remained unchanged across R3 -> R4:

- `infra/n3w-t1/production/t1-core-stack-current.json`;
- `infra/n3w-t1/production/docker-compose.fresh.yml`;
- `infra/n3w-t1/production/docker-compose.yml`;
- `host/greenhouse-manager/Dockerfile`;
- `host/greenhouse-manager/pyproject.toml`;
- `runtime/app.py`.

The R4 source was additionally tightened so that when OTA is disabled, the legacy pre-R4 Manager builder/constructor call shape is preserved instead of forwarding `ota_manager=None` through the legacy path.

Focused regression tests lock this default-off behavior.

## 4. Privilege boundary

```text
GREENHOUSE_MANAGER_DOCKER_SOCKET_ACCESS=false
GREENHOUSE_MANAGER_BLOCK_DEVICE_ACCESS=false
GREENHOUSE_MANAGER_ROOT_PRIVILEGE=false
GREENHOUSE_MANAGER_ARBITRARY_SHELL=false
SECOND_MANAGER_MQTT_CLIENT=false
FOURTH_DOCKER_SERVICE=false
```

Manager requests contain only bounded intent plus exact release identity.

Manager/MQTT cannot supply:

- device path;
- mount path;
- filesystem path;
- Docker image argument;
- Docker command;
- shell command;
- authorization ID;
- SSH target;
- credential;
- backup path;
- raw USB serial as direct authority.

The host side independently resolves privileged resources.

## 5. Source review repairs before closure

The first R4 source attempt reached `7f166c1bedd60e9318c9e635afb2ab5995f3a7af`.

Its failing shared workflows were caused by Ruff I001 import-order violations in the two Manager integration files. They did not reach runtime assertion failures.

The bounded repair at `506136a8...`:

- corrected import ordering;
- preserved the exact legacy Manager call shape while OTA is disabled;
- added regression tests for legacy base-service and simplified-builder paths;
- retained strict bool rejection for progress values;
- retained bounded generic host rejection for unexpected adapter failures.

No design scope expansion was required.

## 6. Exact-head CI evidence

Final executable-head workflow result:

```text
TOTAL_WORKFLOWS=22
APPLICABLE_SUCCESS=20
EXPECTED_SKIPPED=2
FAILURE=0
```

Key evidence:

### greenhouse-manager CI

```text
WORKFLOW_RUN=42180834198
RESULT=SUCCESS
RUFF=PASS
PYTEST=1528_PASSED_1_SKIPPED
R8_SIMULATED_FIRST_REGISTRATION=8_PASSED
```

### Manager A-to-B CI

```text
WORKFLOW_RUN=42180834162
RESULT=SUCCESS
SOURCE=PASS
EXACT_MANAGER_SLICE=PASS
UPSTREAM_GITHUB_ARTIFACT_IDENTITY=PASS
T1_CORE_UPDATER_MANAGER_V2_PACKAGE_BINDING=PASS
T1_CORE_UPDATER_PYZ_EXECUTION=PASS
PRE_U1_V2_SIMULATION=PASS
```

This proves the existing Manager Generic V2 baseline remains usable after R4.

### Home Assistant target binding CI

```text
WORKFLOW_RUN=42180834183
RESULT=SUCCESS
SOURCE_TESTS=150_PASSED
HA_TARGET_UPSTREAM_GITHUB_ARTIFACT_IDENTITY=PASS
HA_2026_10_4_TARGET_V2_BINDING=PASS
```

### Private Mosquitto shared regression

The first attempt failed only while downloading `mosquitto-2.0.21.tar.gz` with:

```text
SSL: UNEXPECTED_EOF_WHILE_READING
```

The source/Ruff stage had already passed. The failed job was rerun without source change.

```text
WORKFLOW_RUN=42180834269
RERUN_RESULT=SUCCESS
RUFF=PASS
PYTEST=15_PASSED
```

Therefore the transient external download failure is not an R4 product/source blocker.

### Additional shared regressions

The final exact head also passed:

- current core-stack authority;
- public repository safety;
- first-pairing onboarding;
- node-auth isolated/native/board labs;
- Dynamic Security;
- Manager runtime secret ownership;
- Broker ingress guard;
- H0/H1 restore;
- H3 pairing runtime;
- C-06 history replay;
- C-07 retirement;
- M0 vertical slice;
- project roadmap/identity semantics;
- fast source/exact closure contract.

The two skipped workflows were path-gated fresh-install/bootstrap workflows and are expected.

## 7. Production authority

R4 changes no accepted production stack identity.

```text
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
```

Home Assistant 2026.10.4 has not been live-applied through the mandatory-USB route.

## 8. T1 Core Stack OTA successor architecture

During R4 closure, the product-level successor architecture was separately frozen in:

`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.0_20261106.md`

That architecture defines:

```text
PRODUCT_OTA_TARGET=T1_CORE_STACK_OTA
PRIVILEGED_EXECUTION_ENGINE=T1_Core_Updater

Manager=Generic V2 successor
Broker=Generic V2 successor
HomeAssistant=mandatory-USB successor
```

It is a successor product design only.

It does not modify the R4 executable authority, does not expand R4 scope, and does not authorize Broker OTA or real stack OTA execution.

## 9. R4 closure decision

```text
R4_HOST_INTEGRATION=PASS
R4_MANAGER_TO_HOST_IPC=PASS
R4_MANAGER_BASELINE_NON_DRIFT=PASS
R4_MANAGER_A_TO_B_REGRESSION=PASS
R4_HA_TARGET_BINDING=PASS
R4_PRIVILEGE_BOUNDARY=PASS
R4_FALSE_PASS_PATH_FOUND=false
R4_NEW_SOURCE_BLOCKER_COUNT=0
R4_SOURCE_REPAIR_REQUIRED=false
R4=CLOSED_PASS
```

## 10. Next boundary

The next Home Assistant gate remains:

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01
R5_SCOPE=REAL_T1_READONLY_PREFLIGHT
R5_MUTATION=false
USB_FORMAT=false
SERVICE_STOP=false
AUTO_EXECUTE_NEXT_GATE=false
STOP_BOUNDARY=BEFORE_R5_ENTRY
```

R5 requires explicit authorization because it crosses into real-T1 access.

R4 closure does not authorize R5, USB formatting, Docker mutation, production service stop, board access or merge.
