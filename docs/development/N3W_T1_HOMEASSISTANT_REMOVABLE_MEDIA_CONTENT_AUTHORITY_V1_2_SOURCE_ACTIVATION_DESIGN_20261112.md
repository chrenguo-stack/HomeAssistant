# N3-W T1 Home Assistant removable-media content-authority V1.2 source activation design

Date: 2026-11-12

GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_ACTIVATION_20261112_01
STATUS=SOURCE_ACTIVATION_PACKAGE_PREPARED_UNGRANTED

## Objective

Activate the V1.2 repaired HA USB updater source on the real T1 while preserving the current U4 transaction byte-for-byte and without touching USB content or entering U5.

## Exact source slice

Eight files are replaced as one bounded source slice:

1. n3w_t1_core_updater_ha_usb_state.py
2. n3w_t1_core_updater_ha_usb.py
3. n3w_t1_core_updater_ha_usb_media.py
4. n3w_t1_core_updater_ha_backup.py
5. n3w_t1_core_updater_ha_recovery.py
6. n3w_t1_core_updater_ha_prepare.py
7. n3w_t1_core_updater_ha_prepare_host.py
8. n3w_t1_core_updater_ha_ipc.py

Each file binds:
- real-T1 predecessor SHA-256 from the just-closed read-only preexecution;
- repository target SHA-256;
- exact repository Git blob.

## Preflight

Before any staging or authorization claim:

- exact legacy /1 U4 transaction and transaction SHA-256;
- all four new V1.2 identity fields remain absent/null;
- exact eight predecessor source hashes;
- unchanged runtime dependency Git blobs;
- OTA host service healthy;
- service owner active;
- Manager/HA/Broker running with exact runtime image identities;
- IPC READY_TO_INSTALL;
- exactly one safe compatible ext4 N3W-UPDATE removable media by fresh inventory;
- no UUID/fingerprint continuity comparison.

## Execute contract

Execution is impossible while the manifest is ungranted.

After a future explicit grant:

1. local preflight passes;
2. exact eight target files are staged under a private remote staging directory;
3. predecessor files are copied to a private rollback directory and verified;
4. one-shot authorization is durably claimed;
5. service owner stops, then OTA host service stops;
6. all eight files are atomically replaced;
7. OTA host service starts, then service owner starts;
8. postvalidation requires exact target files, unchanged U4 transaction SHA, healthy runtime, READY_TO_INSTALL IPC, and compatible media rediscovery;
9. success deletes staging and stops before INSTALL/U5;
10. any lifecycle/source failure performs at most one automatic source rollback and revalidates the exact predecessor baseline.

## Forbidden

MOUNT=false
UMOUNT=false
USB_MUTATION=false
USB_FILESYSTEM_WRITE=false
TRANSACTION_MUTATION=false
TARGET_ARCHIVE_MUTATION=false
U5_TRANSITION=false
U6_PLUS=false
HOMEASSISTANT_IMAGE_MUTATION=false
MANAGER_IMAGE_MUTATION=false
BROKER_IMAGE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
AUTOMATIC_RETRY=false

## Authorization boundary

LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

The current package is source/test material only. A separate explicit user authorization and a grant-only successor manifest commit are required before any live source activation command may be issued.
