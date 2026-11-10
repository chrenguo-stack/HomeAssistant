# N3-W T1 KF-147 Manager IPC V3 R2 portable-identity preauthorization closure — 2026-11-10

## 0. Closure

```text
TASK=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_R2_PREAUTHORIZATION
RESULT=CLOSED_PASS
PR=800
SOURCE_HEAD=b8cfcdf88b38a82634845c5ab79ad098c4723a3d
LIVE_AUTHORIZATION=NOT_GRANTED
LIVE_MUTATION_DURING_THIS_CLOSURE=false
BOARD_ACCESS=false
MERGE=false
```

This closure records the source repair, CI closure and fresh read-only T1 evidence after the first live authorization was consumed by a pre-service-mutation image-identity false blocker.

## 1. Predecessor authorization

```text
AUTHORIZATION=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_20261110_01
GRANTED=true
CLAIMED=true
CONSUMED=true
REPLAY_PERMITTED=false
RESULT=STOP_PRE_SERVICE_MUTATION_LOADED_TARGET_IDENTITY_INVALID
ROLLBACK=NOT_REQUIRED
```

The predecessor authorization is historical evidence only and must never be replayed.

## 2. Proven failed-attempt boundary

The consumed attempt successfully staged and loaded the exact Manager image tar, then stopped at the build-store-specific target image ID check.

```text
MANAGER_TAR_SHA256=9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5
LIVE_APPLY_INVOKED=true
SERVICE_OWNER_STOP_REACHED=false
COMPOSE_ENV_REWRITE_REACHED=false
MANAGER_CONTAINER_RECREATE_REACHED=false
ROLLBACK_REQUIRED=false
USB_MUTATION=false
U2_PLUS=false
```

Therefore the running Manager was not switched by the failed attempt.

## 3. Root cause

```text
ROOT_CAUSE_CLASS=KF-106_CROSS_STORE_IMAGE_IDENTITY_RECURRENCE
BUILD_CONFIG_DIGEST=sha256:fd5104d610645347fe47137dbb24121851fa8a48530df3e3c905704607c5e3d4
OCI_MANIFEST_DIGEST=sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2
OCI_INDEX_DIGEST=sha256:82eac15f6a07bb6e60b6317b094321f942674f18f5049ff3a5f7439a5c4b43e0
T1_DOCKER_DRIVER_TYPE=io.containerd.snapshotter.v1
T1_TARGET_RUNTIME_IMAGE_ID=sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2
```

The old KF-147 remote executor incorrectly required Docker runtime image `.Id` to equal the build-side config digest. The repository already defines the portable cross-store authority in `tools/n3w_t1_portable_image_identity.py`.

## 4. R2 source repair

R2 uses a successor gate rather than reopening the consumed predecessor gate.

```text
R2_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_R2_20261110_01
R2_CONFIRMATION=EXECUTE KF147 MANAGER IPC V3 IMAGE ONLY LIVE APPLY R2: YES
R2_LIVE_EXECUTION_AUTHORIZED=false
R2_AUTHORIZATION_GRANTED=false
R2_AUTHORIZATION_CLAIMED=false
R2_AUTHORIZATION_CONSUMED=false
R2_REPLAY_PERMITTED=false
```

Repair commits:

```text
EXECUTOR_PORTABLE_BINDING=8b1a5e2097dd2de647c6cea406049927de6e176a
REMOTE_PORTABLE_VERIFICATION=617e89b57b3282c29b70940b863cad81e58c00f9
R2_UNAUTHORIZED_MANIFEST=66ddde97cda136c454883d7e9f9b6e3d479baac8
REGRESSION_TESTS_AND_VALIDATED_HEAD=b8cfcdf88b38a82634845c5ab79ad098c4723a3d
```

R2 rules:
- exact Manager tar SHA/size/tag remain mandatory;
- build-side config digest remains provenance, not a universal runtime ID oracle;
- any preexisting target tag must verify portable-identical before live authorization claim;
- post-load target verification uses platform + normalized config semantics + RootFS diff IDs;
- T1-local runtime image ID is captured and used for post-container binding;
- same-host predecessor identity checks remain exact;
- HA/Broker/U1/USB continuity checks are unchanged;
- old T1 execution state is preserved and not deleted.

## 5. Fresh read-only T1 evidence

Fresh read-only verification after the failed attempt proved:

```text
PORTABLE_VERDICT=VERIFIED
PORTABLE_REASON=portable_identity_match
TARGET_RUNTIME_OS=linux
TARGET_RUNTIME_ARCH=arm64

RUNNING_MANAGER_IMAGE_REF=local/greenhouse-manager:fresh-7807271e4c48
RUNNING_MANAGER_IMAGE_ID=sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b
RUNNING_MANAGER_RUNNING=true
RUNNING_MANAGER_RESTART_COUNT=0
RUNNING_MANAGER_IS_PREDECESSOR=true
COMPOSE_MANAGER_IMAGE=local/greenhouse-manager:fresh-7807271e4c48

N3WFC4_SERVICES_ACTIVATION=active
N3W_T1_HA_OTA=active
OLD_STATE_ROOT_EXISTS=true
OLD_AUTHORIZATION_CLAIMED=true
OLD_AUTHORIZATION_CONSUMED=true
OLD_REPLAY_PERMITTED=false
```

This proves the loaded target image is exact under the repository portable identity contract while the production Manager remains on the predecessor.

## 6. CI closure

Exact head `b8cfcdf88b38a82634845c5ab79ad098c4723a3d`:

```text
KF147_MANAGER_PACKAGE_CI=SUCCESS run=42776734168
CORE_STACK_CURRENT_AUTHORITY_CI=SUCCESS run=42776734260
FAST_SOURCE_EXACT_CLOSURE_CI=SUCCESS run=42776734238
MANAGER_A_TO_B_CI=SUCCESS run=42776734179
STORAGE_IMAGE_LIFECYCLE_CI=SUCCESS run=42776734242
PUBLIC_REPOSITORY_SAFETY_CI=SUCCESS run=42776734056
REQUIRED_CI=PASS
```

## 7. Authorization boundary

```text
PREAUTHORIZATION_RESULT=CLOSED_PASS
NEW_LIVE_AUTHORIZATION_REQUIRED=true
NEW_LIVE_AUTHORIZATION_GRANTED=false
AUTO_RETRY=false
OLD_AUTHORIZATION_REPLAY=false
```

The next live operation is the R2 Manager-only apply. It requires a new explicit user authorization. No source, CI or read-only evidence in this closure grants that live mutation authority.

## 8. Next gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_R2_20261110_01
STOP_BEFORE=NEW_R2_LIVE_AUTHORIZATION
```
