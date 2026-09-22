# N3-W Production Multi-Relay Gateway Selection V1
## SOURCE_REVIEW R2 Closure

Date: 2026-09-22

```text
TASK=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_R2_20260922_01

REVIEW_BASE=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

REVIEW_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

REVIEW_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

SOURCE_DESIGN_HEAD=
1f628983820646ed53157cdd77d6ba39b9d5de86

DESIGN_DELTA=
97bd99b0c9d257a3c5ffaa62c874dd973663e0fc

DEDICATED_CI_RUN=
35708774330

DEDICATED_CI_RESULT=
PASS
```

## Independent review result

Astra completed a read-only independent R2 source review and returned:

```text
SOURCE_REVIEW_R2=PASS
READY_FOR_EXACT_ARTIFACT_GATE=true
```

The review was bound to the exact R1->R2 diff and did not use later main state.

## R1 blocker closure

```text
R1_BLOCKER_1_LOCAL_FAULT_CONSUMPTION=CLOSED
R1_BLOCKER_2_RESOURCE_AND_TRANSACTION_BOUNDS=CLOSED
R1_BLOCKER_3_ACCEPT_DEADLINE_ORDERING=CLOSED
```

### Blocker 1

R2 now consumes Gateway-selection transaction-local failures at the component boundary.

The verified path is:

```text
runtime local transaction failure
-> component consumes result
-> stop same-loop normal processing
-> radio shutdown
-> clear stale RX
-> bounded RELAY_RESTORE
-> restore/reinitialize
-> runtime rebind
-> resume only after coherent radio state
```

Ordinary packet rejection and non-aborting `STATE_REJECTED` do not enter this recovery path.

### Blocker 2

R2 now freezes:

```text
MAX_GATEWAY_CANDIDATES=8
CANDIDATE_OVERFLOW_POLICY=DROP_NEW_DISTINCT_KEEP_EXISTING_UPDATES
GATEWAY_SELECTION_TRANSACTION_MAX_MS=30000
```

Candidate count is explicitly bounded, the ninth distinct candidate cannot grow the table, existing retained candidates may continue to update, and the whole selection transaction has a non-renewable absolute deadline.

Normal candidate exhaustion and absolute-budget exhaustion return through ordinary Discovery radio alignment before the selection transaction becomes idle.

### Blocker 3

R2 `handle_accept_()` checks both:

```text
pending Challenge expiry
absolute Gateway-selection transaction deadline
```

before channel/peer/path side effects.

Exact deadline equality is expired.

RX-first and tick-first may return different local error classifications after expiry, but they converge to the same final state and cannot activate an expired Relay.

## R2 independent review findings

```text
R2_NEW_BLOCKING_FINDINGS=NONE
R2_NON_BLOCKING_FINDINGS=TEST_AND_PHYSICAL_EVIDENCE_GAPS

RX_RING_CLEAR_SAFETY=PASS_SOURCE_REVIEW
SHUTDOWN_RESTORE_SEQUENCE=PASS_SOURCE_REVIEW
TRANSACTION_BUDGET_TERMINATION=PASS
DIRECT_RECOVERY_REGAINS_OPPORTUNITY=PASS_SOURCE_REVIEW
CANDIDATE_CAPACITY_SEMANTICS=PASS
ACTIVE_RELAY_STICKINESS=PASS
OPTION_B_PRESERVATION=PASS_SOURCE_REVIEW
RADIO_CHANNEL_OWNERSHIP=PASS_SOURCE_REVIEW
```

## Remaining non-blocking gaps

The following are not source blockers but remain future validation work:

1. Component-level fault-injection coverage for:
   - shutdown failure;
   - rebind failure followed by recovery;
   - Relay-restore budget exhaustion.

2. Integrated proof that a due Direct recovery gets the next execution opportunity after selection-budget expiry while stale advertisements exist.

3. Expanded stored regression matrix for:
   - expiry-1 / expiry / expiry+1 in both RX-first and tick-first order;
   - hard transaction deadline in tick-first order.

4. Physical RF proof for:
   - three-board Gateway selection;
   - real RSSI ranking;
   - real scan/advertisement phase behavior;
   - Gateway disappearance and reselection;
   - channel readback;
   - Direct -> Relay -> Direct on the exact R2 artifact.

## Candidate-capacity scope

Gateway Selection V1 supports a bounded candidate set of eight.

When more than eight valid Relay Gateways are simultaneously visible:

```text
GLOBAL_STRONGEST_ACROSS_UNBOUNDED_GATEWAYS=NOT_CLAIMED
```

Selection remains deterministic only within the retained supported candidate set.

## Real-sensor acceptance boundary

No current communication physical test has included live greenhouse sensor data.

Freeze:

```text
REAL_SENSOR_DATA_USED_IN_CURRENT_COMMUNICATION_PHYSICAL_TEST=false
REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
```

This is not a failure of SOURCE_REVIEW R2, but it remains a later product acceptance requirement.

## Gate closure

```text
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_R2=PASS

SOURCE_REPAIR_R2=PASS
DEDICATED_CI=PASS
SOURCE_REVIEW_R2=PASS

READY_FOR_EXACT_ARTIFACT_GATE=true

SOURCE_MUTATION=false
PRODUCTION_ARTIFACT_BUILD=false
BOARD_ACCESS=false
T1_ACCESS=false
MERGE=false

STOP=true
```

## Proposed next gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_EXACT_ARTIFACT_BUILD_AND_BINDING_20260922_01

EXACT_SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

BOARD_FLASH=false
PHYSICAL_EXECUTION=false
AUTO_MERGE=false
```

The next gate should build and bind an exact artifact only. It must not automatically proceed to board write or physical validation.
