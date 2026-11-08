# 温室环境监测系统（ESP32-C6）
# N3-W T1 R7A simplified-runtime OTA compatibility source-repair CI closure — 2026-11-08

```text
GATE=N3W_T1_R7A_SIMPLIFIED_RUNTIME_OTA_COMPATIBILITY_SOURCE_REPAIR_CI_CLOSURE_20261108_01
RESULT=CLOSED_PASS

REPOSITORY=chrenguo-stack/HomeAssistant
PR=800
PR_STATE=OPEN_DRAFT
SOURCE_REPAIR_HEAD=7807271e4c48161f2fad96a7886fa4c24b038321
SOURCE_REPAIR_TREE=3d2893914d62645011a9a4badc7f939d10f9029e

FAILED_WORKFLOW_RUN_ID=42452239964
ATTEMPT_1_RESULT=FAIL
ATTEMPT_1_FAILED_STEP=Verify uploaded exact binding
ATTEMPT_1_FAILURE=homeassistant-arm64.tar SHA256 mismatch after upload/redownload

ATTEMPT_2_RESULT=SUCCESS
EXACT_HEAD_CI=25_SUCCESS_0_FAILURE_0_PENDING
EXACT_ARM64_ARTIFACT_ID=13615963302
EXACT_ARM64_ARTIFACT_DIGEST_SHA256=72b05593b91c75912e05ccd3b00bc72af5bd7ec03e39c283d0ce7acfb513fbe7
EXACT_ARM64_ARTIFACT_SIZE_BYTES=2539062230
POST_UPLOAD_BINDING=PASS

MANAGER_TAR_SHA256=9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67
MANAGER_TAR_SIZE_BYTES=62950400
HOMEASSISTANT_TAR_SHA256=13a1b097562fdadb92fa0d75f37341ee8769191944e88bbe106c70373a5a8b64
HOMEASSISTANT_TAR_SIZE_BYTES=2448553472
BROKER_TAR_SHA256=7e14f96544edceb01a7db8f7f09bac4be48672ea66285679dd8fe8f1ead53d79
BROKER_TAR_SIZE_BYTES=27556352

FOCUSED_RUFF=PASS
FOCUSED_MANAGER_PYTEST=1538_PASS_1_SKIP
FOCUSED_HA_MQTT_BOOTSTRAP=1_PASS
FOCUSED_SOURCE_REVIEW=PASS
NEW_FALSE_PASS_BLOCKER_COUNT=0

KF_ID=KF-144
KF_STATUS=SOURCE_REPAIR_CLOSED_LIVE_REVALIDATION_PENDING

LIVE_T1_MUTATION=false
BOARD_ACCESS=false
PREPARE=false
USB_MUTATION=false
MERGE=false
```

## Root cause and repair

The live external Manager environment was correct: `GH_N3W_RUNTIME_ENABLED=true` and the R7A OTA variables were present. The defect was inside the simplified Manager compatibility layer. `N3wSimplifiedIsolatedMqttService` intentionally creates an internal Settings copy with legacy `n3w_runtime_enabled=false`; before this repair, that copy retained `n3w_t1_ota_enabled=true`, and the base `ManagerMqttService` constructor re-ran `Settings.validate()`, producing the observed restart-loop error.

The repair keeps the original validated Settings long enough to construct `T1OtaManager`, then, only when that already-built object is injected into the simplified service, clears the internal base-service `n3w_t1_ota_enabled` flag. OTA capability remains object-carried: MQTT OTA subscription, control handling, and Home Assistant OTA projection are all gated by the injected manager object rather than the internal compatibility flag.

A second source guard adds a 15-second post-activation hold and rechecks that the services owner remains active and the same Manager, Home Assistant and Broker container identities remain running. This prevents the earlier instantaneous-running false PASS.

## CI failure classification

Attempt 1 built and exercised the exact ARM64 Manager, validated the runtime/deployment contract and Home Assistant MQTT bootstrap, uploaded and redownloaded the artifact, then failed only at the downloaded Home Assistant tar SHA assertion.

No product-source path in the compatibility repair mutates that Home Assistant tar. Historical runs of the same workflow had passed with the same fixed Home Assistant image and same tar size. The unchanged-source failed-job rerun passed the exact same upload/download/SHA path and emitted `R6_EXACT_ARM64_POST_UPLOAD_BINDING=PASS`.

Therefore:

```text
FAILED_RUN_CLASSIFICATION=TRANSIENT_CI_ARTIFACT_ROUNDTRIP_INTEGRITY_FAILURE_NONREPRODUCED_ON_UNCHANGED_RERUN
PRODUCT_SOURCE_CAUSATION_PROVEN=false
WORKFLOW_SOURCE_REPAIR_REQUIRED=false
HASH_GUARD_WEAKENED=false
```

The first failed artifact remains historical evidence and is not promoted as closure authority.

## Live boundary

Production had already been restored by the separately authorized A1 wiring-withdrawal recovery. Source closure did not access or mutate the real T1 and did not reactivate OTA wiring. Boundary B remains invalidated for replay; no PREPARE/USB/U2+ work is resumed here.

```text
LIVE_T1_STATE=RECOVERED_OTA_DISABLED_HEALTHY
OLD_A1_AUTHORIZATION_REPLAY=false
OLD_BOUNDARY_B_PREPARE_AUTHORIZATION_REPLAY=false
```

## Next stage

```text
NEXT_ONE_GATE=N3W_T1_R7A_REPAIRED_MANAGER_EXACT_ARTIFACT_AND_FRESH_A1_REACTIVATION_PREEXECUTION_20261108_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_LIVE_AUTHORIZATION_REQUIRED_BEFORE_ANY_T1_MUTATION=true
```

The next stage may bind the successful exact repaired Manager artifact and prepare a fresh A1 reactivation chain. It must stop before any real-T1 deployment, service mutation, A1 activation, PREPARE, USB mutation or board operation unless separately authorized.
