# N3-W Clean Product First-Pair Setup-Secret Handoff and Runtime Identity — P2 T1/Broker-A/Manager Preboot Snapshot Closure — 2026-10-08

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_P2_R5_CONSOLIDATED_READONLY_BASELINE_AND_EXTERNAL_DISCOVERY
STATUS=CLOSED_PASS
P2_STATUS=CLOSED_PASS
P2_R5_PASS=true
P2_READONLY_BASELINE_PASS=true
MANAGER_DISCOVERY_AUTO_SOURCE_A=true
READY_FOR_P2_CLOSURE_REVIEW=true

BOARD_ACCESS=false
BOARD_WRITE=false
T1_CONFIGURATION_MUTATION=false
BROKER_RESTART=false
MANAGER_RESTART=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
AUTO_P3=false
MERGE=false
```

## 1. Entry authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_STATE=OPEN_DRAFT
PR_MERGED=false

P1_R2_CLEAN_BOARD_ELIGIBILITY=CLOSED_PASS
SILICON_BINDING_SHA256=f9c00d136f84d1fdabb1e296608702539ed674271021b28cff2d4a23e4cd2bf7
PRODUCT_HARDWARE_ID_SHA256=DEFERRED_UNTIL_RUNTIME_QR_MANAGER_BINDING

SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
ARTIFACT_ID=11469977052
BUILD_RUN_ID=37594598870
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
```

The candidate clean board remains untouched and in the preboot acceptance state.
P2 did not access or write the board.

## 2. R5 consolidated physical result

The final authorized R5 read-only execution used the operator-proven explicit
T1 root SSH target, bound the live Manager by exact container name and the live
Broker by unique Docker Compose labels, captured the Manager preboot identity
snapshot, and then issued one Mac-origin UDP discovery query.

```text
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
PREDECESSOR_AUTHORIZATION_REPLAY=false
SSH_RETURN_CODE=0
T1_ACCESSED=true

DOCKER_CLI_PRESENT=true
DOCKER_DAEMON_ACCESSIBLE=true

MANAGER_CONTAINER_NAME=greenhouse-manager
MANAGER_CONTAINER_RUNNING=true
MANAGER_CONTAINER_ID_SHA256=7b3c2a4de642e8a57da9d3f1652c9c35a27533c16f056736ecc89e289463bccc
MANAGER_STARTED_AT=2026-10-06T15:08:36.478286093Z
MANAGER_RESTART_COUNT=0
MANAGER_HOST_NETWORK=true
MANAGER_PORTS_EMPTY=true
MANAGER_IMAGE_ID_SHA256=49745bc3fed536b184fa6e2a7ca6d2e20b2adc1587cc07a8f12bc318d16342c9
MANAGER_IMAGE_REVISION_PRESENT=true
MANAGER_IMAGE_REVISION_SHA256=1e771152767f0c94f4d50c60edc65654b6e302f3deb27bb517ced76d5cf785b8

BROKER_CONTAINER_NAME=n3wfc4-broker-1
BROKER_CONTAINER_RUNNING=true
BROKER_RUNTIME_BINDING_UNIQUE=true
BROKER_CONTAINER_ID_SHA256=54a343cf903f5c73fd5b646c233e59cf0313b25d3f2caa55061fc64bc30741cd
BROKER_STARTED_AT=2026-10-06T05:01:47.110364692Z
BROKER_RESTART_COUNT=0
BROKER_IMAGE_REF=local/mosquitto:pr260-source-exact
BROKER_IMAGE_ID_SHA256=4106b5fc65db9a0da8945093166cd0debccf5e8aee9026e235c5200c45dd5f66
```

The live Broker is not literally named `mosquitto`; it is the unique container
selected by Docker Compose project `n3wfc4` and service `broker`. This closes
the earlier R3 executor error caused by a hard-coded Broker container name.

## 3. P2 network and TLS predicates

```text
PAIRING_ADVERTISED_HOST_MODE_AUTO=true
REAL_T1_ADDRESS_MATCH=true
T1_ADDRESS_SHA256=6257bd5c713a053e9efa4c9b036119a068dba2ddb8145e8288e89ad470822338
NODE_CREDENTIAL_BROKER_HOST_MATCH=true

UDP_47111_LISTENING=true
TCP_47112_LISTENING=true
TCP_8883_LISTENING=true

BROKER_TCP_TLS_A_8883=true
TLS_CA_SHA256=11ff133cdab8bf5f3093f6b488f8fa7e2579a1b5e383d066b1a1da56ad5dae9f
TLS_LEAF_CERT_SHA256=8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb
TLS_CA_AND_SERVER_NAME_SHA256=aae921c576258b264b60658bac022d5bcf81c3a3f641c50ba422df271f7a0947
```

The raw LAN address A remains private evidence.

## 4. Manager database mount and preboot identity snapshot

The read-only baseline resolved all three Manager database mounts and opened
SQLite using `mode=ro` plus `PRAGMA query_only=ON`.

```text
DB_MOUNT_RESOLUTION_PASS=true
REGISTRATION_DB_HOST_PATH_SHA256=b0626b173e3369d021096afe3addfe07359e75b82b11b6b28e9810e66749780f
CREDENTIAL_DB_HOST_PATH_SHA256=cf294d3764655d77ea3c53889c7ec4fd5a9f599e9c317d6e0318b8850fa0734c
REPLAY_DB_HOST_PATH_SHA256=c07543c0295d7f246f7f2fecd7ad82835cae6de501c3ca1bfa7059bcf5fb54f3

IDENTITY_SNAPSHOT_STABLE=true
MANAGER_PREBOOT_SNAPSHOT_CREATED=true
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SCHEMA=n3w.kf050.runtime-identity-snapshot/1
MANAGER_PREBOOT_IDENTITY_COUNT=5
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c
```

The raw hardware identity set remains private on the operator Mac. No raw
hardware ID, pairing ID, credential, setup secret, database path, or replay
state is published here.

## 5. External auto-discovery proof

Only after the T1 read-only baseline passed, the Mac issued one synthetic,
non-pairing UDP/47111 discovery query using a fresh UUID, nonce and synthetic
hardware identifier.

```text
EXTERNAL_DISCOVERY_ATTEMPTED=true
EXTERNAL_DISCOVERY_RESPONSE_SOURCE_MATCH=true
EXTERNAL_DISCOVERY_CANDIDATE_HOST_MATCH=true
EXTERNAL_DISCOVERY_PASS=true
MANAGER_DISCOVERY_AUTO_SOURCE_A=true
```

This freshly proves that the current running Manager in `auto` mode returns
the current route-selected T1 address A to the external requester.

## 6. P2 closure review

All Stage P2 predicates required by the physical-acceptance preexecution are
now freshly satisfied:

```text
PAIRING_ADVERTISED_HOST_MODE=auto
REAL_T1_ADDRESS=A
NODE_CREDENTIAL_BROKER_HOST=A
BROKER_TCP_TLS_A_8883=PASS
MANAGER_DISCOVERY_AUTO_SOURCE=A

MANAGER_CONTAINER_ID_FROZEN=true
MANAGER_STARTED_AT_FROZEN=true
MANAGER_RESTART_COUNT_FROZEN=true
BROKER_CONTAINER_ID_FROZEN=true
BROKER_STARTED_AT_FROZEN=true
BROKER_RESTART_COUNT_FROZEN=true
TLS_CA_AND_SERVER_NAME_HASH_FROZEN=true
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_FROZEN=true
```

Decision:

```text
P2_STATUS=CLOSED_PASS
READY_FOR_P3=true
P3_AUTHORIZATION_GRANTED=false
P3_BOARD_WRITE_AUTHORIZED=false
P3_AUTO_EXECUTE=false
STOP=true
```

Stage P3 remains a separate physical mutation gate. It must use only the
replacement exact artifact already bound in the preexecution authority and
must preserve `AFTER_WRITE=no-reset` so that normal product boot does not
begin before flash readback verification.
