# N3-W T1 Core Updater — Home Assistant product-grade upgrade validation preparation

Date: 2026-11-05

## 1. Gate

```text
TASK=N3W_T1_CORE_UPDATER_HOMEASSISTANT_PRODUCT_GRADE_UPGRADE_VALIDATION_PREPARATION_20261105_01
STATE=SOURCE_PREPARATION

ORIGINAL_BASE_MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774
ORIGINAL_UPSTREAM_U2_HEAD=f4ee85707e01e4359df39e155ee717a350a602b7
PR779_U2_CI=SUCCESS
SUCCESSOR_CONVERGENCE_BASE_MAIN=ede7bc85956fca8eb6c4e6ac31b76500b3432d99
PR790_U2_SUCCESSOR_MERGED=true
SOURCE_PARITY_TO_SUCCESSOR_MAIN=PASS

LIVE_T1_MUTATION=false
BOARD_ACCESS=false
HA_APPLY=false
HA_ROLLBACK=false
SERVICE_RESTART=false
IMAGE_LOAD=false
CREDENTIAL_MUTATION=false
MERGE=false
```

This preparation starts only after U2 CLOSED_PASS. It does not reopen Manager U1/KF-141 and
does not replay any consumed Manager authorization.

## 2. Current product baseline

Current accepted stack authority remains:

```text
MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER=local/n3w-mosquitto:2.1.2-3184566d

MANAGER_BINDING_MODE=dynamic
HOMEASSISTANT_BINDING_MODE=legacy_static
BROKER_BINDING_MODE=legacy_static
```

The fresh U2 runtime-state confirms the same live binding modes. Therefore the current T1 cannot
enter a Home Assistant V2 apply directly: the updater intentionally fails closed while the HA
binding is `legacy_static`.

## 3. Product target selection

The first product-grade HA upgrade candidate is:

```text
PREDECESSOR_VERSION=2026.10.0
CANDIDATE_VERSION=2026.10.4
MUTATION_PROFILE=IMAGE_ONLY_V1
```

Reason:

- `core.config_entries`: 1.5 -> 1.5;
- `core.device_registry`: 3.4 -> 3.4;
- `core.entity_registry`: 1.23 -> 1.23.

This keeps the first acceptance inside the current IMAGE_ONLY_V1 contract: image changes only,
without a known managed-storage migration.

The current stable 2026.11.0 is deliberately not the first acceptance target. Its
`core.entity_registry` minor version advances 1.23 -> 1.24 and contains a semantic registry
migration. That route requires a separate migration/rollback design and must not be falsely
presented as plain image-only rollback compatibility.

Machine-readable review:

`infra/n3w-t1/upgrades/homeassistant-2026.10.4-compatibility-review.json`

Canonical review payload SHA256:

`8b02e9bb0143fc4fc7900c4c0e4c52b27f92725cd41f1f03b82ba67ffb9e0267`

## 4. Focused updater safety repair

A product-level source review found that the existing A1 HA storage observation recorded only the
top-level `version`, not `minor_version`. That is insufficient for Home Assistant because real
storage migrations can occur on a minor-version advance.

Focused repair:

- capture `minor_version` for the three managed HA storage documents;
- compare `minor_version` before/after an IMAGE_ONLY_V1 mutation;
- fail with `a1_ha_storage_minor_version_drift:<label>` on any change;
- do not alter the existing A1 hard-authority/baseline shape.

This is intentionally backward-compatible with the closed Manager path: historical Manager
baseline/target authority does not change, while future HA apply postconditions become stricter.

## 5. Runtime-template convergence prerequisite

The V2 updater requires the selected component's image binding to be dynamic. U0 already recorded
HA/Broker as legacy-static and required a separate convergence gate before either module is
independently upgradeable.

Preparation adds a read-only inspector:

`tools/n3w_t1_core_updater_ha_template_convergence.py`

The inspector:

1. reads the current canonical Compose and env files;
2. constructs in memory the minimal HA-only convergence:
   - add exactly one `GH_HOMEASSISTANT_IMAGE=<current image>` env binding;
   - replace only the Home Assistant literal image source with the dynamic variable;
3. renders current and candidate Compose;
4. requires semantic equality of the complete rendered Compose;
5. returns PASS only when no effective product behavior changes.

It writes only temporary files under the system temporary directory for Compose rendering and
removes them automatically. It has no apply mode and cannot mutate product paths or restart a
service.

The read-only proof may proceed before any future Stack release is published. The live convergence
mutation may not proceed as a standalone manual deployment step. If live convergence is later
needed for HA validation, it must be executed by T1_Core_Updater as part of the same bounded updater
transaction that applies the exact HA target. It must use the exact candidate proven by this
read-only step and must not substitute the whole fresh Compose if doing so would introduce any
other semantic delta.

## 6. Exact HA package still required

The compatibility review is not an image artifact.

Before live HA apply, a later source/build gate must produce and bind:

```text
TARGET_COMPONENT=homeassistant
UPSTREAM_IMAGE=ghcr.io/home-assistant/home-assistant:2026.10.4
PLATFORM=linux/arm64
LOCAL_IMAGE=local/n3w-homeassistant:2026.10.4-<exact-arm64-digest-prefix>

TARGET_SCHEMA=gh.n3w-t1-core-updater-target/2
EXACT_IMAGE_TAR=true
TARGET_ARCHIVE_SHA256=REQUIRED
ARTIFACT_ID=REQUIRED
ARTIFACT_DIGEST_SHA256=REQUIRED
PORTABLE_IMAGE_IDENTITY=REQUIRED
COMPATIBILITY_REVIEW_SHA256=8b02e9bb0143fc4fc7900c4c0e4c52b27f92725cd41f1f03b82ba67ffb9e0267
```

No target manifest may set `persistent_schema_compatible=true` or
`rollback_compatible=true` without this review and exact image smoke/portable-identity evidence.

## 7. Baseline rule

Do not reuse the old U0 baseline directly for HA apply. It predates the accepted Manager B.

Do not mutate HA template convergence merely to create a baseline. The fresh updater baseline must
be captured twice before any updater-owned HA mutation.

Expected predecessor baseline:

```text
STACK_VERSION=1.0.0
MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER=local/n3w-mosquitto:2.1.2-3184566d
MANAGER_BINDING_MODE=dynamic
HOMEASSISTANT_BINDING_MODE=legacy_static
BROKER_BINDING_MODE=legacy_static
```

The HA binding changes to `dynamic` only inside a later explicitly authorized T1_Core_Updater
transaction that also owns the HA component mutation and rollback evidence.

## 8. Product-grade updater acceptance route

This workstream remains a T1_Core_Updater validation route. It does not publish or deploy a new
T1_Core_Stack release.

The bounded route is:

```text
HA_P0_SOURCE_AND_COMPATIBILITY_PREPARATION
-> HA_P1_RUNTIME_TEMPLATE_CONVERGENCE_READONLY_PREFLIGHT
-> HA_P2_EXACT_2026_10_4_PACKAGE_AND_COMPONENT_TARGET
-> HA_P3_UPDATER_SOURCE_SIMULATION_AND_READONLY_PLAN
-> HA_P4_FRESH_READONLY_PREMUTATION_BASELINE
-> HA_P5_EXPLICIT_UPDATER_AUTHORIZATION
-> HA_P6_UPDATER_LIVE_TRANSACTION
     -> HA_RUNTIME_TEMPLATE_CONVERGENCE_MUTATION
     -> HA_COMPONENT_APPLY
     -> MANAGER_HA_BROKER_ACCEPTANCE
-> HA_P7_EXPLICIT_UPDATER_ROLLBACK_PROOF
     -> restore HA predecessor image
     -> restore predecessor HA binding
     -> verify full predecessor product health
-> HA_P8_FRESH_AUTHORIZATION_AND_FINAL_HA_REAPPLY
-> HA_P9_FINAL_UPDATER_ACCEPTANCE
```

A future T1_Core_Stack 1.1.0 product release may reuse the validated result of this work, but release
publication is outside this gate.

Live authorizations are one-shot and stage-specific. An apply or rollback authorization is not
created by this preparation document.

## 9. Required acceptance properties

A product PASS must prove:

- only HA image binding changes;
- Manager image/runtime contract remains unchanged across HA image mutation;
- Broker image/runtime contract remains unchanged;
- the Manager + HA shared systemd owner lifecycle is respected;
- HA MQTT identity is unchanged and authenticated again;
- Manager MQTT authentication is restored after the shared owner restart;
- HA HTTP is healthy (200/401);
- listener contract is restored;
- HA fixed configuration and n3w_mqtt_bootstrap tree remain unchanged;
- HA persistent path ownership/type remains safe;
- managed HA storage major and minor versions remain unchanged for IMAGE_ONLY_V1;
- exact target portable image identity is verified;
- rollback restores exact predecessor HA binding and product health;
- no consumed authorization is replayed.

## 10. Current stop boundary

```text
LIVE_HA_UPGRADE_READY=false
HA_RUNTIME_TEMPLATE_CONVERGENCE_REQUIRED=true
HA_EXACT_TARGET_PACKAGE_READY=false
STACK_1_0_0_RELEASE_FROZEN=true
STACK_1_1_0_RELEASE_BUILD_IN_THIS_WORKSTREAM=false
INDEPENDENT_HA_CONVERGENCE_MUTATION_ALLOWED=false
FIELD_UPGRADE_EXECUTOR=T1_Core_Updater

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_HOMEASSISTANT_RUNTIME_TEMPLATE_CONVERGENCE_READONLY_PREFLIGHT_20261105_01

NEXT_AFTER_READONLY_GATE=EXACT_HA_2026_10_4_UPDATER_ARTIFACT_AND_COMPONENT_TARGET
NEXT_GATE_LIVE_MUTATION=false
AUTO_EXECUTE_MUTATION=false
```

The next gate is read-only against the real T1 and may only inspect whether the minimal HA
legacy-static -> dynamic source convergence is semantically identical. It stops before any product
file write or service restart. A PASS goes to exact HA updater artifact/component-target
construction, not to Stack 1.1.0 publication and not directly to a live template mutation.
