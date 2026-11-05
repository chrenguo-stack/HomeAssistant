# N3W T1 Core Updater Home Assistant P5 Post-cleanup Reapply Readonly Preflight Closure

DATE=2026-11-06

## Gate

GATE_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_POSTCLEANUP_REAPPLY_READONLY_20261106_01

EXACT_SOURCE_HEAD=77848355eb18c1d9b2a65f5bb209202f9f3ac2e3

TARGET_MANIFEST_BLOB_SHA=6966b4fe4d7620ccc436643cc840da9ae95e6010

## Result

STATUS=CLOSED_PASS

MUTATION=false

PRODUCTION_RUNTIME_HEALTHY=true

HOMEASSISTANT_RESIDUE_COUNT=0

REAPPLY_CANDIDATE=true

RUNNING_PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

TARGET_IMAGE_PRESTATE=PRESENT_AND_EXACT

TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f

TARGET_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365

TARGET_CONFIG_SEMANTICS_SHA256=2ceae2ee88683a423315a3faf81cd14af36d8542cd5d948e1747479d4ec749bd

TARGET_ROOTFS_DIFF_IDS_SHA256=971b2515c2e33e9b661f40f87494519dd5d4db945a35384709c694ecc93f60c9

MANAGER_MQTT_AUTHENTICATED=true

HOMEASSISTANT_MQTT_AUTHENTICATED=true

HOMEASSISTANT_HTTP_STATUS=401

SYSTEM_STATE=running

LISTENER_TCP_8883=1

LISTENER_TCP_47110=1

LISTENER_UDP_47111=1

LISTENER_TCP_47112=0

BOARD_ACCESS=false

## Interpretation

The Attempt 03 non-running Home Assistant residue is absent.

The production Home Assistant predecessor remains healthy and running.

The retained 2026.10.4 target image is not accepted by tag alone. Its Docker image ID, normalized configuration semantics fingerprint, and RootFS diff-ID fingerprint match the frozen target evidence.

This gate grants no live update authority.

LIVE_REAPPLY_AUTHORIZED=false

OLD_ATTEMPT03_AUTHORIZATION_REUSABLE=false

CLEANUP_AUTHORIZATION_REUSABLE=false

## Successor design boundary

A fresh reapply execution package may be prepared.

The successor must:
- use a new authorization ID;
- require a fresh preflight before authorization claim;
- accept only target_image_prestate=PRESENT_AND_EXACT;
- continue to verify the exact frozen archive before mutation;
- rely on Generic V2 to skip docker load when the exact target image is already resident;
- preserve automatic rollback;
- use the widened Home Assistant readiness budget;
- never reuse the consumed Attempt 03 or cleanup authorization.

MERGE=false
