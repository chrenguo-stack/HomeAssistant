# N3-W T1 Home Assistant mandatory-USB OTA R7A PREPARE pipeline source implementation closure — 2026-11-07

## 1. Gate result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_PREPARE_PIPELINE_SOURCE_IMPLEMENTATION_20261107_01
RESULT=CLOSED_PASS
R7A_SCOPE=SOURCE_IMPLEMENTATION_AND_SYNTHETIC_VALIDATION_ONLY

SOURCE_IMPLEMENTATION_HEAD=d5c7aca0b8f39acb0d9d014b649d943a81956262
STACKED_PR=800
STACKED_BASE_PR=799
STACKED_BASE_BRANCH=docs/n3w-r5-readonly-preflight-handoff-20261107
CHANGED_FILE_COUNT=18

CI_TOTAL=28
CI_SUCCESS=18
CI_SKIPPED=10
CI_FAILURE=0
CI_PENDING=0

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
REAL_USB_MUTATION=false
SERVICE_MUTATION=false
DOCKER_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

R7A closes the repository-only U1→U4 PREPARE implementation frozen by R6. The exact source head above is the executable authority for this closure. Later closure/state commits are documentation-only and do not replace that source authority.

## 2. Frozen architecture preserved

```text
DOCKER_PRODUCT_SERVICES=3
FOURTH_DOCKER_SERVICE=false
MANAGER_UID_GID=999:999
MANAGER_ROOT=false
MANAGER_DOCKER_SOCKET=false
MANAGER_BLOCK_DEVICE_ACCESS=false

PRIVILEGED_OWNER=host_side_T1_Core_Updater
HOST_DAEMON=systemd_managed
HOST_EFFECTIVE_UID=root
HOST_PRIMARY_GID=999

HOST_RUNTIME_DIR=/run/n3w-t1-ota
HOST_SOCKET=/run/n3w-t1-ota/ha-ota.sock
MANAGER_RUNTIME_MOUNT=/run/n3w/t1-ota
MANAGER_SOCKET=/run/n3w/t1-ota/ha-ota.sock
MANAGER_MANIFEST=/run/n3w/t1-ota/approved-homeassistant.json

DEFAULT_PRODUCTION_ACTIVATION=false
```

The Manager remains a non-privileged control plane. The host daemon is the only owner of block-device, filesystem and host-side Docker observation required by this stage.

## 3. Implemented R7A path

```text
PREPARE
-> U1 PREPARE_REQUESTED
-> read-only removable-media inventory
-> exactly one newly observed eligible USB candidate
-> publish public model/capacity/fingerprint
-> USB_REQUIRED_CONFIRMATION
-> CONFIRM_USB_ERASE
-> re-enumerate and revalidate exact candidate
-> wipefs/GPT/ext4 only after confirmation
-> UUID binding + write/fsync/read self-test
-> measured usable capacity gate
-> full transaction capacity formula
-> U2 USB_QUALIFIED_FORMATTED_BOUND
-> U3 TARGET_DOWNLOADING_VERIFYING
-> exact target streamed directly to bound USB
-> size/SHA256/portable-image verification + fsync
-> U4 READY_TO_INSTALL
-> STOP
```

No full target archive is first staged on the internal root filesystem.

## 4. High-risk closure matrix

```text
CONFIRMATION_BEFORE_MUTATION=PASS
INTERNAL_DISK_NEVER_SELECTABLE=PASS
MULTIPLE_USB_FAIL_CLOSED=PASS
READ_ONLY_USB_FAIL_CLOSED=PASS
PRODUCTION_MOUNT_BACKING_DEVICE_FAIL_CLOSED=PASS
NO_CALLER_DEVICE_PATH=PASS
NO_CALLER_MOUNT_PATH=PASS

U1_TO_U4_ONLY=PASS
NO_U5_PLUS_MUTATION=PASS
NO_INSTALL_COMMAND_PUBLICATION=PASS

NO_MANAGER_ROOT=PASS
NO_MANAGER_DOCKER_SOCKET=PASS
NO_MANAGER_BLOCK_ACCESS=PASS
SO_PEERCRED_UID_999=PASS

DIRECT_TO_USB_TARGET=PASS
USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=15032385536
FULL_TRANSACTION_CAPACITY_FORMULA=PASS

SAME_MEDIA_U2_U3_RECOVERY=PASS
NO_AUTOMATIC_SECOND_USB_FORMAT=PASS
INTERRUPTED_TARGET_TEMP_CLEANUP=PASS
STALE_TEMP_SYMLINK_FAIL_CLOSED=PASS

HOST_OBSERVED_INSTALLED_VERSION=PASS
DEFAULT_PRODUCTION_ACTIVATION_OFF=PASS
NO_REAL_T1_OR_USB_WRITE=PASS
```

## 5. Focused repairs found during independent review

The existing R7A branch was not accepted at face value. Independent source/test review found and repaired four classes of defects before closure.

### 5.1 Duplicated test-module tail

The R7A PREPARE test file contained a duplicated appended module body beginning with a malformed `rom __future__ import annotations`, causing pytest collection failure. The duplicated tail was removed.

### 5.2 False U4 hard-stop

The initial branch still contained an executable INSTALL path:

```text
HA discovery
-> INSTALL MQTT intent
-> Manager
-> Manager AF_UNIX bridge
-> host IPC
-> request_install()
-> U4 -> U5
```

That contradicted the R6 contract. R7A now rejects INSTALL across the Manager parser/control path, Manager IPC bridge and host IPC executor, and Home Assistant discovery no longer publishes an INSTALL command at U4.

The remaining U5+ names are compatibility/status vocabulary only; no R7A source path can execute U4→U5.

### 5.3 Default-off overlay coupling

The opt-in Compose overlay originally required `GH_N3W_T1_OTA_INSTALLED_VERSION` even while OTA was disabled. It now remains genuinely default-off without that mandatory input. Enabled-mode validation remains in Manager settings.

### 5.4 Power-loss and version-projection defects

Interrupted target downloads could leave `.homeassistant-target.*` temporary files on the bound USB. R7A now removes only regular files with that strict prefix inside the already validated bound USB target directory and fsyncs the directory; a matching symlink fails closed.

Two new semantic-version regexes also contained over-escaped dots and rejected valid HA versions/image refs. Those expressions were corrected before the final exact-head CI run.

## 6. Durable restart behavior

```text
U1_RESTART=READONLY_REENUMERATION_AND_NEW_CONFIRMATION_IF_REQUIRED
U2_U3_RESTART=SAME_UUID_AND_PUBLIC_FINGERPRINT_ONLY
PARTIAL_TARGET_PROMOTION=false
WRONG_OR_MISSING_BOUND_MEDIA=RECOVERABLE_WAIT
SECOND_USB_AUTO_FORMAT=false
U4_INSTALL_AUTHORIZATION=false
```

The R7A worker resumes only U2/U3 against the already bound filesystem/device identity. It does not automatically format a replacement device.

## 7. CI closure

At exact source head `d5c7aca0b8f39acb0d9d014b649d943a81956262`:

```text
WORKFLOW_TOTAL=28
SUCCESS=18
SKIPPED=10
FAILURE=0
PENDING=0
PR800_MERGEABLE_AT_CLOSURE_REVIEW=true
```

The skipped workflows are path-gated jobs not applicable to this source delta. All applicable visible workflows completed successfully.

## 8. Production/runtime authority remains unchanged

```text
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED

R7A_SOURCE_PRESENT_IN_PR=true
R7A_SOURCE_DEPLOYED_TO_T1=false
R7A_HOST_SERVICE_INSTALLED=false
R7A_HOST_SERVICE_ENABLED=false
R7A_MANAGER_OTA_ENABLED=false
REAL_USB_FORMAT=false
```

R7A source presence is not production activation authority.

## 9. R7B remains deferred

R7A does not choose or implement:

- HA-data backup authenticated-encryption and key-recovery design;
- predecessor image export details beyond existing artifact-family constraints;
- U5+ one-shot install authorization;
- HA service-stop/cutover/rollback procedure.

Those remain R7B design concerns.

## 10. Next ONE gate

R7A source is closed, but the next step must not jump directly to real USB mutation. The next bounded gate is a real-T1 **read-only preactivation preflight** for the new host/Manager wiring.

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_REAL_T1_PREACTIVATION_READONLY_PREFLIGHT_20261107_01
NEXT_SCOPE=REAL_T1_READONLY_PREACTIVATION_PREFLIGHT

REPOSITORY_MUTATION=false
LIVE_T1_ACCESS=true
LIVE_T1_MUTATION=false
REAL_USB_MUTATION=false
SERVICE_INSTALL=false
SERVICE_ENABLE=false
SERVICE_START=false
DOCKER_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false

AUTO_EXECUTE_NEXT_GATE=false
```

The preflight may inspect host prerequisites, existing production/runtime identity, systemd/Docker capabilities and removable-device inventory read-only if needed. It must not install/enable/start the R7A daemon, mount/format/write a USB device or change the production Manager container.

A later real activation / real-USB validation gate requires its own explicit physical boundary.
