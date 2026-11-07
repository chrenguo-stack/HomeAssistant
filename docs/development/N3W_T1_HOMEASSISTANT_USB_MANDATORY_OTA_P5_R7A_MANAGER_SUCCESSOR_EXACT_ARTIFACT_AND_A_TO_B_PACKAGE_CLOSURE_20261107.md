# N3-W T1 Home Assistant mandatory-USB OTA R7A Manager successor exact artifact + A-to-B package closure — 2026-11-07

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_MANAGER_SUCCESSOR_EXACT_ARTIFACT_AND_A_TO_B_PACKAGE_20261107_01
RESULT=CLOSED_PASS_PACKAGE_READY_NOT_EXECUTED

PR=800
PR_BRANCH=feat/n3w-ha-usb-r7a-prepare-pipeline-20261107
PACKAGE_CONTROL_HEAD=921e7d5557ff3dbf4b7e7ae5510186d98f803a2a
MANAGER_ARTIFACT_SOURCE_HEAD=bf38e388497b0d480f4bd322426e32a98652cf6c

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
MANAGER_LIVE_UPGRADE=false
SERVICE_MUTATION=false
DOCKER_RUNTIME_MUTATION=false
REAL_USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This gate closes only the exact R7A-capable Manager successor artifact and the Generic V2 Manager A-to-B execution package required for Boundary A0. The accepted live T1 stack is unchanged.

## 2. Why a Manager successor is required

The accepted production Manager remains:

```text
local/greenhouse-manager:fresh-5b32e1ae8210
```

That image predates the R7A Manager OTA control-plane source. Adding the HA-OTA Compose overlay or host socket cannot add missing code to an already-built container image.

Therefore the physical R7A sequence requires a bounded Manager-only predecessor-to-successor transition first, while `GH_N3W_T1_OTA_ENABLED=false`.

## 3. Exact ARM64 source artifact

Successful exact ARM64 workflow:

```text
RUN_ID=42347679643
RUN_RESULT=SUCCESS
ARTIFACT_ID=13564472128
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-bf38e388497b0d480f4bd322426e32a98652cf6c
ARTIFACT_DIGEST_SHA256=eca37ec38d29c488e271b16de11af2d13b18ca2867694e92ccc4b5366cea3dd8
POST_UPLOAD_BINDING=PASS
```

Manager slice:

```text
TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-bf38e388497b
MANAGER_BUILD_IMAGE_ID=sha256:136cdcacf84a388a91cf0adbf7e0653a78b754e1879a59d3a2ac066ecba9fa5f
MANAGER_TAR_SHA256=4c4492ef5008a968b2553240b3fde97912eb3ae862604ae492e5a639a93db008
MANAGER_TAR_SIZE_BYTES=62950912
TARGET_PLATFORM=linux/arm64
```

The artifact binding reports source head `bf38e388497b0d480f4bd322426e32a98652cf6c`.

Independent continuity review from the artifact source head to package control head found seven later commits and **zero Manager product-source changes** under `host/greenhouse-manager/src/`.

## 4. Compatibility authority

```text
PREDECESSOR_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
TARGET_SOURCE_HEAD=bf38e388497b0d480f4bd322426e32a98652cf6c

COMPATIBILITY_AUTHORITY=infra/n3w-t1/upgrades/manager-bf38e388497b-compatibility.json
COMPATIBILITY_CANONICAL_PAYLOAD_SHA256=d898d0439f628522343f8d367d179bf42ae43a9868be1d52c2cb28534a3824b0

MUTATION_PROFILE=IMAGE_ONLY_V1
PEER_CONTRACTS_COMPATIBLE=true
PERSISTENT_SCHEMA_COMPATIBLE=true
DATABASE_MIGRATION_REQUIRED=false
CONFIG_MIGRATION_REQUIRED=false
RUNTIME_TEMPLATE_CHANGE_REQUIRED=false
BROKER_CHANGE_REQUIRED=false
HOMEASSISTANT_CHANGE_REQUIRED=false
BOARD_CHANGE_REQUIRED=false
ROLLBACK_COMPATIBLE=true
```

R7A Manager adds a default-off OTA configuration/control surface, read-only approved-manifest provider, narrow AF_UNIX client and Home Assistant MQTT projection. It does not add a persistent database schema or migration path. Boundary A0 keeps OTA disabled.

## 5. Current-stack predecessor baseline

```text
BASELINE_AUTHORITY=infra/n3w-t1/clean-reference/r7a-manager-predecessor-baseline-20261107.json
BASELINE_FILE_SHA256=68e5021ed0010ea97c11d2fa8e05254ae234ae8ba92953f7c57cf8519a51672a
BASELINE_CANONICAL_SHA256=78c3b0b58ad39cf887689658bec90c8466d30a93d58830b0289f1463dafad868
```

The canonical baseline SHA exactly matches the independently captured real-T1 P4 double-read stable baseline from 2026-11-05:

```text
P4_REAL_T1_BASELINE_SHA256=78c3b0b58ad39cf887689658bec90c8466d30a93d58830b0289f1463dafad868
BASELINE_MATCH=PASS
```

Bound predecessor stack:

```text
Manager=local/greenhouse-manager:fresh-5b32e1ae8210
Home Assistant=local/n3w-homeassistant:2026.10.0-0c73235a
Broker=local/n3w-mosquitto:2.1.2-3184566d

Manager binding mode=dynamic
Home Assistant binding mode=legacy_static
Broker binding mode=legacy_static
```

## 6. Manager target manifest

```text
TARGET_AUTHORITY=infra/n3w-t1/upgrades/manager-bf38e388497b.json
TARGET_SCHEMA=gh.n3w-t1-core-updater-target/2
TARGET_MANAGER=local/greenhouse-manager:fresh-bf38e388497b
EXPECTED_PREDECESSOR_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
TARGET_ARCHIVE_SHA256=4c4492ef5008a968b2553240b3fde97912eb3ae862604ae492e5a639a93db008
ARTIFACT_ID=13564472128
ARTIFACT_DIGEST_SHA256=eca37ec38d29c488e271b16de11af2d13b18ca2867694e92ccc4b5366cea3dd8
ROLLBACK_COMPATIBLE=true
```

## 7. Final Manager-only V2 package

Successful package workflow:

```text
RUN_ID=42349904235
RUN_NUMBER=399

SOURCE=PASS
EXACT_MANAGER_SLICE=PASS
PRE_U1_V2_SIMULATION=PASS
```

Final package:

```text
PACKAGE_ARTIFACT_ID=13564899377
PACKAGE_NAME=n3w-t1-core-updater-manager-v2-bf38e388497b
PACKAGE_ARTIFACT_DIGEST_SHA256=6e9ca4cf103434330c0a31b51e1ba27b7d12b554648f4b0a017fd69bc4a32e1c
PACKAGE_SIZE_BYTES=63169493

PACKAGE_CONTROL_HEAD=921e7d5557ff3dbf4b7e7ae5510186d98f803a2a
TARGET_SOURCE_HEAD=bf38e388497b0d480f4bd322426e32a98652cf6c
UPSTREAM_RUN_ID=42347679643
UPSTREAM_ARTIFACT_ID=13564472128
UPSTREAM_ARTIFACT_DIGEST_SHA256=eca37ec38d29c488e271b16de11af2d13b18ca2867694e92ccc4b5366cea3dd8

MANAGER_BUILD_IMAGE_ID=sha256:136cdcacf84a388a91cf0adbf7e0653a78b754e1879a59d3a2ac066ecba9fa5f
MANAGER_TAR_SHA256=4c4492ef5008a968b2553240b3fde97912eb3ae862604ae492e5a639a93db008
MANAGER_TAR_SIZE_BYTES=62950912

UPDATER_PYZ_SHA256=1b556d5601f33ef050c91e990bedaaeb1611bef325350fad008a1ec69fc7dc99
UPDATER_PYZ_SIZE_BYTES=212673

MANAGER_REBUILT=false
HOMEASSISTANT_INCLUDED=false
BROKER_INCLUDED=false
SECRET_VALUES_INCLUDED=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
```

The package was re-downloaded and re-verified by CI after upload.

## 8. Simulation closure

The first retargeted run produced a valid exact package but the historical pre-U1 simulation still loaded the old predecessor/target fixture. The failure was a test-authority drift, not a Manager artifact/package failure.

The simulation was repaired to use:

```text
TARGET=infra/n3w-t1/upgrades/manager-bf38e388497b.json
BASELINE=infra/n3w-t1/clean-reference/r7a-manager-predecessor-baseline-20261107.json
CURRENT_STACK_AUTHORITY=infra/n3w-t1/production/t1-core-stack-current.json
```

The replacement run passed source, exact package and full pre-U1 plan/apply/rollback simulation.

## 9. Live authority remains unchanged

This closure does **not** promote the successor to accepted production.

```text
CURRENT_ACCEPTED_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_ACCEPTED_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_ACCEPTED_BROKER=local/n3w-mosquitto:2.1.2-3184566d

TARGET_MANAGER=local/greenhouse-manager:fresh-bf38e388497b
TARGET_MANAGER_LIVE_ACCEPTED=false

LIVE_T1_MUTATION=false
MANAGER_LIVE_UPGRADE=false
```

The production authority must not advance until a separately authorized real-T1 A0 transaction completes and acceptance evidence passes.

## 10. Next ONE gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_MANAGER_SUCCESSOR_A0_LIVE_EXECUTION_PACKAGE_PREEXECUTION_20261107_01
NEXT_SCOPE=SOURCE_ONLY_A0_EXECUTOR_AND_PREEXECUTION_REVIEW

REPOSITORY_MUTATION=true
LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
MANAGER_LIVE_UPGRADE=false
SERVICE_MUTATION=false
DOCKER_RUNTIME_MUTATION=false
REAL_USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

The next gate may build and review the exact operator-side A0 executor around this frozen package. It must stop before opening the real SSH epoch or invoking updater apply.

Real A0 execution is a separate explicit authorization boundary.
