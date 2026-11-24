# N3-W T1 Core Stack OTA V1.3 — KF-153 live repair read-only preflight pre-execution

Date: 2026-11-24

## 0. Result

```text
TASK=N3W_T1_OTA_V1_3_KF153_LIVE_REPAIR_READONLY_PREFLIGHT
STATUS=REAL_T1_READONLY_PREFLIGHT_PASS
T1_MUTATION=false
LIVE_MUTATION_AUTHORIZATION_GRANTED=false
R8V13_07_RESULT=NOT_PASS
R8V13_08_BLOCKED=true
BROKER_OTA=DEFERRED
```

KF-153 source, focused regression, real-Docker regression and exact recovery artifact are closed sufficiently to perform a fresh read-only live preflight. This stage does not authorize deployment of the repaired recovery pyz or creation of a new HA transaction.

## 1. Source and package authority

```text
KF153_SOURCE_REPAIR_HEAD=90ce32ce4b6c329fd38c2771e352d129d6d00a86
SOURCE_REGRESSION=327_PASSED_1_SKIPPED
REAL_DOCKER_RELEASE_INTEGRATION=1_PASSED

RECOVERY_ARTIFACT_RUN=45357836296
RECOVERY_ARTIFACT_ID=14902399722
RECOVERY_ARTIFACT_DIGEST_SHA256=c19280ac1fcbca7ef0de10ba2a24c0e1993898b0de988693ae14cff2c8e63a66
RECOVERY_INSTALL_MANIFEST_SHA256=90e83d4c4ce2a25e6c9fbce0245344b8c3ba247a4b5ecc58d4e93c4ceb169877
RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
RECOVERY_PYZ_SIZE_BYTES=495983
```

The GitHub artifact ZIP was independently downloaded and re-hashed. Its manifest binds source head `90ce32ce...` and the exact pyz above. The ten non-pyz payload hashes are frozen by the manifest and are checked against the live T1 by the read-only preflight.

## 2. Last verified spare-T1 baseline

```text
TRANSACTION_ID_SHA256=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
TRANSACTION_FILE_SHA256=b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0
TRANSACTION_STATUS=ROLLED_BACK
TRANSACTION_PHASE=U8_RECOVERY_ADMISSION_COMPLETE
FAILURE_CODE=ha_usb_release_predecessor_container_drift
RECOVERY_REQUIRED=false
PRE_CUTOVER_PREDECESSOR_RESTORED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
PREDECESSOR_RELEASE_INTENT_PRESENT=false
PREDECESSOR_RELEASE_OBSERVED=false
TARGET_10_0_PRESENT=false

LIVE_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
LIVE_HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
LIVE_MANAGER=local/greenhouse-manager:fresh-1cae18039eee
LIVE_MANAGER_IMAGE_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
LIVE_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
LIVE_LAUNCH_SHA256=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
LIVE_COMPOSE_SHA256=6cd522b55136beceb8661820896351238d2218c23c3b3e71e98a7521ac67f0f4
LIVE_RECOVERY_PYZ_SHA256=d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
```

The current live pyz is intentionally the guarded KF-152 predecessor. The KF-153 repaired pyz has not been deployed.

## 3. Why the full recovery installer is not used for the patch

The recovery package installer is fail-closed for existing files: an existing destination is accepted only if its bytes already equal the package payload. Because `ha-recovery.pyz` is the one intentionally changed file, invoking the full installer against the current T1 would stop with existing-file drift rather than upgrade it.

Therefore the next live mutation, if later authorized, must use the already-established bounded updater-only patch pattern: quiesce only the recovery retry/IPC control plane needed to avoid concurrent updater execution, atomically replace only `/opt/n3w-t1-core-updater/ha-recovery.pyz`, fsync/read back, and re-arm the control plane. The application stack must remain running and unchanged.

This preflight does not perform that mutation.

## 4. Read-only preflight executor

```text
EXECUTOR=tools/execution_packages/n3w/t1_ota_kf153/N3W_T1_V1_3_KF153_LIVE_REPAIR_READONLY_PREFLIGHT_20261124_01.sh
EXECUTOR_SHA256=9cbab3061376009338bed9dd28505c21266bcef6a9b78ac63f41125122a3305c
BASH_SYNTAX=PASS
REMOTE_MUTATION=false
PRIVATE_T1_LOCATOR_IN_REPOSITORY=false
```

The executor requires the operator to supply `N3W_T1_SSH_TARGET` locally. The repository contains no private T1 address.

It checks:

- exact terminal KF-153 transaction bytes and semantic fields;
- exact current 10.4 predecessor, Manager and Broker runtime identities;
- zero container restart-count drift;
- exact active application/Broker and armed recovery timer/IPC socket;
- target 10.0 remains absent;
- current pyz is exactly the old `d3e844...` and not the new `5208dadc...`;
- all ten non-pyz installed recovery payloads equal the KF-153 successor manifest;
- current product predecessor launch binding remains exact.

Expected terminal output:

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

Any nonzero exit or missing final PASS is a STOP. Do not rerun destructive or recovery actions in response.

## 5. Next gate after PASS

A PASS permits preparation of, but does not itself grant, the next live mutation gate.

Proposed next gate:

```text
PROPOSED_AUTHORIZATION_GATE=N3W_T1_V1_3_KF153_LIVE_REPAIR_20261124_01
PROPOSED_SCOPE=EXACT_RECOVERY_PYZ_PATCH_ONLY
EXPECTED_OLD_PYZ_SHA256=d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
EXPECTED_NEW_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
APPLICATION_SERVICE_RESTART=false
BROKER_MUTATION=false
HA_IMAGE_MUTATION=false
MANAGER_IMAGE_MUTATION=false
USB_MUTATION=false
NEW_HA_TRANSACTION=false
REBOOT=false
MERGE=false
RELEASE=false
```

After a successful bounded pyz patch, a second read-only post-patch closure must prove the application runtime unchanged and the new pyz exact. Only then may a separate fresh R8V13-07 transaction/reacceptance package be prepared. The terminal failed transaction is never reused.

## 6. Hard boundaries

- Never replay the old U5 continuation executor or INSTALL intent.
- Never change the terminal KF-153 transaction.
- Do not load target 10.0 during the preflight or pyz-patch stage.
- Do not restart Home Assistant, Manager or Broker for the pyz patch.
- Broker OTA remains deferred until HA OTA acceptance closes.
- No reboot/power-cycle, merge or release is authorized here.


## 7. Real-T1 execution closure

The operator-reported execution completed with the expected terminal PASS:

```text
PHASE=KF153_LIVE_REPAIR_READONLY_PREFLIGHT
DURABLE_TERMINAL_TRANSACTION=PASS
RUNTIME_IDENTITIES=PASS
CURRENT_PREDECESSOR_BINDING=PASS
CURRENT_LAUNCH_SHA256=67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26
EXPECTED_SOURCE_HEAD=90ce32ce4b6c329fd38c2771e352d129d6d00a86
EXPECTED_NEW_MANIFEST_SHA256=90e83d4c4ce2a25e6c9fbce0245344b8c3ba247a4b5ecc58d4e93c4ceb169877
EXPECTED_NEW_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
LIVE_OLD_PYZ_SHA256=d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
NON_PYZ_SUCCESSOR_PARITY=PASS
TARGET_10_0_PRESENT=false
LIVE_MUTATION=false
RESULT=KF153_LIVE_REPAIR_READONLY_PREFLIGHT_PASS
```

Focused CI on exact checkout later emitted the current repository executor SHA256
`9cbab3061376009338bed9dd28505c21266bcef6a9b78ac63f41125122a3305c`.
The earlier pre-execution metadata value `4ba8d123...` is superseded and must not be used as repository byte authority.
This is a documentation-authority correction, not a live T1 drift classification. The next live-patch executor independently revalidates the complete live baseline immediately before mutation.

```text
READONLY_PREFLIGHT_LIVE_RESULT=PASS
READONLY_PREFLIGHT_LIVE_MUTATION=false
READONLY_EXECUTOR_CURRENT_REPOSITORY_SHA256=9cbab3061376009338bed9dd28505c21266bcef6a9b78ac63f41125122a3305c
OLD_DOCUMENTED_EXECUTOR_SHA256=4ba8d12307c294b8fe043ead1aaecff262380acfcd977c4454406d2e3101be33
OLD_DOCUMENTED_EXECUTOR_SHA256_STATUS=SUPERSEDED_METADATA
```
