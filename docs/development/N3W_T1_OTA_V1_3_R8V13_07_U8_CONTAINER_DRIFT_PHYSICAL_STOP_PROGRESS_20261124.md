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
