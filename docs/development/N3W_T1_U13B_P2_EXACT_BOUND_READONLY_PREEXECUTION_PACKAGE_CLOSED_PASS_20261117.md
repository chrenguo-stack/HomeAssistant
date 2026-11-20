# N3-W T1 U13B P2 exact-bound read-only preexecution package CLOSED_PASS — 2026-11-17

## Result

```text
GATE=N3W_T1_U13B_P2_EXACT_BOUND_READONLY_PREEXECUTION_PACKAGE_20261117_01
PACKAGE_HEAD=67b2995c983c1265dfcb24aed1395c2eefc50302
CI=16_OF_16_SUCCESS
REAL_T1_ACCESS=false
T1_MUTATION=false
USB_MUTATION=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
HA_DATA_MUTATION=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
U13B_LIVE_EXECUTION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

P2 binds the fresh P1 real-T1 terminal facts to the closed U13B read-only preexecution source hashes.

The bound real-T1 baseline remains:

```text
PHASE=U13A_COMMITTED
STATUS=COMMITTED
TRANSACTION_SHA256=06951ac4d8a8723ae808f25d955560052eee02f884ab78f5c6ffe0580e84b600
TRANSACTION_ID_SHA256=ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738
USB_FILESYSTEM_UUID=967cf065-abe5-49ee-8499-7c3f50d2c48f
USB_PHASE_SHA256=11d150bc3828a0e400a90670671a607a02f6d1a53350ef53b3366d95fcb64288
ROLLBACK_ELIGIBLE=false
NEW_CLEAN_OTA_REQUIRED=true
```

The package is deliberately not authorized to access T1. At this exact terminal U13A state, any later separately authorized P2 read-only execution must classify the machine as outside the U13B rollback domain and STOP safely. It must never manufacture rollback eligibility.

## Source/package binding

```text
EXECUTOR_BLOB=0af6168c7026bb58be53f2cfee3105226cecde78
MANIFEST_BLOB=34cf2f34bd85c096bcb386b33309fa0fb4aa6970
U13B_READONLY_PREEXECUTION_SOURCE_HEAD=c02335e728797c953e623cf439d314c0affc3d32
P1_EXECUTION_PACKAGE=e41723d8fa278021db95fc497426678a8a52d3c2
P1_EXECUTION_ID=u13b-p1-readonly02-20261117T122835Z
P1_RESULT=U13B_REAL_T1_READONLY_BINDING_PASS
```

## Next boundary

P2 is CLOSED_PASS. The next stage is P3 target/transaction preparation for a new clean OTA transaction.

P3 may not reuse the current 2026.10.4 image as a same-image rollback proof. A distinct exact target must first be selected, source-reviewed and artifact-bound.

The repository already defers Home Assistant 2026.11.0 because its entity-registry minor version advances 23 -> 24 and therefore falls outside the current IMAGE_ONLY_V1 compatibility contract.

```text
P2_CLOSED_PASS=true
P3_TARGET_SELECTION_REQUIRED=true
P3_NEW_CLEAN_OTA_LIVE_MUTATION_NOT_ENTERED=true
```
