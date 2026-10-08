# N3-W Clean Product First-Pair — P4 Preboot Runtime Continuity Read-Only Physical Closure — 2026-10-08

```text
GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_20261008_01
STATUS=CLOSED_PASS
P4_PREBOOT_PASS=true
MANAGER_BROKER_PREBOOT_CONTINUITY_PASS=true
EVIDENCE_PROVENANCE=OPERATOR_SUPPLIED_EXACT_EXECUTOR_JSON
PR=522
PR_EXPECTED_STATE=OPEN_DRAFT_UNMERGED
STOP=true
```

## 1. Entry authority

This gate follows the exact P3 four-region write and independent readback closure, and the frozen P2 host/Manager identity baseline. The supplied terminal output constitutes the physical-host read-only execution evidence; the public closure does not contain raw T1 host address, private identity values, private TLS keys, database contents, setup secrets, or serial paths.

```text
P3_PHYSICAL_CLOSURE=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_P3_WRITE_ONLY_OFFLINE_ARTIFACT_R2_CLOSURE_20261008.md
P3_RESULT=CLOSED_PASS
P3_WRITE_ONLY_AUTHORIZATION_CONSUMED=true
P3_REPLAY=false
CURRENT_BOARD_STATE=FOUR_REGIONS_WRITTEN_AND_EXACT_READBACK_PASS_NO_PRODUCT_BOOT
CURRENT_CLEAN_CANDIDATE_SILICON_BINDING_SHA256=4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc

HOST_READONLY_EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p4_preboot_runtime_continuity_readonly/executor.py
HOST_READONLY_EXECUTOR_BLOB_SHA=0a588be746baa78c22e7dfa54167ad966de1e3f9
HOST_READONLY_STAGE=P4_PREBOOT_RUNTIME_CONTINUITY_READONLY
```

## 2. Actual read-only execution result

```text
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
PREDECESSOR_AUTHORIZATION_REPLAY=false

T1_ACCESSED=true
SSH_RETURN_CODE=0
SSH_STDERR_SHA256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

DOCKER_CLI_PRESENT=true
DOCKER_DAEMON_ACCESSIBLE=true
MANAGER_CONTAINER_RUNNING=true
BROKER_CONTAINER_RUNNING=true
BROKER_RUNTIME_BINDING_UNIQUE=true
MANAGER_HOST_NETWORK=true
MANAGER_PORTS_EMPTY=true

PAIRING_ADVERTISED_HOST_MODE_AUTO=true
REAL_T1_ADDRESS_MATCH=true
NODE_CREDENTIAL_BROKER_HOST_MATCH=true
T1_ADDRESS_SHA256=6257bd5c713a053e9efa4c9b036119a068dba2ddb8145e8288e89ad470822338

BROKER_TCP_TLS_A_8883=true
UDP_47111_LISTENING=true
TCP_47112_LISTENING=true
TCP_8883_LISTENING=true

DB_MOUNT_RESOLUTION_PASS=true
IDENTITY_SNAPSHOT_STABLE=true
MANAGER_PREBOOT_SNAPSHOT_CREATED=true

EXTERNAL_DISCOVERY_ATTEMPTED=true
EXTERNAL_DISCOVERY_RESPONSE_SOURCE_MATCH=true
EXTERNAL_DISCOVERY_CANDIDATE_HOST_MATCH=true
EXTERNAL_DISCOVERY_PASS=true
MANAGER_DISCOVERY_AUTO_SOURCE_A=true

P4_PREBOOT_READONLY_BASELINE_PASS=true
MANAGER_BROKER_PREBOOT_CONTINUITY_PASS=true
P4_PREBOOT_PASS=true
READY_FOR_P4_AUTHORIZATION=true
```

The live T1/Broker/Manager probe found all required listeners and trustworthy TLS and auto-discovery behavior. It required and passed exact match against the P2 runtime/identity authority, not merely broad health.

## 3. Exact continuity to frozen P2

```text
MANAGER_CONTAINER_NAME=greenhouse-manager
MANAGER_CONTAINER_RUNNING=true
MANAGER_CONTAINER_CONTINUITY_FROM_PRIOR_P2=true
MANAGER_CONTAINER_ID_SHA256=7b3c2a4de642e8a57da9d3f1652c9c35a27533c16f056736ecc89e289463bccc
MANAGER_STARTED_AT=2026-10-06T15:08:36.478286093Z
MANAGER_RESTART_COUNT=0
MANAGER_IMAGE_ID_SHA256=49745bc3fed536b184fa6e2a7ca6d2e20b2adc1587cc07a8f12bc318d16342c9
MANAGER_IMAGE_REVISION_PRESENT=true
MANAGER_IMAGE_REVISION_SHA256=1e771152767f0c94f4d50c60edc65654b6e302f3deb27bb517ced76d5cf785b8

BROKER_CONTAINER_NAME=n3wfc4-broker-1
BROKER_CONTAINER_RUNNING=true
BROKER_CONTAINER_CONTINUITY_FROM_PRIOR_P2=true
BROKER_CONTAINER_ID_SHA256=54a343cf903f5c73fd5b646c233e59cf0313b25d3f2caa55061fc64bc30741cd
BROKER_STARTED_AT=2026-10-06T05:01:47.110364692Z
BROKER_RESTART_COUNT=0
BROKER_IMAGE_ID_SHA256=4106b5fc65db9a0da8945093166cd0debccf5e8aee9026e235c5200c45dd5f66

TLS_CA_SHA256=11ff133cdab8bf5f3093f6b488f8fa7e2579a1b5e383d066b1a1da56ad5dae9f
TLS_LEAF_CERT_SHA256=8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb
TLS_CA_AND_SERVER_NAME_SHA256=aae921c576258b264b60658bac022d5bcf81c3a3f641c50ba422df271f7a0947

REGISTRATION_DB_HOST_PATH_SHA256=b0626b173e3369d021096afe3addfe07359e75b82b11b6b28e9810e66749780f
CREDENTIAL_DB_HOST_PATH_SHA256=cf294d3764655d77ea3c53889c7ec4fd5a9f599e9c317d6e0318b8850fa0734c
REPLAY_DB_HOST_PATH_SHA256=c07543c0295d7f246f7f2fecd7ad82835cae6de501c3ca1bfa7059bcf5fb54f3

MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SCHEMA=n3w.kf050.runtime-identity-snapshot/1
MANAGER_PREBOOT_IDENTITY_COUNT=5
MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256=81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c
PREBOOT_IDENTITY_SNAPSHOT_CONTINUITY_FROM_PRIOR_P2=true
```

This snapshot is the *pre-product-boot* historical Manager identity union, not an assertion that the silicon binding is the runtime product hardware identity. The baseline of five identities is intact, and comparison to a unique new pending identity remains a separate P4-C acceptance requirement. The operator's private snapshot is retained outside GitHub.

## 4. No mutation, authorization, and current STOP

```text
BOARD_ACCESS=false
BOARD_WRITE=false
PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED_BY_THIS_GATE=false
P4_FIRST_NORMAL_BOOT_EXECUTED=false

T1_CONFIGURATION_MUTATION=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MANAGER_RESTART=false
BROKER_RESTART=false

P4_PREBOOT_READONLY_AUTHORIZATION_CLAIMED=true
P4_PREBOOT_READONLY_AUTHORIZATION_CONSUMED=true
P4_PREBOOT_READONLY_REPLAY=false

P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_AUTHORIZATION_GRANTED=false
P4_AUTHORIZATION_CLAIMED=false
P4_AUTHORIZATION_CONSUMED=false
AUTO_RETRY=false
AUTO_P4=false
STOP=true
```

No P4 product boot, production Wi-Fi provisioning, real LCD QR display, Setup Secret handoff, Manager COMMIT, KF-050 controlled interruption, or postboot telemetry has been performed or proven by this gate.

## 5. Next gate and stage constraints

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_FIRST_NORMAL_BOOT_PHYSICAL_PREEXECUTION_20261008_01
NEXT_GATE_SCOPE=DESIGN_AND_OPERATOR_AUTHORIZATION_REQUIRED
P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
P4_FIRST_NORMAL_BOOT_STARTED=false
STOP=true
```

Before authorizing product boot, bind the exact P3 written board + intact P2 identity snapshot, and prepare bounded P4-A normal product boot and Wi-Fi commissioning followed by P4-B Manager hello / physical LCD pairing QR. STOP after QR visibility before any private optical payload intake, and again before Setup Secret import. Preserve the short pending TTL: stage identity verification and secret-handoff authorization/executor must be ready **before** pending is created, or the P4 plan must stop earlier. Later pairing import, Manager COMMIT, the precise after-COMMIT-before-first-canonical power interruption, reboot and telemetry recovery require dedicated separate gate boundaries and actual evidence.

The original design authority remains:
`docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261007.md`, Stage P4-A through P4-F.

No erases, flash writes, board resets, manual USB reconnects, T1 service restarts, high-water clearing or automatic transition to P4 are authorized by this closure.
