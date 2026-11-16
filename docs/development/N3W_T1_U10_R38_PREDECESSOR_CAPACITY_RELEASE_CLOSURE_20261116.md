# N3-W T1 U10 R38 real-T1 predecessor-capacity release closure — 2026-11-16

## Result

```text
PR=807
R38_AUTHORIZED_HEAD=b38a43b11beecb1dc73680aed933ad05db084c9b
R38_AUTHORIZED_HEAD_CI=16_OF_16_SUCCESS
R38_EXECUTOR_BLOB=8dce8f6ee0c777ae6266d83f980f1972f97600e1
R38_GRANTED_MANIFEST_BLOB=443ab5960aa7ce4cb26ed0fa45e0a0b4b96aebb1
R38_EXECUTION_ID=u10-r38-live01-20261116T034011Z
R38_RESULT=U10_R38_PREDECESSOR_CAPACITY_RELEASE_PASS
R38_RC=0
R38_STATUS=CLOSED_PASS
SSH_MASTER_CLEANUP=true
STATUS_RECONCILIATION_ATTEMPTED=false
```

R38 executed once against the real T1 from the exact authorized head after 16/16 CI SUCCESS. The executor returned RC=0 and a directly observed terminal PASS. No reconciliation path was required.

## Preclaim continuity

```text
R37_PRECLAIM=U10_R37_READONLY_PREFLIGHT_PASS
PRE_TRANSACTION_PHASE=U9_LIVE_AUTHORIZATION_CLAIMED
PRE_TRANSACTION_SHA256=69f5a8c2190dac0a12df3aac1bdc9c9f3b02050e9541e7a202907204d280f7c3
R35_CLAIMED=true
R35_CONSUMED=true
R35_REPLAY_PERMITTED=false
R36_CLAIMED=true
R36_CONSUMED=true
R36_REPLAY_PERMITTED=false
BOUND_FILESYSTEM_UUID=967cf065-abe5-49ee-8499-7c3f50d2c48f
R37_USB_MIRROR_EXACT=true
R37_BACKUP_VERIFIED=true
R37_RECOVERY_CAPACITY_PASS=true
R37_OBSERVED_USB_FREE_BYTES=28132077568
R37_REQUIRED_FREE_AFTER_RECOVERY_ASSETS_BYTES=1610612736
```

The embedded R37 preclaim revalidated the exact U9 transaction, consumed/no-replay prior authorization ledgers, bound USB, exact recovery assets, protected Home Assistant backup, capacity and runtime release allowlist before any R38 destructive action.

## One-shot authorization and destructive scope

```text
R38_AUTHORIZATION_CLAIMED=true
R38_AUTHORIZATION_CONSUMED=true
R38_REPLAY_PERMITTED=false
DESTRUCTIVE_CUTOVER=true

PREDECESSOR_RUNTIME_DELETE=true
PREDECESSOR_RUNTIME_RELEASED=true
PREDECESSOR_IMAGE_DELETE=true
PREDECESSOR_IMAGE_RELEASED=true

RELEASED_HOMEASSISTANT_CONTAINER=26b095e1ba8aa3a009f02a2460234eae45764debf61d878b965761ce75212676
RELEASED_PREDECESSOR_IMAGE=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306

MANAGER_BROKER_RELEASE_FORBIDDEN=true
BROKER_RUNNING=true
MANAGER_QUIESCED=true
```

The destructive action remained exactly bounded to the previously approved stopped Home Assistant predecessor container and predecessor image. Manager and Broker were not released.

## Durable U10 result

```text
POST_TRANSACTION_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
POST_TRANSACTION_SHA256=c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3
USB_MIRROR_EXACT=true

POST_USB_MANIFEST_SHA256=3aa5e247636b1bb891aa151a8fb0219294d4803ea22dc7b66d821f6250d9e728
POST_USB_CONTENT_AUTHORITY_SHA256=3da14eb03447beaf38579a3fa5e4e076d4f3e806f7a787cbc0bba6b2cb1b8727
POST_USB_CHECKSUMS_SHA256=2a21aa2b8fb362242fa087a49a2ebfb93caf65d1dd8a6f9c6da44edbb9f8c7f2
POST_USB_PHASE_SHA256=005285eb177803b2fd387725730abf8e28b30f4727f422672e88cc998c14b589

USB_MUTATION=true
TRANSACTION_MUTATION=true
U10_TRANSITION=true
```

USB U10 metadata was durably synchronized before the host transaction. Terminal verification then proved the exact U10 transaction and exact removable-media mirror.

## U11 stop boundary

```text
TARGET_INTERNAL_IMAGE_ABSENT=true
TARGET_IMAGE_LOAD=false
SERVICE_MUTATION=false
U11_PLUS=false
BOARD_ACCESS=false
MERGE=false

U10_STATUS=CLOSED_PASS
U11_AUTHORIZED=false
NEXT_ONE_GATE=U11_TARGET_INSTALL_SOURCE_AND_READONLY_PREFLIGHT_PREPARATION
STOP_BOUNDARY=BEFORE_ANY_REAL_T1_U11_TARGET_IMAGE_LOAD_SERVICE_START_OR_U11_TRANSITION
```

R38 did not load the target Home Assistant image, did not start or restart services, and did not enter U11. Any U11 real-T1 target installation/start operation requires a new explicit authorization after repository-side source design, focused tests, exact-head CI and read-only preflight closure.

The post-command `shell_session_save...parameter not set` warning occurred after executor RC=0 and successful SSH master cleanup. It does not alter the R38 PASS result.

Private SSH locator, known-hosts binding, host-key material and raw evidence remain operator-private and are not stored in the public repository.
