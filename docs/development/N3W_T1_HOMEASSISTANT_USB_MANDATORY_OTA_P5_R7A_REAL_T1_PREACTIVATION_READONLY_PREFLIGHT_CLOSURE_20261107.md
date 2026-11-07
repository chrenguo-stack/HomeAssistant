# N3-W T1 Home Assistant mandatory-USB OTA R7A real-T1 preactivation read-only preflight closure — 2026-11-07

## 1. Gate result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_REAL_T1_PREACTIVATION_READONLY_PREFLIGHT_20261107_01
RESULT=CLOSED_PASS
SCOPE=REAL_T1_READONLY_PREACTIVATION_PREFLIGHT

R7A_SOURCE_IMPLEMENTATION_HEAD=d5c7aca0b8f39acb0d9d014b649d943a81956262
R7A_CLOSURE_DOCS_HEAD_AT_ENTRY=6053936421621c6facd9c86bae1eab8651068ee8

LIVE_T1_ACCESS=true
LIVE_T1_MUTATION=false
REAL_USB_MUTATION=false
SERVICE_INSTALL=false
SERVICE_ENABLE=false
SERVICE_START=false
DOCKER_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This gate refreshed the accepted production T1 baseline immediately before any future R7A activation. Private SSH locator, password, local trusted-known-hosts path and other private connection material are intentionally not archived.

## 2. Trusted SSH transport

```text
SSH_TRANSPORT_BLOB=dec4c9159195e2008094d94fef3fc76c4b977e46
HOST_KEY_BINDING=PASS
SSH_MASTER_START=PASS
SSH_CHILD_READONLY_REUSE=PASS
AUTH_FALLBACK_USED=false
PASSWORD_PROMPT_COUNT=1
SSH_MASTER_CLEANUP=PASS
```

One production `SSHTransport` epoch was used. Child commands reused the established master with no second authentication path.

## 3. Host prerequisites

```text
HOST_ARCHITECTURE=aarch64
HOST_SYSTEM_STATE=running
PYTHON3_VERSION=3.14.4
DOCKER_SERVER_VERSION=29.1.3

HOST_TOOL_PYTHON3=PASS
HOST_TOOL_DOCKER=PASS
HOST_TOOL_SYSTEMCTL=PASS
HOST_TOOL_LSBLK=PASS
HOST_TOOL_FINDMNT=PASS
HOST_TOOL_WIPEFS=PASS
HOST_TOOL_SFDISK=PASS
HOST_TOOL_MKFS_EXT4=PASS
HOST_TOOL_UDEVADM=PASS
HOST_TOOL_BLKID=PASS
HOST_TOOL_MOUNT=PASS
HOST_TOOL_UMOUNT=PASS
```

The host has the command set required by the R7A source implementation. No command in this gate mutated disks, mounts, services or Docker state.

## 4. Accepted production stack identity

```text
MANAGER_IMAGE=local/greenhouse-manager:fresh-5b32e1ae8210
MANAGER_RUNTIME_IMAGE_ID=sha256:228a42a8b14f36694cca6778b18c7be880def25c567ea5492a9e2a40a8ce912e
MANAGER_RESTART_COUNT=0
MANAGER_STATE=running

HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_RUNTIME_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
HOMEASSISTANT_RESTART_COUNT=0
HOMEASSISTANT_STATE=running

BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_RUNTIME_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
BROKER_RESTART_COUNT=0
BROKER_STATE=running

REAL_T1_STACK_IDENTITY=PASS
```

Broker and services activation units were both active/enabled.

## 5. Manager privilege boundary

```text
MANAGER_UID_GID=999:999
MANAGER_DOCKER_SOCKET_ABSENT=PASS
MANAGER_R7A_RUNTIME_MOUNT_ABSENT=PASS
MANAGER_R7A_ENV_ABSENT=PASS
```

The currently running production Manager has no R7A wiring and remains non-privileged.

## 6. R7A not deployed yet

```text
R7A_HOST_SERVICE_LOAD_STATE=not-found
R7A_HOST_SERVICE_ACTIVE_STATE=inactive
R7A_HOST_RUNTIME_DIR_PRESENT=false
R7A_HOST_SOCKET_PRESENT=false
R7A_APPROVED_MANIFEST_PRESENT=false

R7A_HOST_SERVICE_NOT_DEPLOYED_EXPECTED=PASS
R7A_RUNTIME_DIR_ABSENT_EXPECTED=PASS
R7A_SOCKET_ABSENT_EXPECTED=PASS
R7A_APPROVED_MANIFEST_ABSENT_EXPECTED=PASS
```

This proves there is no partial prior live activation to reconcile before the physical activation gate.

## 7. Updater state

```text
UPDATER_STATE_ROOT_METADATA=root|root|700

R7A_SUCCESSOR_TRANSACTION_PRESENT=false
R7A_PREPARE_STATE_PRESENT=false
MANAGER_UPGRADE_TRANSACTION_PRESENT=false

GENERIC_V2_TRANSACTION_PRESENT=PASS
GENERIC_V2_COMPONENT=homeassistant
GENERIC_V2_STATUS=ROLLED_BACK
GENERIC_V2_PHASE=ROLLED_BACK
RECOVERY_REQUIRED=false
```

No R7A successor transaction exists. The historical Generic V2 Home Assistant transaction remains terminal and does not require recovery.

## 8. Production compose

```text
PRODUCTION_COMPOSE_READABLE=PASS
PRODUCTION_COMPOSE_R7A_MARKERS_ABSENT=PASS
```

The live production Compose has not silently acquired R7A environment variables, runtime mounts or socket wiring.

## 9. Read-only removable-media inventory

```text
ROOT_DEVICE_MAJ_MIN=179:2
USB_INVENTORY_READONLY_COMMAND=PASS
USB_LIKE_DISK_COUNT=0
```

No USB mass-storage candidate was present during preflight. This is a clean starting condition for the later physical validation gate and avoids ambiguity with an already-present unbound device.

## 10. Closure classification

```text
PREACTIVATION_READONLY_PREFLIGHT=PASS
SOURCE_BLOCKER_COUNT=0
LIVE_RUNTIME_BLOCKER_COUNT=0
RECOVERY_BLOCKER_COUNT=0
PARTIAL_R7A_DEPLOYMENT_RESIDUE_COUNT=0

PRODUCTION_STACK_DRIFT=false
MANAGER_PRIVILEGE_DRIFT=false
R7A_PARTIAL_ACTIVATION=false
REAL_USB_WRITE_OCCURRED=false
```

The system is eligible to proceed to a separately bounded physical activation gate. This closure does not itself authorize activation or USB mutation.

## 11. Next ONE gate

The next gate must separate **software activation** from the first destructive USB operation.

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_LIVE_ACTIVATION_AND_USB_PREPARE_PREEXECUTION_20261107_01
NEXT_SCOPE=PREEXECUTION_DESIGN_AND_EXACT_COMMAND_FREEZE

REPOSITORY_MUTATION=true
LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
REAL_USB_MUTATION=false
SERVICE_MUTATION=false
DOCKER_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false

AUTO_EXECUTE_PHYSICAL_ACTIVATION=false
```

This preexecution gate must freeze an exact staged procedure for:
1. host-side R7A daemon installation and approved-manifest publication;
2. systemd unit installation without accidental early destructive work;
3. Manager runtime socket/manifest wiring with default-off semantics preserved until the intended transition;
4. activation verification while no USB mass-storage candidate is present;
5. explicit operator insertion of one dedicated test USB only after clean activation;
6. PREPARE read-only candidate publication;
7. separate confirmation immediately before the first destructive USB operation;
8. stop at U4 READY_TO_INSTALL, with U5+ still forbidden.

No real T1 mutation or USB write is authorized by this document.
