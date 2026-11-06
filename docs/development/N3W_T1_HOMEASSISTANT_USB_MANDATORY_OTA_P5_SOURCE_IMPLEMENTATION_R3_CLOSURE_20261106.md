# N3-W T1 Home Assistant mandatory-USB OTA P5 source implementation R3 closure — 2026-11-06

## 1. Gate result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R3_20261106_01
GATE_RESULT=CLOSED_PASS

R2_EXECUTABLE_SOURCE_HEAD=e5d9575d24d30f2498e1e64cedd245b6f124c866
R3_FRESH_BASE_HEAD=86b6c0cc671d6f2050593878f43b615c2351df73
R3_EXECUTABLE_SOURCE_HEAD=f30b7cf154abdbfed1863074ed855949aaecaf3b
PR=#788
BRANCH=review/n3w-t1-core-updater-storage-policy-20261105

APPLICABLE_WORKFLOW_COUNT=19
SUCCESS=19
FAILURE=0
EXPECTED_SKIPPED_WORKFLOW_COUNT=2

LIVE_T1_MUTATION=false
REAL_USB_FORMAT=false
REAL_BLOCK_DEVICE_ACCESS=false
REAL_DOCKER_COMMAND=false
BOARD_ACCESS=false
MERGE=false
R4_ENTERED=false
```

R3 closes the non-privileged greenhouse-manager OTA control-plane slice for the mandatory-USB Home Assistant successor route. It implements approved-manifest normalization, Home Assistant MQTT Update projection, a separate PREPARE control surface, and strict PREPARE / INSTALL / STATUS intent admission while preserving the existing Manager MQTT client and all privilege boundaries.

R3 does not activate a real upgrade path on T1. The host-side `T1_Core_Updater` remains the sole real USB/Docker/HA-data mutation authority. Production runtime wiring is intentionally unchanged until R4.

## 2. Final executable source authority

```text
runtime/t1_ota_manager.py=bb48962b4cc78bc91b337e16ef931bfd36f0de8d
runtime/ha_update.py=40bebdfd2d286138bd20715bdf2f099db1c4b962
runtime/mqtt_service.py=12358fa9ab68bdf8796f64c92b452878049e5aee
runtime/topics.py=e9199f546a00b9492c5b3efaf4c7f7dad6c69aae

tests/runtime/test_t1_ota_manager.py=6086dee11a5c24f86a78ab473cbe654341422e47
tests/runtime/test_ha_update.py=e32a07aacccedf77bcbaabb5a337b98d669e8f38
tests/runtime/test_mqtt_ota_control_plane.py=febb4074f04630e4d2df1ce503719a2cb0443b7c
```

The production authority and runtime-control files below remain byte-identical to the R3 fresh base:

```text
infra/n3w-t1/production/t1-core-stack-current.json=07ceb3b352f21d925127caa71304cc3b29827fdb
infra/n3w-t1/production/docker-compose.yml=8c469fd0d2fcaea52733d68c5799e95bf5001ecf
runtime/config.py=ed4f334bb5f265b8eef55b4433be5d2d7074d672
runtime/n3w_manager_runtime_wiring.py=55c448cab9e7665bb9b11209950b505f116d5ef0
```

Therefore:

```text
CURRENT_AUTHORITY_MANIFEST_CHANGED=false
PRODUCTION_COMPOSE_CHANGED=false
PRODUCTION_RUNTIME_WIRING_CHANGED=false
PRODUCTION_MANAGER_ACTIVATION_CHANGED=false
LIVE_T1_RUNTIME_CHANGED=false
```

## 3. Approved-manifest control-plane contract

R3 adds `ApprovedManifestProvider` as an interface only. There is no hard-coded GitHub/CDN/network provider in this gate.

Normalization is fail-closed and requires exact envelope fields plus:

```text
schema=gh.n3w-t1-ota-approved-manifest/1
approval_status=APPROVED
signature_status=VERIFIED
validity_status=VALID
verification_status=PASS
component=homeassistant
platform=linux/arm64
target_schema=gh.n3w-t1-core-updater-target/2
mutation_profile=IMAGE_ONLY_V1
rollback_compatible=true
```

The frozen Home Assistant 2026.10.4 target manifest is used as the test vector. Target image/version binding, archive SHA-256, artifact identity, compatibility evidence and 40-character source-head identities are independently validated.

Unsigned, unapproved, expired, unsupported, ambiguous or malformed provider results do not become installable updates.

## 4. Home Assistant user surface

R3 deliberately preserves two product actions:

```text
PREPARE != INSTALL
```

The mapping is:

```text
MQTT Update entity:
  - installed/latest version
  - update availability
  - in-progress/progress state
  - final INSTALL command only when ota_phase=READY_TO_INSTALL

MQTT Button entity:
  - PREPARE only
  - visible only while an update is available, not already ready, and not in progress
```

This avoids the forbidden semantic collapse where pressing the ordinary Update install action would silently perform PREPARE and INSTALL as one step.

The implementation was independently checked against the current Home Assistant MQTT Update and MQTT Button contracts:

```text
MQTT_UPDATE_JSON_STATE_CONTRACT=PASS
MQTT_UPDATE_COMMAND_TOPIC_PAYLOAD_INSTALL=PASS
MQTT_BUTTON_COMMAND_TOPIC_PAYLOAD_PRESS=PASS
```

References:

- https://www.home-assistant.io/integrations/update.mqtt
- https://www.home-assistant.io/integrations/button.mqtt/

## 5. Control intent and privilege boundary

The accepted MQTT control payload has exactly two fields:

```json
{
  "action": "PREPARE | INSTALL | STATUS",
  "target_release_id": "<manifest-owned release identity>"
}
```

Unknown fields fail closed. Duplicate JSON fields fail closed. The release identity must exactly match the currently approved manifest.

The MQTT payload cannot supply:

```text
host path
block-device path
Docker arguments
shell command
authorization ID
transaction token
private evidence locator
credential/private value
```

Transport admission is also fail-closed:

```text
RETAINED_CONTROL_MESSAGE=REJECT
CONTROL_QOS_NOT_1=REJECT
WILDCARD_CONTROL_SUBSCRIPTION=false
```

The retained-message guard prevents an old PREPARE/INSTALL command from being replayed automatically after an MQTT reconnect.

## 6. PREPARE / INSTALL / STATUS semantics

```text
STATUS:
  read-only
  does not submit mutation intent

PREPARE:
  requires approved newer release
  rejected while another OTA phase is in progress
  rejected after READY_TO_INSTALL

INSTALL:
  requires approved newer release
  requires ota_phase=READY_TO_INSTALL
  rejected before READY_TO_INSTALL
```

R3 does not claim that a PREPARE or INSTALL intent has reached a privileged executor. The `OtaIntentSink` remains a narrow non-privileged interface seam for R4.

## 7. Existing MQTT client reuse

Final source review confirms:

```text
NEW_MQTT_CLIENT_CREATED_BY_R3=false
EXISTING_MANAGER_MQTT_CLIENT_REUSED=true
SECOND_MANAGER_CLIENT_ID=false
```

`ManagerMqttService` retains its single existing `mqtt.Client(...)`. OTA subscription/publication is optional and injected into that service; no auxiliary process or second Paho client is introduced.

## 8. CI and regression result

Final exact executable head:

```text
R3_EXECUTABLE_SOURCE_HEAD=f30b7cf154abdbfed1863074ed855949aaecaf3b
APPLICABLE_WORKFLOW_COUNT=19
SUCCESS=19
FAILURE=0
EXPECTED_SKIPPED=2
```

All applicable workflows completed successfully, including:

- greenhouse-manager CI;
- N3W T1 Core Updater Home Assistant 2026.10.4 target binding CI;
- N3W T1 Core Updater Manager A-to-B CI;
- N3W T1 Core Stack current authority CI;
- N3W CI fast source and exact closure contract;
- Public repository safety CI;
- M2 manager runtime secret ownership CI;
- M2 Dynamic Security CI;
- node auth isolated/board/native-board CI;
- C-06 history replay host-only CI;
- C-07 node retirement CI;
- Broker ingress guard CI;
- H0/H1 initialization and portable restore CI;
- M0 vertical slice CI;
- H3 N2 Stage2B3 Pairing Runtime CI;
- Project roadmap V0.7 and C-07 identity semantics.

The main Manager job also reports:

```text
RUFF=PASS
PYTEST=1517_PASSED_1_SKIPPED
N3W_R8_SIMULATED_FIRST_REGISTRATION_E2E=8_PASSED
```

## 9. Repair history

The bounded implementation sequence was:

```text
INITIAL_R3_IMPLEMENTATION_HEAD=64b007572573bf24aa7ae0c2b62e795c1e11e403
MANIFEST_AND_TEST_BINDING_REPAIR_HEAD=96ca15e4eb69aa5c9ab1ba0fe73f2ea7cb53b27f
LINT_REPAIR_HEAD=a098dc7458f4af2dadac62b5b4579201c43771e2
FINAL_REPLAY_GUARD_HEAD=f30b7cf154abdbfed1863074ed855949aaecaf3b
```

Repairs were local and did not expand the architecture:

1. compatibility source heads were corrected to validate as 40-character Git SHA identities rather than SHA-256;
2. Ruff import-source/order failures were repaired;
3. final independent review added retained-command replay rejection and strict QoS1 control admission.

No repair introduced R4 IPC, host privilege, production activation or live mutation.

## 10. Independent closure review

```text
APPROVED_MANIFEST_PROVIDER_INTERFACE=PASS
APPROVED_MANIFEST_STRICT_VALIDATION=PASS
VERSION_COMPARISON=PASS
MQTT_UPDATE_DISCOVERY=PASS
MQTT_UPDATE_STATE=PASS
PREPARE_UI_MAPPING=SEPARATE_MQTT_BUTTON_PASS
PREPARE_INSTALL_SEPARATION=PASS
INSTALL_TARGET_RELEASE_BINDING=PASS
UNKNOWN_FIELD_FAIL_CLOSED=PASS
DUPLICATE_JSON_FIELD_FAIL_CLOSED=PASS
PATH_DEVICE_DOCKER_SHELL_INJECTION_REJECTED=PASS
PRIVATE_VALUE_EXPOSURE=false
RETAINED_COMMAND_REPLAY_REJECTED=PASS
CONTROL_QOS1_REQUIRED=PASS
SECOND_MQTT_CLIENT=false
GREENHOUSE_MANAGER_DOCKER_SOCKET_ACCESS=false
GREENHOUSE_MANAGER_BLOCK_DEVICE_ACCESS=false
GREENHOUSE_MANAGER_ROOT_PRIVILEGE=false
PRODUCTION_RUNTIME_WIRING_CHANGED=false
LIVE_T1_RUNTIME_MUTATION=false
REAL_USB_FORMAT=false
BOARD_ACCESS=false
MERGE=false
NEW_R3_BLOCKER_COUNT=0
```

R3 is therefore CLOSED_PASS.

## 11. Next boundary

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R4_20261106_01
R4_SCOPE=HOST_INTEGRATION_PACKAGE_AND_NARROW_VALIDATED_MANAGER_TO_PRIVILEGED_UPDATER_IPC
AUTO_EXECUTE_NEXT_GATE=false
STOP_BOUNDARY=BEFORE_R4_ENTRY
```

R4 may connect the already bounded Manager intent/state interfaces to the host-side privileged HA-USB executor through a narrow validated IPC while preserving the three-container product architecture. R4 must not give greenhouse-manager Docker socket, block-device, root or arbitrary-shell authority.

Real T1/USB discovery, format, install, rollback, production deployment, board access and PR merge remain later separately bounded work.
