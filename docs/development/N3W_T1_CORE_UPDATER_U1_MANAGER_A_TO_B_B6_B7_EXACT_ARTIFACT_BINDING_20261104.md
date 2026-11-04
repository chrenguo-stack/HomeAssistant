# N3-W T1 Core Updater U1 — Manager A -> B B6/B7 exact artifact binding

Date: 2026-11-04

## Scope

```text
TASK=N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_B6_B7_EXACT_ARTIFACT_BINDING_20261104_01
MANAGER_A_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
MANAGER_B_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
MANAGER_B_PRODUCT_REPAIR_HEAD=cf2a27a1662fbfa0bf1e769f8bd92bbff762cb96
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
U1_LIVE_APPLY_AUTHORIZED=false
MERGE=false
```

## B6 exact ARM64 closure

```text
WORKFLOW=N3W T1 fresh install exact ARM64 CI
RUN_ID=41826182757
RUN_NUMBER=983
RUN_RESULT=SUCCESS
SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615

ARTIFACT_ID=13319777217
ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-5b32e1ae82104a42f9e4e6907fe44d9172e87615
ARTIFACT_DIGEST_SHA256=cb8794de2a5dc28f99c44e6369de403bec37db5b251c28e2edeeda22d281ce6c

MANAGER_IMAGE=local/greenhouse-manager:fresh-5b32e1ae8210
MANAGER_IMAGE_ID=sha256:80d34358094638ce9c8ce5fb2635fe0a5c75ee7cc5e8c628b38ab223134e585f
MANAGER_PLATFORM=linux/arm64
MANAGER_TAR_SHA256=2de1705096b9dfcecbc260f5acb95898b4df059510b7bc4ae6ea6b60debb23fa
MANAGER_TAR_SIZE_BYTES=62873600

R6_EXACT_ARM64_POST_UPLOAD_BINDING=PASS
FRESH_HELPERS_IN_EXACT_MANAGER_IMAGE=PASS
EXACT_MANAGER_FRESH_CONSTRUCTORS=PASS
BROKER_TLS_RUNTIME_UID_PATH=PASS
FRESH_RUNTIME_IDENTITY_COMPOSE_BINDING=PASS
HA_EXACT_ARM64_CONFIG_FLOW_RUNTIME=PASS
T1_ACCESS=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
B6=CLOSED_PASS
```

The artifact was uploaded and downloaded again by the same workflow. The Manager, Home Assistant and
Broker tar SHA-256/size bindings were checked against `binding.json`.

## Rollback compatibility

Fresh comparison from the real current Manager A source
`b863ddd959090ca139af76bd68dbef31d773e6de` to the B6 source head shows only two paths under
`host/greenhouse-manager/`:

1. `src/greenhouse_manager/runtime/mqtt_service.py` — bounded Discovery retry correctness repair;
2. `tests/runtime/test_mqtt_discovery_retry.py` — permanent regression coverage.

```text
ROLLBACK_COMPATIBLE=true
EXPECTED_PREDECESSOR_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
DATABASE_MIGRATION_REQUIRED=false
CONFIG_MIGRATION_REQUIRED=false
RUNTIME_TEMPLATE_CHANGE_REQUIRED=false
BROKER_CHANGE_REQUIRED=false
HOMEASSISTANT_CHANGE_REQUIRED=false
BOARD_CHANGE_REQUIRED=false
```

## B7 exact target/package binding

Target manifest:

`infra/n3w-t1/upgrades/manager-5b32e1ae8210.json`

The manifest binds the B6 source head, artifact ID/name/digest, exact Manager image ref/image ID,
Manager tar SHA-256, real predecessor Manager A image and rollback compatibility.

The existing Manager A-to-B package workflow is retargeted to consume run #983 and this manifest.
It copies the exact B6 Manager tar; it does not rebuild Manager. The package also contains the reviewed
`t1-core-updater.pyz`, then is uploaded, re-downloaded and verified.

```text
MANAGER_REBUILT=false
HOMEASSISTANT_INCLUDED=false
BROKER_INCLUDED=false
SECRET_VALUES_INCLUDED=false
T1_MUTATION=false
B7_STATUS=IMPLEMENTED_PENDING_PACKAGE_CI
```

The production current-stack authority is intentionally unchanged. Manager B remains a successor
candidate until updater plan/simulation and a separately authorized real T1 apply/acceptance complete.
