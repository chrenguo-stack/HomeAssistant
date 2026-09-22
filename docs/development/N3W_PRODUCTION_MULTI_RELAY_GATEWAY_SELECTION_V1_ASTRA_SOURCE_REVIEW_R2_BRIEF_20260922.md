# N3-W Production Multi-Relay Gateway Selection V1
## Astra Independent SOURCE_REVIEW R2 Brief

- Date: 2026-09-22
- Repository: `chrenguo-stack/HomeAssistant`
- Main task: `N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE`
- Subtask: `Production Multi-Relay Gateway Selection V1`
- Review gate: `N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_R2_20260922_01`
- Review mode: independent, read-only source review
- Do not modify source, build a production artifact, access boards, or access T1 in this gate.

---

## 1. What Astra is being asked to decide

This is a targeted independent review of the R2 repair.

R1 source review returned:

```text
SOURCE_REVIEW=REQUEST_CHANGES
BLOCKING_FINDINGS=3
READY_FOR_EXACT_ARTIFACT_GATE=false
```

R2 is intended to close exactly those three blockers with a bounded patch, without reopening or redesigning the broader PR #437/KF-096 architecture.

Astra should determine:

1. Did R2 fully close each of the three R1 blocking findings?
2. Did the R2 patch introduce any new blocking source/state-machine/radio-ownership defect?
3. Are the new bounds and error paths actually enforced by runtime + component call flow, not merely represented in tests/comments?
4. Is R2 safe to advance to a later exact-artifact build/physical validation gate?
5. Which remaining gaps are test-only or physical-proof gaps rather than source blockers?

Return either:

```text
SOURCE_REVIEW_R2=PASS
READY_FOR_EXACT_ARTIFACT_GATE=true
```

or:

```text
SOURCE_REVIEW_R2=REQUEST_CHANGES
READY_FOR_EXACT_ARTIFACT_GATE=false
```

Do not accept R2 simply because CI is green.

---

## 2. Exact authorities

### R1 source under prior review

```text
R1_HEAD=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

R1_TREE=
7dd99defcb27d2869e0fdaf2989afa4992480014
```

### R2 source under this review

```text
R2_BRANCH=
fix/n3w-production-multi-relay-gateway-selection-v1-source-repair-r2-20260922

R2_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

R2_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

R2_BASE=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

R2_AHEAD_BY=
12 commits

R2_BEHIND_BY=
0
```

### Original frozen SOURCE_DESIGN

```text
SOURCE_DESIGN_HEAD=
1f628983820646ed53157cdd77d6ba39b9d5de86

SOURCE_DESIGN_DOC=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260922.md
```

### R2 repair-design delta

```text
DESIGN_DELTA_COMMIT=
97bd99b0c9d257a3c5ffaa62c874dd973663e0fc

DESIGN_DELTA_DOC=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_REPAIR_DESIGN_DELTA_20260922.md
```

The design delta is authoritative only for the three R1 blocker repairs and related timing/test clarifications. All unaffected original SOURCE_DESIGN behavior remains frozen.

### Prior physical role-symmetry authority

```text
ROLE_SWAP_PHYSICAL_AUTHORITY=
61fc6537fa5b856e8797d21af0c40b2159176981

ROLE_SWAP_DOC=
docs/development/N3W_PR437_A_B_RELAY_ROLE_SWAP_PHYSICAL_ACCEPTANCE_CLOSURE_20260922.md
```

This physical authority predates Gateway Selection V1 and proves A/B role interchangeability for its bound PR #437 artifact only.

---

## 3. R2 exact diff scope

Compare:

```text
BASE=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c
```

R2 changes exactly six files:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h
tests/n3w_production/n3w_multi_relay_gateway_selection_v1_host_test.cpp
tests/n3w_production/test_multi_relay_gateway_selection_v1_contract.py
```

No workflow-file change was required in R2.

R2 exact diff size relative to R1:

```text
component.cpp: +74 / -5
component.h:   +6 / -1
runtime.cpp:   +58 / -4
runtime.h:     +9 / -0
host test:     +416 / -1
contract test: +179 / -0
```

No frozen `greenhouse_n3w_core`, Phase4 test, KF-089 test, Board, T1, broker, or Manager source is changed by R2.

---

## 4. R1 blocking finding #1

### Finding

R1 runtime returned local failures such as:

```text
RADIO_FAILED
CRYPTO_FAILED
STATE_REJECTED
```

but component code discarded return values from:

```cpp
(void) runtime_.tick();
(void) runtime_.on_radio_receive(...);
```

Therefore a Gateway-selection transaction could be logically cleared while the concrete ESP-NOW radio remained on a selected-candidate channel or had uncertain peer state.

### R2 intended repair

R2 adds:

```text
gateway_selection_local_fault_requires_restore(...)
```

with the intended classification:

```text
selection_busy_before == true
selection_busy_after  == false

AND result is one of:
RADIO_FAILED
CRYPTO_FAILED
STATE_REJECTED
```

`PACKET_REJECTED` must not trigger local-radio recovery.

The component now:

- captures `gateway_selection_busy()` before runtime calls;
- consumes the runtime result;
- stops normal loop processing when a transaction-local fault is detected;
- checks that ownership/state is:
  `RELAY_ESPNOW + DISCOVERY`;
- explicitly calls `radio_.shutdown()` first;
- clears stale RX;
- enters existing bounded `RELAY_RESTORE`;
- uses a new cause:
  `GATEWAY_SELECTION_LOCAL_FAULT`.

This extra teardown step was added because the existing Relay-restore quiesce path normally assumes the old ESP-NOW event source has already been stopped.

### Astra must verify

Do not merely verify that the new helper exists.

Trace exact call flow through:

- `SimpleProductComponent::loop()`
- `SimpleProductComponent::drain_radio_()`
- `SimpleProductComponent::consume_gateway_selection_runtime_result_()`
- `SimpleProductComponent::begin_relay_restore_()`
- `SimpleProductComponent::advance_relay_restore_()`
- `SimpleProductComponent::restore_relay_radio_()`
- `SimpleProductRuntime::rebind_radio_state()`

Check:

1. A local Challenge failure cannot continue processing stale RX or telemetry in the same loop.
2. A local Accept channel/peer/state failure follows the same bounded recovery path.
3. A normal `STATE_REJECTED` packet that does not abort selection cannot incorrectly trigger restore.
4. A transaction-aborting local `STATE_REJECTED` does trigger restore.
5. Failed `radio_.shutdown()` fails safe and cannot hand the live radio to another owner.
6. Clearing RX cannot create an SPSC ring race or corrupt producer/consumer ownership.
7. Restore success returns to a coherent Discovery scan/channel state.
8. Restore exhaustion still reaches the existing bounded fail-safe path.
9. There is no new infinite restore/reselection loop.

Classify blocker #1:

```text
CLOSED
PARTIAL
OPEN
```

with concrete source evidence.

---

## 5. R1 blocking finding #2

### Finding

R1 had:

```cpp
std::vector<RelayCandidate> candidates{};
```

with no candidate count limit.

The 6500 ms candidate collection window bounded time, but did not bound:

- candidate memory;
- candidate count;
- sequential Challenge fallbacks;
- total time `gateway_selection_busy()` could suppress Direct recovery.

Astra's R1 reproduction demonstrated that many candidates could produce a long serial timeout chain.

### R2 frozen bounds

R2 Design Delta freezes:

```text
MAX_GATEWAY_CANDIDATES=8

CANDIDATE_OVERFLOW_POLICY=
DROP_NEW_DISTINCT_KEEP_EXISTING_UPDATES

GATEWAY_SELECTION_TRANSACTION_MAX_MS=30000

CANDIDATE_WINDOW_MS=6500
PENDING_CHALLENGE_TIMEOUT_MS=3000
```

Important: `max_gateway_candidates=8` is independent from `max_relay_children=8`; the same number does not mean the fields have the same semantics.

### R2 intended behavior

- first admissible candidate starts the epoch;
- candidate vector reserves the fixed capacity;
- the ninth distinct candidate is rejected;
- updates to one of the retained eight candidates remain allowed;
- absolute transaction deadline is first-candidate time + 30000 ms;
- transaction hard deadline is checked before ordinary per-candidate timeout fallback;
- no new Challenge starts at/after the hard transaction deadline;
- normal candidate exhaustion calls `begin_discovery_()` rather than merely clearing the vector;
- hard-budget exhaustion calls `begin_discovery_()`;
- ordinary Discovery scan/channel state is therefore concretely re-established before selection stays idle;
- if that re-alignment fails, runtime returns local `RADIO_FAILED`, which blocker #1's component handling must consume.

### Astra must verify

Inspect:

- policy validation;
- candidate insertion;
- identity conflict ordering vs capacity rejection;
- candidate update when full;
- exact transaction start/deadline;
- `tick()` ordering;
- `attempt_next_gateway_candidate_()`;
- candidate exhaustion;
- `begin_discovery_()`;
- `gateway_selection_busy()`;
- Direct recovery guards.

Check:

1. Candidate vector can never exceed eight logical candidates.
2. Existing candidate refresh/update remains possible at capacity.
3. The ninth distinct candidate cannot evict a retained candidate.
4. A hostile stream cannot bypass the cap using identity/channel refresh rules.
5. The transaction cannot remain busy beyond its 30-second bound due only to sequential Challenge timeouts.
6. Equality at the 30-second deadline is treated as expired.
7. No Challenge may start after the hard deadline.
8. Candidate exhaustion re-aligns the concrete scan channel, not just logical state.
9. Hard-budget exhaustion re-aligns the concrete scan channel.
10. A due Direct-recovery probe can regain execution opportunity after transaction termination.
11. A failed scan re-alignment is surfaced into the blocker #1 bounded recovery path.
12. The new 30-second ceiling does not accidentally create proactive roaming or a second radio owner.

Classify blocker #2:

```text
CLOSED
PARTIAL
OPEN
```

---

## 6. R1 blocking finding #3

### Finding

R1 component order is:

```text
drain RX
then runtime.tick()
```

R1 `tick()` expired a Challenge at:

```text
now >= expires_at_ms
```

but `handle_accept_()` did not perform the same deadline check.

Therefore the exact same valid Accept at the exact deadline could either activate Relay or time out depending on whether RX or tick ran first.

### R2 intended repair

Before cryptographic/radio/peer/path side effects, `handle_accept_()` now checks:

```text
now >= pending.expires_at_ms
OR
now >= gateway_selection_epoch.transaction_deadline_ms
```

If expired:

- Accept cannot activate Relay;
- no channel/peer/path side effect occurs;
- receive path returns `PACKET_REJECTED`;
- pending state remains;
- the following normal `tick()` performs the single authoritative timeout/fallback path.

Frozen timing semantics remain:

```text
GATEWAY_SELECTION_TIME_SEMANTICS=
MAIN_LOOP_PROCESSING_TIME
```

This is not an RF-arrival timestamp guarantee.

### Astra must verify

Check:

1. Deadline checks occur before verification side effects and before channel/peer installation.
2. Exact equality is expired.
3. `expires_at_ms - 1` remains admissible.
4. RX-before-tick and tick-before-RX converge to the same final state.
5. Hard transaction deadline also prevents otherwise valid late Accept activation.
6. Expired Accept does not accidentally clear pending before `tick()` has a chance to perform fallback.
7. No duplicated timeout/fallback transition can occur.

Classify blocker #3:

```text
CLOSED
PARTIAL
OPEN
```

---

## 7. R2 tests added or strengthened

R2 expands the host behavior and source-contract tests to cover:

- exact 3 dB equivalent-band boundary;
- fixed known SHA-256 selection digest vector;
- narrow local-fault classification;
- active-selection scan-channel failure;
- exactly eight candidates;
- existing candidate update at capacity;
- ninth distinct candidate rejection;
- eight sequential non-responsive candidates;
- 30-second hard transaction budget;
- valid Accept rejected by hard transaction deadline;
- Accept at `expires_at_ms - 1`;
- Accept exactly at `expires_at_ms`;
- Accept after `expires_at_ms`;
- RX-before-tick vs tick-before-RX convergence;
- peer-install failure with failed best-effort peer cleanup;
- virtual timing model for:
  - three channels;
  - 250 ms dwell;
  - 2000 ms advertisement period;
  - phase variation across the advertisement period.

Astra should still distinguish:

```text
HOST_TEST_PROVEN
SOURCE_CONTRACT_ONLY
FULL_PRODUCT_COMPILE_PROVEN
PHYSICAL_RF_PROOF_REQUIRED
REAL_SENSOR_PHYSICAL_PROOF_REQUIRED
```

Do not treat the virtual timing model as proof of real RF delivery under loss/interference.

---

## 8. Final R2 CI authority

Exact-head dedicated CI:

```text
CI_RUN_ID=
35708774330

CI_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

CI_STATUS=
completed

CI_CONCLUSION=
success
```

All required steps passed:

```text
Gateway Selection V1 source contract=PASS
Build and run Gateway Selection V1 host behavior=PASS
Validate F1.0-RC2 production N3-W target=PASS
Compile F1.0-RC2 production N3-W target=PASS
```

There were failed workflow runs on intermediate commits while the R2 tests were being assembled.

Those intermediate failures are not the final authority. Review exact HEAD `8c445f2b...`.

Do not use final CI success as a substitute for source review.

---

## 9. Existing Gateway Selection invariants that R2 must not regress

The following original V1 policy remains frozen:

```text
CANDIDATE_WINDOW_MS=6500
CANDIDATE_DEDUP_KEY=relay_node_id
RSSI_AGGREGATION=ARITHMETIC_MEAN

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

Astra should verify R2 does not accidentally damage these while repairing the blockers.

---

## 10. Review areas beyond the three blocker closures

R2 is targeted, but Astra should still look for newly introduced defects in these areas.

### A. SPSC RX ring handling

R2 adds `clear_rx_ring_()`.

Verify setting consumer `rx_read_` to current producer `rx_write_` is valid under the existing single-producer/single-consumer memory-order contract and cannot consume a partially published slot.

### B. Shutdown-before-restore sequence

Verify:

```text
local fault
-> radio_.shutdown()
-> clear stale RX
-> begin RELAY_RESTORE
-> callback quiesce
-> restore radio
-> runtime.rebind_radio_state()
```

is compatible with the driver's shutdown/teardown semantics.

Check whether calling `shutdown()` before `begin_relay_restore_()` can invalidate any state required by `rebind_radio_state()`.

### C. Hard budget vs pending Challenge

At the transaction deadline, runtime calls `begin_discovery_()`.

Verify this cannot leave:
- stale pending Challenge;
- stale selected candidate channel;
- stale peer;
- stale scan timer;
- false `gateway_selection_busy`;
- stale encrypted peer.

### D. Hard budget vs Direct recovery

Verify the component can actually run a due Direct recovery after the selection budget ends, rather than immediately re-entering another 6500 ms candidate epoch from queued/stale advertisements.

R2 clears stale RX only on local-fault restore, not on normal transaction-budget exhaustion. Decide whether this is correct.

### E. Candidate cap semantics

Because V1 keeps the first eight distinct candidates and rejects later distinct candidates, the result is no longer globally order-invariant when more than eight valid Gateways exist.

This is an explicitly bounded V1 behavior, not necessarily a bug.

Verify source/test/docs do not falsely claim global strongest-candidate selection beyond the supported eight-candidate set.

### F. Policy arithmetic

Review whether:

```text
gateway_selection_transaction_max_ms > candidate_window_ms
```

is sufficient validation, or whether a more specific relationship with Challenge timeout/candidate count is required for safety.

Do not invent a stronger relationship unless it is actually necessary.

### G. State promotion failure classification

Confirm a transaction-aborting local `STATE_REJECTED` after authenticated Accept correctly routes to bounded restore, while ordinary state rejects do not.

---

## 11. Physical and product acceptance boundaries

Current communication physical tests still did not inject live greenhouse sensor measurements.

Freeze:

```text
REAL_SENSOR_DATA_USED_IN_CURRENT_COMMUNICATION_PHYSICAL_TEST=false

REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
```

This is not a failure condition for this source-review gate.

It remains a later product acceptance requirement.

Likewise, R2 host tests and F1.0-RC2 compile do not prove:

- real three-board Gateway selection;
- real RSSI ranking;
- real scan/advertisement phase behavior;
- real Gateway disappearance/reselection;
- real Direct -> Relay -> Direct behavior for the R2 artifact.

Those are later physical gates after source review and exact-artifact binding.

---

## 12. What Astra must not do

Do not:

- modify R2 source;
- merge R2;
- create/build a production exact artifact;
- flash Board A/B/C;
- access Board USB/serial/NVS;
- access or mutate T1;
- mutate Manager/Broker/DynSec/TLS/credentials;
- modify PR #469;
- modify frozen `greenhouse_n3w_core`;
- add proactive roaming;
- add dynamic load balancing;
- turn Option B into every-sample durable resend.

This gate is read-only source review.

---

## 13. Required Astra output

Please return:

```text
=== N3W GATEWAY SELECTION V1 SOURCE REVIEW R2 ===

REVIEW_BASE=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

REVIEW_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

SOURCE_DESIGN_HEAD=
1f628983820646ed53157cdd77d6ba39b9d5de86

DESIGN_DELTA=
97bd99b0c9d257a3c5ffaa62c874dd973663e0fc

AUTHORITY_BINDING=
CHANGED_FILE_SCOPE=

R1_BLOCKER_1_LOCAL_FAULT_CONSUMPTION=
CLOSED | PARTIAL | OPEN

R1_BLOCKER_2_RESOURCE_AND_TRANSACTION_BOUNDS=
CLOSED | PARTIAL | OPEN

R1_BLOCKER_3_ACCEPT_DEADLINE_ORDERING=
CLOSED | PARTIAL | OPEN

R2_NEW_BLOCKING_FINDINGS=
R2_NON_BLOCKING_FINDINGS=
R2_TEST_GAPS=

RX_RING_CLEAR_SAFETY=
SHUTDOWN_RESTORE_SEQUENCE=
TRANSACTION_BUDGET_TERMINATION=
DIRECT_RECOVERY_REGAINS_OPPORTUNITY=
CANDIDATE_CAPACITY_SEMANTICS=
ACTIVE_RELAY_STICKINESS=
OPTION_B_PRESERVATION=
RADIO_CHANNEL_OWNERSHIP=

DEDICATED_CI=
PASS

REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=
NOT_PROVEN

SOURCE_REVIEW_R2=
PASS | REQUEST_CHANGES

READY_FOR_EXACT_ARTIFACT_GATE=
true | false

SOURCE_MUTATION=false
BOARD_ACCESS=false
T1_ACCESS=false

=== END ===
```

For every remaining or new source finding, provide:

- severity: BLOCKING / NON_BLOCKING / TEST_GAP / DOCUMENTATION_ONLY;
- exact file;
- function/region;
- concrete failure scenario;
- whether current tests catch it;
- smallest safe correction.

Avoid a broad redesign unless the exact R2 source truly requires it.

---

## 14. Suggested Astra chat start prompt

```text
请对 N3-W Production Multi-Relay Gateway Selection V1 的 R2 修补做一次独立源码复核。

先阅读：

docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_ASTRA_SOURCE_REVIEW_R2_BRIEF_20260922.md

brief 位于：

docs/n3w-production-multi-relay-gateway-selection-v1-astra-source-review-r2-20260922

真正需要复核的 exact source：

R1_BASE=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

R2_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

原始 SOURCE_DESIGN：

1f628983820646ed53157cdd77d6ba39b9d5de86
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260922.md

R2 Design Delta：

97bd99b0c9d257a3c5ffaa62c874dd973663e0fc
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_REPAIR_DESIGN_DELTA_20260922.md

R1 的 Astra 复核结论是 REQUEST_CHANGES，共 3 个 blocker：
1. runtime 本地故障返回后 component 没有真正消费并恢复无线；
2. candidate vector 和整个 selection transaction 无明确上限，可长期压住 Direct recovery；
3. Accept 在 expires_at_ms 边界的结果依赖 drain RX / tick 调用顺序。

本轮不要重新相信“R2 已修好”或“CI 全绿”的结论。请从 exact diff、component/runtime 调用关系、单射频状态机和错误路径独立判断三个 blocker 是否真正 CLOSED，并检查 R2 是否引入新的 blocker。

重点检查：
- local fault -> radio.shutdown -> RELAY_RESTORE -> rebind 的完整性；
- clear_rx_ring_ 的 SPSC 安全；
- max_gateway_candidates=8 是否真正封顶且已有候选仍可更新；
- gateway_selection_transaction_max_ms=30000 是否真正封顶整个 busy 事务；
- 30 秒预算结束后 Discovery 物理信道是否重新对齐；
- Direct recovery 是否真正重新获得机会；
- Accept 在 expiry-1 / exact expiry / expiry+1 和不同调用顺序下是否一致；
- hard transaction deadline 是否同样阻止晚到 Accept；
- R2 是否仍保持 healthy active Relay sticky、无主动漫游、无动态负载均衡；
- Option-B FIFO/one-attempt/no-resend 是否未被破坏。

最终 exact CI：
run 35708774330
head 8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c
result PASS

当前通信实机测试没有加入真实传感器数据：
REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN

这不是本轮 SOURCE_REVIEW R2 的失败条件。

本轮只做 read-only review。
不要 merge、不要 build production artifact、不要烧板、不要访问 T1。

最后给出：
SOURCE_REVIEW_R2=PASS 或 REQUEST_CHANGES
READY_FOR_EXACT_ARTIFACT_GATE=true/false
并对每个 finding 给出最小安全修复建议。
```

---

## 15. Frozen state for this review

```text
R1_SOURCE_REVIEW=REQUEST_CHANGES

R2_SOURCE_REPAIR=IMPLEMENTED
R2_DEDICATED_CI=PASS

R2_SOURCE_REVIEW=NOT_YET_COMPLETED

READY_FOR_EXACT_ARTIFACT_GATE=false
AUTO_MERGE=false
AUTO_ARTIFACT_BUILD=false
AUTO_BOARD_FLASH=false

REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN

NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_R2_20260922_01

STOP_AFTER_REVIEW=true
```
