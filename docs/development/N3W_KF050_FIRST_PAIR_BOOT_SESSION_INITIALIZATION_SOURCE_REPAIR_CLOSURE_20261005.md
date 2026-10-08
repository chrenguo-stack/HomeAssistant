# N3-W KF-050 First-Pair Boot-Session Initialization — Source Repair Closure — 2026-10-05

```text
TASK=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_SOURCE_REPAIR_20261005_01
STATUS=CLOSED_PASS
SOURCE_REPAIR=PASS
BOARD_ACCESS=false
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
RECOVERY_FLOOR_EXECUTION=false
MERGE=false
```

## 1. Authority binding

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_BASE=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
DESIGN_BASE=b7ea62ee3a742968905fbe5e33b6d5f86a7f9db1
SOURCE_REPAIR_CODE_COMMIT=fe2c2283f178e572fc8f83d0d48b320a065a3bd8
SOURCE_REPAIR_HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
SOURCE_REPAIR_TREE=f45ca257de0b6e41f0458346711bb4e105ba1fcc
R2_RELOCATION_SOURCE=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
R2_RELOCATION_SOURCE_DEFECT_PROVEN=false
```

The source-repair design authority is:

```text
docs/development/N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_SOURCE_REPAIR_DESIGN_20261005.md
```

The current repair closes only the inherited KF-050 first-pair initialization window. It does not redesign Broker relocation, Manager replay/high-water, B2 naming, Relay behavior, pairing cryptography or credential semantics.

## 2. Implemented product behavior

The repaired product startup order is now:

```text
GreenhouseN3wCore::setup()
-> if product runtime is disabled, preserve the existing disabled/legacy path without new product-state mutation
-> classify durable startup product identity state
-> INVALID_OR_PARTIAL: fail closed
-> PROVEN_FRESH:
     inspect durable boot_state
     if missing: persist floor=0 through BootSessionManager::provision_recovery_floor()
     readback verification is performed by the existing BootSessionManager primitive
     if exact zero already exists: accept idempotently without rewrite
     if nonzero/corrupt/I/O error: fail closed
-> only after the above succeeds, enter SimpleProductComponent::setup()
-> normal pairing may persist product identity
```

The delayed zero-floor creation was removed from the telemetry path. `begin_boot_session_if_needed_()` now only invokes normal `BootSessionManager::begin()` against an already existing durable boot-state record. Missing/corrupt/unavailable state therefore remains fail closed.

## 3. Fresh-state classification

The old negative inference:

```text
fresh_identity_candidate_ = !persisted_runtime_state_present_()
```

was removed.

The new classifier requires explicit evidence:

```text
peer=MISSING + broker=MISSING + pending_ack=MISSING
-> PROVEN_FRESH

valid matching peer+broker + pending_ack=MISSING or VALID
-> EXISTING_IDENTITY

partial/corrupt/invalid/mismatched peer/broker/ack
-> INVALID_OR_PARTIAL
```

Setup Secret and pairing-intent state are deliberately not treated as formal product identity.

This prevents a partial historical state from gaining authority to write a new zero floor.

## 4. Boot-floor policy

New source:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_first_pair_boot_policy.h
```

Policy:

```text
boot_state=MISSING
-> persist 0 + readback verify

boot_state=OK,value=0
-> PASS idempotently
-> no rewrite

boot_state=OK,value>0
-> fail closed
-> no lowering/overwrite

boot_state=CORRUPT
-> fail closed

boot_state=IO_ERROR
-> fail closed
```

The implementation reuses the existing `BootSessionManager::provision_recovery_floor()` durability primitive. No second counter persistence format or recovery mechanism was introduced.

## 5. Exact defect closure

The previously failing sequence was:

```text
fresh board
-> pair and persist complete peer/broker identity
-> boot_state still missing
-> reboot before first telemetry
-> existing identity + missing counter
-> fail closed forever without a separate recovery path
```

The repaired sequence is:

```text
fresh board
-> verified floor=0 before pairing
-> pair and persist identity
-> reboot before first telemetry
-> existing identity + boot_state=0
-> first telemetry begin() persists session=1
-> boot_id=boot_0000000000000001
```

A later reboot advances to session 2. Existing provisioned identity with a genuinely missing counter remains rejected.

## 6. Regression implementation

Added production-scoped tests:

```text
tests/n3w_production/n3w_first_pair_boot_policy_host_test.cpp
tests/n3w_production/test_n3w_first_pair_boot_policy_behavior.py
tests/n3w_production/test_kf050_first_pair_boot_initialization_contract.py
```

The host behavior regression proves:

```text
PROVEN_FRESH classification
EXISTING_IDENTITY classification with and without valid pending ack
partial/corrupt/mismatched state rejection
missing boot_state -> verified zero floor
existing zero -> idempotent no-write
existing nonzero -> fail closed without rewrite
corrupt/I/O/save/readback mismatch -> fail closed
completed identity + reboot before first telemetry -> session 1 accepted
next reboot -> session 2
existing identity + missing counter -> rejected
```

The source contract proves startup ordering:

```text
startup identity classification
< initial zero-floor preparation
< SimpleProductComponent::setup()
```

and proves delayed zero-floor creation is absent from `begin_boot_session_if_needed_()`.

## 7. Existing pairing multi-key boundary remains explicit

`SimplePairingClient::persist_bundle_()` still persists peer, broker and pending ack as separate durable operations.

This repair does not claim arbitrary power-loss atomicity between those existing writes. Partial/corrupt startup state remains fail closed and is never reclassified as fresh.

This is not a regression introduced by the current change and is outside this bounded KF-050 repair. A generic pairing transaction framework was not added.

## 8. R2 relocation non-regression

The repair does not modify the R2 Broker-relocation algorithm.

The old production convergence test used the removed `persisted_runtime_state_present_()` symbol only as a text slicing boundary. That test initially failed after the repair even though relocation source behavior was unchanged. The contract was corrected to use the new adjacent startup-identity helper as the boundary; all original relocation assertions remain intact.

Frozen non-regression:

```text
R2_BROKER_RELOCATION_CHANGED=false
BROKER_CANDIDATE_RAM_ONLY=true
DURABLE_BROKER_REWRITE=false
MANAGER_REPLAY_RELAXATION=false
MANAGER_HIGH_WATER_CLEAR=false
PAIRING_CRYPTO_CHANGED=false
MQTT_CREDENTIAL_SEMANTICS_CHANGED=false
TELEMETRY_CADENCE_CHANGED=false
```

## 9. CI evidence

### 9.1 Current-head KF-050 and regression evidence

Production convergence run:

```text
RUN=37249123918
HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
AUTO_FALLBACK_PRODUCTION_CONVERGENCE_SOURCE_CONTRACT=PASS
KF050_FIRST_PAIR_BOOT_SESSION_REGRESSION=PASS
PR474_FULL_CHANNEL_REGRESSION_CONTRACT=PASS
GATEWAY_SELECTION_V1_REGRESSION_CONTRACT=PASS
BROKER_RELOCATION_POLICY_HOST_TEST=PASS
PR474_FULL_CHANNEL_HOST_REGRESSION=PASS
GATEWAY_SELECTION_V1_HOST_REGRESSION=PASS
F1_0_RC2_TARGET_CONFIG_VALIDATION=PASS
```

At the closure snapshot, the duplicate F1.0-RC2 compile step in this run was still executing. It is not used as the sole compile authority below.

### 9.2 Exact product-source compile evidence

Earlier production convergence run:

```text
RUN=37248794324
HEAD=3efe1262940c9b70954adda3624c4f556ab45bbb
JOB=production-convergence
CONCLUSION=SUCCESS
F1_0_RC2_TARGET_CONFIG_VALIDATION=PASS
F1_0_RC2_PRODUCTION_COMPILE=PASS
PR474_FULL_CHANNEL_REGRESSION=PASS
GATEWAY_SELECTION_V1_REGRESSION=PASS
BROKER_RELOCATION_REGRESSION=PASS
```

Fresh compare from `3efe126...` to the final source-repair head `157448b...` proves there are no firmware/product-source changes. The only differences are CI/test scoping, test-file moves and the test wrapper path correction.

Therefore:

```text
PRODUCT_SOURCE_EQUAL_BETWEEN_COMPILE_PASS_AND_FINAL_REPAIR_HEAD=true
SOURCE_EQUIVALENT_PRODUCTION_COMPILE=PASS
REQUIRED_SOURCE_REPAIR_CI_EVIDENCE=PASS
```

The later exact-artifact gate must still build and bind a new artifact from the repaired authority. This source-repair compile evidence does not substitute for exact artifact binding.

## 10. CI scope correction during the gate

The first attempt placed the new KF-050 tests under `tests/n3w_phase4/` and temporarily widened greenhouse-manager CI to include the production-core path. That exposed a deliberate Phase5-E guard which treats `greenhouse_n3w_product_core` as retired in the main-line architecture.

That is a different architecture authority from this stacked PR #522 production-core branch. The generic guard was not weakened.

Final organization is:

```text
KF050_TEST_SUITE=tests/n3w_production/
KF050_TEST_AUTHORITY=N3W auto safe fallback production core convergence CI
GREENHOUSE_MANAGER_GENERIC_PHASE5E_GUARD_CHANGED=false
```

This preserves both contracts rather than making one branch's test assumptions override the other.

## 11. Acceptance matrix

```text
EXACT_BASE_BOUND=PASS
SOURCE_CHANGE_MATCHES_DESIGN=PASS
PROVEN_FRESH_CLASSIFICATION_EXPLICIT=PASS
BOOT_FLOOR_ZERO_PREPARED_BEFORE_PAIRING=PASS
BOOT_FLOOR_READBACK_VERIFIED=PASS
ZERO_FLOOR_RESTART_IDEMPOTENT=PASS
NONZERO_OR_BAD_PREPAIR_BOOT_STATE_FAILS_CLOSED=PASS
EXISTING_IDENTITY_MISSING_COUNTER_FAILS_CLOSED=PASS
DELAYED_ZERO_FLOOR_CREATION_REMOVED=PASS
FIRST_PAIR_PRETELEMETRY_REBOOT_REGRESSION=PASS
BOOT_SESSION_MONOTONIC_REBOOT_REGRESSION=PASS
R2_RELOCATION_TESTS=PASS
REQUIRED_CI=PASS
BOARD_ACCESS=false
T1_MUTATION=false
RECOVERY_FLOOR_EXECUTION=false
MANAGER_REPLAY_MUTATION=false
MERGE=false
```

## 12. Artifact-binding inputs

```text
SOURCE_REPAIR_HEAD=157448b621f288c5ac5038e7a1ac906cf2575a7f
SOURCE_REPAIR_TREE=f45ca257de0b6e41f0458346711bb4e105ba1fcc
TARGET_BLOB_SHA=32a2b3cb29be4e1bce46807d8825b6a4c37999ec
TELEMETRY_BRIDGE_BLOB_SHA=ce16f2389d146f9b25e95cbb628547e11ce36bd6
TRANSPORT_BLOB_SHA=aa39d4b083f2db1b30a76efb1afef156db355a35
PRODUCT_CORE_INIT_BLOB_SHA=75949b916144383ae57ebe90ece41e9f248b8cbe
PRODUCT_CORE_HEADER_BLOB_SHA=8132c86f4af91e3a2edc203cfd1ab183d0c06429
FIRST_PAIR_POLICY_BLOB_SHA=c06dd29e1c43a00be6ab3399febe941176ce0177
ESPHOME_VERSION=2026.4.3
```

Any exact artifact used for Final Clean Product-State Gate F must be built from the repaired source authority, not the old R2 artifact.

## 13. Gate disposition

```text
SOURCE_REPAIR=PASS
KF050_FIRST_PAIR_INITIALIZATION_GAP_SOURCE_LEVEL=CLOSED
R2_RELOCATION_REDESIGN=false
OLD_R2_EXACT_ARTIFACT_FINAL_RELEASE_AUTHORITY=false
NEW_REPAIRED_EXACT_ARTIFACT_REQUIRED=true
PHYSICAL_EXECUTION_AUTHORIZED=false
BOARD_ACCESS=false
T1_MUTATION=false
PR_522_MERGE=false
```

Next gate:

```text
NEXT_ONE_GATE=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_EXACT_ARTIFACT_BUILD_AND_BINDING_20261005_01
```

That successor is build/binding only. It does not authorize board flashing, T1 mutation, clean-board pairing, replay/high-water mutation, recovery-floor execution or PR merge.
