# N3-W Production Multi-Relay Gateway Selection V1
## SOURCE_REVIEW Repair Design Delta

- Date: 2026-09-22
- Gate: `N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_REPAIR_DESIGN_DELTA_20260922_01`
- Repository: `chrenguo-stack/HomeAssistant`
- Mutation class: documentation/design only
- Product source mutation: **none**
- Board / T1 / artifact access: **none**

---

## 1. Purpose

This delta closes the three blocking findings from the independent Astra review of exact SOURCE_REPAIR:

```text
SOURCE_REPAIR_BASE=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

SOURCE_REPAIR_TREE=
7dd99defcb27d2869e0fdaf2989afa4992480014

SOURCE_REVIEW=
REQUEST_CHANGES

BLOCKING_FINDINGS=3
```

The original frozen SOURCE_DESIGN remains authoritative for RSSI selection, deterministic tie-breaking, active-Relay stickiness, no proactive roaming, no dynamic load balancing, and Option-B semantics.

This document overrides/adds only the following boundaries:

1. component consumption of local Gateway-selection failures;
2. candidate-count and total-transaction bounds;
3. Accept deadline semantics independent of loop ordering;
4. related regression requirements and timing-language clarification.

No broad radio/recovery redesign is authorized.

---

## 2. Authority chain

```text
PRODUCTION_SOURCE_BASE=
c1b3d9d016d06c21c9ff7070c0043163739565ca

SOURCE_DESIGN_HEAD=
1f628983820646ed53157cdd77d6ba39b9d5de86

SOURCE_DESIGN_DOC=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260922.md

SOURCE_REPAIR_R1_HEAD=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

ASTRA_REVIEW_BRIEF_COMMIT=
9fb8867564fa4616946e25beef6f85643f8ce963

ASTRA_REVIEW_RESULT=
REQUEST_CHANGES
```

R2 must be based on exact `97e6d789...`, not rebuilt from the earlier `c1b3d9d...` baseline.

---

## 3. Finding A — local selection faults must be consumed by the component

### 3.1 Problem

R1 correctly returns local errors such as:

```text
RADIO_FAILED
CRYPTO_FAILED
STATE_REJECTED
```

from selected-candidate operations, but the component currently discards results from:

```cpp
(void) runtime_.tick();
(void) runtime_.on_radio_receive(...);
```

A transaction can therefore be logically cleared while the concrete ESP-NOW radio remains on a selected-candidate channel or has uncertain peer state.

### 3.2 Frozen R2 classification

Do **not** treat every `STATE_REJECTED` or every rejected packet as a local radio fault.

Freeze this transaction-local classification:

```text
SELECTION_LOCAL_FAULT =
    gateway_selection_busy_before == true
    AND gateway_selection_busy_after == false
    AND runtime_result IN {
        RADIO_FAILED,
        CRYPTO_FAILED,
        STATE_REJECTED
    }
```

Normal cases that must **not** enter Relay restore include:

- `PACKET_REJECTED`;
- ordinary `STATE_REJECTED` while the selection transaction remains busy;
- discovery received outside `DISCOVERY`;
- invalid/unauthenticated Accept while pending remains valid;
- normal candidate timeout/exhaustion that returns `NONE`.

This rule preserves the existing error classification while giving the component an unambiguous way to distinguish a transaction-aborting local fault.

### 3.3 Frozen component action

When a transaction-local fault is detected while:

```text
radio_ownership == RELAY_ESPNOW
path == DISCOVERY
```

the component must:

1. stop consuming further RX slots in that loop;
2. stop ordinary runtime/telemetry/recovery progression for that loop;
3. enter the existing bounded `RELAY_RESTORE` path;
4. use a distinct cause such as:
   `RelayRestoreCause::GATEWAY_SELECTION_LOCAL_FAULT`;
5. let existing shutdown/quiesce/reinitialize/rebind logic restore a coherent Discovery radio state;
6. only after successful restore permit a new selection transaction;
7. if teardown/callback quiesce/rebind cannot be confirmed within the existing restore budget, preserve the existing fail-safe exit/reboot behavior.

The existing restore authority remains:

```text
RelayRestoreBudget:
max attempts = 10
max elapsed = 30000 ms
```

R2 must not invent an unbounded retry loop.

### 3.4 Component loop requirement

Because `loop()` computes its initial recovery state before `drain_radio_()`, R2 must ensure that a restore started from inside radio draining causes an immediate loop-level stop/re-evaluation.

Acceptable implementation shapes include:

```text
drain_radio_() -> bool recovery_started
```

or an equivalent explicit result.

It is **not** sufficient to call `begin_relay_restore_()` and then continue the remainder of the normal loop using stale assumptions.

### 3.5 Scope boundary

This delta repairs Gateway-selection transaction failures.

It does **not** automatically expand into a redesign of every historical runtime error outside Gateway selection.

---

## 4. Finding B — candidate memory and whole transaction must be bounded

### 4.1 Candidate capacity

Freeze a new independent product limit:

```text
MAX_GATEWAY_CANDIDATES=8
```

This is **not** the same semantic field as `max_relay_children`.

The numeric value 8 is frozen independently for Gateway Selection V1 because:

- V1 is a small, local, single-hop greenhouse-node network;
- the immediate accepted topology requires only A/B as possible Gateways for C;
- 8 provides substantial headroom beyond the current three-node acceptance case;
- NODE_ID is already bounded by the protocol;
- a fixed cap gives a hard heap/CPU bound.

If a future deployment requires more than eight simultaneously visible Relay Gateways, that is a future product-policy revision, not an implicit V1 expansion.

### 4.2 Candidate overflow policy

Freeze:

```text
CANDIDATE_OVERFLOW_POLICY=
DROP_NEW_DISTINCT_KEEP_EXISTING_UPDATES
```

When eight distinct candidates are already retained:

- repeated advertisements for an existing retained candidate may continue updating that candidate;
- a ninth new logical candidate is rejected;
- no existing candidate is evicted;
- no dynamic replacement/load-balancing policy is introduced;
- overflow must be diagnosable, for example via a dedicated discovery reject reason such as `CANDIDATE_CAPACITY`.

V1 order-invariance guarantees apply to candidate sets within the supported capacity.

When the environment exceeds the eight-candidate V1 capacity, behavior is deliberately bounded rather than claiming a globally strongest selection across an unsupported number of Gateways.

### 4.3 Whole selection transaction deadline

Freeze:

```text
GATEWAY_SELECTION_TRANSACTION_MAX_MS=30000
```

Start:

```text
transaction_started_ms =
time the first fully admissible candidate starts the selection epoch
```

Deadline:

```text
transaction_deadline_ms =
transaction_started_ms + 30000
```

The existing candidate collection deadline remains:

```text
candidate_window_deadline_ms =
transaction_started_ms + 6500
```

The 30-second absolute transaction budget is independent of:

- candidate count;
- individual Challenge timeout;
- candidate fallback order.

At or after the transaction deadline:

- no Accept may activate a Relay;
- no new candidate Challenge may begin;
- pending Challenge is abandoned;
- the selection epoch is ended;
- ordinary Discovery radio alignment is re-established;
- `gateway_selection_busy()` becomes false only after a coherent transition;
- an already-due Direct recovery gets an execution opportunity before another candidate transaction can monopolize the radio.

### 4.4 Why 30 seconds

With:

```text
candidate window = 6500 ms
candidate cap = 8
normal per-candidate pending timeout = 3000 ms
```

eight full sequential timeouts would otherwise require approximately:

```text
6500 + 8 * 3000 = 30500 ms
```

The 30-second absolute ceiling intentionally wins over the final per-candidate timeout if needed.

This prevents a large or hostile candidate set from extending Direct-recovery suppression indefinitely.

It also stays aligned with the system's existing use of explicit 30-second single-radio hard ceilings in recovery logic, without making the two policies semantically identical.

### 4.5 Terminal Discovery re-alignment

Normal candidate exhaustion or the 30-second absolute deadline must not merely clear the candidate vector while leaving the concrete radio on a stale selected-candidate channel.

Freeze:

```text
NORMAL_SELECTION_EXHAUSTION
OR
TRANSACTION_BUDGET_EXHAUSTION
=>
restore ordinary Discovery scan/channel alignment
=>
then expose gateway_selection_busy=false
```

The existing `begin_discovery_()` behavior, or a narrowly factored equivalent, is the intended authority because it:

- clears pending selection state;
- configures the existing scan plan;
- sets the concrete scan channel;
- updates the next scan-switch time.

If that channel restoration itself fails, it becomes a transaction-local `RADIO_FAILED` and the component must enter the bounded Relay-restore path from section 3.

---

## 5. Finding C — Accept expiry must not depend on loop order

### 5.1 Existing conflict

The component drains RX before calling `runtime.tick()`.

R1 therefore allows this ambiguity at exact Challenge expiry:

```text
drain Accept first -> may activate Relay
tick first         -> Challenge is expired
```

### 5.2 Frozen expiry rule

Use the same processing-time clock already used by R1.

An Accept is admissible only while:

```text
now < pending_challenge.expires_at_ms
AND
now < gateway_selection_transaction_deadline_ms
```

At:

```text
now >= pending_challenge.expires_at_ms
OR
now >= gateway_selection_transaction_deadline_ms
```

that Accept must **not** activate the Relay.

Equality is expired.

### 5.3 Minimal ordering-safe handling

In `handle_accept_()`, before:

- cryptographic side effects;
- channel fixation;
- encrypted-peer installation;
- path promotion;

check the deadline.

If expired:

- reject the Accept;
- do not mutate radio/peer/path state;
- do **not** clear the pending Challenge in the receive handler;
- leave pending state intact so the immediately following normal `tick()` executes the single authoritative timeout/fallback path.

Recommended result:

```text
PACKET_REJECTED
```

This prevents the receive path from duplicating candidate-timeout state transitions and guarantees the same outcome whether RX is drained just before or just after the logical timeout check.

### 5.4 Transaction hard deadline

The same rule applies to the 30-second absolute transaction deadline.

An otherwise valid Accept processed at or after the hard transaction deadline is expired and cannot activate Relay.

---

## 6. Timing semantics clarification

Gateway Selection V1 currently uses **main-loop packet processing time**, not the ESP-NOW ISR/callback receive timestamp, for candidate-window and Accept deadline decisions.

Freeze for V1:

```text
GATEWAY_SELECTION_TIME_SEMANTICS=
MAIN_LOOP_PROCESSING_TIME
```

Consequences:

- a frame physically received before 6500 ms but processed after the deadline may be excluded;
- this is acceptable under the existing contract that the candidate window is bounded discovery, not a guarantee that every RF advertisement is captured;
- R2 does not add an RX timestamp field;
- later physical validation must not describe this as an RF-arrival-time guarantee.

This clarification closes the documentation ambiguity without expanding R2.

---

## 7. Regression delta required for R2

The original 23-case regression matrix remains required.

R2 must additionally prove at least:

### 7.1 Local fault consumption

1. Challenge channel/submit local failure:
   - runtime transaction aborts;
   - component enters Relay restore;
   - no new selection starts before restore succeeds.

2. Authenticated Accept followed by local channel failure:
   - same bounded restore behavior.

3. Encrypted-peer install failure:
   - partial peer cleanup is attempted;
   - regardless of cleanup result, component enters bounded restore;
   - unconfirmed teardown cannot silently resume selection.

4. Local state-promotion failure:
   - ordinary `STATE_REJECTED` packets do not trigger restore;
   - transaction-aborting local `STATE_REJECTED` does trigger restore.

### 7.2 Candidate capacity

5. Exactly 8 distinct candidates are accepted.
6. Existing candidates still update while table is full.
7. Ninth distinct candidate is rejected with capacity diagnostics.
8. Candidate memory cannot grow beyond 8.

### 7.3 Total transaction budget

9. Multiple successful Challenge submissions with no Accept cannot keep `gateway_selection_busy` beyond 30000 ms from the first candidate.
10. Hard deadline ends a pending candidate even if its normal 3000 ms timeout would expire later.
11. After budget exhaustion, ordinary Discovery scan/channel state is coherent.
12. Direct recovery that is already due receives an execution opportunity after selection budget exhaustion.

### 7.4 Accept deadline ordering

13. Valid Accept at `expires_at_ms - 1`: may activate normally.
14. Valid Accept at exactly `expires_at_ms`: cannot activate.
15. Valid Accept after `expires_at_ms`: cannot activate.
16. RX-before-tick and tick-before-RX produce the same expired outcome.
17. Valid Accept at/after the absolute 30000 ms transaction deadline cannot activate.

### 7.5 Original timing-model gap

18. Replace the previous “inject at 6499 ms” interpretation of SOURCE_DESIGN case 23 with an actual virtual-time timing-model test:
   - three channels;
   - 250 ms scan dwell;
   - 2000 ms Relay advertisement period;
   - phase variation sufficient to exercise the worst alignment assumed by the 6500 ms design rationale.

This remains a host timing-model proof, not physical RF proof.

### 7.6 Exact 3 dB edge

19. Add an exact `3 dB` boundary behavior test.

### 7.7 Hash test independence

20. Add at least one fixed known-vector test for the selection hash input encoding/digest generated independently of the production helper.

This is a test-strengthening item, not a newly discovered hash defect.

---

## 8. R2 source allowlist

R2 source mutation, if separately authorized later, remains limited to the existing Gateway Selection allowlist:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.cpp

tests/n3w_production/n3w_multi_relay_gateway_selection_v1_host_test.cpp
tests/n3w_production/test_multi_relay_gateway_selection_v1_contract.py

.github/workflows/n3w-production-multi-relay-gateway-selection-v1-ci.yml
```

No additional source/test/CI path is authorized by this delta.

If implementation proves another file is required:

```text
STOP_ALLOWLIST_EXPANSION_REQUIRED=true
```

---

## 9. Frozen behavior that does not change

R2 must preserve:

```text
CANDIDATE_WINDOW_MS=6500
CANDIDATE_DEDUP_KEY=relay_node_id
CANDIDATE_RSSI_UPDATE_RULE=ARITHMETIC_MEAN
RSSI_EQUIVALENT_BAND_DB=3
RSSI_BAND_ANCHORED_TO_STRONGEST=true

STABLE_HASH_PRIMITIVE=SHA-256
STABLE_HASH_DOMAIN=N3W-GWSEL-V1
HASH_COLLISION_FINAL_TIEBREAK=relay_node_id_lexicographic

ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true
PROACTIVE_ROAMING=false
DYNAMIC_LOAD_BALANCING=false

EXISTING_RELAY_FAILURE_THRESHOLD_TO_DISCOVERY_PRESERVED=true

OPTION_B_QUEUE_ORDERING_PRESERVED=true
OPTION_B_ONE_REAL_ATTEMPT_NO_APPLICATION_RESEND_PRESERVED=true
```

Do not reopen the broader PR #437/KF-096 architecture without new direct counter-evidence.

---

## 10. Real-sensor acceptance remains outside this source repair

Freeze:

```text
REAL_SENSOR_DATA_USED_IN_CURRENT_COMMUNICATION_PHYSICAL_TEST=false
REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
```

R2 source/CI success cannot change these values.

A later product physical gate must separately exercise real sensor acquisition through the full Direct/Relay/Manager path.

---

## 11. Documentation correction

The original SOURCE_DESIGN contains wording equivalent to:

> the earlier 6500 ms draft was insufficient and is superseded by this 6500 ms value

The identical numbers make that sentence internally inconsistent.

This delta does **not** change the frozen value.

Authority remains:

```text
CANDIDATE_WINDOW_MS=6500
```

Treat the original sentence as documentation wording error only.

---

## 12. R2 expected implementation outcome

After a separately authorized R2 source repair, the expected closure must include:

```text
SOURCE_REPAIR_R2_BASE=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

MAX_GATEWAY_CANDIDATES=8
CANDIDATE_OVERFLOW_POLICY=DROP_NEW_DISTINCT_KEEP_EXISTING_UPDATES
GATEWAY_SELECTION_TRANSACTION_MAX_MS=30000

LOCAL_SELECTION_FAULT_COMPONENT_CONSUMPTION=PASS
LOCAL_SELECTION_FAULT_BOUNDED_RESTORE=PASS
LOCAL_STATE_REJECTION_CLASSIFICATION=PASS

ACCEPT_EXACT_DEADLINE_ORDER_INVARIANCE=PASS
TRANSACTION_HARD_DEADLINE_ACCEPT_GUARD=PASS

NORMAL_SELECTION_EXHAUSTION_SCAN_REALIGN=PASS
TRANSACTION_BUDGET_EXHAUSTION_SCAN_REALIGN=PASS
DIRECT_RECOVERY_REGAINS_EXECUTION_OPPORTUNITY=PASS

CANDIDATE_CAPACITY_TEST=PASS
TRANSACTION_BUDGET_TEST=PASS
COMPONENT_FAULT_CONSUMPTION_TEST=PASS
ACCEPT_DEADLINE_TEST=PASS
WORST_PHASE_TIMING_MODEL_TEST=PASS
EXACT_3DB_EDGE_TEST=PASS
HASH_KNOWN_VECTOR_TEST=PASS

OPTION_B_SEMANTICS=PASS
ACTIVE_RELAY_STICKINESS=PASS
PROACTIVE_ROAMING=false
DYNAMIC_LOAD_BALANCING=false

F1RC2_PRODUCTION_COMPILE=PASS
DEDICATED_CI=PASS

REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
```

---

## 13. GitHub CI waiting rule

For subsequent source/compile gates:

```text
LONG_RUNNING_GITHUB_CI_POLLING_POLICY=
DO_NOT_REPEATEDLY_POLL

WHEN_CI_START_CONFIRMED=
RETURN_RUN_LINK_AND_STOP_AT_WAIT_POINT

RECHECK=
ONLY_ON_USER_REQUEST_OR_LATER_EXPLICIT_GATE
```

This avoids long tool loops and does not change CI acceptance criteria.

---

## 14. Gate result

```text
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_REPAIR_DESIGN_DELTA=
PASS

SOURCE_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false
ARTIFACT_BUILD=false

READY_FOR_SOURCE_REPAIR_R2=true

PROPOSED_NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REPAIR_R2_20260922_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
```
