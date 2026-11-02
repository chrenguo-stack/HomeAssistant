# N3-W T1_Core_Stack Clean Reference — R1 local exact-image-cache deployment source repair closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_LOCAL_EXACT_IMAGE_CACHE_DEPLOYMENT_SOURCE_REPAIR_20261101_01

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R1_DEPLOYMENT_TOOL_SOURCE_AUTHORITY=4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1

S1_RESULT=CLOSED_PASS
SOURCE_REPAIR=PASS
SOURCE_REVIEW=PASS
SOURCE_CI=PASS
SOURCE_REPAIR_CLOSURE=CLOSED_PASS

R1_LIVE_APPLY_AUTHORIZED=false
T1_ACCESS=false
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

## 1. Blocker that required source repair

The existing fresh deployable workflow independently rebuilt Manager from the same repository
source head and produced a different image ID from the exact S1 image artifact.

```text
S1_MANAGER_IMAGE_ID=
sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8

INDEPENDENT_DEPLOYABLE_MANAGER_IMAGE_ID=
sha256:1b97cba4a63a1c6c7f714b15f89b6859dc68cb2d6236f2eb7c52ea6689ecccd3

MANAGER_IMAGE_ID_MATCH=false
```

Therefore source-head equality was not sufficient to prove exact image continuity.

The frozen R1 rule is now:

```text
BUILD_ONCE
-> VERIFY_EXACT_IMAGE
-> CACHE_EXACT_IMAGE
-> DEPLOY_THE_SAME_EXACT_IMAGE
```

## 2. Source repair

Added deployment-tooling components:

```text
tools/n3w_t1_clean_reference_runtime_payload_builder.py
tools/n3w_t1_clean_reference_executor.py
tools/n3w_t1_clean_reference_staging_host.py
tests/tools/test_n3w_t1_clean_reference_r1.py
.github/workflows/n3w-t1-clean-reference-runtime-payload-ci.yml
```

These are deployment/control-plane tools outside T1_Core_Stack component identity.

The repair introduces:

- runtime-only payload rebinding around the exact S1 image artifact;
- exact S1 image ID / tar SHA / size cross-binding;
- Mac local-cache transport without GitHub large-artifact download during R1;
- an isolated Clean Reference stopped-state executor;
- direct reuse of the existing `run_fresh_staging()` business primitive;
- explicit separation from production V2 run-context/marker authority.

## 3. T1_Core_Stack source identity remained frozen

Comparison between:

```text
24382caae4a1f5d459297f86e8d18f10a848ca64
and
4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1
```

confirmed no modifications to the frozen component/runtime implementation paths used by the
S0 component identity.

Exact blob equality was independently confirmed for:

```text
tools/n3w_t1_fresh_product_bootstrap.py
tools/n3w_t1_fresh_product_staging_host.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py
infra/n3w-t1/production/docker-compose.fresh.yml
```

Therefore:

```text
T1_CORE_STACK_COMPONENT_SOURCE_DRIFT=false
```

## 4. Repair source review

The new R1 production paths were independently reviewed at
`4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1`.

Results:

```text
CLEAN_REFERENCE_RUNTIME_BUILDER_DOCKER_BUILD=false
CLEAN_REFERENCE_RUNTIME_BUILDER_DOCKER_PULL=false

CLEAN_REFERENCE_EXECUTOR_DOCKER_BUILD=false
CLEAN_REFERENCE_EXECUTOR_DOCKER_PULL=false
CLEAN_REFERENCE_EXECUTOR_PRODUCTION_RUN_CONTEXT=false
CLEAN_REFERENCE_EXECUTOR_PRODUCTION_MARKER=false
CLEAN_REFERENCE_EXECUTOR_CALLS_RUN_FRESH_STAGING=true

CLEAN_REFERENCE_HOST_DOCKER_BUILD=false
CLEAN_REFERENCE_HOST_DOCKER_PULL=false
CLEAN_REFERENCE_HOST_PRODUCTION_RUN_CONTEXT=false
CLEAN_REFERENCE_HOST_PRODUCTION_MARKER=false
```

Production V2 source was not modified.

## 5. CI closure

Exact repair head:

```text
4b0ec26e04a8f10d0d9e746c05b6a5794510d8a1
```

Required CI:

```text
N3W T1 Clean Reference runtime payload CI
run=41284729100
result=SUCCESS

N3W CI fast source and exact closure contract
run=41284728939
result=SUCCESS

N3W T1 fresh install host-only CI
run=41284728966
result=SUCCESS

Public repository safety CI
run=41284729010
result=SUCCESS

greenhouse-manager CI
run=41284729018
result=SUCCESS

N3W T1 fresh install exact ARM64 CI
run=41284728968
result=SUCCESS

N3W T1 fresh bootstrap deployable payload CI
run=41284729006
result=SUCCESS
```

The CI-policy registration and workflow-count regression discovered during repair were both
locally bounded and closed before this source authority was accepted.

## 6. Runtime-only artifact production inputs

The next gate uses existing exact artifacts only.

Exact image authority:

```text
IMAGE_RUN_ID=41275979177
IMAGE_ARTIFACT_ID=13070404405
IMAGE_ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-24382caae4a1f5d459297f86e8d18f10a848ca64
IMAGE_ARTIFACT_DIGEST=sha256:99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93
IMAGE_ARTIFACT_EXPIRED=false
```

Runtime-source authority:

```text
BASE_RUN_ID=41275979325
BASE_ARTIFACT_ID=13071308834
BASE_ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-24382caae4a1f5d459297f86e8d18f10a848ca64
BASE_ARTIFACT_DIGEST=sha256:90ad34008a733dc58638b3617f70f7393b556c0f336264db1b52b0302d84a45f
BASE_ARTIFACT_EXPIRED=false
```

Both artifacts are bound to the same exact S0 source head.

The runtime-only producer must:

```text
IMAGE_REBUILD_PERFORMED=false
REGISTRY_PULL_PERFORMED=false
T1_ACCESS=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

## 7. Next gate

```text
NEXT_ONE_GATE=
N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_RUNTIME_ONLY_EXACT_ARTIFACT_PRODUCTION_AND_BINDING_20261101_01
```

This gate is CI-only. It must complete before any T1_B preflight or R1 live apply.
