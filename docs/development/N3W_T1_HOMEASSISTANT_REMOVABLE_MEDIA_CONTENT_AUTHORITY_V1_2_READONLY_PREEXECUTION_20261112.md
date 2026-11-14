# N3-W T1 Home Assistant removable-media content-authority V1.2 real-T1 read-only preexecution

Date: 2026-11-12

TASK=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_READONLY_PREEXECUTION_20261112_01
STATE=PREEXECUTION_SOURCE_READY
SOURCE_REPAIR_AUTHORITY_HEAD=2639538a9c00a3ac1d9655681a49bef1d821ba1c

READ_ONLY_PREFLIGHT=true
LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false

## Purpose

Perform the first fresh real-T1 validation after V1.2 source repair without deploying that source.

The preflight proves:

1. the live transaction is still the exact legacy schema /1 U4 transaction;
2. authorization remains unclaimed/unconsumed;
3. the three R10-installed runtime sources remain exact and all V1.2 replacement-file predecessor hashes are collected read-only;
4. OTA service and Manager/Home Assistant/Broker runtime remain healthy;
5. IPC still reports READY_TO_INSTALL;
6. fresh block inventory finds exactly one safe compatible N3W-UPDATE ext4 removable USB;
7. root/internal or production-mounted media cannot be selected;
8. serial/WWN is not required;
9. old transaction UUID/fingerprint are never compared against the currently observed device;
10. no mount, unmount, filesystem write, source deployment, restart, transaction edit, U5/U6+, board access or merge occurs.

## Stop boundary

STOP_BOUNDARY=STOP_AFTER_V1_2_REAL_T1_READONLY_PREEXECUTION_BEFORE_SOURCE_ACTIVATION_DESIGN

A PASS does not authorize source activation. Its evidence is used to bind the exact predecessor source hashes and real-T1 prestate for a later, separate V1.2 source-activation design.

## Expected live continuity

TRANSACTION_PHASE=U4_READY_TO_INSTALL
TRANSACTION_SHA256=dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259
TRANSACTION_ID_SHA256=ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738
TARGET_ARTIFACT_IDENTITY_EXPECTED_ON_LEGACY_U4=null
PREDECESSOR_RECOVERY_IDENTITY_EXPECTED_ON_LEGACY_U4=null
HA_DATA_BACKUP_IDENTITY_EXPECTED_ON_LEGACY_U4=null
RECOVERY_CONTENT_MANIFEST_EXPECTED_ON_LEGACY_U4=null

PHYSICAL_USB_IDENTITY_CONTINUITY_REQUIRED=false
USB_UUID_COMPARISON_FOR_CONTINUITY=false
USB_FINGERPRINT_COMPARISON_FOR_CONTINUITY=false

## Mutation boundary

REMOTE_STAGING=false
SOURCE_DEPLOYMENT=false
SERVICE_RESTART=false
MOUNT=false
UMOUNT=false
USB_MUTATION=false
USB_FILESYSTEM_WRITE=false
TRANSACTION_MUTATION=false
HOMEASSISTANT_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
U5_TRANSITION=false
U6_PLUS=false
BOARD_ACCESS=false
MERGE=false
