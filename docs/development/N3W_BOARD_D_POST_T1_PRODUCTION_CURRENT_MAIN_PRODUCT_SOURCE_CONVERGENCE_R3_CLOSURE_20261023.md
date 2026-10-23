# N3-W Board_D current-main 产品源码收敛 R3 Closure — 2026-10-23

## 1. Closure

```text
TASK=N3W_BOARD_D_POST_T1_PRODUCTION_CURRENT_MAIN_PRODUCT_SOURCE_CONVERGENCE_SOURCE_REPAIR_R3_20261023_01

BASE_MAIN=5ff09efb650cc3818d2c6a58d4fb4c489a21d784
R3_BASE_PRODUCT_HEAD=87cff4424ddee9e13e47c9326a731725bd25aad1
R3_EXACT_PRODUCT_SOURCE_HEAD=9a2024212566d831d94b167833d5485307119d78
MAIN_DRIFT=false

AUTO_SAFE_FALLBACK_IN_CURRENT_CORE=true
SECOND_RECOVERY_STATE_MACHINE=false
RAM_ONLY_BROKER_RETARGET=true
BROKER_NVS_REWRITE=false
TLS_IDENTITY_PRESERVED=true
BOUNDED_ROLLBACK=true
BROKER_ROLLBACK_FAILURE_SAFE_REBOOT=true

R1_REGRESSION=NOT_OBSERVED
R2_REGRESSION=NOT_OBSERVED

EXACT_HEAD_WORKFLOW_TOTAL=30
EXACT_HEAD_WORKFLOW_SUCCESS=27
EXACT_HEAD_WORKFLOW_FAILURE=3
EXACT_HEAD_WORKFLOW_PENDING=0
RELEVANT_CI=PASS

LEGACY_STAGE2D2_BOUNDARY_FALSE_FAIL=true
LEGACY_STAGE2D3_BOUNDARY_FALSE_FAIL=true
LEGACY_STAGE2D4_BOUNDARY_FALSE_FAIL=true

FALSE_PASS_PATH_DETECTED_DURING_FINAL_REVIEW_COUNT=1
FALSE_PASS_PATH_REPAIRED_COUNT=1
OPEN_NEW_FALSE_PASS_PATH_COUNT=0

R3_SOURCE_BLOCKER_COUNT=0
R3_SOURCE_REPAIR_REQUIRED=false
R3_CLOSURE=CLOSED_PASS

PR656_MERGE_READY=false
R4_ENTERED=false

LIVE_RUNTIME_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
FLASH_MUTATION=false
NVS_MUTATION=false
RF_EXECUTION=false
MERGE=false

NEXT_ROUTE=R4_IF_R3_CLOSED_PASS_AND_SEPARATELY_ENTERED
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```

## 2. Scope actually closed

R3 integrates Broker Auto Safe Fallback into the active
`firmware/esphome_rc/components/greenhouse_n3w_core` product path. The retired
`greenhouse_n3w_product_core` and `greenhouse_n3w_product_runtime` directories
were not restored.

The implemented behavior is bounded to the frozen R3 semantics:

- Direct Wi-Fi remains associated while MQTT is continuously unavailable.
- After the bounded failure threshold, the node performs Manager discovery.
- Discovered Broker candidates are filtered by system identity, UDP source/IP
  agreement, same-subnet constraints, and bounded TTL.
- Runtime Broker retargeting is RAM-only. Durable Broker state in NVS is not
  rewritten.
- TLS server name, CA, MQTT username/password and client ID remain tied to the
  provisioned durable Broker identity.
- Candidate reconnect is bounded. Candidate failure returns to the durable
  Broker target.
- Successful candidate promotion is current-boot runtime state only.
- Existing Direct/Relay recovery remains the single product recovery state
  machine; R3 does not introduce a second Direct/Relay state machine.
- Existing R2 Multi-Relay selection and full-channel discovery logic are
  preserved.

## 3. Final independent false-PASS review

The first R3 implementation head passed relevant CI, but independent exact-source
review found one CI-uncovered edge: if rollback from a temporary Broker candidate
to the durable Broker target itself failed, the source logged the failed restore
and cleared relocation state. That could leave the runtime Broker destination
uncertain while appearing to have completed rollback.

The final repair at `9a2024212566d831d94b167833d5485307119d78` makes that edge fail closed. If the runtime
rollback cannot restore the durable Broker target, the component requests the
existing safe reboot. Normal startup then reloads the durable Broker configuration
from NVS. The repair adds no candidate persistence and does not alter credentials,
TLS identity, R2 radio policy, or recovery ownership.

Final delta from the prior reviewed head `f83befb907b057418d0d08838ab71f7fe377e6e4`:

- `n3w_simple_product_component_broker_relocation.cpp`: rollback failure
  requests safe reboot.
- `test_current_main_product_source_convergence_r3_contract.py`: contract guard
  requires that fail-closed path.

No additional open false-PASS path was found after this repair.

## 4. Exact-head CI

Exact product source head: `9a2024212566d831d94b167833d5485307119d78`.

Relevant required workflows all passed:

- N3W current-main product source convergence R3 CI — PASS
- F1.0-RC2 firmware CI — PASS
- N3W production multi-relay gateway selection V1 CI — PASS
- N3W production relay discovery full-channel fallback V1 CI — PASS
- greenhouse-manager CI — PASS
- Public repository safety CI — PASS

Repository-wide exact-head summary: 30 workflows total, 27 success, 3 failure,
0 pending.

The three failures are the pre-existing Stage2D2/Stage2D3/Stage2D4 legacy boundary
false-fails already excluded by the R2/R3 handoff. Their functional fault matrices
pass; the failure occurs in historical boundary-gate logic unrelated to this R3
product source change. They are not treated as R3 blockers and are not repaired in
this gate.

## 5. Disposition

R3 is `CLOSED_PASS` at exact product source head `9a2024212566d831d94b167833d5485307119d78`.

This closure does not make PR #656 merge-ready by itself. The approved convergence
program still requires a separately entered R4 integrated source / exact production
artifact closure before any merge decision.

No T1 access, Board access, flash, NVS mutation, RF execution, live runtime
mutation, or merge occurred in R3 closure.
