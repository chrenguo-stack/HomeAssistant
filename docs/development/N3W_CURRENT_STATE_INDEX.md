# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current local-chat/GitHub alignment: `docs/development/N3W_KF089_LOCAL_CHAT_GITHUB_ALIGNMENT_20260912.md`  
Current T1 runtime-convergence archive: `docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`  
Previous detailed KF-089 progress archive: `docs/development/N3W_KF089_RELAY_ACQUISITION_TELEMETRY_OBSERVABILITY_AND_SCHEMA_V5_PROGRESS_ALIGNMENT_20260910.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Current source authority

```text
REPOSITORY_MAIN=7478e0fbcf893761ab76cc9952e09e77cda22755
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
PRODUCT_SOURCE_TREE=1ae70a7d8776f8343d53d5c784141e8d8d1b1abc
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
DIAGNOSTIC_SCHEMA_VERSION=5
```

## Current physical/runtime boundary

```text
BOARD_B_BOOT_RECOVERY=CLOSED_ENOUGH_FOR_RELAY_TESTING
PRODUCT_RUNTIME_AFTER_POWER_CYCLE=PASS
N3W_RUNTIME=PASS
SCHEMA_V5_RUNTIME_STATE=PASS
BOARD_A_DIRECT_CURRENT=true
BOARD_B_DIRECT_CURRENT=true
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
```

The stale state that Board B remains in ROM download mode is superseded. ID10 performed a complete power cycle and post-power-cycle T1/Broker evidence recovered 194 accepted Direct telemetry messages from Board B.

## Current KF-089 boundary

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF089_AB_RELAY_DATA_PATH_END_TO_END_PHYSICAL_20260912_11
CURRENT_GATE_STATE=AUTHORIZED_NOT_YET_ADJUDICATED
```

ID11 is one bounded physical RF capture with no automatic retry, no flash/NVS/otadata write, no pairing change, and no T1 mutation. It must localize the path through Board B async unicast completion, Board A compact RX/decode/forward submit, and final T1 ingress.

## OTA Guard side state

```text
PR385_STATE=OPEN_UNMERGED
GUARD_PREMUTATION_AND_MUTATION_DATA_PATH=PASS
GUARD_IDENTITY_CONTRACT_REPAIR=PASS
GUARD_POSTMUTATION_FLASH_FINISH_HANDLING=REPAIR_REQUIRED
GUARD_FAILURE_STATE_RECONNECT_PATH=REVIEW_REQUIRED
N3W_OTA_GUARD_FULLY_READY=false
```

The OTA Guard is not the current main gate. Its remaining work is the post-mutation completion/verification repair exposed by the real Board B ID03 execution.

Historical archives remain historical and are not rewritten. No PR merge is authorized by this index refresh.