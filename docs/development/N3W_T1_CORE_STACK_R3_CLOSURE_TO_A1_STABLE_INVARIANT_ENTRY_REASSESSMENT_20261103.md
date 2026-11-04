# N3-W T1 Core Stack R3 closure -> A1 stable-invariant entry reassessment — 2026-11-03

## 0. Decision

```text
TASK=N3W_T1_CORE_STACK_R3_CLOSURE_TO_A1_STABLE_INVARIANT_ENTRY_REASSESSMENT_20261103_01

DIRECT_RELAY_REPEAT_REQUIRED=false
DIRECT_RELAY_HISTORICAL_ACCEPTANCE_REMAINS_VALID=true

R3_FIRST_REGISTRATION=PASS
R3_POST_REGISTRATION_DIRECT_TELEMETRY_HA=PASS
R3_PRODUCT_DEFECT_BLOCKER_COUNT=0

R3_ENGINEERING_OBJECTIVE_COMPLETE=true
R3_CLEAN_REFERENCE_AUTHORITY_CLOSURE=PARTIAL
R3_REFERENCE_SHA256=NOT_FROZEN
R3_R2_SEMANTIC_COMPARE_AUTHORITY=NOT_YET_FROZEN

NEXT_ONE_GATE=N3W_T1_CORE_STACK_R3_REFERENCE_CONVERGENCE_AND_A1_ENTRY_READONLY_20261103_01
A1_ENTRY_AFTER_GATE_PASS=true
BOARD_ACCESS=false
T1_MUTATION=false
MERGE=false
```

## 1. Why Direct -> Relay -> Direct must not be repeated

The frozen R3 execution plan explicitly defines R3 as:

```text
healthy zero-node production T1
-> one normal first-registration transaction
-> durable Manager COMMIT
-> healthy one-node production T1
```

and explicitly states that R3 does not require MQTT telemetry, Home Assistant discovery/entity acceptance, Direct/Relay failover, ESP-NOW relay traffic, sensor measurement acceptance, or long-duration stability.

Direct -> Relay -> Direct same-boot physical acceptance was already completed in the earlier N3-W wireless phase. The post-registration Direct telemetry / Home Assistant gate completed on 2026-11-03 is additional downstream evidence and does not create a reason to repeat the historical failover acceptance.

## 2. What is already closed

```text
R3_REAL_FIRST_REGISTRATION=PASS
KF139=CLOSED_PASS
PAIRING_WINDOW_FINAL=CLOSED
PAIRING_CLOSE_REASON=committed
ACTIVE_CREDENTIAL_GENERATION=1
UNRESOLVED_FIRST_REGISTRATION_COUNT=0

DIRECT_TELEMETRY_MANAGER_SEQ_RANGE=71..101
DIRECT_TELEMETRY_MISSING_SEQ_COUNT=0
DIRECT_TELEMETRY_REJECTED_COUNT=0
DIRECT_TELEMETRY_DUPLICATE_COUNT=0
HOME_ASSISTANT_FRESH_RUNTIME_RECEIPT=PASS

KF140=CLOSED_FALSE_POSITIVE
SOURCE_REPAIR_REQUIRED=false
```

## 3. Why R3 is not yet formally complete as a Clean Reference authority

The Clean Reference development plan defines:

```text
R3_REFERENCE=NORMAL_RUNTIME_REFERENCE
```

and requires an R2-vs-R3 comparison before A1.

Repository search finds the frozen R2 common-reference digest, but no frozen `R3_REFERENCE_SHA256` and no final authoritative R2->R3 reference comparison artifact. Therefore the business execution is complete, but the reference artifact required by A1 is not yet formally frozen.

No physical first-registration replay is justified. No Direct/Relay repeat is justified.

## 4. Reference-frame complication introduced by KF-139

The original Clean Reference route expected R2 and R3 to use the same exact stack so that business-runtime drift could be isolated.

During R3, KF-139 required a real Manager repair and accepted A->B live update:

```text
HISTORICAL_CLEAN_REFERENCE_MANAGER=local/greenhouse-manager:fresh-24382caae4a1
CURRENT_MANAGER=local/greenhouse-manager:fresh-b863ddd95909
```

Therefore a naive current-R3-vs-old-R2 hash compare would mix:

```text
LEGITIMATE_BUSINESS_RUNTIME_DRIFT
+
INTENTIONAL_MANAGER_VERSION_CHANGE
```

The next gate must preserve that distinction. Manager version/source drift is an explicit version axis, not an automatic stable-contract failure.

## 5. Correct next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_R3_REFERENCE_CONVERGENCE_AND_A1_ENTRY_READONLY_20261103_01
```

Scope:

1. rebind R0/R1/R2 reference authorities and the accepted R3 first-registration/KF-139 evidence;
2. determine which R3 reference fields can be reconstructed exactly from archived evidence;
3. if any reference field still needs live confirmation, perform only a fresh read-only T1 observer snapshot;
4. freeze an authoritative R3 reference/delta with the Manager version transition explicitly separated from runtime-state changes;
5. produce the A1 input table;
6. enter A1 stable-invariant classification after this gate passes.

Forbidden:

- first-registration replay;
- Board reflash/NVS reset;
- Direct/Relay movement retest;
- sensor acceptance;
- T1 service/image/config mutation;
- updater apply;
- merge.

## 6. A1 meaning

A1 is not another physical workload test. It creates the authoritative field-classification table:

```text
FIELD
OWNER_MODULE
R0_VALUE_CLASS
R1_VALUE_CLASS
R2_CHANGED
R3_CHANGED
CLASSIFICATION
CONCRETE_SAFETY_REASON
```

Allowed classifications come from the frozen Clean Reference design:

```text
HARD_STABLE_INVARIANT
SOFT_RUNTIME_CHECK
DIAGNOSTIC_ONLY
REMOVE
```

Only after A1 converges should A2 redesign per-module upgrade contracts and then U0/U1/U2 perform real version-delta upgrade validation.
