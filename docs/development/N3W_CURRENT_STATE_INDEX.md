# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current local-chat/GitHub alignment: `docs/development/N3W_KF089_LOCAL_CHAT_GITHUB_ALIGNMENT_20260912.md`  
Latest ID11 STOP: `docs/development/N3W_KF089_ID11_RF_CAPTURE_STOP_HOST_IDENTITY_NORMALIZATION_20260912.md`  
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
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
```

## Current KF-089 boundary

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

## ID11 consumed capture

```text
ID11_CLAIMED=true
RF_WINDOW_SECONDS=90
BOARD_A_DIRECT_BASELINE=true
BOARD_A_DIRECT_DURING_WINDOW=true
BOARD_B_COLD_BOOT_EXECUTED=true
SELECTIVE_RF_ZONE_USED=true
BOARD_B_DIRECT_INGRESS_COUNT=0
BOARD_B_RELAY_INGRESS_COUNT=0
BOARD_B_ACCEPTED_RELAY_COUNT=0
SECOND_RF_CAPTURE=false
```

The RF window completed. Product-path adjudication did not complete because the Board B diagnostic readback was stopped by a host-side identity validation/normalization error before NVS snapshot recovery. Zero relay ingress alone is not a product-failure proof.

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF089_ID11_BOARD_B_IDENTITY_HOST_NORMALIZATION_FORENSIC
BOARD_ACCESS=false
USB_ACCESS=false
SECOND_RF_CAPTURE=false
AUTO_RETRY=false
```

The goal is to repair or correctly classify the host identity validation using already captured evidence, then—only if safe and separately authorized—recover the persisted A/B Schema-v5 snapshots from this same ID11 capture. Do not repeat RF.

## OTA Guard side state

```text
PR385_STATE=OPEN_UNMERGED
GUARD_PREMUTATION_AND_MUTATION_DATA_PATH=PASS
GUARD_IDENTITY_CONTRACT_REPAIR=PASS
GUARD_POSTMUTATION_FLASH_FINISH_HANDLING=REPAIR_REQUIRED
GUARD_FAILURE_STATE_RECONNECT_PATH=REVIEW_REQUIRED
N3W_OTA_GUARD_FULLY_READY=false
```

Historical archives remain historical and are not rewritten. No PR merge is authorized by this index refresh.