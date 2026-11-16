# N3-W T1 U10 R37 real-T1 read-only preflight closure — 2026-11-16

## Result

```text
PR=807
R37_SOURCE_HEAD=6d4e93b9fded6b719e48f3d0678850677dc0dce8
R37_SOURCE_CI=16_OF_16_SUCCESS
R37_EXECUTION_ID=u10-r37-readonly-20261116T024337Z
R37_RESULT=U10_R37_READONLY_PREFLIGHT_PASS
R37_RC=0
READ_ONLY=true
SSH_MASTER_CLEANUP=true
R37_STATUS=CLOSED_PASS
```

R37 executed against the real T1 using the exact reviewed source head and returned RC=0. The gate remained read-only and did not advance the product state.

## U9 authority continuity

```text
TRANSACTION_PHASE=U9_LIVE_AUTHORIZATION_CLAIMED
TRANSACTION_SHA256=69f5a8c2190dac0a12df3aac1bdc9c9f3b02050e9541e7a202907204d280f7c3
R35_CLAIMED=true
R35_CONSUMED=true
R35_REPLAY_PERMITTED=false
R36_CLAIMED=true
R36_CONSUMED=true
R36_REPLAY_PERMITTED=false
USB_MIRROR_EXACT=true
BOUND_FILESYSTEM_UUID=967cf065-abe5-49ee-8499-7c3f50d2c48f
```

The durable U9 transaction remained exact. R35 and R36 remain permanently consumed/no-replay.

## Recovery authority

```text
TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
TARGET_ARCHIVE_SIZE_BYTES=835309535
PREDECESSOR_ARCHIVE_SHA256=34cec37ab021e1081e236502bfd06760894f6bca93bd8d6bf99d8d90bb89848d
PREDECESSOR_ARCHIVE_SIZE_BYTES=743074537
BACKUP_VERIFIED=true
RECOVERY_CAPACITY_PASS=true
OBSERVED_USB_FREE_BYTES=28132077568
REQUIRED_FREE_AFTER_RECOVERY_ASSETS_BYTES=1610612736
```

Target archive, predecessor recovery archive, protected Home Assistant backup and fresh removable-media capacity all passed exact verification.

## Exact U10 release candidate

```text
BROKER_RUNNING=true
MANAGER_QUIESCED=true
HOMEASSISTANT_EXITED=true
SERVICES_OWNER_STATE=failed
PREDECESSOR_RUNTIME_RELEASE_ALLOWLIST=26b095e1ba8aa3a009f02a2460234eae45764debf61d878b965761ce75212676
PREDECESSOR_IMAGE_RELEASE_ALLOWLIST=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306
TARGET_INTERNAL_IMAGE_ABSENT=true
MANAGER_BROKER_RELEASE_FORBIDDEN=true
U10_READONLY_ELIGIBLE=true
```

R37 proves that the only predecessor runtime object eligible for a future U10 release is the exact stopped Home Assistant container above, followed by the exact predecessor image above. Manager and Broker are explicitly outside the release set.

## Mutation proof and stop boundary

```text
TRANSACTION_MUTATION=false
USB_MUTATION=false
PREDECESSOR_RUNTIME_DELETE=false
PREDECESSOR_IMAGE_DELETE=false
TARGET_IMAGE_LOAD=false
SERVICE_MUTATION=false
U10_TRANSITION=false
U11_PLUS=false
BOARD_ACCESS=false
MERGE=false
U10_DESTRUCTIVE_EXECUTION_AUTHORIZED=false
```

The shell-session-save warning observed after the command completed occurred after executor RC=0 and successful SSH master cleanup. It does not alter the R37 result.

Private SSH locator, known-hosts binding, host-key material and raw evidence remain operator-private and are not stored in the public repository.

```text
NEXT_ONE_GATE=U10_DESTRUCTIVE_SUCCESSOR_SOURCE_AND_EXECUTION_PACKAGE_PREPARATION
STOP_BOUNDARY=FRESH_EXPLICIT_AUTHORIZATION_REQUIRED_BEFORE_ANY_REAL_T1_U10_DESTRUCTIVE_MUTATION
```
