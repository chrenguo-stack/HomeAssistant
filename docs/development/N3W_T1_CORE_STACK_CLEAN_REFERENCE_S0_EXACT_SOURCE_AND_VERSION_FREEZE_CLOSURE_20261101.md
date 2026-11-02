# N3-W T1_Core_Stack Clean Reference — S0 exact source and version freeze closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_S0_EXACT_SOURCE_AND_VERSION_FREEZE_20261101_01

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
SOURCE_DRIFT_AFTER_AUTHORITY=DOCS_ONLY

MANAGER_SOURCE_MODEL=CURRENT_REPOSITORY_HEAD_BUILD
HOMEASSISTANT_SOURCE_MODEL=EXTERNAL_VERSION_PLUS_ARM64_DIGEST
BROKER_SOURCE_MODEL=EXTERNAL_VERSION_PLUS_ARM64_DIGEST

S0_RESULT=CLOSED_PASS

T1_ACCESS=false
T1_MUTATION=false
T1_CORE_STACK_DEPLOYMENT=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

S0 freezes the exact current T1_Core_Stack source/version authority without deploying any
application payload to T1_B.

## 1. Source-head freeze

The exact source authority is:

```text
24382caae4a1f5d459297f86e8d18f10a848ca64
```

Comparison from this head to the R0H-closure workspace showed only documentation changes.
No Manager source, fresh-build workflow, Compose/runtime source, Home Assistant integration,
Mosquitto configuration, or product deployment source changed after this head.

Therefore later documentation commits do not advance S0 application source identity.

## 2. Manager authority

The current fresh deployment workflows build Manager directly from the exact checkout:

```text
SOURCE_HEAD=current exact pull-request head or github.sha
BUILD_CONTEXT=host/greenhouse-manager
DOCKERFILE=host/greenhouse-manager/Dockerfile
TARGET_PLATFORM=linux/arm64
RUNTIME_USER=greenhouse
ENTRYPOINT=greenhouse-manager
```

For S0:

```text
MANAGER_SOURCE_SHA=24382caae4a1f5d459297f86e8d18f10a848ca64
MANAGER_RUNTIME_IMAGE_PATTERN=local/greenhouse-manager:fresh-<source-head-prefix>
MANAGER_RUNTIME_IMAGE_AT_S0=local/greenhouse-manager:fresh-24382caae4a1
```

The historical S20 production image lock still records:

```text
MANAGER_SOURCE_SHA=511db028780988a7c07cb9342c8be507380bae0f
MANAGER_IMAGE=local/greenhouse-manager:s20-511db028
```

That historical binding is not the Clean Reference S0 Manager authority because the current
fresh workflow explicitly builds Manager from the current exact repository source head.

## 3. Home Assistant authority

The current fresh workflows freeze Home Assistant as:

```text
HOMEASSISTANT_SOURCE_REF=ghcr.io/home-assistant/home-assistant:2026.10.0
HOMEASSISTANT_ARM64_MANIFEST_DIGEST=sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4
HOMEASSISTANT_EXPECTED_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
HOMEASSISTANT_LOCAL_RUNTIME_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
PLATFORM=linux/arm64
```

The external version and digest match the existing production image lock and the current
fresh exact ARM64 workflow.

## 4. Mosquitto Broker authority

The current fresh workflows freeze Broker as:

```text
BROKER_PRIMARY_SOURCE_REF=m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine
BROKER_FALLBACK_SOURCE_REF=docker.io/library/eclipse-mosquitto:2.1.2-alpine
BROKER_ARM64_MANIFEST_DIGEST=sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
BROKER_EXPECTED_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
BROKER_LOCAL_RUNTIME_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
PLATFORM=linux/arm64
```

Primary/fallback registries are transport choices only; the exact ARM64 manifest digest is
the component identity authority.

## 5. Runtime-source authority

The Clean Reference payload at S0 is also bound to the same source head for project-owned
runtime material, including at minimum:

```text
infra/n3w-t1/production/docker-compose.fresh.yml
infra/n3w-t1/production/homeassistant-configuration.yaml
infra/n3w-t1/broker/mosquitto.conf
infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap/**
tools/n3w_t1_fresh_product_bootstrap.py
tools/n3w_t1_fresh_product_staging_host.py
tools/n3w_t1_clean_product_deployment_gate.py
tools/n3w_t1_device_provisioning_host.py
```

These are source/runtime-contract inputs, not separate fourth product components.

## 6. Existing exact ARM64 build evidence

The exact source authority already has a successful exact-three-image CI run:

```text
WORKFLOW=N3W T1 fresh install exact ARM64 CI
RUN_ID=41275979177
RESULT=SUCCESS
SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
```

Its artifact currently exists and is not expired:

```text
ARTIFACT_ID=13070404405
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-24382caae4a1f5d459297f86e8d18f10a848ca64
ARTIFACT_SIZE_BYTES=2538800086
ARTIFACT_DIGEST=sha256:99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93
EXPIRES_AT=2026-12-01T05:20:26Z
```

This artifact is a valid S1 acquisition candidate. S0 does not yet declare the Mac cache
populated or the artifact locally verified.

## 7. Boundary and next route

```text
S0_RESULT=CLOSED_PASS
T1_B_APPLICATION_IMAGE_COUNT_EXPECTED_AT_S0=0
T1_CORE_STACK_DEPLOYED=false

NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_S1_EXACT_THREE_IMAGE_ARTIFACT_ACQUISITION_AND_MAC_CACHE_20261101_01
```

S1 should reuse the existing exact ARM64 artifact if its GitHub identity, source head and
archive digest remain exact. Rebuilding is required only if that artifact is unavailable,
expired, corrupt, or fails exact binding verification.
