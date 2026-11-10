# N3-W T1 Home Assistant mandatory-USB OTA P5 R7A Manager successor A0 live execution package preexecution closure — 2026-11-07

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_MANAGER_SUCCESSOR_A0_LIVE_EXECUTION_PACKAGE_PREEXECUTION_20261107_01
RESULT=CLOSED_PASS_EXECUTOR_READY_LIVE_AUTHORIZATION_PENDING

PR=800
EXECUTABLE_HEAD=bed9aeb7c41f614bdeb8e445d71171e669e45942
EXECUTABLE_TREE=7f07e82f688dfee24e22e9330485e2c02edbd4fa

LIVE_EXECUTION_AUTHORIZED=false
LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
MANAGER_LIVE_UPGRADE=false
SERVICE_MUTATION=false
DOCKER_RUNTIME_MUTATION=false
REAL_USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This gate closes the source-only A0 operator executor required before the real-T1 Manager successor apply. It does not authorize or perform the live Manager upgrade.

## 2. Frozen package authority

```text
PACKAGE_CONTROL_HEAD=921e7d5557ff3dbf4b7e7ae5510186d98f803a2a
PACKAGE_RUN_ID=42349904235
PACKAGE_ARTIFACT_ID=13564899377
PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-v2-bf38e388497b
PACKAGE_ARTIFACT_DIGEST_SHA256=6e9ca4cf103434330c0a31b51e1ba27b7d12b554648f4b0a017fd69bc4a32e1c
PACKAGE_ARTIFACT_EXPIRED=false

UPDATER_PYZ_SHA256=1b556d5601f33ef050c91e990bedaaeb1611bef325350fad008a1ec69fc7dc99
MANAGER_TAR_SHA256=4c4492ef5008a968b2553240b3fde97912eb3ae862604ae492e5a639a93db008
MANAGER_BUILD_IMAGE_ID=sha256:136cdcacf84a388a91cf0adbf7e0653a78b754e1879a59d3a2ac066ecba9fa5f

EXPECTED_PREDECESSOR_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
TARGET_MANAGER=local/greenhouse-manager:fresh-bf38e388497b
```

The package remains the previously closed Manager-only Generic V2 package. The A0 executor does not rebuild Manager or mutate the frozen target/baseline authority.

## 3. Package continuity

Independent compare from package control head to executable head:

```text
BASE=921e7d5557ff3dbf4b7e7ae5510186d98f803a2a
HEAD=bed9aeb7c41f614bdeb8e445d71171e669e45942
AHEAD_BY=16

MANAGER_PRODUCT_SOURCE_CHANGE_COUNT=0
GENERIC_V2_PACKAGE_INPUT_CHANGE_COUNT=0
TARGET_MANIFEST_DRIFT=false
PREDECESSOR_BASELINE_DRIFT=false
```

The changed files after package closure are limited to the A0 executor/manifest/tests, the Manager A-to-B CI wiring, and project documentation.

## 4. A0 executor authority

```text
EXECUTOR=tools/execution_packages/n3w/r7a/manager_a0_live_apply/executor.py
MANIFEST=tools/execution_packages/n3w/r7a/manager_a0_live_apply/manifest.json
TEST=tests/tools/test_n3w_t1_r7a_manager_a0_executor.py

LIVE_EXECUTION_AUTHORIZED=false
STOP_BOUNDARY=BEFORE_REAL_SSH_EPOCH_UNTIL_SEPARATE_LIVE_AUTHORIZATION
TRUSTED_SSH_TRANSPORT_REQUIRED=true
SINGLE_SSH_EPOCH_REQUIRED=true
HOST_KEY_PINNING_REQUIRED=true
```

The executor binds the existing trusted SSH transport blob and refuses live execution while the manifest keeps `live_execution_authorized=false`.

## 5. Final execution order

The reviewed order is:

```text
LOCAL_EXACT_AUTHORITY_CHECK
-> LIVE_EXECUTION_AUTHORIZATION_CHECK
-> DOWNLOAD_AND_VERIFY_FROZEN_PACKAGE
-> TRUSTED_SSH_SINGLE_EPOCH
-> ACCEPTED_STACK_READONLY_CHECK
-> R7A_ACTIVATION_RESIDUE_READONLY_CHECK
-> USB_LIKE_DISK_COUNT_ZERO
-> UPDATER_STATE_READONLY_RECOVERY_CHECK
-> REMOTE_PACKAGE_STAGING
-> UPDATER_STATUS
-> UPDATER_INSPECT
-> UPDATER_PLAN
-> ONE_SHOT_APPLY
-> POST_STATUS
-> POST_INSPECT
-> EXACT_TARGET_AND_PEER_ACCEPTANCE
-> USB_ZERO_RECHECK
-> SSH_MASTER_CLEANUP
```

No T1 filesystem staging occurs before the updater state/recovery gate.

## 6. Final-review repairs

Independent final review found and repaired source-level preexecution blockers that were not covered by the earlier happy-path CI.

```text
PRESTAGING_UPDATER_STATE_GATE=PASS
REMOTE_STAGING_EXACT_FILE_SET=PASS
STATE_ROOT_SYMLINK_FAIL_CLOSED=PASS
STATE_FILE_SYMLINK_FAIL_CLOSED=PASS
REMOTE_STAGING_SYMLINK_FAIL_CLOSED=PASS
APPROVED_MANIFEST_RESIDUE_GUARD=PASS
POST_APPLY_MANAGER_IMAGE_ID_BINDING=PASS
POST_FAILURE_STATUS_CAPTURE=PASS
POST_FAILURE_INSPECT_CAPTURE=PASS
```

Rollback semantics are now explicit:

```text
EXECUTOR_EXPLICIT_ROLLBACK=false
UPDATER_INTERNAL_FAILURE_ROLLBACK=true
AUTOMATIC_RETRY=false
SECOND_APPLY=false
```

The Generic V2 updater retains its bounded internal failure rollback. The operator executor does not issue a second explicit rollback or retry. Any apply return is followed by post-status/post-inspect evidence capture before the executor decides whether the transaction committed.

## 7. Read-only A0 entry preconditions

Before any later live apply, the executor must prove:

```text
HOST_ARCHITECTURE=aarch64
HOST_SYSTEM_STATE=running

MANAGER_IMAGE=local/greenhouse-manager:fresh-5b32e1ae8210
MANAGER_RUNTIME_IMAGE_ID=sha256:228a42a8b14f36694cca6778b18c7be880def25c567ea5492a9e2a40a8ce912e
MANAGER_UID_GID=999:999
MANAGER_RESTART_COUNT=0
MANAGER_DOCKER_SOCKET=false
MANAGER_OTA_ENV_ABSENT=true
MANAGER_OTA_RUNTIME_MOUNT_ABSENT=true

HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
HOMEASSISTANT_RUNTIME_IMAGE_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306

BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_RUNTIME_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563

R7A_HOST_SERVICE_LOAD_STATE=not-found
R7A_RUNTIME_DIR_ABSENT=true
R7A_ACTIVATION_ENV_ABSENT=true
R7A_APPROVED_MANIFEST_ABSENT=true
USB_LIKE_DISK_COUNT=0

UPDATER_STATE_ROOT=root:root:700
UPDATER_RECOVERY_REQUIRED=false
HA_USB_SUCCESSOR_STATE_ABSENT=true
```

Any mismatch is STOP before apply.

## 8. Remote staging contract

The remote staging directory is fixed and root-private. It must contain exactly:

```text
greenhouse-manager-arm64.tar
manager-target-v2.json
package-binding.json
t1-core-updater.pyz
upgrade-baseline-a.json
```

No extra file, symlink, non-regular package file, SHA mismatch or metadata drift is accepted.

## 9. Apply contract

The live A0 transaction, when separately authorized, is Manager-only:

```text
MUTATION_PROFILE=IMAGE_ONLY_V1
MANAGER_ONLY_MUTATION=true
HOMEASSISTANT_IMAGE_MUTATION=false
BROKER_IMAGE_MUTATION=false
HOST_DAEMON_ACTIVATION=false
USB_MUTATION=false

APPLY_LIMIT=1
AUTOMATIC_RETRY=false
EXECUTOR_EXPLICIT_ROLLBACK=false
UPDATER_INTERNAL_FAILURE_ROLLBACK=true
```

The accepted production authority is not promoted by this source closure.

## 10. CI closure

Exact executable-head evidence:

```text
EXECUTABLE_HEAD=bed9aeb7c41f614bdeb8e445d71171e669e45942
PR_WORKFLOW_RUNS_TOTAL=31
SUCCESS=27
FAILURE=0
PENDING=0
CANCELLED=4

A0_MANAGER_A_TO_B_RUN_ID=42362708336
A0_SOURCE=SUCCESS
A0_EXACT_MANAGER_SLICE=SUCCESS
A0_PRE_U1_V2_SIMULATION=SUCCESS
```

The four cancelled workflows are ancillary non-A0 runs; the dedicated A0 three-stage workflow completed successfully and there are no failed or pending workflows on the executable head.

## 11. Live production remains unchanged

```text
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615

CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d

R7A_MANAGER_SUCCESSOR=local/greenhouse-manager:fresh-bf38e388497b
R7A_MANAGER_SUCCESSOR_LIVE_ACCEPTED=false

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
MANAGER_LIVE_UPGRADE=false
```

## 12. Authorization ledger

```text
PROPOSED_AUTHORIZATION=N3W_T1_R7A_MANAGER_SUCCESSOR_A0_LIVE_APPLY_20261107_01
GRANTED=false
CLAIMED=false
CONSUMED=false
REPLAY_PERMITTED=false
```

No prior Manager authorization is reusable for this A0 transaction.

## 13. Next ONE gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_MANAGER_SUCCESSOR_A0_LIVE_APPLY_20261107_01

LIVE_T1_ACCESS=true
LIVE_T1_MUTATION=true
MANAGER_LIVE_UPGRADE=true
SERVICE_MUTATION=true
DOCKER_RUNTIME_MUTATION=true

REAL_USB_MUTATION=false
HOST_DAEMON_ACTIVATION=false
BOARD_ACCESS=false
MERGE=false

EXPLICIT_USER_AUTHORIZATION_REQUIRED=true
AUTO_EXECUTE_NEXT_GATE=false
```

The next gate may not begin until the user explicitly authorizes this real-T1 Manager-only A0 apply. The first live phase must still repeat the minimal fresh read-only preconditions before staging/apply.

R7A host-daemon/Compose activation remains Boundary A1 and is not part of A0.
