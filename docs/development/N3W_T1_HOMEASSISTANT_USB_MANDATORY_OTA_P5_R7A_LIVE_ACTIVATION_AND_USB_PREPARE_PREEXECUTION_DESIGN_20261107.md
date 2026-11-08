# N3-W T1 Home Assistant mandatory-USB OTA R7A live activation + USB prepare preexecution design — 2026-11-07

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_LIVE_ACTIVATION_AND_USB_PREPARE_PREEXECUTION_20261107_01
RESULT=SOURCE_PREEXECUTION_DESIGN_FROZEN_PENDING_EXACT_HEAD_CI

PREACTIVATION_READONLY_PREFLIGHT=CLOSED_PASS
PREACTIVATION_CLOSURE_COMMIT=7c9244b44868f00c9d6ce514c2d3ab6c7d0b8495

R7A_EXECUTABLE_SOURCE_BASE=d5c7aca0b8f39acb0d9d014b649d943a81956262
LIVE_ACTIVATION_WIRING_REPAIR_BASE=7ddb53205112bb2a2b0d1c009f1aede8e5b8d377
ACTIVATION_ENV_REPAIR_HEAD=c046e88bbe808d170b0c93824dc750d0ab7be8ab

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
REAL_USB_MUTATION=false
SERVICE_MUTATION=false
DOCKER_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This gate freezes the physical execution boundaries after the real-T1 read-only PASS. It does not activate R7A, restart production services, insert/format a USB device, or enter U5+.

## 2. Fresh facts entering the design

The latest read-only real-T1 evidence established:

```text
HOST_ARCHITECTURE=aarch64
HOST_SYSTEM_STATE=running
CURRENT_STACK_EXACT_ACCEPTED=PASS
MANAGER_UID_GID=999:999
MANAGER_DOCKER_SOCKET_ABSENT=PASS
R7A_HOST_SERVICE=not-found
R7A_RUNTIME_DIR_ABSENT=PASS
R7A_TRANSACTION_ABSENT=PASS
GENERIC_V2_STATUS=ROLLED_BACK
RECOVERY_REQUIRED=false
USB_LIKE_DISK_COUNT=0
SSH_MASTER_CLEANUP=PASS
```

The clean zero-USB state is intentionally preserved as the starting point for software activation.

A further independent review found one additional deployment prerequisite:

```text
CURRENT_MANAGER_IMAGE=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_MANAGER_CONTAINS_R7A_CONTROL_PLANE=false
R7A_MANAGER_SUCCESSOR_REQUIRED=true
```

R7A changed Manager source. Therefore the existing accepted Manager image cannot gain PREPARE/CONFIRM/IPC behavior merely by adding environment variables and a socket mount. A new exact ARM64 Manager successor built from the R7A source authority must be deployed through the already-proven Manager A-to-B updater path before the HA-OTA bridge can be activated.

## 3. Source repairs discovered before physical activation

Independent preexecution review found three deployment-level gaps.

### 3.1 Compose overlay was not owned by the production services unit

The initial R7A source had a reviewed `docker-compose.ha-ota.yml`, but the production `n3wfc4-services-activation.service` command still loaded only the main Compose file.

Repair at `7ddb53205112bb2a2b0d1c009f1aede8e5b8d377` makes the R7A services drop-in reset and replace ExecStart/ExecStop so both the production Compose and HA-OTA overlay are used.

### 3.2 Approved release envelope existed only as synthetic test data

The privileged daemon requires:

```text
/etc/n3w-t1-ota/approved-homeassistant.json
```

A repository-owned exact approved envelope is now frozen as:

```text
infra/n3w-t1/upgrades/homeassistant-2026.10.4-approved.json
```

It is exact-bound to the frozen 2026.10.4 target manifest.

### 3.3 Enabled-mode startup fallback had no activation authority

R6 explicitly forbids hard-coding `2026.10.0` as the installed-version authority. Runtime truth must come from host-observed Home Assistant state.

The R7A services drop-in now has:

```text
EnvironmentFile=-/etc/n3wfc4/ha-ota-activation.env
```

Source presence therefore remains default-OFF. During the later live activation transaction, the activation executor must derive the current HA version from the exact running Docker predecessor and atomically create this root-owned file:

```text
GH_N3W_T1_OTA_ENABLED=true
GH_N3W_T1_OTA_INSTALLED_VERSION=<host-observed current version>
```

The value is only a startup fallback. Once the IPC is available, Manager projection uses host-observed runtime status. No source file may hard-code the current version.

## 4. Physical execution is split into four independent boundaries

The physical sequence must not be one monolithic command.

### Boundary A0 — exact R7A Manager successor, OTA still disabled

Purpose: place the R7A Manager code on the real T1 using the existing Manager A-to-B updater while keeping the HA-OTA control plane disabled.

Entry requirements:

```text
USB_LIKE_DISK_COUNT=0
CURRENT_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
R7A_MANAGER_EXACT_ARM64_ARTIFACT=PASS
R7A_MANAGER_TARGET_MANIFEST=PASS
MANAGER_A_TO_B_PACKAGE=PASS
R7A_ACTIVATION_ENV_ABSENT=true
R7A_HOST_SERVICE_NOT_ACTIVE=true
```

Required artifact workflow:

```text
N3W T1 fresh install exact ARM64 CI
SOURCE_HEAD=c28130da1fcdeaa16d61a186d5a27c4c06fe791d
RUN_ID=42347391151
STATUS=IN_PROGRESS_AT_DESIGN_UPDATE
```

The workflow source head is an executable-equivalent authority for the Manager source. Later documentation-only commits do not invalidate the Manager bytes, but the artifact binding must explicitly retain this source head.

Permitted mutation in the later physical gate:

- load the exact R7A Manager successor artifact;
- use the existing Generic V2 / Manager A-to-B transaction path;
- replace only the Manager image/binding;
- keep `GH_N3W_T1_OTA_ENABLED=false`;
- do not install/start the R7A host daemon yet;
- do not insert or mutate USB media.

A0 postconditions:

```text
MANAGER=R7A_SUCCESSOR_BOUND_RUNNING
MANAGER_IMAGE=R7A_EXACT_SUCCESSOR
MANAGER_UID_GID=999:999
MANAGER_DOCKER_SOCKET=false
MANAGER_OTA_ENABLED=false
HOMEASSISTANT=UNCHANGED_ACCEPTED_PREDECESSOR
BROKER=UNCHANGED_ACCEPTED
USB_LIKE_DISK_COUNT=0
```

A0 is a live Manager mutation and requires its own explicit authorization.

### Boundary A1 — software activation with no USB present

Purpose: activate the host daemon and Manager IPC/control surface after the R7A-capable Manager successor is already healthy, while proving no removable-media mutation is possible.

Entry requirements:

```text
USB_LIKE_DISK_COUNT=0
R7A_MANAGER_SUCCESSOR_BOUND_RUNNING=PASS
HOMEASSISTANT_ACCEPTED_PREDECESSOR=PASS
BROKER_ACCEPTED=PASS
R7A_TRANSACTION_ABSENT=true
RECOVERY_REQUIRED=false
EXACT_SOURCE_HEAD_CI=PASS
```

Permitted mutation:

- install the exact R7A host Python source set required by the daemon;
- install the exact approved manifest to the fixed root-owned path;
- install `n3w-t1-ha-ota.service`;
- install the reviewed services-owner HA-OTA drop-in;
- atomically create `/etc/n3wfc4/ha-ota-activation.env` from the host-observed current HA runtime;
- `systemctl daemon-reload`;
- enable/start the host daemon;
- restart the existing services owner once so the already-upgraded R7A Manager successor is recreated with the read-only runtime bind and OTA environment.

Not permitted:

```text
USB_INSERTION=false
USB_FORMAT=false
USB_MOUNT=false
PREPARE_INTENT=false
CONFIRM_USB_ERASE=false
U2_PLUS=false
U5_PLUS=false
```

Postconditions:

```text
HOST_DAEMON=active
HOST_SOCKET=/run/n3w-t1-ota/ha-ota.sock
HOST_SOCKET_OWNER=root:999
HOST_SOCKET_MODE=0660

MANAGER_UID_GID=999:999
MANAGER_DOCKER_SOCKET=false
MANAGER_BLOCK_ACCESS=false
MANAGER_RUNTIME_BIND=/run/n3w/t1-ota:ro
MANAGER_OTA_ENABLED=true

HA_IMAGE=unchanged accepted predecessor
BROKER_IMAGE=unchanged accepted broker
UPDATER_TRANSACTION=absent
USB_LIKE_DISK_COUNT=0
```

The services-owner restart can briefly restart Manager and Home Assistant. Broker must remain continuous. This is a live service mutation boundary and requires explicit authorization before execution.

### Boundary B — one USB inserted, PREPARE only, still no write

Purpose: prove candidate discovery and the confirmation-before-mutation contract on real hardware.

Entry requirements:

- Boundary A PASS;
- no active R7A transaction;
- dedicated test USB **not yet inserted** when PREPARE is submitted;
- no second removable mass-storage device may be inserted during this gate.

Sequence:

```text
user selects PREPARE
-> U1 transaction created
-> host records current removable-device baseline
-> phase=USB_REQUIRED
-> user inserts exactly one dedicated removable test USB
-> host enumerates block devices read-only
-> exactly one fresh eligible candidate published
-> phase=USB_REQUIRED_CONFIRMATION
-> visible model/capacity shown
-> destructive confirmation action becomes available
-> STOP
```

The ordering is intentional. PREPARE baselines every already-present removable-device fingerprint and only a device appearing after that baseline may become the fresh candidate. A USB inserted before PREPARE is therefore excluded rather than promoted.

Hard stop:

```text
CONFIRM_USB_ERASE=false
WIPEFS=false
PARTITION_WRITE=false
MKFS=false
MOUNT=false
TARGET_DOWNLOAD=false
```

Physical evidence should record read-only media identity before and after PREPARE so the no-write claim is independently verifiable.

### Boundary C — explicit destructive confirmation, U2 -> U4

Boundary C is intentionally **not authorized or fully frozen by this document**.

Before `CONFIRM_USB_ERASE`, two authorities still need exact closure.

#### C1. Engineering HTTPS target source

The architecture freezes direct HTTPS streaming to USB but explicitly defers the final OTA/CDN provider.

For real R7A physical acceptance, an engineering-only exact HTTPS locator may be used if and only if:

```text
HTTPS=true
URL_CREDENTIALS=false
TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
TARGET_ARCHIVE_SIZE_BYTES=835309535
TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
PUBLIC_PRODUCT_PROVIDER_DECISION=false
```

A temporary GitHub Release asset is the preferred engineering transport because it provides ordinary trusted HTTPS and allows the current direct-stream implementation to be exercised without weakening TLS validation.

Using such an engineering asset does **not** freeze GitHub Releases as the product OTA/CDN provider.

#### C2. Full transaction USB-capacity inputs

The product formula is frozen:

```text
USB_REQUIRED_BYTES =
  target_artifact_bytes
+ predecessor_recovery_worst_case_bytes
+ ha_data_backup_worst_case_bytes
+ transaction_metadata_and_working_bytes
+ removable_media_reserve_bytes
```

However, repository evidence currently contains only synthetic test values for the four non-target inputs. No source authority supports inventing production numbers.

Therefore:

```text
REAL_CAPACITY_POLICY_NUMBERS=NOT_YET_FROZEN
CONFIRM_USB_ERASE_AUTHORIZED=false
```

These values must be derived and reviewed before Boundary C.

## 5. Exact deployment ownership

R7A remains within the existing three-product-service architecture.

```text
PRODUCT_DOCKER_SERVICES=3
GREENHOUSE_MANAGER=nonprivileged
MOSQUITTO=unchanged
HOME_ASSISTANT=unchanged during R7A

PRIVILEGED_OWNER=T1_Core_Updater host systemd daemon
MANAGER_ROOT=false
MANAGER_DOCKER_SOCKET=false
MANAGER_BLOCK_DEVICE_ACCESS=false
MANAGER_CALLER_SUPPLIED_DEVICE_PATH=false
```

The host daemon is infrastructure ownership, not a fourth Docker product service.

## 6. Activation asset expectations

The later execution chain has two distinct exact authorities:

1. an exact ARM64 Manager successor artifact built from the R7A Manager source and deployed through Manager A-to-B;
2. the host-side R7A source/activation asset bundle.

The later executor must exact-bind all files before live mutation.

Minimum source set includes the daemon plus all imported R7A modules required at runtime, the systemd unit, services-owner drop-in, Compose overlay and approved manifest.

The live executor must not use a broad `git checkout` on T1 as activation authority. It must transfer an exact source bundle, verify file digests, stage safely, and replace only the frozen R7A asset set.

Home Assistant and Broker image authority must remain unchanged during R7A. Manager image authority must advance once, through Boundary A0, from the accepted predecessor to the exact R7A Manager successor. The reviewed HA-OTA overlay is activated only in Boundary A1.

## 7. Rollback for Boundaries A0/A1

Boundary A0 uses the already-proven Manager A-to-B rollback contract. Its predecessor is the currently accepted Manager image. No HA/Broker image mutation is allowed.

Boundary A1 does not create a USB transaction. Its rollback must be prepared before the services-owner restart and must be able to:

1. stop/disable the R7A host daemon;
2. remove the HA-OTA services-owner drop-in;
3. remove the activation env file;
4. daemon-reload;
5. restart the services owner without the HA-OTA overlay;
6. verify the R7A Manager successor remains healthy with OTA default-OFF, or invoke the separately bound A0 Manager rollback if the successor itself is implicated;
7. verify Home Assistant and Broker remain at the exact accepted identities;
8. leave approved manifest/source files inert if retained, because no active service/socket/runtime bind remains.

No USB or HA-upgrade transaction recovery is involved in A0/A1 rollback.

## 8. Next ONE gate

After exact-head CI for `c046e88bbe808d170b0c93824dc750d0ab7be8ab` is green:

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_MANAGER_SUCCESSOR_EXACT_ARTIFACT_AND_A_TO_B_PACKAGE_20261107_01

REPOSITORY_MUTATION=true
LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
REAL_USB_MUTATION=false
SERVICE_MUTATION=false
DOCKER_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

That gate must close the exact ARM64 Manager successor artifact, freeze its Manager target manifest, produce/review the Manager A-to-B package for Boundary A0, and remain T1-readonly/non-mutating.

Only after A0 package closure may the host-daemon/overlay Boundary A1 executor be frozen.

It must stop before actually connecting to or mutating the real T1. Real execution of A0 or A1 is a separate explicit authorization boundary.

R7B remains deferred.
