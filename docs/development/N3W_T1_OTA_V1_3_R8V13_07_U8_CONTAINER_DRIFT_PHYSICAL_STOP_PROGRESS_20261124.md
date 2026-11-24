# N3-W T1 OTA V1.3 R8V13-07 U8 container-drift physical STOP progress

Date: 2026-11-24

## Scope

This record archives the first physical result after the bounded U5 continuation from the existing fresh transaction.

```text
CURRENT_TASK=R8V13-07
R8V13_08_BLOCKED=true
TRANSACTION_ID_SHA256=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
CONTINUATION_EXECUTOR_SHA256=8a026b108954c524964a0373c516f3904c08d42424fd497605f27caa60ada9b3
CONTINUATION_AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_R8V13_07_INSTALL_CUTOVER_20261124_03
```

## Physical execution result

The bounded continuation passed its U5 preflight and issued a fresh valid install authority:

```text
DURABLE_U5=PASS
CURRENT_RELEASE_PIN_VALID=PASS
PREDECESSOR_RUNTIME_BEFORE_AUTHORITY=PASS
CURRENT_LAUNCH_SHA256=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
TARGET_10_0_PRESENT_BEFORE_AUTHORITY=false

INSTALL_REQUEST_BINDING_SHA256=f012b3ed4fe47090e5dc23b23c48b558099ce6247dad716b4d6252ae8ef5cd83
INSTALL_REQUEST_AUTHORIZATION_ID=N3W_T1_CORE_UPDATER_R8V13_07_INSTALL_CUTOVER_20261124_03
INSTALL_AUTHORITY_ISSUED=true
FRESH_VALID_INSTALL_AUTHORITY=PASS
FRESH_INSTALL_AUTHORITY_SHA256=1fc4602d2e0cae643685dffacda6300d7392b2b8f1d613df69d5506b3a2414be
POST_AUTHORITY_PREDESTRUCTIVE_STATE=PASS
```

The product worker then stopped during the U8 predecessor-release admission path:

```text
STATUS=ACTIVE
PHASE=U8_RECOVERY_ADMISSION_COMPLETE
FAILURE_CODE=ha_usb_release_predecessor_container_drift
RECOVERY_REQUIRED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_ID_SHA256=null
PREDECESSOR_START_PRESENT=true
PREDECESSOR_RELEASE_INTENT_PRESENT=false
PREDECESSOR_RELEASE_OBSERVED=null
TARGET_LOADED_IMAGE_ID=null
TARGET_ACTIVATION=null
HA_DATA_RESTORE_PRESENT=false
```

This proves the failure occurred before release intent, before predecessor image release, before target import/activation, and before authorization claim/consume.

## Automatic pre-cutover recovery result

A later readback from the same durable transaction returned:

```text
STATUS=ROLLED_BACK
PHASE=U8_RECOVERY_ADMISSION_COMPLETE
FAILURE_CODE=ha_usb_release_predecessor_container_drift
RECOVERY_REQUIRED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_ID_SHA256=null
PRE_CUTOVER_PREDECESSOR_RESTORED=true
PREDECESSOR_RELEASE_OBSERVED=null
TARGET_LOADED_IMAGE_ID=null
TARGET_ACTIVATION=null
PREDECESSOR_START_PRESENT=true
PREDECESSOR_RELEASE_INTENT_PRESENT=false
HA_DATA_RESTORE_PRESENT=false
TARGET_ACCEPTANCE_PRESENT=true
```

Source semantics require predecessor restart plus predecessor-health verification before the pre-cutover recovery path writes this terminal `ROLLED_BACK` state. This is therefore a successful automatic pre-cutover recovery, not a complete U13B rollback.

The subsequent re-execution of the same continuation executor stopped in `U5_CONTINUATION_PREFLIGHT` because the durable transaction was already terminal and no longer `ACTIVE / U5_INSTALL_REQUESTED_REVALIDATING`. No INSTALL intent replay or further cutover action is claimed from that second invocation.

## Current classification

```text
R8V13_07_RESULT=NOT_PASS
R8V13_08_BLOCKED=true
SYSTEM_RECOVERY_CLASS=PRE_CUTOVER_AUTO_RECOVERY_COMPLETED
FULL_U13B_ACCEPTANCE=false
PRODUCT_FAILURE_BOUNDARY=U8_PREDECESSOR_RELEASE_ADMISSION
NEW_DISTINCT_DEFECT_CLASSIFICATION=PENDING_READONLY_FORENSIC
KF152_REOPENED=false
INSTALL_INTENT_REPLAY_ALLOWED=false
CONTINUATION_REPLAY_ALLOWED=false
BROKER_OTA=false
HOST_REBOOT=false
MERGE=false
RELEASE=false
```

The failure code is distinct from the already-guarded KF-152 RepoDigest/image-reference predicate. The exact `ha_usb_release_predecessor_container_drift` predicate can be raised when the single exited Home Assistant Compose residue has an unexpected container ID shape, non-`exited` status, a non-empty Compose replacement label, or image reference/runtime-ID drift; it can also be raised if the captured release candidate changes before destructive release. Because `PREDECESSOR_RELEASE_INTENT_PRESENT=false`, the physical failure occurred during the initial capture/admission check, before destructive release. The exact field mismatch remains unproven until read-only container residue evidence is collected.

## Next action

Perform read-only forensic capture only:

- exact durable transaction and SHA256;
- current Manager/Home Assistant/Broker runtime identities and health;
- systemd owner state;
- all Home Assistant Compose containers, including exited residue;
- each residue container's full ID, state, Config.Image, image ID and Compose labels, especially `com.docker.compose.replace`;
- predecessor image references and target-image absence/presence.

Do not replay PREPARE, INSTALL intent, install authority, continuation executor, predecessor release, target load, or recovery mutation.

A new KF number should be assigned only after the exact physical mismatch is identified or the source/harness defect is otherwise independently proven.


## KF-153 root-cause closure from read-only forensic

The physical read-only capture proves the exact failed residue was not a foreign or ambiguous container.

```text
TX_FILE_SHA256=b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0
STATUS=ROLLED_BACK
PHASE=U8_RECOVERY_ADMISSION_COMPLETE
RECOVERY_REQUIRED=false
PRE_CUTOVER_PREDECESSOR_RESTORED=true

LIVE_SERVICES_OWNER=active
LIVE_BROKER_OWNER=active
CURRENT_PREDECESSOR_BINDING=PASS
CURRENT_LAUNCH_SHA256=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
TARGET_PRESENT=false

HOMEASSISTANT_CONTAINER_ID=b18431447f114c3958b68c30b20c8b9dbc4fa05d8e34ddc56d8ce0764d1ce6dd
HOMEASSISTANT_IMAGE_REF=local/n3w-homeassistant:2026.10.4-5881590f
HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
HOMEASSISTANT_REPLACE_LABEL=homeassistant-1
HOMEASSISTANT_CREATED=2026-11-23T14:35:24.957641413Z
HOMEASSISTANT_FAILED_ATTEMPT_FINISHED=2026-11-24T08:10:55.402856886Z
HOMEASSISTANT_RECOVERY_RESTARTED=2026-11-24T08:14:03.538416693Z
```

The container creation time predates the failed U8 attempt and the same container ID is running after automatic recovery. Its image ref/ID match the durable predecessor exactly; launch binding and protected mounts pass; target 10.0 is absent. The nonempty Compose replace label is therefore normal metadata on the exact owned container, not evidence of replacement drift.

Source predicate review shows `capture_predecessor_release()` rejected this otherwise exact exited residue solely because `container["replace"]` was nonempty. The rollback-target residue path had the same false predicate and would be vulnerable later in a real U13B path.

Classification:

```text
KF=KF-153
ROOT_CAUSE=COMPOSE_REPLACE_LABEL_MISUSED_AS_CONTAINER_OWNERSHIP_DRIFT_ORACLE
PRODUCT_SAFETY_FAILURE=false
PRODUCT_AVAILABILITY_RECOVERY=PASS
R8V13_07_RESULT=NOT_PASS
R8V13_08_BLOCKED=true
OLD_TRANSACTION_REPLAY=false
OLD_CONTINUATION_REPLAY=false
SOURCE_REPAIR_HEAD=90ce32ce4b6c329fd38c2771e352d129d6d00a86
SOURCE_REPAIR_CI=IN_PROGRESS
```

The repair removes only the replace-label predicate. All stronger safety checks remain mandatory: a single residue at most, full SHA256 container ID, valid stopped state, exact image ref/runtime ID, protected mount equality, exact ancestor-user set, rollback-writer quiescence, and the pre-existing release-intent/destructive-boundary state machine.


## KF-153 source / CI / exact package closure

```text
KF153_SOURCE_REPAIR_HEAD=90ce32ce4b6c329fd38c2771e352d129d6d00a86
SOURCE_REGRESSION=327_PASSED_1_SKIPPED
REAL_DOCKER_RELEASE_INTEGRATION=1_PASSED

RECOVERY_ARTIFACT_RUN=45357836296
RECOVERY_ARTIFACT_ID=14902399722
RECOVERY_ARTIFACT_DIGEST_SHA256=c19280ac1fcbca7ef0de10ba2a24c0e1993898b0de988693ae14cff2c8e63a66
RECOVERY_INSTALL_MANIFEST_SHA256=90e83d4c4ce2a25e6c9fbce0245344b8c3ba247a4b5ecc58d4e93c4ceb169877
RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a

LIVE_T1_RECOVERY_PYZ_SHA256=d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
LIVE_REPAIRED_PACKAGE_DEPLOYED=false
LIVE_REVALIDATION_PENDING=true
```

The recovery artifact was independently downloaded and re-hashed after upload. The ZIP SHA256 matches the GitHub artifact digest; `manifest.json` SHA256 matches the workflow-emitted install-manifest digest; the manifest binds `ha-recovery.pyz` to the exact SHA256 above and records source head `90ce32ce...`.

The later repository-only documentation/security commits do not alter the recovery executable source. The next physical action must be a separate live-repair/reacceptance gate; source/package closure alone does not authorize T1 mutation.


## KF-153 real-T1 read-only closure and live-repair authorization boundary

The real spare-T1 preflight completed without mutation:

```text
DURABLE_TERMINAL_TRANSACTION=PASS
RUNTIME_IDENTITIES=PASS
CURRENT_PREDECESSOR_BINDING=PASS
CURRENT_LAUNCH_SHA256=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
NON_PYZ_SUCCESSOR_PARITY=PASS
TARGET_10_0_PRESENT=false
LIVE_MUTATION=false
RESULT=KF153_LIVE_REPAIR_READONLY_PREFLIGHT_PASS
```

The bounded live-patch executor is now exact-head CI closed:

```text
LIVE_PATCH_EXECUTOR=tools/execution_packages/n3w/t1_ota_kf153/N3W_T1_V1_3_KF153_LIVE_REPAIR_20261124_01.sh
LIVE_PATCH_EXECUTOR_SHA256=1e6184ffae961bf8dbbb00361a1b90f4a6a56401a67a70f34b150e867000e6e9
LIVE_PATCH_EXECUTOR_SOURCE_HEAD=ae3d43e372423d1eb46ba5f9dcadbeccd351f4ae
FOCUSED_CI_RUN=45361435421
FOCUSED_CI=SUCCESS
FOCUSED_TESTS=23_PASSED
ALL_EXACT_HEAD_WORKFLOWS=SUCCESS

AUTHORIZATION_GATE=N3W_T1_V1_3_KF153_LIVE_REPAIR_20261124_01
AUTHORIZATION_STATUS=NOT_GRANTED
FIRST_MUTATION=STOP_RECOVERY_RETRY_TIMER
```

Scope is pyz-only. The application stack must remain running; target 10.0 must remain absent; the terminal failed transaction must remain byte-identical. On any post-publish failure, the executor re-quiesces recovery retry/IPC before atomically restoring the old pyz.

R8V13-07 remains NOT_PASS until a completely new fresh physical reacceptance succeeds. R8V13-08 remains blocked.


## KF-153 live repair PASS

```text
AUTHORIZATION_GATE=N3W_T1_V1_3_KF153_LIVE_REPAIR_20261124_01
AUTHORIZATION_STATUS=APPROVED_CONSUMED_FOR_BOUNDED_SCOPE
LIVE_PATCH_EXECUTOR_SHA256=1e6184ffae961bf8dbbb00361a1b90f4a6a56401a67a70f34b150e867000e6e9
LIVE_RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
DURABLE_TRANSACTION_UNCHANGED=PASS
APPLICATION_RUNTIME_UNCHANGED=PASS
POST_PATCH_PREDECESSOR_BINDING=PASS
TARGET_10_0_PRESENT=false
RESULT=KF153_LIVE_REPAIR_PASS
KF153_STATUS=GUARDED
```

This closes the live deployment/revalidation requirement for KF-153. The failed transaction remains terminal/no-replay and R8V13-07 remains NOT_PASS only because the physical 10.4→10.0 reacceptance has not yet been re-run with a fresh transaction.
