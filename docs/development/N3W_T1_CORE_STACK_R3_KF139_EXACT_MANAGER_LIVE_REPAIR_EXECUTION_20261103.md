# N3-W R3 KF-139 exact Manager live repair execution binding — 2026-11-03

TASK=N3W_T1_CORE_STACK_R3_KF139_EXACT_MANAGER_LIVE_REPAIR_AND_VALIDATION_20261103_01

SOURCE_REPAIR_PR=769
SOURCE_REPAIR_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
SOURCE_REPAIR_STATUS=CI_PASS_LIVE_VALIDATION_PENDING

LIVE_PREDECESSOR_MANAGER=local/greenhouse-manager:fresh-3539c8f871e2
TARGET_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
TARGET_MANAGER_BUILD_IMAGE_ID=sha256:9ff3b651ba0fc5879de76a91875356c522cc5809ea9f242fa11ec2fa192e4036
TARGET_MANAGER_TAR_SHA256=ea158fbefe81084989941b951e0f5c8c65f630748c72bef3f8d03a1c453c328f

UPSTREAM_EXACT_RUN_ID=41583719655
UPSTREAM_EXACT_ARTIFACT_ID=13206763644
UPSTREAM_EXACT_ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-b863ddd959090ca139af76bd68dbef31d773e6de
UPSTREAM_EXACT_ARTIFACT_DIGEST_SHA256=eddeff81b3e670b66765558bb7e9795ae846caba6f487cfd6d727d5c0795403a

TARGET_MANIFEST=infra/n3w-t1/upgrades/manager-b863ddd95909.json

LIVE_PREFLIGHT=PASS
FAILED_ATTEMPT_STATE=EXPIRED_TERMINAL_COMPLETE
UNRESOLVED_FIRST_REGISTRATION_COUNT=0
BUSINESS_STATE_RESIDUE=0
PAIRING_WINDOW_STATE=CLOSED
LISTENER_47112=CLOSED
LIVE_CREDENTIAL_LIFECYCLE_DB_MODE=0644

## Execution contract

1. Build a Manager-only updater package from the exact upstream Manager artifact.
2. Keep Broker image/runtime unchanged.
3. Keep Home Assistant image unchanged.
4. Stop/start Manager and Home Assistant only through the production systemd owner.
5. Rewrite only the unique GH_MANAGER_IMAGE binding.
6. Preserve automatic rollback to the current Manager B on failure.
7. Do not merge PR #769 before real-T1 validation.
8. Do not retry first registration until the repaired Manager is live and the credential lifecycle DB is proven mode 0600.

## Existing 0644 state

The existing credential lifecycle DB contains zero credential assignments and is the proven live KF-139 defect.
The live repair must preserve forensic evidence before replacement and must not delete or rewrite the separate
manager-state.sqlite3 terminal replay tombstones.

T1_MUTATION=false
BOARD_ACCESS=false
SECOND_REGISTRATION_RETRY=false
MERGE=false
