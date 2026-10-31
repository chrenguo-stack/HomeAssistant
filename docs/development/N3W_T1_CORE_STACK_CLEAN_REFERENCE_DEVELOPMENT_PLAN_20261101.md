# N3-W T1_Core_Stack clean reference development plan
# 2026-11-01

## 0. Status

```text
PLAN_STATUS=FROZEN_FOR_NEXT_CHAT
CANONICAL_PRODUCT_STACK=T1_Core_Stack
COMPONENTS=greenhouse-manager,Home Assistant,Mosquitto Broker

OLD_E03_UPGRADE_ROUTE=PAUSED
PR745_INTEGRATION=PAUSED_UNMERGED
LIVE_UPGRADE_RETRY=false

CLEAN_REFERENCE_ROUTE=SELECTED
```

This plan replaces the immediate continuation of E03 transaction/recovery patching.
It does not discard the incident evidence or PR #745 source work; both remain historical
engineering evidence while the upgrade architecture is rebuilt from a clean product
reference.

## 1. Governing design principle

The upgrade architecture must be derived from values that are stable across healthy T1
operation, not from exact equality with a historical runtime snapshot.

Every observed field must be classified as:

```text
HARD_STABLE_INVARIANT
SOFT_RUNTIME_CHECK
DIAGNOSTIC_ONLY
REMOVE
```

A HARD_STABLE_INVARIANT must satisfy both:

1. it is expected to remain stable on every healthy T1 through normal runtime/reboot; and
2. violating it creates a concrete upgrade-safety or compatibility risk.

## 2. Local artifact policy

The previously accepted Mac exact-artifact-cache mechanism remains valid and preferred for
large artifacts.

However, the 2026-10-15 cached product artifact is now explicitly historical and must not
be used for the new clean reference:

```text
OLD_LOCAL_CACHE_ARTIFACT_ID=11954286988
OLD_LOCAL_CACHE_ARTIFACT_ZIP_SHA256=047a40ed640bc1bfcbc8adb7007da2a4eea1f8abedffbc3cb2e2a4d9f6817928
OLD_LOCAL_CACHE_REUSE_ALLOWED=false
REASON=MANAGER_AND_PRODUCT_SOURCE_ADVANCED_AFTER_2026_10_15
```

The cache mechanism itself stays active:

```text
MAC_EXACT_ARTIFACT_CACHE_REUSE_POLICY=KEEP
NEW_EXACT_T1_CORE_STACK_DOWNLOAD_COUNT_TARGET=ONE
CACHE_HIT_REQUIRES_EXACT_ARTIFACT_BINDING=true
CACHE_REUSE_ACROSS_ARTIFACT_IDENTITY_CHANGE=false
DEFAULT_CACHE_ROOT=~/Documents/N3W/exact-artifacts
```

After the new T1_Core_Stack source/version set is frozen, acquire the exact large artifact
once, verify its complete binding, populate the durable Mac cache, and reuse that exact
cached artifact for repeat T1 deployment/testing until the frozen product artifact changes.

## 3. Offline-install boundary

Current capability:

```text
T1_CORE_STACK_IMAGE_DEPLOYMENT_OFFLINE_CAPABLE=true
FRESH_ARMBIAN_END_TO_END_AIRGAPPED_INSTALL=false
```

The three product images can be staged and loaded locally. A newly installed Armbian host
can still depend on network APT sources for Docker Engine, Compose and host packages.
Full air-gapped host installation is a later productization phase and does not block the
clean-reference experiment.

## 4. Evidence already preserved before wiping the old T1

The old failed-upgrade T1 maintenance evidence has been privately archived by the operator.

```text
PREWIPE_PRIVATE_EVIDENCE_ARCHIVED=true
PREWIPE_PRIVATE_EVIDENCE_SHA256=711359c2b6a3522daac4ce9697a20b9876b71f202b44d6c79f65eda79f67025c
PUBLIC_REPOSITORY_CONTAINS_PRIVATE_ARCHIVE=false
OLD_T1_RUNTIME_MAY_BE_DISCARDED=true
```

Historical failed transaction/recovery conclusions remain in PR #705/#745 and repository
documents. The clean-reference route must not replay their consumed authorizations.

## 5. Phased development route

### Phase R0 — Fresh Armbian read-only baseline

Operator prepares one T1 with official Armbian only.

First new-chat gate is read-only and records the clean host before product-runtime
installation.

Collect only current host facts needed to establish a clean baseline, for example:

- architecture / OS release / kernel;
- machine identity presence without publishing private raw identity;
- storage and filesystem capacity;
- network manager / default-route / time-sync state;
- installed Docker/Compose presence or absence;
- product containers/images/volumes/networks absence;
- T1_Core_Stack product paths/units/listeners absence.

Do not install Docker, packages or product software in R0.

```text
R0_MUTATION=false
R0_RESULT=FRESH_ARMBIAN_REFERENCE
```

### Phase R0H — Host runtime establishment

After R0 closes, separately authorize the minimum host-runtime mutation required by the
current supported route.

Likely scope:

- Docker Engine / Compose baseline;
- required host packages;
- repository-owned host units/guards only when actually required for the product route.

This phase must distinguish stable host prerequisites from distro/runtime details that are
allowed to vary.

```text
R0H_T1_MUTATION=true
R0H_PRODUCT_STACK_DEPLOYMENT=false
```

### Phase S0 — Freeze the new exact T1_Core_Stack source/version set

Freshly rebind current product source and independently freeze:

- greenhouse-manager source/artifact identity;
- Home Assistant image/version identity;
- Mosquitto image/version identity;
- production Compose/config contract;
- compatibility assumptions between the three services.

Do not default to the 2026-10-15 artifact or the historical E03 successor target.

```text
S0_OLD_CACHE_AUTHORITY=false
S0_NEW_EXACT_ARTIFACT_REQUIRED=true
```

### Phase S1 — Build/acquire once and populate Mac exact cache

Produce or select the exact T1_Core_Stack deployable artifact for S0.

Requirements:

- fresh exact binding;
- complete outer/inner SHA verification;
- all three image bindings;
- local durable cache population;
- second cache-only verification with no large GitHub download.

```text
S1_LARGE_DOWNLOAD_EXPECTED_COUNT=1
S1_FUTURE_SAME_ARTIFACT_DOWNLOAD_REQUIRED=false
```

### Phase R1 — Clean T1_Core_Stack deployment and first reference

Deploy the newly frozen stack to the R0/R0H host using the supported production route,
complete explicit per-device provisioning, then start and accept the three product
services.

Before pairing customer/board nodes or accumulating business history, capture:

- stable component identity;
- fixed configuration contracts;
- persistent path/schema contracts;
- service ownership and interface contracts;
- minimum product-health observations;
- runtime-variable observations for later comparison.

```text
R1_REFERENCE=CLEAN_T1_CORE_STACK_FIRST_RUNNING_REFERENCE
CUSTOMER_NODE_PAIRING=false
```

### Phase R2 — Controlled reboot reference

Perform one normal controlled T1 reboot, allow normal convergence, then repeat the same
reference collection.

Compare R1 vs R2.

Any value that changes solely due to a healthy reboot is presumptively disqualified from
HARD_STABLE_INVARIANT unless a separate safety argument proves otherwise.

```text
R2_REFERENCE=POST_REBOOT_CLEAN_T1_CORE_STACK_REFERENCE
R1_R2_DIFF_CLASSIFICATION_REQUIRED=true
```

### Phase R3 — Normal business-runtime reference

Only after R1/R2 analysis, introduce a bounded normal workload, preferably one ordinary
node/pairing path, and collect the same reference again.

Compare R2 vs R3 to identify fields that change under legitimate product use.

```text
R3_REFERENCE=NORMAL_RUNTIME_REFERENCE
R3_BOARD_WORK_REQUIRES_SEPARATE_GATE=true
```

### Phase A1 — Stable-invariant classification

Create the authoritative table for all collected fields:

```text
FIELD
OWNER_MODULE
R0_VALUE_CLASS
R1_VALUE_CLASS
R2_CHANGED
R3_CHANGED
CLASSIFICATION
CONCRETE_SAFETY_REASON
```

No field becomes a hard gate merely because it was easy to hash.

### Phase A2 — Per-module upgrade architecture

Redesign upgrades independently:

```text
MANAGER_UPGRADE_SCOPE=MANAGER_ONLY_BY_DEFAULT
HOMEASSISTANT_UPGRADE_SCOPE=HOMEASSISTANT_ONLY_BY_DEFAULT
BROKER_UPGRADE_SCOPE=BROKER_ONLY_BY_DEFAULT
```

Cross-module coordinated upgrade is permitted only when an explicit compatibility boundary
requires it.

Historical terminal maintenance evidence should not remain a permanent runtime blocker.
Only unresolved current maintenance may block a new upgrade.

### Phase O1 — Full offline installation

After the clean reference and simplified upgrade architecture converge, finish the
end-to-end air-gapped installer by packaging the required host packages/dependencies in
addition to the three product images.

This is not part of R0/R1/R2 acceptance.

## 6. Current repository boundaries

```text
PR705=ACTIVE_PARENT_WORKSPACE
PR745=OPEN_UNMERGED_ARCHITECTURE_HOLD
PR746=MERGED_INTO_PR705
PR705_UPWARD_MERGE=false
```

PR #745 may later be:

- retained as incident-reference source;
- selectively harvested if a simplified design needs one of its bounded fixes; or
- closed as superseded.

Do not merge it automatically before A1/A2 decides whether its recovery/gate lineage model
belongs in the simplified architecture.

## 7. Next one gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0_FRESH_ARMBIAN_READONLY_BASELINE_20261101_01
```

This gate starts only after the operator reports that the T1 has been wiped/reinstalled
with official Armbian and no T1_Core_Stack product deployment has occurred.

It is read-only. It must not install Docker, install packages, deploy images, provision the
product instance, start T1_Core_Stack, access boards, or reuse old artifact/authorization
state.
