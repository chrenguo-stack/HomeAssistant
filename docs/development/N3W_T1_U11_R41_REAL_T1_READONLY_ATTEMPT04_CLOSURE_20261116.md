# N3-W T1 U11 R41 real-T1 read-only Attempt 04 closure

## Result

```text
GATE=R41_REAL_T1_READONLY_ATTEMPT04
EXECUTION_ID=u11-r41-readonly04-20261116T140219Z
RC=0
STATUS=U11_R41_POST_R40_READONLY_PREFLIGHT_PASS
READ_ONLY=true
T1_ACCESS=true
REMOTE_PREFLIGHT_INVOKED=true
SSH_MASTER_CLEANUP=true

SUCCESSOR_LIVE_RECOVERY_ELIGIBLE=true
SUCCESSOR_LIVE_RECOVERY_AUTHORIZED=false
R40_REPLAY=false

TRANSACTION_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
TRANSACTION_SHA256=c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3
USB_MIRROR_EXACT=true
BOUND_FILESYSTEM_UUID=967cf065-abe5-49ee-8499-7c3f50d2c48f

TARGET_IMAGE_PRESENT=true
TARGET_RUNTIME_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
TARGET_COMPOSE_BINDING=local/n3w-homeassistant:2026.10.4-5881590f
HOMEASSISTANT_CONTAINER_ABSENT=true
PREDECESSOR_IMAGE_ABSENT=true
SERVICES_OWNER_STATE=failed
BROKER_RUNNING=true
MANAGER_QUIESCED=true

POST_TARGET_LOAD_INTERNAL_FREE_BYTES=5665595392
POST_TARGET_LOAD_REQUIRED_RESERVE_BYTES=1610612736
POST_TARGET_LOAD_RESERVE_PASS=true
USB_FREE_BYTES=28132077568
USB_RECOVERY_CAPACITY_PASS=true
BACKUP_VERIFIED=true

EFFECTIVE_SUPERVISION_CONTRACT=EXACT_HA_OTA_OVERLAY
SUPERVISION_REPAIR_SOURCE_AUTHORITY=155f9a7b62d6b758fb87c109b3ffbf54aa5614c7

TRANSACTION_MUTATION=false
USB_MUTATION=false
TARGET_IMAGE_LOAD=false
COMPOSE_BINDING_MUTATION=false
SERVICE_MUTATION=false
U11_TRANSITION=false
U12_PLUS=false
U13_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

## Interpretation

R41 Attempt 04 completed the successor read-only gate on the real production T1. The exact post-R40 partial-U10 transaction, consumed/no-replay R38 and R40 ledgers, bound USB mirror and filesystem identity, recovery assets, protected backup, loaded target image identity, target Compose binding, peer/runtime quiescence, repaired effective HA-OTA supervision contract, and post-target-load internal reserve all passed.

The result establishes only that a separately designed successor live recovery may now be considered eligible. It does **not** authorize or perform a service start/restart, transaction or USB persistence, U11 completion, U12/U13 work, board access, merge, or R40 replay.

The raw Attempt 04 evidence remains in the operator-approved private evidence root and is intentionally not committed because it includes private target/transport context. This record preserves the public-safe execution ID, hashes, states, and acceptance result needed for continuation.

## Source / CI binding

```text
MAIN_AT_R41_REBIND=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
PR=807
R41_EXACT_SOURCE=d42776f768a0cab1ebf054e393fa64721d155dcb
R41_CI=16_OF_16_SUCCESS
R41_HA_TARGET_BINDING_RUN=43872081096
R41_HA_TARGET_BINDING_SOURCE=SUCCESS
R41_HA_TARGET_BINDING_EXACT_BINDING=SUCCESS
R41_FOCUSED_TESTS=790_PASSED
R41_EXECUTOR_BLOB=ec8bafdffd971c1695b0336b89833c86a7879749
R41_MANIFEST_BLOB=44c6716b41e06f64214e3231df7f16c11325cf81
R41_FOCUSED_TEST_BLOB=8cb9c95b2ae9a361910527545a98f967ed463b61
R41_EXACT_U11_SOURCE_BLOB=33bd5e486db17b2476674009a6c23eecf750c12a
```

## Stop boundary

```text
NEXT_BOUNDARY=SUCCESSOR_LIVE_RECOVERY_SEPARATE_DESIGN_REVIEW_AND_EXPLICIT_AUTHORIZATION
SUCCESSOR_LIVE_RECOVERY_AUTHORIZED=false
R40_REPLAY_FORBIDDEN=true
SERVICE_START_OR_RESTART_AUTHORIZED=false
U11_LIVE_TRANSITION_AUTHORIZED=false
U12_AUTHORIZED=false
U13_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
STOP_AFTER_R41_READONLY_BEFORE_ANY_SUCCESSOR_LIVE_CLAIM=true
```

No further live mutation is authorized by this closure.
