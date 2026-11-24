# N3-W T1 Core Stack OTA V1.3 — R8V13-07 new fresh transaction A PREPARE-to-U4 pre-execution

Date: 2026-11-24

## 0. Coordinate

```text
ACTIVE_STAGE=N3W_T1_CORE_STACK_OTA_V1_3_R8_PHYSICAL_ACCEPTANCE
CURRENT_TASK=R8V13-07
NEXT_TASK=R8V13-08
R8V13_08_BLOCKED=true
TASK_CHAIN_MUTATION=false
```

This is not a new stage node and does not reopen the old terminal transaction. The first transaction A failed safely and is terminal/no-replay; R8V13-07 therefore needs a new fresh transaction A before INSTALL/cutover can be re-attempted.

## 1. Real-T1 entry evidence

KF-154 V2 rebind closed PASS:

```text
OLD_TRANSACTION_ID=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
OLD_TRANSACTION_TERMINAL_NO_REPLAY=PASS
RUNTIME_IDENTITIES=PASS
CURRENT_PREDECESSOR_BINDING=PASS
MANAGER_BROKER_HA_SELF_TEST=PASS
MANAGER_BROKER_HA_SELF_TEST_SHA256=a01012f6c91d023cdf580d4bc9216d698f15c1e5f30ae0fe75ad6dd5d199b9e6
HA_PREPARE_AUTHORITY_STATE=ACTIVE_OLD_TERMINAL_SAFE_REPLACEABLE
HA_INSTALL_AUTHORITY_STATE=ACTIVE_OLD_TERMINAL_SAFE_REPLACEABLE
HA_RELEASE_AUTHORITY_STATE=ACTIVE_VALID_FOR_FRESH_PREPARE
USB_FILESYSTEM_UUID=b72ac2fc-79a0-4fb8-888e-f35b0114f959
BOUND_USB_MOUNT_0_AVAILABLE_BYTES=13441150976
ROOT_AVAILABLE_BYTES=4686303232
TARGET_10_0_PRESENT=false
LIVE_RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
PERSISTENT_CONFIGURATION_MUTATION=false
OLD_TRANSACTION_REPLAY=false
```

## 2. Capacity classification

Exact target archive:

```text
TARGET_ARCHIVE_SIZE_BYTES=2448553472
TARGET_ARCHIVE_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
USB_AVAILABLE_BYTES_AT_REBIND=13441150976
ROOT_AVAILABLE_BYTES_AT_REBIND=4686303232
```

No static whole-transaction reserve is used. The current snapshot shows no entry capacity blocker for the exact candidate spool or target write, but it is not a promise that every later operation will fit. V1.3 remains authoritative: target, predecessor export and protected-data backup each remeasure current free bytes immediately before their own write.

The new executor adds only an exact pre-write root check for the imminent 2,448,553,472-byte internal candidate spool; it does not create a generic reserve.

## 3. Fresh transaction A contract

```text
OLD_TRANSACTION_REPLAY=false
OLD_TRANSACTION_ID_REUSE=false
NEW_TRANSACTION_ID_REQUIRED=true

SEQUENCE=
PREMUTATION_REBIND
-> VERIFY_OLD_USB_TARGET_SOURCE
-> EXACT_INTERNAL_CANDIDATE_CAPACITY_CHECK
-> MATERIALIZE_FRESH_CANDIDATE
-> MAINTENANCE_PREPARE
-> NEW_FRESH_U1
-> ISSUE_NEW_PREPARE_AUTHORITY
-> RESUME_PREPARE
-> NEW_FRESH_U4_READY_TO_INSTALL
-> STOP_BEFORE_NEW_INSTALL_AUTHORIZATION
```

The source archive is the exact old-terminal transaction USB `target.tar`, used only as a read-only byte source. Product `materialize-candidate` re-hashes and parses the entire archive into the updater-owned internal spool. The old transaction journal and old prepare/install authorities are never replayed as the new transaction.

Expected success:

```text
NEW_FRESH_TRANSACTION_A_PREPARE_RESULT=PASS
NEW_FRESH_TRANSACTION_ID!=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
TRANSACTION_STATUS=ACTIVE
TRANSACTION_PHASE=U4_READY_TO_INSTALL
CURRENT_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
TARGET_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_ARTIFACT_VERIFIED=true
PREPARED_TARGET_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
TARGET_10_0_DOCKER_IMAGE_LOADED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
INSTALL_INTENT=false
HA_INSTALL_OR_CUTOVER=false
```

## 4. Exact executor

```text
EXECUTOR=tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_TO_U4_20261124_01.sh
EXECUTOR_IMPLEMENTATION_HEAD=fe10f4c48269e8e90809cbdefd078066cbce98bd
TEST_HEAD=87ca44ce23206d8fbcce197c9146969ddaff6926
CI_WIRING_HEAD=ebeeb5b9bfc14e251715473afd1b3c31de16cf36
EXECUTOR_SHA256=PENDING_FOCUSED_CI
FOCUSED_CI=PENDING
```

## 5. Authorization boundary

```text
GATE=N3W_T1_R8V13_07_NEW_FRESH_TRANSACTION_A_PREPARE_TO_U4_20261124_01
AUTHORIZATION_STATUS=PENDING_EXPLICIT_USER_APPROVAL

PERMITTED_AFTER_APPROVAL=
- exact candidate materialization from the bound old-terminal USB target bytes
- create one new fresh HA PREPARE transaction
- issue one fresh prepare authority for that new transaction
- advance that transaction through existing product PREPARE to U4

NOT_PERMITTED=
- reuse old transaction ID
- submit INSTALL intent
- issue install authority
- load/start target 10.0
- stop HA/Manager for cutover
- U5+
- Broker OTA
- reboot
- merge
- release
```

Focused CI must pass and the exact executor SHA256 must be bound before this gate can be presented for approval.
