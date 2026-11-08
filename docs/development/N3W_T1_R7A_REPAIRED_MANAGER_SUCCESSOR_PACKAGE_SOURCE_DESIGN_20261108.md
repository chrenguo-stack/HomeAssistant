# N3W T1 R7A repaired Manager successor package source design — 2026-11-08

```text
GATE=N3W_T1_R7A_REPAIRED_MANAGER_EXACT_ARTIFACT_AND_FRESH_A1_REACTIVATION_PREEXECUTION_20261108_01
PHASE=REPAIRED_MANAGER_PACKAGE_SOURCE_DESIGN

PREDECESSOR_SOURCE=bf38e388497b0d480f4bd322426e32a98652cf6c
PREDECESSOR_IMAGE=local/greenhouse-manager:fresh-bf38e388497b
TARGET_SOURCE=7807271e4c48161f2fad96a7886fa4c24b038321
TARGET_IMAGE=local/greenhouse-manager:fresh-7807271e4c48

UPSTREAM_RUN_ID=42452239964
UPSTREAM_SUCCESS_ATTEMPT=2
UPSTREAM_ARTIFACT_ID=13615963302
UPSTREAM_ARTIFACT_DIGEST_SHA256=72b05593b91c75912e05ccd3b00bc72af5bd7ec03e39c283d0ce7acfb513fbe7
MANAGER_TAR_SHA256=9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67

MUTATION_PROFILE=IMAGE_ONLY_V1
DATABASE_MIGRATION_REQUIRED=false
CONFIG_MIGRATION_REQUIRED=false
RUNTIME_TEMPLATE_CHANGE_REQUIRED=false
HOMEASSISTANT_CHANGE_REQUIRED=false
BROKER_CHANGE_REQUIRED=false
BOARD_CHANGE_REQUIRED=false
ROLLBACK_COMPATIBLE=true

LIVE_T1_MUTATION=false
A1_REACTIVATION=false
PREPARE=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## Exact artifact identity

Run 42452239964 contains two artifacts with the same artifact name because attempt 1 failed after upload and attempt 2 reran the failed job successfully. Therefore artifact name is not unique authority for this successor.

The package builder must select the upstream artifact by the frozen successful artifact ID 13615963302 and independently require the expected name, SHA-256 digest, run ID and source head. The historical failed-attempt artifact 13605603605 remains evidence and must not be deleted or silently selected.

## Compatibility delta

The executable Manager product delta from bf38e388497b0d480f4bd322426e32a98652cf6c to 7807271e4c48161f2fad96a7886fa4c24b038321 is limited to:

```text
host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_isolated_mqtt_service.py
```

The repair changes only the internal simplified-runtime/base-service OTA compatibility behavior. It introduces no persistent schema, database, Home Assistant, Broker, board or runtime-template migration.

## Predecessor baseline provenance

The repository does not claim a fresh live baseline capture in this source-only gate.

The package baseline is a derived preexecution candidate. It starts from the previously live-captured R7A predecessor baseline and advances only:

```text
stack_images.manager:
  local/greenhouse-manager:fresh-5b32e1ae8210
  ->
  local/greenhouse-manager:fresh-bf38e388497b
```

All A1 hard authority, image binding modes, platforms and runtime-contract hashes remain identical. This derivation is supported by the accepted bf38 Generic V2 IMAGE_ONLY_V1 apply and its post-target runtime-contract validation, followed by the later A1 wiring-withdrawal recovery that restored the OTA-disabled base runtime path.

This is not a substitute for live eligibility. Before any future Manager mutation, Generic V2 must compare the baseline against a fresh live snapshot and fail closed on any stack image, binding mode, platform, runtime-contract or A1 hard-authority drift.

## Package simulation authority

The repaired package simulation must not use the repository canonical current-stack JSON as if it represented the current PR-local live predecessor, because that canonical authority still records the older 5b32 Manager. The simulation instead binds the explicit bf38 predecessor evidence and proves:

- exact target archive verification;
- manager-only apply;
- unchanged Home Assistant and Broker;
- unchanged runtime contract;
- COMMITTED target state;
- explicit rollback back to bf38;
- no T1 or board access.

## Gate boundary

This source/package phase does not authorize a real T1 SSH epoch, Manager deployment, service restart, A1 reactivation, PREPARE, USB insertion/write, U2+, board access or merge. A fresh live read-only eligibility check and a new one-shot authorization remain mandatory after package/preexecution closure.
