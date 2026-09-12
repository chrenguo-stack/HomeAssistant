# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current local-chat/GitHub alignment: `docs/development/N3W_KF089_LOCAL_CHAT_GITHUB_ALIGNMENT_20260912.md`  
Latest consumed RF gate: `docs/development/N3W_KF089_AB_RELAY_DATA_PATH_ID11_PHYSICAL_AUTHORIZATION_20260912.md`  
Latest ID12 authorization: `docs/development/N3W_KF089_ID11_AB_SCHEMA_V5_READONLY_RECOVERY_ID12_AUTHORIZATION_20260912.md`  
Current T1 runtime-convergence archive: `docs/development/N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`  
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
RF_WINDOW_COMPLETED=true
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

Product-path adjudication remains incomplete because A/B Schema-v5 counters were not recovered. The RF capture must not be repeated merely to recover host evidence.

## ID12 consumed read-only attempt

```text
ID12_CLAIMED=true
REPLAY_PERMITTED=false
BOARD_ACCESS=false
READ_MAC_EXECUTED=false
RAW_EVIDENCE_PERSISTED=false
RESULT=STOP
FIRST_UNPROVEN_OR_FAILED_STAGE=BOARD_B_IDENTITY_COMMAND_START
```

The only observed failure statement is that the esptool wrapper lacked executable permission and the command failed before `read-mac`. The detailed invocation form and root cause are not proven because raw argv/stdout/stderr/traceback were not preserved. Do not treat a Python-wrapper explanation as OBSERVED fact.

## Process transition

```text
PR388_STATE=OPEN_UNMERGED
HANDOFF_STANDARD_CANDIDATE_VERSION=1.1
EXECUTION_MODEL=HIGH_LEVEL_MODEL_DESIGNS_VERSIONED_EXECUTION_PACKAGE
CODEX_ROLE=EXACT_EXECUTOR
RAW_EVIDENCE_FIRST=true
DSL_EXECUTION_MODEL=false
```

End-of-chat user direction: future code should be authored by the high-level model and committed to GitHub; Codex should execute exact committed code and report raw evidence/results only. Repository storage convention for Execution Packages must be frozen in the next host-only gate.

## Current ONE gate

```text
CURRENT_ONE_GATE=N3W_KF089_EXECUTION_PACKAGE_ROLE_AND_STORAGE_FREEZE
BOARD_ACCESS=false
USB_ACCESS=false
SECOND_RF_CAPTURE=false
AUTO_RETRY=false
```

After the role/storage convention is frozen and the process candidate is aligned, the high-level model must author and commit the next A/B read-only recovery Execution Package. Only after host tests/review may a new physical read-only authorization be requested.

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
