# N3-W T1 Core Updater post-U1 product completion read-only audit

Date: 2026-11-05

## 1. Gate

```text
TASK=N3W_T1_CORE_UPDATER_POST_U1_PRODUCT_COMPLETION_READONLY_AUDIT_20261105_01
RESULT=CLOSED_PASS

REPOSITORY_BASE_MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774
REPOSITORY_MUTATION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
APPLY=false
ROLLBACK=false
MERGE=false
```

## 2. Executive conclusion

```text
T1_CORE_UPDATER_ARCHITECTURE=COMPLETE
GENERIC_V2_CORE_SOURCE=COMPLETE
GENERIC_COMPONENT_MODEL=COMPLETE

MANAGER_UPGRADE_PRODUCT_PATH=CLOSED_PASS

HOMEASSISTANT_UPGRADE_SOURCE_CAPABILITY=IMPLEMENTED
HOMEASSISTANT_UPGRADE_PRODUCT_PATH=NOT_COMPLETE

BROKER_UPGRADE_SOURCE_CAPABILITY=IMPLEMENTED
BROKER_UPGRADE_PRODUCT_PATH=NOT_COMPLETE

U2_LEGACY_DIRTY_VALIDATION=PARTIALLY_COVERED_NOT_FORMALLY_CLOSED

T1_CORE_UPDATER_OVERALL_PRODUCT_COMPLETION=false
NEW_ARCHITECTURE_REWRITE_REQUIRED=false
```

The remaining work is product validation, not another generic updater redesign.

## 3. Generic V2 design/source status

Current `main` already implements the A2 target architecture:

```text
T1_Core_Updater
├── Generic transaction/core
├── Generic host primitives
├── component target schema /2
├── transaction schema /2
├── Manager component path
├── Home Assistant component path
└── Broker component path
```

Direct source review confirms:
- component adapters accept `manager`, `homeassistant`, and `broker`;
- component-only image binding rewrite is implemented;
- peer runtime authority is captured and checked;
- transaction status/runtime-state classification is component-aware;
- apply/rollback/failure regression is parameterized across all three components;
- Broker has a dedicated lifecycle path: quiesce application services, stop Broker, start Broker, then restart application services;
- Broker mutation safety checks the certificate-lifecycle boundary;
- exact image archive verification and portable runtime identity are shared core behavior.

Therefore the old A2 stage statement `A2_SOURCE_IMPLEMENTATION_REQUIRED=true` is historical stage text and no longer describes the current source state.

## 4. Manager path

Manager upgrade has full product-level proof:

```text
U0_BASELINE=CLOSED_PASS
U1_MANAGER_REAL_APPLY=CLOSED_PASS
KF141_RECOVERY=CLOSED_PASS
R4_REAPPLY=CLOSED_PASS
TRANSACTION=COMMITTED
RECOVERY_REQUIRED=false
RUNTIME_CLASS=TARGET_BOUND_RUNNING
HEALTH_STATE=HEALTHY
CANONICAL_AUTHORITY_PROMOTION=CLOSED_PASS
```

Current repository/live accepted Manager authority is:

```text
PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
MANAGER_IMAGE=local/greenhouse-manager:fresh-5b32e1ae8210
PR777_MERGE_COMMIT=62e498e2eefb9b5eedb70529b07e7354bd2921dc
PR778_MERGE_COMMIT=5cabdcb50656851f9912685c2f7044cdba3eb774
```

Manager does not need another product-validation cycle merely to close this audit.

## 5. Home Assistant gap

Generic source support exists, but no product-grade Home Assistant upgrade authority exists yet.

Repository audit of `infra/n3w-t1/upgrades/` found only Manager target manifests. No Home Assistant target manifest is currently present.

Current Home Assistant completion state:

```text
GENERIC_ENGINE_SUPPORT=true
GENERIC_TEST_SUPPORT=true
REAL_TARGET_MANIFEST=false
EXACT_UPGRADE_PACKAGE=false
FORMAL_LIVE_EXECUTOR=false
REAL_T1_APPLY=false
POST_UPGRADE_PRODUCT_ACCEPTANCE=false
PRODUCT_PATH_COMPLETE=false
```

## 6. Broker gap

Generic source support exists, including Broker-specific quiesce/activation and certificate-lifecycle guarding, but no product-grade Broker upgrade authority exists yet.

Repository audit of `infra/n3w-t1/upgrades/` found no Broker target manifest.

Current Broker completion state:

```text
GENERIC_ENGINE_SUPPORT=true
GENERIC_TEST_SUPPORT=true
REAL_TARGET_MANIFEST=false
EXACT_UPGRADE_PACKAGE=false
FORMAL_LIVE_EXECUTOR=false
REAL_T1_APPLY=false
POST_UPGRADE_PRODUCT_ACCEPTANCE=false
PRODUCT_PATH_COMPLETE=false
```

## 7. U2 legacy/dirty disposition

Original U2 purpose:

```text
1. freshly classify a real historical failed/dirty T1 state
2. prove consumed historical authorization is not silently replayed
3. determine DIRECTLY_COMPATIBLE vs BOUNDED_CLEANUP_REQUIRED
```

Recent U1/KF-141 real execution already provides substantial overlapping proof:
- real `FAILED_EMERGENCY` transaction state existed;
- transaction history was not treated as current runtime authority;
- fresh runtime classified a healthy predecessor independently;
- consumed authorization remained replay-forbidden;
- bounded transaction metadata reconciliation completed;
- a fresh successor authorization was required for the next apply;
- the subsequent repaired A-to-B apply committed cleanly.

However this evidence was collected on the current U1 path, not on the preserved legacy/dirty T1_A specimen specified by the original U2 plan.

Therefore:

```text
U2_RECOVERY_STATE_MACHINE_EVIDENCE=STRONG_REAL_OVERLAP
U2_NO_REPLAY_EVIDENCE=REAL_PASS
U2_RECONCILIATION_EVIDENCE=REAL_PASS
U2_T1A_FRESH_CLASSIFICATION=NOT_EXECUTED
U2_FORMAL_RESULT=NOT_CLOSED
```

U2 should be reduced to a bounded read-only classification gate. It should not automatically trigger a new apply, rollback, service restart, transaction edit/delete, or cleanup.

## 8. Completion route

```text
STEP_1=U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION
STEP_2=HOMEASSISTANT_PRODUCT_GRADE_UPGRADE_VALIDATION
STEP_3=BROKER_PRODUCT_GRADE_UPGRADE_VALIDATION
STEP_4=T1_CORE_UPDATER_FINAL_PRODUCT_CLOSURE
```

Home Assistant/Broker validation should reuse the existing generic V2 core. A new generic-core rewrite is out of scope unless a fresh product-level blocker proves one is necessary.

## 9. Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_U2_LEGACY_DIRTY_T1A_READONLY_CLASSIFICATION_20261105_01

T1_A_ACCESS=true
T1_A_MUTATION=false
REPOSITORY_MUTATION=false
BOARD_ACCESS=false
APPLY=false
ROLLBACK=false
SERVICE_RESTART=false
TRANSACTION_EDIT=false
TRANSACTION_DELETE=false
MERGE=false
```

Expected U2 outputs:

```text
LEGACY_TRANSACTION_PRESENT=
LEGACY_TRANSACTION_TERMINAL=
RECOVERY_REQUIRED=
CURRENT_RUNTIME_CLASS=
CONSUMED_AUTHORIZATION_REPLAY_RISK=
LEGACY_STATE_DISPOSITION=NO_ACTION_REQUIRED|DIRECTLY_COMPATIBLE|BOUNDED_CLEANUP_REQUIRED|UNRESOLVED
```

Any required mutation after that classification must be a separate gate.

## 10. Final audit state

```text
COMPLETION_AUDIT=CLOSED_PASS
UPDATER_REWRITE_REQUIRED=false
MANAGER_PATH_REOPEN=false
U2_READONLY_CLASSIFICATION_REQUIRED=true
HOMEASSISTANT_PRODUCT_VALIDATION_REQUIRED=true
BROKER_PRODUCT_VALIDATION_REQUIRED=true
T1_CORE_UPDATER_PRODUCT_DEVELOPMENT=CLOSURE_PENDING
```
