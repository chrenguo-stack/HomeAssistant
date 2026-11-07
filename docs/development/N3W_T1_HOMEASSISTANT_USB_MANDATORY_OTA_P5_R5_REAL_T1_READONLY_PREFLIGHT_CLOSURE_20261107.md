# N3-W T1 Home Assistant mandatory-USB OTA R5 real-T1 read-only preflight closure — 2026-11-07

## 1. Gate result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01
RESULT=CLOSED_PASS
R5_SCOPE=REAL_T1_READONLY_PREFLIGHT

REPOSITORY_MAIN=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_AUTHORITY_BLOB=07ceb3b352f21d925127caa71304cc3b29827fdb

LIVE_RUNTIME_MUTATION=false
USB_FORMAT=false
SERVICE_STOP=false
DOCKER_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

R5 refreshed the real T1 baseline without changing the target. Repository authority, live stack identity, updater terminal state and the R4 host-prerequisite absence were independently classified.

## 2. Repository rebind

```text
PR798_STATE=MERGED
PR798_MERGE_COMMIT=bce6bd82023d5f5322eea1ab363a29df8a4cadd8
PR798_VISIBLE_HEAD_CI=24_SUCCESS_0_FAILURE

PR799_HEAD_AT_R5_ENTRY=776598e1aeafefca28bd24a29a7dc6dfc2106b94
PR799_EXECUTABLE_DRIFT=false
PR799_ENTRY_DELTA=HANDOFF_DOC_ONLY
```

No R4 executable or production-authority drift was found before the live read-only preflight.

## 3. Trusted SSH transport

```text
SSH_TRANSPORT_BLOB=dec4c9159195e2008094d94fef3fc76c4b977e46
HOST_KEY_BINDING=PASS
SSH_MASTER_START=PASS
SSH_CHILD_READONLY_REUSE=PASS
AUTH_FALLBACK_USED=false
SSH_MASTER_CLEANUP=PASS
```

The private target locator and credentials remain operator-local and are intentionally not archived here.

## 4. Fresh real-T1 stack identity

```text
HOST_ARCHITECTURE=aarch64
HOST_SYSTEM_STATE=running

MANAGER_IMAGE=local/greenhouse-manager:fresh-5b32e1ae8210
MANAGER_RUNTIME_IMAGE_ID=sha256:228a42a8b14f36694cca6778b18c7be880def25c567ea5492a9e2a40a8ce912e
MANAGER_RESTART_COUNT=0
MANAGER_UID_GID=999:999
MANAGER_DOCKER_SOCKET_ACCESS=false

HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_RUNTIME_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
HOMEASSISTANT_RESTART_COUNT=0

BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_RUNTIME_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
BROKER_RESTART_COUNT=0

BROKER_ACTIVATION_SERVICE=active/running/enabled
SERVICES_ACTIVATION_SERVICE=active/running/enabled
REAL_T1_STACK_IDENTITY=PASS
```

The runtime IDs match previously accepted Docker-29/containerd live identities. Build-side image IDs in the repository authority are not incorrectly substituted for runtime IDs.

## 5. Updater state

```text
STATE_ROOT=/var/lib/n3w-t1-core-updater
STATE_ROOT_MODE=0700
STATE_ROOT_OWNER=root

V2_TRANSACTION_PRESENT=true
V2_TRANSACTION_COMPONENT=homeassistant
V2_TRANSACTION_STATUS=ROLLED_BACK
V2_TRANSACTION_PHASE=ROLLED_BACK
V2_AUTHORIZATION_CONSUMED=true

LEGACY_MANAGER_TRANSACTION_PRESENT=false
HA_USB_SUCCESSOR_TRANSACTION_PRESENT=false
HISTORY_FILE_COUNT=7

UNEXPECTED_ACTIVE_TRANSACTION=false
RECOVERY_REQUIRED=false
```

`MultiComponentCoreUpdater.status()` derives `recovery_required=false` when the current V2 and any legacy transaction are terminal `COMMITTED` or `ROLLED_BACK`. The Generic V2 transaction file does not need a stored `recovery_required` field. The present `homeassistant / ROLLED_BACK` record is therefore terminal historical evidence, not a recovery blocker.

## 6. R4 production activation prerequisites

```text
R4_HOST_RUNTIME_DIR_PRESENT=false
R4_HOST_SOCKET_PRESENT=false
R4_PRODUCTION_COMPOSE_OTA_ENABLE_PRESENT=false
R4_MANAGER_OTA_RUNTIME_MOUNT_PRESENT=false
R4_IPC_HOST_PREREQUISITE_CLASSIFICATION=PASS_NOT_ACTIVATED_EXPECTED
```

This absence is expected. R4 explicitly did not modify production Compose or install a real host service. The fresh Manager UID/GID remains `999:999`, preserving the reviewed peer-credential boundary for a later host implementation.

## 7. USB classification

```text
USB_INVENTORY_CLASSIFICATION=NOT_REQUIRED_FOR_THIS_PREFLIGHT
```

R5 did not need removable-media enumeration to decide whether the accepted stack and host are safe for subsequent repository-side design work.

## 8. Closure

```text
NEW_SOURCE_BLOCKER_COUNT=0
NEW_RUNTIME_BLOCKER_COUNT=0
RECOVERY_BLOCKER_COUNT=0

R5_RESULT=PASS
R5_STATUS=CLOSED_PASS
```

R5 does not authorize USB formatting, production service stop, Docker/image mutation, Home Assistant backup/cutover, live INSTALL/apply/rollback, board access or merge.

## 9. Next bounded gate

Fresh review of the R4 implementation and mandatory-USB V1.1 architecture shows that direct production activation would be premature: the R4 IPC only records PREPARE through U1 and INSTALL through U5. It does not provide the privileged worker that advances U1 -> U4 or U5 -> U13, and the product still requires an explicit user-visible destructive USB confirmation before U2.

Therefore the next gate is repository-only source design:

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R6_PRIVILEGED_PREPARE_PIPELINE_SOURCE_DESIGN_20261107_01
R6_SCOPE=REPOSITORY_SOURCE_DESIGN_ONLY
LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
REAL_USB_MUTATION=false
SERVICE_MUTATION=false
DOCKER_MUTATION=false
BOARD_ACCESS=false
MERGE=false
AUTO_EXECUTE_LIVE_ACTIVATION=false
```
