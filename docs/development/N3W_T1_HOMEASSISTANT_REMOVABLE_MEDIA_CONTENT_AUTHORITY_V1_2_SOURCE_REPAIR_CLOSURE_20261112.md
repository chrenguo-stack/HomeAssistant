# N3-W T1 Home Assistant removable-media content-authority V1.2 source repair closure

Date: 2026-11-12

GATE=REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_REPAIR
STATUS=CLOSED_PASS
SOURCE_REPAIR_AUTHORITY_HEAD=2639538a9c00a3ac1d9655681a49bef1d821ba1c
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED

## Closure evidence

The V1.2 source repair is complete and independently reviewed.

Implemented authority changes:

- physical /dev node, filesystem UUID and public fingerprint are no longer cross-session transaction authority;
- exact target identity is required at U5+;
- exact predecessor identity is required at U7+;
- exact protected HA backup identity and media-independent recovery-content manifest are required at U8+;
- post-U9 recovery classification is exact-content based;
- rollback recomputes the expected recovery-content authority from freshly validated target/predecessor/backup records;
- anonymous USB without serial/WWN is supported;
- newly-inserted-only media selection is retired;
- compatible N3W-UPDATE ext4 media may be reused;
- bounded U4->U3 target reprepare is permitted before authorization/destructive stages;
- old active schema /1 U4 remains readable without a migration executor;
- historical R7A/R11/R12 execution authorities were not rebound to the new source.

## CI

N3W_T1_CORE_UPDATER_MANAGER_A_TO_B_CI=SUCCESS
RUN_MANAGER_A_TO_B=43244108994

N3W_T1_CORE_STACK_CURRENT_AUTHORITY_CI=SUCCESS
RUN_CORE_STACK_AUTHORITY=43244109259

N3W_CI_FAST_SOURCE_EXACT_CLOSURE=SUCCESS
RUN_FAST_SOURCE=43244109264

PUBLIC_REPOSITORY_SAFETY_CI=SUCCESS
RUN_PUBLIC_SAFETY=43244109060

N3W_T1_STORAGE_HEADROOM_IMAGE_LIFECYCLE_CI=SUCCESS
RUN_STORAGE=43244109187

GREENHOUSE_MANAGER_CI=SUCCESS
RUN_GREENHOUSE_MANAGER=43244109314

N3W_T1_CORE_UPDATER_HOMEASSISTANT_TARGET_BINDING_CI=SUCCESS
RUN_TARGET_BINDING=43244109304

SOURCE_REVIEW=PASS
NEW_DESIGN_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false

## Live boundary

T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
TRANSACTION_MUTATION=false
U5_TRANSITION=false
U6_PLUS=false
BOARD_ACCESS=false
MERGE=false

R12_LIVE_MOUNT_RESTORATION=SUPERSEDED_NOT_EXECUTED
AUTO_RETRY_R11=false

## Next gate

NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_READONLY_PREEXECUTION_20261112_01
NEXT_GATE_MODE=REAL_T1_READONLY_PREFLIGHT
LIVE_T1_MUTATION=false
USB_MUTATION=false
BOARD_ACCESS=false
MERGE=false

The next gate may read the real T1 only. It must stop before any V1.2 source deployment or U4->U5 transition.
