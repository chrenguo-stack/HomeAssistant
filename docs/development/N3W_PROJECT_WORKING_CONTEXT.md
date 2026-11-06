## Stable updater authority — PR #779 successor convergence, 2026-11-06

```text
PROJECT_WORKING_CONTEXT_VERSION=1.5

T1_CORE_UPDATER_ARCHITECTURE=COMPLETE
GENERIC_V2_CORE_SOURCE=COMPLETE
GENERIC_COMPONENT_MODEL=COMPLETE

MANAGER_UPGRADE_PRODUCT_PATH=CLOSED_PASS
U2_LEGACY_DIRTY_VALIDATION=CLOSED_PASS
U2_T1A_CURRENT_DIRTY_STATE=false
U2_LEGACY_STATE_DISPOSITION=NO_ACTION_REQUIRED
U2_CLEANUP_REQUIRED=false

HOMEASSISTANT_UPGRADE_PRODUCT_PATH=NOT_COMPLETE
BROKER_UPGRADE_PRODUCT_PATH=NOT_COMPLETE

UPDATER_GENERIC_REWRITE_REQUIRED=false
UPDATER_COMPLETION_ROUTE=
HOMEASSISTANT_PRODUCT_VALIDATION
-> BROKER_PRODUCT_VALIDATION
-> FINAL_PRODUCT_CLOSURE
```

Fresh U2 evidence established that T1_A no longer has a current dirty legacy transaction; current
V2 state is terminal COMMITTED and runtime is TARGET_BOUND_RUNNING / HEALTHY. Historical updater
transactions remain terminal evidence with consumed authorizations. Do not manufacture a dirty
state merely to repeat U2, and do not replay consumed Manager authorizations.

This stable updater route coexists with the four-layer Stack authority model defined in Working
Context 1.5. Home Assistant and Broker validation must reuse the generic V2 core unless fresh
evidence proves a bounded core repair is required.

Authorities:
- `docs/development/N3W_T1_CORE_UPDATER_POST_U1_PRODUCT_COMPLETION_READONLY_AUDIT_20261105.md`
- `docs/development/N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_CLOSURE_20261105.md`

## Latest stable authority — 2026-11-05 U1 R4 Manager B canonical authority

```text
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2

CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d

HISTORICAL_CLEAN_REFERENCE_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_CLEAN_REFERENCE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1

LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
LIVE_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
LIVE_MANAGER_RUNTIME_IMAGE_ID=sha256:228a42a8b14f36694cca6778b18c7be880def25c567ea5492a9e2a40a8ce912e
LIVE_RUNTIME_CLASS=TARGET_BOUND_RUNNING
LIVE_HEALTH_STATE=HEALTHY

PR777_MERGED=true
PR777_MERGE_COMMIT=62e498e2eefb9b5eedb70529b07e7354bd2921dc
KF141=CLOSED_PASS
CANONICAL_AUTHORITY_PROMOTED=true
```

Manager B is the accepted live and repository-canonical Manager. Build-side image identity and T1-local runtime image identity are intentionally distinct authority fields. No further T1 mutation is required for this convergence.

## Latest authority — 2026-11-04 Pre-U1 G3 Node B Wi-Fi setup CLOSED_PASS; Node A restore next

```text
AUTHORITY_STATE=PRE_U1_G3_NODE_B_WIFI_SETUP_CLOSED_PASS_IDLE_UNREGISTERED
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
HISTORICAL_CLEAN_REFERENCE_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_CLEAN_REFERENCE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED

PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
PRE_U1_G2_RESULT=CLOSED_PASS
PRE_U1_G3_RESULT=IN_PROGRESS

LOCAL_FACTORY_BINDING=PASS
NODE_B_WIFI_CONNECTED=true
NODE_B_IDLE_UNREGISTERED_QR_VISIBLE=true
NODE_B_FIRST_REGISTRATION_STARTED=false

NODE_A_CURRENTLY_TEMPORARILY_OFFLINE=true
NODE_A_G2_ACCEPTANCE_RETAINED=true

T1_RUNTIME_MUTATION=false
REGISTRATION_MUTATION=false

NEXT_ONE_GATE=N3W_PRE_U1_G3_NODE_A_RESTORE_AND_DUAL_BASELINE_READONLY_20261104_01
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

Node B completed normal Captive Portal setup and is now online but still unregistered. The stop boundary was honored: no registration flow was entered. Node A remains temporarily offline and must be restored under a separate physical authorization before formal Node B registration.

Closure: `docs/development/N3W_PRE_U1_G3_NODE_B_WIFI_SETUP_AND_IDLE_UNREGISTERED_CLOSURE_20261104.md`.

## Latest authority — 2026-11-04 Pre-U1 G3 Node B factory write PASS; Wi-Fi setup next

```text
AUTHORITY_STATE=PRE_U1_G3_NODE_B_FACTORY_WRITE_PASS_WIFI_SETUP_PENDING
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
HISTORICAL_CLEAN_REFERENCE_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_CLEAN_REFERENCE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED

PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
PRE_U1_G2_RESULT=CLOSED_PASS
PRE_U1_G3_RESULT=IN_PROGRESS

NODE_A_CURRENTLY_TEMPORARILY_OFFLINE=true
NODE_A_G2_ACCEPTANCE_RETAINED=true

NODE_B_ERASE_FLASH=PASS
NODE_B_FACTORY_WRITE=PASS
NODE_B_WRITE_STAGE_INTERNAL_HASH_VERIFY=PASS
NODE_B_POST_BOOT_WHOLE_IMAGE_VERIFY=FAIL_EXPECTED_KF132_PATTERN
NODE_B_REFLASH_REQUIRED=false
NODE_B_FIRST_BOOT=PASS
NODE_B_WIFI_CONFIGURED=false
NODE_B_WIFI_SETUP_QR_VISIBLE=true
NODE_B_FIRST_REGISTRATION_STARTED=false
T1_RUNTIME_MUTATION=false

NEXT_ONE_GATE=N3W_PRE_U1_G3_NODE_B_WIFI_SETUP_AND_IDLE_UNREGISTERED_20261104_01
AUTO_EXECUTE_NEXT_GATE=false
BOARD_ACCESS=false
STOP=true
```

Node B has been fully erased and written with the same frozen factory artifact intended for Node A. The write-stage hash oracle passed. Post-boot whole-image verify mismatch is covered by KF-132 and must not cause an automatic reflash. The board booted normally and is currently at the unconfigured-Wi-Fi QR. Node A is temporarily offline for the Mac USB swap. Formal registration has not started.

Formal handoff: `docs/development/N3W_PRE_U1_G3_NODE_B_EXACT_FACTORY_WRITE_PASS_TO_WIFI_SETUP_NEW_CHAT_HANDOFF_V1.0_20261104.md`.

## Latest authority — 2026-11-04 Pre-U1 G2 Node A real sensor runtime CLOSED_PASS; STOP before G3

```text
AUTHORITY_STATE=PRE_U1_G2_NODE_A_REAL_SENSOR_RUNTIME_CLOSED_PASS
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
HISTORICAL_CLEAN_REFERENCE_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_CLEAN_REFERENCE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED

U0_RESULT=CLOSED_PASS
U0_REOPEN=false
PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
PRE_U1_G2_RESULT=CLOSED_PASS
U1_MANAGER_A_TO_B_STATUS=SUSPENDED
U1_PLAN_PRESERVED=true

NODE_A_REAL_SENSOR_RUNTIME=PASS
NODE_A_IDENTITY_PRESERVED=true
NODE_A_FIRMWARE_UNCHANGED=true
NODE_A_NVS_UNCHANGED=true
REPAIR_PAIRING_REQUIRED=false

CANONICAL_SOURCE=direct
CANONICAL_SAME_BOOT=true
CANONICAL_SEQ_BASELINE=14
CANONICAL_SEQ_FINAL=19
FIVE_CONSECUTIVE_CANONICAL_ADVANCES=true
CANONICAL_SEQUENCE_GAP=false

HA_NODE_DEVICE_MATCH_COUNT=1
HA_ALL_7_RAW_ENTITIES_PRESENT=true
HA_ALL_7_RAW_STATES_FINITE=true
HA_UI_NODE_A_SINGLE_DEVICE=true
HA_UI_7_RAW_ENTITIES_HAVE_VALUES=true
HA_UI_VALUES_CONTINUE_UPDATING=true

MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
SERVICE_RESTART_AS_TEST_REPAIR=false

NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G3_NODE_B_FIRST_REGISTRATION_20261104_01
G3_T1_BUSINESS_MUTATION=true
G3_BOARD_ACCESS=true
AUTO_EXECUTE_NEXT_GATE=false
BOARD_ACCESS=false
STOP=true
```

G2 real-sensor runtime acceptance is complete. The authoritative machine proof is the Manager durable canonical cursor advancing on one Direct boot for five consecutive 60-second cycles (seq 14 through 19), plus read-only Home Assistant registry/Recorder evidence showing one Node A device and all seven required raw entities with finite state. The operator also confirmed the seven entities remain live in the normal HA UI. No product-service restart or identity repair was required.

Observer-only R1/R2 failures are not product failures; the final observer did not create an additional MQTT client and relied on durable/read-only product state.

Authority: `docs/development/N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G2_NODE_A_REAL_SENSOR_RUNTIME_CLOSURE_20261104.md`.

## Latest authority — 2026-11-04 Pre-U1 G1 Home Assistant local onboarding CLOSED_PASS; STOP before G2

```text
AUTHORITY_STATE=PRE_U1_G1_HOMEASSISTANT_LOCAL_ONBOARDING_CLOSED_PASS
U0_RESULT=CLOSED_PASS
U0_REOPEN=false
PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
U1_MANAGER_A_TO_B_STATUS=SUSPENDED
U1_PLAN_PRESERVED=true

HOMEASSISTANT_LOCAL_OWNER_CREATED=true
HOMEASSISTANT_LOGIN_SUCCESS=true
HOMEASSISTANT_ONBOARDING_COMPLETE=true
MQTT_INTEGRATION_VISIBLE=true
MQTT_INTEGRATION_ERROR_VISIBLE=false
NO_CONTAINER_RESTART_SINCE_G0=true
UPDATER_TRANSACTION_STATUS=COMMITTED
UPDATER_RECOVERY_REQUIRED=false
PAIRING_WINDOW_STATE=CLOSED
PRODUCT_IMAGES_UNCHANGED=true
RUNTIME_CONTRACTS_UNCHANGED=true

NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G2_NODE_A_REAL_SENSOR_RUNTIME_20261104_01
G2_BOARD_PHYSICAL_WORK=true
AUTO_EXECUTE_NEXT_GATE=false
BOARD_ACCESS=false
STOP=true
```

G1 normal Home Assistant local onboarding is complete and retained as intended business state. Post-onboarding read-only evidence proves no unexpected product-container restart, no updater/pairing mutation, and no image/runtime-contract drift. G2 is the next gate, but it requires physical Node A sensor work and is not auto-executed.

Authority: `docs/development/N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G1_HA_LOCAL_ONBOARDING_CLOSURE_20261104.md`.

## Latest authority — 2026-11-04 Pre-U1 normal product runtime acceptance selected; U1 Manager A->B suspended

```text
AUTHORITY_STATE=PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_SELECTED
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED

U0_RESULT=CLOSED_PASS
BASELINE_A_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
U0_REOPEN=false

U1_MANAGER_A_TO_B_STATUS=SUSPENDED
U1_PLAN_PRESERVED=true
U1_LIVE_APPLY_AUTHORIZED=false
MANAGER_B_SOURCE_CREATED=false

PRE_U1_PLAN=docs/development/N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_PLAN_20261104.md
U1_SUSPENDED_PLAN=docs/development/N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_SUSPENDED_PLAN_20261104.md
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_20261104_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
MERGE=false
```

The project intentionally inserts a bounded normal-product-runtime acceptance stage before the first clean Manager upgrade. The intended eventual predecessor state for U1 is a real user/business state: Home Assistant local user active, one node with real sensors, a second normally registered node, and two-node runtime continuity. G5 then proves the upgrade hard authority still matches U0 and freezes a separate Pre-U1 business-runtime reference.

U1 remains preserved but paused; do not create/retag Manager B or enter updater apply until the Pre-U1 route closes and U1 is explicitly resumed.

## Latest authority — 2026-11-04 U0 real T1 read-only Baseline A CLOSED_PASS; U1 preparation next

```text
AUTHORITY_STATE=U0_REAL_T1_READONLY_BASELINE_A_CLOSED_PASS
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
HISTORICAL_CLEAN_REFERENCE_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_CLEAN_REFERENCE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
PR774=OPEN_DRAFT_UNMERGED
A2_REVIEWED_SOURCE_HEAD=4dd39befedce891bd2db3cc84c592d41f778bc51
BASELINE_A_MANIFEST=infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json
BASELINE_A_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
BASELINE_A_BYTES=2275
U0_TWO_READ_STABILITY=PASS
U0_RESULT=CLOSED_PASS

MANAGER_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
PLATFORM_ALL=linux/arm64
MANAGER_BINDING_MODE=dynamic
HOMEASSISTANT_BINDING_MODE=legacy_static
BROKER_BINDING_MODE=legacy_static

T1_PRODUCT_MUTATION=false
SERVICE_RESTART=false
UPDATER_TRANSACTION_CREATED=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_PREPARATION_20261104_01
U1_LIVE_APPLY_AUTHORIZED=false
```

U0 is closed. Two real T1_B observations produced byte-identical Baseline A JSON. Manager is eligible for successor planning through its dynamic image binding. HA/Broker legacy-static binding is accepted as current baseline but is not independently upgradeable until a separate template-convergence gate.

Authority:
- `infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json`
- `docs/development/N3W_T1_CORE_UPDATER_U0_REAL_T1_READONLY_BASELINE_CLOSURE_20261104.md`

## Latest authority — 2026-11-03 A2 per-module upgrade architecture CLOSED_PASS; source implementation next, STOP

```text
AUTHORITY_STATE=A2_PER_MODULE_UPGRADE_ARCHITECTURE_CLOSED_PASS_SOURCE_IMPLEMENTATION_REQUIRED
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
HISTORICAL_CLEAN_REFERENCE_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_CLEAN_REFERENCE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED

A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7
A2_ARCHITECTURE_SHA256=447f57f3563cb7766f145a2ea005d5d79d1beee7585ed07c6572ce2b3a833faa

UPDATER_CONCEPT=KEEP
REWRITE_FROM_SCRATCH=false
A2_TARGET_ARCHITECTURE=GENERIC_CORE_PLUS_COMPONENT_ADAPTERS
CURRENT_SYSTEMD_OWNERSHIP=KEEP

MANAGER_UPGRADE_SCOPE=MANAGER_IMAGE_BINDING_ONLY_BY_DEFAULT
HOMEASSISTANT_UPGRADE_SCOPE=HOMEASSISTANT_IMAGE_BINDING_ONLY_BY_DEFAULT
BROKER_UPGRADE_SCOPE=BROKER_IMAGE_BINDING_ONLY_BY_DEFAULT
DEFAULT_MUTATION_PROFILE=IMAGE_ONLY_V1
ONE_ACTIVE_UPDATER_TRANSACTION=true

A2_EXECUTED=true
A2_RESULT=CLOSED_PASS
A2_SOURCE_IMPLEMENTATION_REQUIRED=true
U0_ENTRY_READY=false
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_A2_PER_MODULE_SOURCE_IMPLEMENTATION_20261103_01
AUTO_EXECUTE_NEXT_GATE=false

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCT_SOURCE_CHANGE=false
PR745_MERGE=false
PR773_MERGE=false
STOP=true
```

A2 keeps the proven updater transaction/recovery concepts, but removes Manager-only architecture coupling. Manager and Home Assistant keep the existing shared systemd lifecycle owner; Broker keeps its independent owner. Module-only means only the target module image binding mutates, while owner-required restart side effects are allowed and checked semantically.

Authority:
- `infra/n3w-t1/clean-reference/a2-per-module-upgrade-architecture-20261103.json`
- `docs/development/N3W_T1_CORE_STACK_A2_PER_MODULE_UPGRADE_ARCHITECTURE_CLOSURE_20261103.md`

## Latest authority — 2026-11-03 A1 stable-invariant classification CLOSED_PASS; A2 entry ready, STOP

```text
AUTHORITY_STATE=A1_STABLE_INVARIANT_CLASSIFICATION_CLOSED_PASS_A2_ENTRY_READY
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
HISTORICAL_CLEAN_REFERENCE_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_CLEAN_REFERENCE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED

R3_REFERENCE_SHA256=e09139564280c700bc02b2e16360c511f780f7da7817f0d9bf0a22ff59dfcceb
R3_NORMALIZED_DELTA_SHA256=0d2ade72c9dbdc8299cc09754ed87768a02762244447c619d007951e9a522895
A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7

REFERENCE_FIELD_COUNT=150
HARD_STABLE_INVARIANT_COUNT=32
SOFT_RUNTIME_CHECK_COUNT=40
DIAGNOSTIC_ONLY_COUNT=67
REMOVE_COUNT=11

A1_EXECUTED=true
A1_RESULT=CLOSED_PASS
A2_ENTRY_READY=true
NEXT_ONE_GATE=N3W_T1_CORE_STACK_A2_PER_MODULE_UPGRADE_ARCHITECTURE_20261103_01
AUTO_EXECUTE_NEXT_GATE=false

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PR773_MERGE=false
STOP=true
```

A1 rejects whole-reference byte equality as the future upgrade model. Hard fields are baseline/target/per-instance contracts, not values that can never change across an authorized version transition. Runtime-variable fields are soft, diagnostic or removed. No T1 or Board access was required.

Authority:
- `infra/n3w-t1/clean-reference/a1-stable-invariant-classification-20261103.json`
- `docs/development/N3W_T1_CORE_STACK_A1_STABLE_INVARIANT_CLASSIFICATION_CLOSURE_20261103.md`

## Latest authority — 2026-11-03 R3 reference convergence CLOSED_PASS; A1 entry ready, STOP

```text
AUTHORITY_STATE=R3_REFERENCE_CONVERGENCE_CLOSED_PASS_A1_ENTRY_READY
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2

MAIN=e0841a5a43fd5847d5c5c40ab1cece42faedf3c8
PR773_GATE_INPUT_HEAD=aa30c1bdcc42dbea8048822de181b0b7540d6494

R3_ENGINEERING_OBJECTIVE_COMPLETE=true
R3_REFERENCE_SHA256=e09139564280c700bc02b2e16360c511f780f7da7817f0d9bf0a22ff59dfcceb
R3_NORMALIZED_DELTA_SHA256=0d2ade72c9dbdc8299cc09754ed87768a02762244447c619d007951e9a522895

REFERENCE_FIELD_COUNT=150
DIRECTLY_COMPARABLE_COUNT=48
EXPECTED_BUSINESS_RUNTIME_DRIFT_COUNT=58
VERSION_AXIS_DRIFT_COUNT=15
HISTORICAL_REFERENCE_GAP_COUNT=29
FRESH_READONLY_OBSERVATION_REQUIRED_COUNT=0

MANAGER_VERSION_AXIS_SEPARATED=true
T1_READONLY_OBSERVER_EXECUTED=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

A1_INPUT_TABLE_COMPLETE=true
A1_ENTRY_READY=true
A1_EXECUTED=false
NEXT_ONE_GATE=N3W_T1_CORE_STACK_A1_STABLE_INVARIANT_CLASSIFICATION_20261103_01
AUTO_EXECUTE_NEXT_GATE=false
PR773_MERGE=false
STOP=true
```

R3 normal-runtime reference authority is now frozen as a public-safe normalized reconstruction from archived evidence. The historical Clean Reference Manager A and current b863 Manager are separated as an explicit version axis; ordinary business-runtime drift is not conflated with the Manager upgrade. All 150 observer leaf fields have a comparability status. The 29 gaps are historical public-reference gaps, not missing current facts, so no fresh T1 observer is required. A1 is ready but has not started.

Closure: `docs/development/N3W_T1_CORE_STACK_R3_REFERENCE_CONVERGENCE_AND_A1_ENTRY_READONLY_CLOSURE_20261103.md`.

## Latest authority — 2026-11-03 R3 engineering closure; reference convergence -> A1 next

```text
AUTHORITY_STATE=R3_ENGINEERING_OBJECTIVE_COMPLETE_REFERENCE_CONVERGENCE_PENDING
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2

MAIN=e0841a5a43fd5847d5c5c40ab1cece42faedf3c8
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
CANONICAL_LIVE_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
HISTORICAL_CLEAN_REFERENCE_SOURCE=24382caae4a1f5d459297f86e8d18f10a848ca64
HISTORICAL_CLEAN_REFERENCE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1

R3_FIRST_REGISTRATION=PASS
KF139=CLOSED_PASS
R3_POST_REGISTRATION_DIRECT_TELEMETRY_HA=PASS
KF140=CLOSED_FALSE_POSITIVE
DIRECT_RELAY_REPEAT_REQUIRED=false
DIRECT_RELAY_HISTORICAL_ACCEPTANCE_REMAINS_VALID=true

R3_ENGINEERING_OBJECTIVE_COMPLETE=true
R3_CLEAN_REFERENCE_AUTHORITY_CLOSURE=PARTIAL
R3_REFERENCE_SHA256=NOT_FROZEN
R3_R2_SEMANTIC_COMPARE_AUTHORITY=NOT_YET_FROZEN
MANAGER_VERSION_AXIS_MUST_BE_SEPARATED_FROM_RUNTIME_DRIFT=true

CURRENT_BLOCKER_COUNT=0
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_STACK_R3_REFERENCE_CONVERGENCE_AND_A1_ENTRY_READONLY_20261103_01
```

The frozen R3 objective is complete: one real first registration reached durable commit and the current registered-node Direct telemetry/Home Assistant runtime was additionally proven healthy. Direct->Relay->Direct same-boot physical acceptance was already completed in the earlier wireless phase and is not an R3 requirement; do not repeat it without new source drift or contradictory evidence.

The only remaining R3-to-A1 work is authority convergence: freeze an R3 normal-runtime reference / R2->R3 semantic delta that can be consumed by A1. Because KF-139 forced an intentional Manager transition from the immutable historical Clean Reference Manager to the current b863 Manager during R3, the next gate must keep version drift separate from business-runtime drift. It is read-only by default. After it closes PASS, enter A1 Stable-invariant classification; A1 is classification work, not another physical workload gate.

## Latest authority — 2026-11-03 R3 first registration closed; downstream runtime/business acceptance next

AUTHORITY_STATE=CURRENT_STACK_LIVE_ACCEPTED
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
AUTHORITY_SCHEMA=gh.n3w-t1-core-stack-current-authority/2
MAIN=e0841a5a43fd5847d5c5c40ab1cece42faedf3c8
MAIN_MERGE_TREE_DRIFT=ZERO
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
CANONICAL_LIVE_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
KF139=CLOSED_PASS
FIRST_REGISTRATION_ACCEPTANCE=PASS
CREDENTIAL_LIFECYCLE_PRIVATE_DATABASE_GATE=PASS
PAIRING_WINDOW_LAST_ACCEPTED_STATE=CLOSED
PAIRING_WINDOW_LAST_ACCEPTED_CLOSE_REASON=committed
POST_MERGE_READONLY_REBIND=PASS
CURRENT_BLOCKER_COUNT=0

CURRENT_T1_RUNTIME_STATE=UNKNOWN_FRESH
CURRENT_REGISTERED_BOARD_STATE=UNKNOWN_FRESH
BOARD_ACCESS_DEFAULT=false
LIVE_MUTATION_DEFAULT=false

POST_REGISTRATION_DOWNSTREAM_DOMAINS=MQTT_TELEMETRY;HA_DISCOVERY_ENTITY;DIRECT_RELAY_FAILOVER;SENSOR_MEASUREMENT;LONG_DURATION_RUNTIME
NEXT_ONE_GATE=N3W_T1_CORE_STACK_R3_POST_REGISTRATION_PRODUCT_RUNTIME_BUSINESS_ACCEPTANCE_READONLY_PREFLIGHT_20261103_01

The first-registration/KF-139 path is closed and fully merged. New work begins from the normal registered-node product state. The next gate is intentionally read-only: fresh-bind repository/main and live T1 business/runtime state, then classify passive MQTT/HA visibility before any new service, board, credential, registration, failover or sensor mutation.

## Latest authority — 2026-11-03 Manager B live accepted; R3 re-entry next

AUTHORITY_STATE=CURRENT_STACK_LIVE_ACCEPTED
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
LIVE_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
LIVE_MANAGER_RUNTIME_IMAGE_ID=sha256:9dd128f0700840d46d300f9a434e2d3fbf5abba7abbd03c7dd432e9f497be035
TRANSACTION_STATUS=COMMITTED
TRANSACTION_PHASE=COMMITTED
RECOVERY_REQUIRED=false
POST_UPGRADE_ACCEPTANCE=PASS
SEMANTIC_ZERO_NODE=PASS
UNRESOLVED_FIRST_REGISTRATION_COUNT=0
TERMINAL_REPLAY_TOMBSTONE_COUNT=1
TERMINAL_REPLAY_TOMBSTONE_PRESERVED=true
HOMEASSISTANT_CONTINUITY=PASS
BROKER_CONTINUITY=PASS
LISTENER_CONTRACT=PASS
SYSTEMD_FAILED_UNITS=0
PAIRING_WINDOW_STATE=CLOSED
KF137=CLOSED_PASS
KF138=CLOSED_PASS
BOARD_ACCESS_DEFAULT=false
NEXT_ONE_GATE=N3W_T1_CORE_STACK_R3_SENSORLESS_REAL_FIRST_REGISTRATION_REENTRY_PREFLIGHT_20261103_01

Manager B is now the accepted live Manager. R3 may resume only through a fresh re-entry preflight.
## Latest authority — 2026-11-03 Manager B live; semantic-zero-node acceptance recheck pending

~~~text
AUTHORITY_STATE=LIVE_MANAGER_B_SEMANTIC_ZERO_NODE_RECHECK_PENDING

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
LIVE_MANAGER_RUNTIME_IMAGE_ID=sha256:9dd128f0700840d46d300f9a434e2d3fbf5abba7abbd03c7dd432e9f497be035

TRANSACTION_STATUS=COMMITTED
TRANSACTION_PHASE=COMMITTED
RECOVERY_REQUIRED=false

RUNTIME_ACCEPTANCE_PREFIX=PASS
THREE_STABLE_STATUS_INSPECT_SNAPSHOTS=PASS
HOMEASSISTANT_CONTINUITY=PASS
BROKER_CONTINUITY=PASS
LISTENER_CONTRACT_STABLE=PASS
SYSTEMD_FAILED_UNITS=0
PAIRING_WINDOW_STATE=CLOSED

FIRST_REGISTRATION_ATTEMPTS=1
ONLY_ATTEMPT_STATE=EXPIRED
ONLY_ATTEMPT_PHASE=TERMINAL
ONLY_ATTEMPT_CLEANUP_STATE=COMPLETE
CURRENT_REGISTRATIONS=0
CURRENT_NODE_ID_LEASES=0
CURRENT_CREDENTIAL_ASSIGNMENTS=0
CURRENT_PAIRING_SESSIONS=0
REPLAY_STATE_ZERO=true
RELAY_AUTHORIZATION_ZERO=true

KF138=ACCEPTANCE_HARNESS_FALSE_STOP
SEMANTIC_ZERO_NODE_RULE=ALLOW_TERMINAL_COMPLETE_REPLAY_TOMBSTONES
DELETE_TOMBSTONE=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_B_POST_UPGRADE_SEMANTIC_ZERO_NODE_RECHECK_20261103_01
~~~

Manager B is live and the runtime half of post-upgrade acceptance has already passed. The only remaining check is semantic zero-node classification. Terminal COMPLETE first-registration tombstones are retained replay authority and must not be deleted merely to make table counts zero.

## Latest authority — 2026-11-03 repaired A -> B live apply PASS; Manager B acceptance pending

~~~text
AUTHORITY_STATE=LIVE_MANAGER_B_POST_UPGRADE_ACCEPTANCE_PENDING

MAIN=13afc9d68824a20af2ca6c6efac515c94ed90cdf
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
LIVE_MANAGER_RUNTIME_IMAGE_ID=sha256:9dd128f0700840d46d300f9a434e2d3fbf5abba7abbd03c7dd432e9f497be035

TRANSACTION_STATUS=COMMITTED
TRANSACTION_PHASE=COMMITTED
RECOVERY_REQUIRED=false

HOMEASSISTANT_IMAGE_UNCHANGED=true
BROKER_RUNTIME_UNCHANGED=true
LISTENER_CONTRACT=PASS

KF137=SOURCE_REPAIR_AND_LIVE_APPLY_PASS
POST_UPGRADE_ACCEPTANCE=PENDING
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_B_POST_UPGRADE_LIVE_ACCEPTANCE_20261103_01
~~~

Manager B is live after a successful repaired V2 apply. The repository still records NOT_YET_APPLIED only because the separate read-only post-upgrade acceptance has not yet closed. Do not resume Board/R3 until that acceptance and repository live-authority convergence are complete.

## Latest authority — 2026-11-03 KF-137 repaired updater exact package ready; A -> B apply authorized

~~~text
AUTHORITY_STATE=KF137_REPAIRED_EXACT_UPDATER_APPLY_AUTHORIZED

MAIN_AT_REPAIR_MERGE=2e3f1c72e5ac17a9c8a1ecb378148a0d6d2d8c29
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2

LAST_TRANSACTION_STATUS=ROLLED_BACK
LAST_TRANSACTION_PHASE=ROLLBACK_COMPLETE
LAST_RECOVERY_REQUIRED=false

KF137=SOURCE_REPAIR_CLOSED_PASS
UPDATER_PACKAGE_ARTIFACT_ID=13196564439
UPDATER_PYZ_SHA256=6222ab4bdcb53e0b612777a585111f5ab2ab114a1c52a4997252937ef27033cc

APPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_KF137_REPAIRED_20261103_01
APPLY_AUTHORIZATION_GRANTED=true
APPLY_AUTHORIZATION_CONSUMED=false
OLD_AUTHORIZATION_REPLAY_PERMITTED=false

BOARD_ACCESS_DEFAULT=false
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_KF137_REPAIRED_EXECUTION_20261103_01
~~~

The repaired updater is the current execution authority. One new A -> B apply is explicitly authorized. Execution must run a fresh exact precheck first, use the repaired package only, issue at most one apply, and capture post-status/post-inspect. Any failure stops without a second apply or blind explicit rollback.

## Latest authority — 2026-11-03 Manager A -> B fresh preauthorization CLOSED_PASS

~~~text
AUTHORITY_STATE=POST_RECONCILIATION_A_TO_B_PREAUTH_PASS_AWAITING_EXPLICIT_APPLY_AUTHORIZATION

MAIN=92e7dfaa5e508fae1bb6477b9cdb23712a33588c
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2

TRANSACTION_STATUS=ROLLED_BACK
TRANSACTION_PHASE=RECOVERY_COMPLETE_FAILED_EMERGENCY
RECOVERY_REQUIRED=false

FRESH_STATUS=PASS
FRESH_INSPECT=PASS
FRESH_PLAN=PASS
MANAGER_TAR_VERIFIED=true
TARGET_IMAGE_PRESTATE=PRESENT_AND_EXACT
ROLLBACK_AVAILABLE=true

OLD_R1_R2_AUTHORIZATION_REPLAY_PERMITTED=false
NEW_A_TO_B_APPLY_AUTHORIZED=false
BOARD_ACCESS_DEFAULT=false

PROPOSED_APPLY_AUTHORIZATION=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_POST_RECONCILIATION_20261103_01
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_LIVE_APPLY_V2_POST_RECONCILIATION_AUTHORIZATION_20261103_01
~~~

The post-reconciliation real-T1 read-only preauthorization is CLOSED_PASS. Manager A is still exact and healthy, Manager B is present and exact, the exact Manager tar is verified, and rollback is available. The next boundary is a new one-shot Manager A -> B apply authorization; no prior consumed authorization may be replayed, and no apply occurs until the user explicitly grants the new authorization.

## Latest authority — 2026-11-03 R2 reconciliation CLOSED_PASS; Manager A -> B fresh preauthorization next

~~~text
AUTHORITY_STATE=POST_RECONCILIATION_PREDECESSOR_A_HEALTHY_A_TO_B_PREAUTHORIZATION

MAIN=5aa000055b3ee48c424ceac4ef6437fb3f98c742
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2

R2_TRANSACTION_STATUS=ROLLED_BACK
R2_TRANSACTION_PHASE=RECOVERY_COMPLETE_FAILED_EMERGENCY
R2_RECOVERY_REQUIRED=false
R2_RECONCILIATION=CLOSED_PASS
R2_RECONCILIATION_T1_MUTATION=false

UPDATER_V2_PACKAGE_ARTIFACT_ID=13187736541
UPDATER_V2_ARTIFACT_EXPIRED=false

OLD_R1_R2_AUTHORIZATION_REPLAY_PERMITTED=false
NEW_A_TO_B_APPLY_AUTHORIZED=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_POST_RECONCILIATION_MANAGER_A_TO_B_READONLY_PREAUTH_20261103_01
~~~

The stale R2 transaction is terminal and no longer blocks a new Manager transaction. The next gate is fresh read-only `status / inspect / plan --manager-tar` against the exact V2 package. A new Manager A -> B apply remains forbidden until that gate closes PASS and the user separately grants a new V2-compatible authorization ID.

## Latest authority — 2026-11-03 real-T1 V2 read-only reconciliation preflight PASS

~~~text
AUTHORITY_STATE=PREDECESSOR_A_HEALTHY_STALE_R2_TRANSACTION_AWAITING_RECOVERY_AUTH

MAIN=41e3031d1fa097043374c7582e552f5a803a1f20
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_RUNTIME_CLASS=PREDECESSOR_HEALTHY

R2_TRANSACTION_STATUS=FAILED_EMERGENCY
R2_TRANSACTION_PHASE=ROLLBACK_FAILED
R2_RECOVERY_REQUIRED=true

V2_PACKAGE_BINDING=PASS
V2_STATUS=PASS
V2_INSPECT=PASS
HA_CONTINUITY=PASS
BROKER_CONTINUITY=PASS
LISTENER_CONTRACT=PASS
MANAGER_RESTART_COUNT=0
HOMEASSISTANT_RESTART_COUNT=0
BROKER_RESTART_COUNT=0

R2_TRANSACTION_RECONCILIATION_AUTHORIZED=false
APPLY_RETRY=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_R2_TRANSACTION_RECONCILIATION_AUTHORIZATION_20261103_01
~~~

The next live action is a transaction-only V2 reconciliation under a separate explicit authorization. Because the runtime is already PREDECESSOR_HEALTHY, the expected V2 behavior is to update only the durable updater transaction to terminal ROLLED_BACK and return `t1_mutation=false`. A new A->B apply remains forbidden until that closure and a post-reconciliation baseline pass.

## Latest authority — 2026-11-03 Updater V2 merged and exact package bound; R2 transaction reconciliation next

~~~text
AUTHORITY_STATE=UPDATER_V2_READY_R2_TRANSACTION_RECONCILIATION_NEXT

MAIN=24fbc6cdf9b05796487459ad7cae038c0bdc7d5a
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json

UPDATER_V2_REVIEWED_HEAD=43de966c70d527433a915f40b9b630227531580a
UPDATER_V2_MERGE_COMMIT=24fbc6cdf9b05796487459ad7cae038c0bdc7d5a
UPDATER_V2_PACKAGE_RUN=41544508199
UPDATER_V2_PACKAGE_ARTIFACT_ID=13187736541
UPDATER_V2_PACKAGE_DIGEST=sha256:e09fb86c8444e0510b0200e759551d3571496064c743b4171992d46ab73babb9
UPDATER_V2_PYZ_SHA256=e92c093c7028d57ddc1e2c9c1eeb3fb97a0791a27b262b472c75482eaa3026bf
MANAGER_TAR_SHA256=0038286140758c27c66eeb005d2a7ea4aec4538ad94447a44021bb61de7e51f0
MANAGER_REBUILT=false

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_RUNTIME_HEALTHY=true

R2_TRANSACTION_STATUS=FAILED_EMERGENCY
R2_TRANSACTION_PHASE=ROLLBACK_FAILED
R2_AUTHORIZATION_REPLAY_PERMITTED=false

KF135=SOURCE_V2_CLOSED_LIVE_ACCEPTANCE_PENDING
KF136=SOURCE_V2_CLOSED_LIVE_RECONCILIATION_PENDING

LIVE_T1_MUTATION=false
R2_TRANSACTION_RECONCILIATION_AUTHORIZED=false
APPLY_RETRY=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_R2_TRANSACTION_RECONCILIATION_READONLY_PREFLIGHT_20261103_01
~~~

The next T1 action is not another A->B apply. First use the V2 package for a fresh read-only preflight against the healthy predecessor-A runtime and the stuck R2 transaction. Any transaction mutation requires a separate explicit recovery authorization. Only after reconciliation to terminal ROLLED_BACK and another fresh PREDECESSOR_HEALTHY check may a new A->B authorization be considered.

## Latest authority — 2026-11-03 R2 incident contained; Updater V2 convergence before any further live apply

~~~text
AUTHORITY_STATE=R2_FAILED_RUNTIME_RECOVERED_UPDATER_V2_SOURCE_REPAIR

MAIN=ae67dc9da98b16c8bb6a23bc45afa2c5adbc4aee
SOLE_DEVELOPMENT_PR=754
INCIDENT_PR_753=CLOSED_SUPERSEDED

LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_RUNTIME_HEALTHY=true
R2_TRANSACTION_STATUS=FAILED_EMERGENCY
R2_TRANSACTION_PHASE=ROLLBACK_FAILED
R2_AUTHORIZATION_REPLAY_PERMITTED=false

KF135=OPEN_SOURCE_REPAIR
KF136=OPEN_SOURCE_REPAIR
UPDATER_V2_ARCHITECTURE_FROZEN=true
FAULT_MATRIX_REQUIRED=true

LIVE_T1_MUTATION=false
IMMEDIATE_LIVE_RETRY=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_V2_SOURCE_REPAIR_CI_AND_EXACT_HEAD_REVIEW_20261103_01
~~~

The project must not treat CI green alone as permission to retry live A→B. Complete V2 architecture review, fault-matrix evidence and exact-head source review first. Only then build a new exact updater artifact, reconcile the stuck transaction under a separate recovery authorization, and later request a fresh apply authorization.

## Latest authority — 2026-11-02 portable-identity live revalidation PASS; R2 apply authorization boundary

~~~text
AUTHORITY_GATE=N3W_T1_CORE_UPDATER_PORTABLE_IMAGE_IDENTITY_LIVE_READONLY_REVALIDATION_CLOSURE_20261102_01
AUTHORITY_STATE=LIVE_READONLY_PASS_MANAGER_A_STILL_ACTIVE

MAIN=9a606e579e3431d2e37e1f4378dab80b10f794f8
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
TARGET_IMAGE_PRESTATE=PRESENT_AND_EXACT
MANAGER_TAR_VERIFIED=true
PORTABLE_IDENTITY_REVALIDATION=PASS
KF106_LIVE_REVALIDATION=CLOSED_PASS

R1_AUTHORIZATION_REPLAY_PERMITTED=false
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_APPLY_R2_20261102_01
NEW_AUTHORIZATION_REQUIRED=true
BOARD_ACCESS_DEFAULT=false
~~~

Do not replay the R1 authorization. The next mutation boundary is a new Manager A->B R2 live apply using the replacement updater package. Until the user explicitly authorizes that gate, keep T1 mutation disabled and do not resume Board/R3 work.

## Latest authority — 2026-11-02 replacement updater merged; read-only portable-identity T1 revalidation next

~~~text
AUTHORITY_GATE=N3W_T1_CORE_UPDATER_REPLACEMENT_PACKAGE_AUTHORITY_ALIGNMENT_20261102_01
AUTHORITY_STATE=REPLACEMENT_UPDATER_READY_NOT_LIVE_APPLIED

MAIN=c80bd9f1374ca33926cc76acbc2f2e2da1ebb67b
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d

UPDATER_REVIEWED_HEAD=667299b6053822ce56c2b27adb8c3c61cca12542
UPDATER_PACKAGE_RUN=41465742145
UPDATER_PACKAGE_ARTIFACT_ID=13151876743
UPDATER_PACKAGE_DIGEST=sha256:42d8580c0e8e2f04363a49e4166ef4b8de0729fa4f25c05703594a2b9ad04b1c
UPDATER_PYZ_SHA256=69227fdb2d4778f53513ace1d9065848d7e2ad771c8291f52f0375a99a65c592

LIVE_DEPLOYMENT_STATE=NOT_YET_APPLIED
LAST_FRESH_LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LAST_LIVE_APPLY=ROLLED_BACK_PRESTOP
OLD_LIVE_AUTHORIZATION_REPLAY_PERMITTED=false

NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_PORTABLE_IMAGE_IDENTITY_LIVE_READONLY_REVALIDATION_20261102_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
~~~

Use the replacement updater package for the next live read-only gate. The old updater package is historical and must not be used for a successor apply. Any new live apply requires a fresh read-only PASS and a new authorization.

## Latest authority — 2026-11-02 post-merge main convergence; Manager A->B live preflight next

The stacked successor-authority chain has fully converged into protected `main`. Repository authority B and the reviewed T1_Core_Updater are now in main, but this does not prove the current live T1 runtime. The last recorded live Manager A state is historical until a fresh read-only `inspect / plan` rebind is executed.

~~~text
AUTHORITY_GATE=N3W_T1_CORE_STACK_POSTMERGE_MAIN_STATE_ALIGNMENT_20261102_01
AUTHORITY_STATE=MAIN_CONVERGED_LIVE_RUNTIME_REBIND_PENDING

MAIN=092c9fca70df4212110b4ad07eb8fba9e8c9ef9e
STACKED_PR_CONVERGENCE=COMPLETE
MAIN_TREE_DRIFT_FROM_FINAL_PR696_HEAD=false

CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=3539c8f871e2cb63f18462009fa03a5eb36d39fd
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d

LAST_RECORDED_LIVE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
LIVE_T1_MANAGER=UNKNOWN_FRESH
LIVE_A_TO_B_APPLIED=UNKNOWN_FRESH

R3_BOARD_CONTINUATION_DEFERRED_UNTIL_MANAGER_B_LIVE_ACCEPTANCE=true
NEXT_ONE_GATE=N3W_T1_CORE_STACK_MANAGER_A_TO_B_LIVE_READONLY_INSPECT_AND_PLAN_20261102_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
~~~

The next operational gate is read-only. It must freshly prove the current T1 runtime, predecessor authority, target-image prestate, updater transaction state, and Manager-only plan before any live A->B apply decision. Board identity/registration work remains paused until the Manager B live path is accepted.

## Latest authority — 2026-11-02 R3 sensorless real first-registration route

The current R3 product route is no longer gated by the pairing-readiness bridge. R3 is frozen to one real sensorless ESP32-C6 first registration against the already-running zero-node production T1, followed by semantic PRE/POST comparison.

~~~text
AUTHORITY_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_SENSORLESS_REAL_FIRST_REGISTRATION_20261102_01
AUTHORITY_STATE=FROZEN_PREEXECUTION
SOURCE_HEAD=ea1488845ba05d362454678f2801232010852ecf

NODE_PROFILE=ESP32_C6_PLUS_LCD_PLUS_USB
SENSORS_CONNECTED=false
NORMAL_PRODUCT_REGISTRATION_PATH=true
POST_CAPTURE_RULE=MANAGER_DURABLE_COMMIT_THEN_IMMEDIATE_NODE_POWER_OFF_THEN_T1_POST

READINESS_BRIDGE_ENTRY_GATE=false
READINESS_BRIDGE_DISPOSITION=HISTORICAL_DIAGNOSTIC_ONLY

KNOWN_GOOD_FIRMWARE_ARTIFACT_ID=13115966258
KNOWN_GOOD_FIRMWARE_ARTIFACT_DIGEST=sha256:0da0eefafc4b108e4dc76864942fb5946419eac10f79a71e5db7e6db8427c715

CURRENT_STOP_POINT=BOARD_USB_ENUMERATED_BEFORE_ESPTOOL_IDENTITY_READ
FLASH_MUTATION=false
NVS_MUTATION=false
FIRST_REGISTRATION_STARTED=false

NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_BOARD_USB_READONLY_IDENTITY_BINDING_20261102_01
~~~

The user explicitly paused before `chip-id` / `flash-id` and requested a new-chat handoff. Do not reuse the earlier continuation as Board authorization. Fresh rebind first, then wait for the user's continuation before local Board commands. Exact local USB locators and raw Board identities stay out of public GitHub.

# N3W_PROJECT_WORKING_CONTEXT

> Status: durable public project working context  
> Version: `N3W_PROJECT_WORKING_CONTEXT_VERSION=1.5`  
> Scope: N3-W development for the greenhouse monitoring system  
> Repository: `chrenguo-stack/HomeAssistant`

## 0. Purpose

This file is the durable **public long-term working context** for N3-W development.

It exists to keep stable project conventions out of individual chat handoffs. A new-chat handoff should describe only the current stage, current evidence, current authorization state, and the next bounded step. It should not repeatedly copy the same development habits, communication rules, GitHub workflow, evidence rules, or public/private boundaries.

```text
PUBLIC_LONG_TERM_CONTEXT=this file
CURRENT_DYNAMIC_STATE=docs/development/N3W_CURRENT_STATE.md
CURRENT_STATE_INDEX=docs/development/N3W_CURRENT_STATE_INDEX.md
KNOWN_FAILURE_GUARDS=docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
STAGE_DELTA=current formal handoff
PRIVATE_RUNTIME_CONTEXT=USER_MANAGED_OUTSIDE_PUBLIC_GIT
```

This file does **not** contain live passwords, private host locators, private network addresses, raw board identities, credentials, setup secrets, private keys, or other sensitive material.

---

## 1. Authority and freshness

Use the authority closest to the thing being proven.

When information conflicts, prefer:

```text
1. fresh exact repository / runtime / physical evidence
2. current N3W_CURRENT_STATE.md and N3W_CURRENT_STATE_INDEX.md
3. current stage-specific formal handoff
4. this long-term working context for stable conventions
5. historical handoffs and historical progress documents
6. conversation inference
```

A historical fact is not automatically a current fact.

Before claiming a live service, board, branch, pull request, artifact, or physical route is current, perform the smallest necessary fresh read-only check.

```text
FRESH_READONLY_REBIND_BEFORE_LIVE_CLAIM=true
HISTORICAL_STATE_IS_NOT_CURRENT_STATE=true
INFERENCE_IS_NOT_PROVEN_FACT=true
```

If a handoff names an exact historical handoff-standard authority, read that exact commit for its standard/process rules. Do not assume current `main` contains the same historical standard file.

Formal handoff template authority is separate from historical standard authority:

```text
SOLE_VALID_HANDOFF_TEMPLATE=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
HISTORICAL_TEMPLATE_COPIES=HISTORICAL_EVIDENCE_ONLY
HISTORICAL_STANDARD_MAY_NOT_REACTIVATE_OLD_TEMPLATE=true
```

A historical commit may remain authoritative for a process standard while its bundled historical handoff template is obsolete. New formal handoffs must use the current V1.3 template unless the repository later explicitly promotes a newer template.

---

## 2. Primary execution principle

The governing rule is:

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
TEST_PRODUCT_NOT_TEST_FRAMEWORK=true
```

Practical meaning:

- choose the simplest method that gives reliable evidence;
- use read-only inspection before mutation whenever possible;
- do not add an executor, framework, manifest layer, branch, or CI job unless it solves a real engineering need;
- do not turn acceptance tooling into a second product architecture;
- stop at the first substantive mismatch unless the current contract explicitly allows continuation;
- after a failure, classify what actually failed before designing a repair;
- do not automatically cross into the next physical or mutation gate.

---

## 3. Communication style

User-facing replies should be concrete and easy to follow.

```text
COMMUNICATION_STYLE=PLAIN_DIRECT_CONCRETE
ABSTRACT_TERM_DENSITY=LOW
EXPLAIN_WHAT_HAPPENED=true
EXPLAIN_WHY=true
EXPLAIN_NEXT_ACTION=true
```

Default order:

1. what is happening now;
2. why it matters;
3. what to do next;
4. exact fields, hashes, commands, or error codes only where they are useful.

Prefer ordinary Chinese over repeated abstract labels such as `authority`, `gate`, `rebind`, `contract`, and `closure`. When an exact project term is necessary, keep the term but explain its concrete meaning.

Commands and exact identifiers must remain precise even when the surrounding explanation is simplified.

---

## 4. GitHub working method

GitHub is the durable shared engineering workspace.

```text
TEAM_SHARED_WORKSPACE=GITHUB
CHAT_SESSIONS_ARE_EPHEMERAL=true
DURABLE_ENGINEERING_ARTIFACTS_GO_TO_GITHUB=true
```

Source, tests, reusable tools, important design decisions, current-state records, known-failure guards, formal handoffs, and reproducibility information should be committed when they have continuing engineering value.

Secrets and private runtime locators are excluded from this rule.

### 4.1 Use short, phased GitHub operations

Long GitHub operations are deliberately split into small stages so that a timeout, truncation, or tool failure does not force a large operation to be repeated.

```text
GITHUB_OPERATION_MODE=PHASED_SHORT_CALLS
LARGE_MONOLITHIC_GITHUB_CALLS=AVOID
VERIFY_AFTER_REPOSITORY_WRITE=true
BLIND_REPLAY_AFTER_TOOL_FAILURE=false
```

Preferred sequence:

```text
A. fresh read-only repository / PR / branch rebind
B. inspect the small set of relevant files
C. decide the exact change
D. write a small bounded file set
E. re-fetch / compare and verify the resulting commit
F. check CI separately
G. merge only after the required review/decision
```

Do not combine unrelated repository reads, large searches, multiple sequential writes to the same file, CI polling, and merge into one long operation.

If a repository operation is interrupted, resume from the last **proven Git commit or remote state**. Do not assume an unconfirmed mutation succeeded and do not blindly repeat it.

### 4.2 Branch and pull-request defaults

For active engineering changes:

- use a purpose-specific branch;
- use a Draft PR while review or physical validation is incomplete;
- preserve exact head SHA for reviews and artifacts;
- do not merge merely because CI is green;
- treat merge as a separate decision when the current stage requires user approval;
- keep documentation-only alignment distinct from product-source authority.

Historical frozen branches or artifacts are evidence, not automatically deployment candidates.

---



### 4.3 CI observation and same-gate continuation — hard execution rules

These rules are mandatory for routine GitHub CI handling and are not optional chat
preferences.

```text
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
CI_FAILURE_READ_JOB_AND_LOG=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
CROSS_GATE_AUTO_EXECUTE=false
```

Execution rules:

1. Poll the same CI head at most three times in one reply. If work is still pending,
   stop polling and give direct links for every unfinished workflow/run that matters.
2. If all required CI for the current exact head is complete and green, immediately
   continue the review/closure step already required by the current gate. Do not stop
   merely to ask the user to say “continue” or “start review” again.
3. If CI fails, inspect the failed job/step/log before reporting the result. When the
   cause is a small, clearly identified source/test/style defect inside the already
   authorized gate, repair it directly, trigger fresh CI, and continue the same gate.
4. The same rule applies when focused review finds a small, bounded, low-risk defect
   inside the current source-only gate: repair it directly rather than manufacturing a
   second approval step.
5. Stop and request a new decision only when the action would expand scope, cross into
   a new gate, perform live/T1/board/service/credential mutation, consume a new
   authorization, merge, or change an already frozen product/design decision.
6. Green CI is never by itself a closure result. Required focused/source review still
   runs before closure.

When a workflow remains unfinished, a run ID without a clickable/direct URL is
insufficient.

### 4.4 Stacked PR convergence

Nested pull requests converge from the innermost PR outward, exactly one layer at a time. A merge into the next PR creates a new target head; upstream CI is historical evidence only and cannot satisfy the fresh-CI gate for that target head.

```text
STACKED_PR_CONVERGENCE=INNER_TO_OUTER_ONE_LAYER_AT_A_TIME
TARGET_PR_NEW_HEAD_IS_NEW_CI_AUTHORITY=true
UPSTREAM_PR_CI_NOT_REUSABLE_FOR_TARGET_NEW_HEAD=true
TARGET_DRAFT_TO_READY_AFTER_INNER_MERGE=true
CI_POLL_MAX_PER_EXACT_HEAD=3
NEXT_LAYER_MERGE_REQUIRES_FRESH_REVIEW_OR_DECISION=true
FINAL_MAIN_MERGE_IS_SEPARATE_DECISION=true
```

## 5. Development environment convention

The Mac development environment is versioned and audited separately from handoffs.

Current environment authority is referenced by:

```text
docs/development/N3W_CURRENT_STATE_INDEX.md
docs/development/local-environment-records/
```

Do not copy volatile package versions, disk state, worktree state, or local paths into every handoff. Read the current environment record when the task actually depends on them.

Stable environment rules:

- host-side Python development uses the project virtual environment;
- ESPHome remains isolated from the host project Python environment when dependency requirements conflict;
- do not casually install or upgrade packages in a working environment to make one command pass;
- rerun the versioned local-environment doctor after meaningful host/toolchain changes;
- local environment warnings are not product failures unless evidence shows they affect the product result;
- prefer existing installed tools; do not install tooling on T1 or another target merely for convenience unless explicitly approved.

```text
LOCAL_ENVIRONMENT_CHANGE_REQUIRES_RECHECK=true
DEPENDENCY_ISOLATION_PRESERVED=true
TARGET_HOST_TOOL_INSTALL_DEFAULT=false
```

---

## 6. Default physical roles

Unless a stage-specific handoff explicitly overrides the roles:

```text
BOARD_A_DEFAULT_ROLE=STATIONARY_RELAY_GATEWAY
BOARD_B_DEFAULT_ROLE=PRIMARY_DEVICE_UNDER_TEST
T1_DEFAULT_ROLE=MANAGER_BROKER_HOMEASSISTANT_HOST
```

These are working roles, not permanent hardware identities.

Public GitHub documentation should use role names and public-safe hashes when identity binding is required. Raw board identity material belongs outside the public repository.

A physical test must still freshly confirm power, location, role, and relevant runtime state before relying on them.

---

## 7. Evidence rules

Use the strongest evidence that directly proves the claim.

### 7.1 N3-W telemetry acceptance

For Manager-visible Direct/Relay acceptance, durable canonical state is preferred over the presence or absence of an INFO log line.

```text
MANAGER_CANONICAL_DURABLE_STATE=PRIMARY_ACCEPTANCE_ORACLE
INFO_LOG_ABSENCE_ALONE=NOT_PRODUCT_FAILURE
```

This preserves the existing KF-010 guard: a missing INFO line can be a logging false negative.

### 7.2 Radio and delivery evidence

- successful API submission is not automatically proof of asynchronous RF delivery;
- source review, CI, artifact binding, flashing, and physical behavior are separate proofs;
- a historical low-level radio error must not be claimed fixed without appropriate post-fix evidence;
- a timing gap must not be attributed to one internal phase without phase-specific evidence.

### 7.3 Serial is not a passive observer

Opening an application serial port can reset or disturb the board.

```text
APPLICATION_SERIAL_AS_PASSIVE_ORACLE=false
```

Use non-intrusive Manager/Broker/durable-state evidence when it can answer the question.

### 7.4 Evidence and conclusion must match

Use explicit classifications:

```text
PASS
FAIL
NOT_EXECUTED
INCONCLUSIVE
UNKNOWN_FRESH
```

Do not turn `NOT_EXECUTED`, missing logs, stale evidence, or an operator assumption into `PASS`.

---

### 7.5 Factory-image post-write verification

The write-stage internal hash verification is the authority for bytes written during flashing. After first boot, runtime-mutable partitions such as `otadata` must be classified separately from immutable firmware regions. Whole-image byte equality after boot is not a valid standalone corruption oracle.

```text
WRITE_FLASH_INTERNAL_HASH_VERIFY=WRITE_STAGE_ORACLE
POST_BOOT_FULL_IMAGE_BYTE_EQUALITY_REQUIRED=false
POST_BOOT_IMMUTABLE_REGION_EQUALITY_REQUIRED=true
RUNTIME_MUTABLE_PARTITIONS_CLASSIFIED_SEPARATELY=true
OTADATA_ONLY_POST_BOOT_DRIFT_IS_NOT_FIRMWARE_CORRUPTION=true
AUTO_REFLASH_AFTER_FULL_IMAGE_VERIFY_MISMATCH=false
```

## 8. Authorization and mutation rules

Read-only inspection does not grant mutation authority.

Any live, physical, credential, firmware, NVS, Broker, Manager, DynSec, or comparable mutation must stay inside the exact authorization granted for that action.

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTHORIZATION_SCOPE_EXPANSION=false
CONSUMED_AUTHORIZATION_REPLAY=false
```

For one-shot authorization:

- claim it only when entering the authorized action;
- once claimed, treat it as consumed according to its contract even if execution later fails;
- never silently reuse a consumed or superseded authorization;
- an operator override is evidence for that one bounded action only unless explicitly stated otherwise;
- a historical target override must not become a permanent identity rule.

After a substantive failure:

```text
AUTO_REPAIR=false
AUTO_RETRY=false
AUTO_REFLASH=false
STOP_AND_REVIEW=true
```

unless the exact current contract explicitly permits a bounded retry.

---

## 9. User / assistant execution split

The user is the physical operator and final decision maker. The assistant owns technical analysis, command design, safety boundaries, evidence interpretation, and repository-quality engineering work.

When the assistant cannot directly access a physical board or private T1 runtime, it should give the user a complete bounded command or operation package rather than pretending the action was executed.

For mechanical user operations, prefer a complete batch when the later commands do not depend on earlier safety results.

Do not default to:

```text
one tiny command
→ wait for one line
→ another tiny command
→ repeat
```

Use separate steps only where an earlier result genuinely determines whether the next action is safe.

---

## 10. Public / private information boundary

Public GitHub may contain:

- source and tests;
- public-safe architecture and process rules;
- sanitized runtime conclusions;
- artifact IDs and hashes;
- hashed device identities where necessary;
- sanitized timing and acceptance evidence;
- reproducibility and recovery instructions that do not expose secrets.

Do not commit:

- passwords or tokens;
- private keys or setup secrets;
- private host addresses or private SSH locators;
- raw credentials;
- raw NVS dumps;
- raw board identity material when a public-safe hash is sufficient;
- private runtime logs containing sensitive values.

```text
PUBLIC_REPOSITORY_SECRET_VALUES_ALLOWED=false
PRIVATE_RUNTIME_LOCATORS_ALLOWED=false
```

Private working context is maintained outside the public repository and may be loaded separately when needed.

---

## 11. What belongs in a handoff

A handoff is a **stage delta**, not a complete project encyclopedia.

It should contain only what the next session needs that is not already durable in this file or the current-state documents.

Required concepts:

- why the chat is switching;
- current project route and stop point;
- exact current repository/candidate/artifact authorities needed by the next step;
- fresh live baseline or explicit `UNKNOWN_FRESH` items;
- newly proven facts;
- current blocker, if any;
- relevant closed/forbidden routes only;
- authorization ledger entries that can still affect execution;
- exactly one next gate;
- exact allowed/forbidden scope for that gate;
- execution method;
- expected structured result;
- what happens after PASS or FAIL;
- any important artifact not yet durably shared to GitHub;
- a compact new-chat start prompt.

Do **not** repeat the full contents of this file in every handoff.

```text
HANDOFF_IS_STAGE_DELTA=true
DUPLICATE_LONG_TERM_RULES_IN_HANDOFF=false
```

A handoff may restate a long-term rule only when:

- the next gate is unusually sensitive to that rule;
- the stage introduces a temporary stricter override;
- the rule is required for a self-contained physical operation package.

---

## 12. Minimum new-chat read set

For an N3-W continuation, the default public read set is:

```text
1. current formal handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. exact handoff standard authority, only when the handoff specifies one
```

Then perform the smallest fresh read-only rebind needed for the current gate.

Do not reread the full project history unless current evidence is insufficient.

---

## 13. Team-workspace completeness

The existing project-wide collaboration standard remains applicable:

```text
docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md
```

A meaningful development result that exists only in chat or a temporary local directory is not durably shared.

Every formal handoff should state:

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=<n>
TEAM_SHARE_COMPLETENESS=PASS|FAIL
```

If a valuable artifact cannot be committed, record a public-safe recovery locator/hash and explain why it remains outside GitHub.

---

## 14. T1_Core_Stack naming and product boundary

The canonical name for the T1 production application stack is:

```text
T1_Core_Stack
```

It contains exactly:

```text
greenhouse-manager
Home Assistant
Mosquitto Broker
```

Armbian, Docker/Compose, systemd, provisioning, maintenance transactions, upgrade/recovery
executors and CI are platform/operations layers around T1_Core_Stack and are not part of the
stack name.

Upgrade design should use a clean T1_Core_Stack product reference and distinguish stable
product invariants from normal runtime drift.

```text
CLEAN_PRODUCT_REFERENCE_NOT_RUNTIME_SNAPSHOT=true
HARD_GATE_REQUIRES_STABLE_PRODUCT_INVARIANT=true
NORMAL_RUNTIME_DRIFT_DEFAULTS_TO_SOFT_OR_DIAGNOSTIC=true
MODULE_UPGRADE_DEFAULT_SCOPE=ONE_T1_CORE_STACK_COMPONENT
```

Design authority:

```text
docs/development/N3W_T1_CORE_STACK_CLEAN_REFERENCE_AND_STABLE_INVARIANTS_DESIGN_20261031.md
```


### 14.1 Baseline and release authority layering

The project uses four separate authority layers and must not use the word `baseline` as if these
objects were interchangeable:

```text
HISTORICAL_CLEAN_REFERENCE
COMPONENT_UPGRADE_BASELINE
CURRENT_PRODUCTION_AUTHORITY
IMMUTABLE_STACK_RELEASE
```

- Historical Clean Reference is immutable engineering/reference evidence.
- Component Upgrade Baseline is transaction-scoped predecessor/rollback authority for
  `T1_Core_Updater`.
- Current Production Authority records the exact stack accepted as running now.
- Immutable Stack Release is the append-only product-version authority used as predecessor/target
  by product OTA.

`T1_Core_Stack OTA` is the product-level release/orchestration/user-experience layer.
`T1_Core_Updater` remains the sole privileged local execution engine.

A Stack release that freezes an already accepted pre-OTA production composition may be classified
as a bootstrap accepted/pre-OTA release. That classification does not imply the signed end-user OTA
publication pipeline is already complete, and future OTA metadata must not be retroactively added by
silently rewriting an already frozen predecessor release.

```text
BASELINE_LAYER_COLLAPSE_FORBIDDEN=true
CURRENT_PRODUCTION_AUTHORITY_IS_NOT_COMPONENT_BASELINE=true
STACK_RELEASE_IS_NOT_LIVE_RUNTIME_PROOF=true
OLD_ACCEPTED_RELEASE_RETROACTIVE_REWRITE=false
T1_CORE_STACK_OTA_REPLACES_UPDATER_AS_EXECUTOR=false
```

### 14.2 Initial immutable Stack release authority

The initial exact Stack release baseline is:

```text
STACK_VERSION=1.0.0
STACK_RELEASE_ID=5debfbe23356d67ea5ff095f7ffc3e5443d771ddb4241589fa496b901ff2b7d9
STACK_RELEASE_PATH=infra/n3w-t1/releases/1.0.0/release.json
STACK_RELEASE_ROLE=BOOTSTRAP_ACCEPTED_PRE_OTA_RELEASE
STACK_RELEASE_IMMUTABLE=true
STACK_1_0_0_END_USER_OTA_PUBLICATION=false
```

It freezes the already accepted production composition and is valid predecessor/rollback authority.
It does not mean the complete signed end-user Stack OTA publication pipeline existed at 1.0.0.
Future richer OTA publication metadata belongs to successor releases; do not mutate or republish
1.0.0 to backfill it.


---

## 15. Dual-T1 clean-reference and upgrade-validation roles

The current canonical physical-role split is:

```text
T1_A_ROLE=LEGACY_UPGRADE_AND_FAILURE_SPECIMEN
T1_A_WIPE=false

T1_B_ROLE=CLEAN_REFERENCE_AND_CLEAN_UPGRADE_TARGET
T1_B_WIPE_AND_REINSTALL_ARMBIAN=true
```

T1_A preserves the real historical E03 successor-upgrade failure state and must not be
reformatted merely to create a second clean machine. It is used later to validate how the
new upgrade tooling handles a long-running/dirty/legacy T1. Any additional historical
Manager business bug present on T1_A must be freshly proven before being used as an
upgrade test case.

T1_B is the clean-reference machine. R0/R0H/R1/R2/R3 clean-reference work starts on T1_B.

The canonical upgrade tool name is:

```text
T1_Core_Updater
CLI=t1-core-updater
```

T1_Core_Updater owns T1_Core_Stack component inspection/planning/upgrade/rollback/status.
It does not own Armbian installation, kernel/host-platform update, initial T1 installation,
or board firmware update.

Clean-reference work and upgrade-validation work are separate phases:

```text
CLEAN_REFERENCE != UPGRADE
UPGRADE_REQUIRES_EXPLICIT_BASELINE_A_AND_TARGET_B=true
DEFAULT_UPGRADE_SCOPE=ONE_T1_CORE_STACK_COMPONENT
```

---

## 16. Maintenance rule

Update this file only when a **stable working convention** changes.

Do not update it for:

- a new sequence number;
- a new physical observation;
- a new candidate SHA;
- a new one-shot authorization;
- a temporary failure;
- a single gate result.

Those belong in current state, progress alignment, known failures, or the current handoff.

A change to this file should explain the durable process need it addresses and should update the handoff template when the change affects new-chat continuation.

```text
N3W_PROJECT_WORKING_CONTEXT_VERSION=1.5
STABLE_CONVENTIONS_ONLY=true
STAGE_SPECIFIC_VALUES_PROHIBITED=true
HANDOFF_TEMPLATE_EXPECTED_TO_REFERENCE_THIS_FILE=true
```
