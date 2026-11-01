# N3-W KF-096 PR #437 Post-Write Direct Baseline Alignment — 2026-09-19

Status: `CURRENT_PROGRESS_ALIGNMENT`

Fresh exact repository/runtime/physical evidence takes precedence if later evidence proves drift.

## Scope

This record aligns the local conversation after the exact PR #437 artifact was written to the operator-confirmed Board B target and a fresh post-write Direct baseline passed through Manager canonical durable state.

No PR #437 source change, PR #437 merge, Board A mutation, T1 runtime mutation, Broker/Manager/DynSec/credential mutation, or application-serial observation is part of this alignment.

## Repository authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
REPOSITORY_MAIN_AT_ALIGNMENT_START=
0ea13c9f9f76fdf7fb79ec82393408ab144b4e18

REPOSITORY_MAIN_TREE_AT_ALIGNMENT_START=
c2bd54b4eccb16170ad34929e170cf67bd5e624d

MERGED_PRODUCT_SOURCE_AUTHORITY=
d1b5c3acbd32cca95483743ffe2edba9aa3f904f

CURRENT_CANDIDATE_PR=437
CURRENT_CANDIDATE_STATE=OPEN_DRAFT
CURRENT_CANDIDATE_SOURCE_HEAD=
cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
CURRENT_CANDIDATE_SOURCE_TREE=
b459fae0a054d45b0d09e60bffae9769e060a5c0
```

PR #437 remains unmerged. Documentation-only main advancement does not redefine the exact candidate artifact or deployed firmware authority.

## Exact artifact authority

```text
ARTIFACT_RUN_ID=35414060819
ARTIFACT_ID=10575077512
ARTIFACT_NAME=n3w-pr437-boardb-exact-source
ARTIFACT_EXPIRED=false

ARTIFACT_ZIP_SIZE=727532
ARTIFACT_ZIP_SHA256=
b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814

APPLICATION_SIZE=1139600
APPLICATION_SHA256=
407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb

OTADATA_SIZE=8192
OTADATA_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

MANIFEST_SHA256=
98a6dec323e8057a30d6b1e332d549fe54288f3b45fcbbbf460292871f7a91a0
```

## Board B write closure

The first bounded preflight stopped before any write because the current target did not match the repository-frozen Board B hardware-identity hash.

The operator then explicitly confirmed the connected physical target as Board B and authorized a one-time direct write. That operator confirmation overrode the automated identity comparison for this write only.

```text
AUTOMATED_BOARD_IDENTITY_MATCH=FAIL
OPERATOR_TARGET_CONFIRMATION=PASS
OPERATOR_IDENTITY_OVERRIDE=true
RAW_BOARD_IDENTITY_PUBLIC=false
IDENTITY_OVERRIDE_REUSABLE=false

ARTIFACT_DOWNLOAD=PASS
ARTIFACT_INNER_BINDING=PASS
SECURITY_STATE=PASS
FLASH_SIZE=8MB
PARTITION_TABLE_BINDING=PASS

APPLICATION_WRITE=PASS
OTADATA_WRITE=PASS
APPLICATION_READBACK_HASH_VERIFY=NOT_EXECUTED
OTADATA_READBACK_HASH_VERIFY=NOT_EXECUTED

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false

WRITE_AUTHORIZATION_CLAIMED=true
WRITE_AUTHORIZATION_CONSUMED=true
WRITE_AUTHORIZATION_REPLAY_PERMITTED=false

PR437_BOARD_B_DEPLOYMENT=PASS
```

The automated identity failure remains an audit fact. It must not be rewritten as a PASS and must not create a reusable exception for future board mutation.

## Post-write Direct baseline

A first Manager-log-only observer returned zero matching Direct acceptance INFO lines. Because the repository already guards against that logging false negative under KF-010, the route did not classify the product as failed.

A second read-only observer used Manager canonical durable state over a fresh 90-second window:

```text
T1_MANAGER_RUNNING=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_STARTED_AT_UNCHANGED=true
MANAGER_RESTART_COUNT_UNCHANGED=true

OBSERVATION_SECONDS=90

BOARD_B_CANONICAL_CURSOR_BEFORE=FOUND
BOARD_B_CANONICAL_CURSOR_AFTER=FOUND
BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SOURCE_AFTER=direct

BOARD_B_SEQ_BEFORE=1370
BOARD_B_SEQ_AFTER=1388
BOARD_B_SEQ_DELTA=18

BOARD_B_SAME_BOOT=true
BOARD_B_CANONICAL_ADVANCED=true
BOARD_B_LAST_SOURCE_DIRECT=true
BOARD_B_CANONICAL_DIRECT_BASELINE=PASS

PR437_POSTWRITE_DIRECT_BASELINE=PASS
MANAGER_INFO_LOG_ORACLE=FALSE_NEGATIVE
PRODUCT_DIRECT_PATH_FAILURE=false
```

The 18-step sequence advance over 90 seconds is consistent with the established approximately 5-second telemetry cadence.

## Current physical boundary

```text
BOARD_B_DEPLOYED_SOURCE_HEAD=
cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
BOARD_B_DEPLOYED_SOURCE_TREE=
b459fae0a054d45b0d09e60bffae9769e060a5c0

PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS
PR437_PHYSICAL_VALIDATION=IN_PROGRESS

BOARD_A_MUTATION=false
T1_RUNTIME_MUTATION=false
APPLICATION_SERIAL_OPEN=false
PR437_MERGE=false

KF096_STATUS=OPEN
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

The last proven runtime state is Board B Direct through Manager canonical state. Board B power source/location and Board A power/location must be freshly rechecked when the next chat starts.

## Current route

```text
NEXT_ONE_GATE=
N3W_KF096_PR437_SAME_BOOT_DIRECT_TO_RELAY_PHYSICAL_VALIDATION_20260919_01
```

The next gate first establishes a fresh Direct baseline on PR #437, confirms Board A as the stationary Relay gateway, then moves only Board B to the qualified Relay location without a reboot after the baseline.

Manager canonical durable state is the authoritative observation path. Application serial remains forbidden as a passive oracle. The gate stops after same-boot Direct -> Relay classification and does not automatically continue into Relay steady-state continuity or Relay -> Direct failback.
