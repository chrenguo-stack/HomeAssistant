# N3-W Production Multi-Relay Gateway Selection V1
## Astra Independent Source Review Brief

- Date: 2026-09-22
- Repository: `chrenguo-stack/HomeAssistant`
- Main task: `N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE`
- Subtask: `Production Multi-Relay Gateway Selection V1`
- Review gate: `N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_20260922_01`
- Review mode: independent, read-only source review
- This document is a review briefing, not a replacement for reading the exact design and exact source diff.

---

## 1. What Astra is being asked to do

Independently review the exact Gateway Selection V1 SOURCE_REPAIR implementation against the frozen SOURCE_DESIGN and existing product invariants.

Do **not** assume the SOURCE_REPAIR is correct merely because host tests and CI passed.

The review should answer:

1. Does exact source `97e6d789...` faithfully implement the frozen design?
2. Are there correctness bugs, state-machine gaps, radio-ownership regressions, timing races, resource-bound problems, or error-path problems not covered by the tests?
3. Are Direct recovery, active-Relay stickiness, Option-B telemetry semantics, and the frozen PR #437 lab boundary preserved?
4. Are the tests strong enough to prove the intended source behavior, or do important cases remain untested?
5. Is the source safe to advance to a later exact-artifact build/physical gate, or are source changes still required?

Please classify findings as:
- BLOCKING
- NON_BLOCKING
- TEST_GAP
- DOCUMENTATION_ONLY

Do not modify source in this review gate unless separately authorized.

---

## 2. Exact authorities

### Repository / source baseline

```text
FRESH_MAIN=
3b4a75b039a8d5d9572b4a8f7cfb1e580e7f3476

PRODUCTION_SUCCESSOR_SOURCE_BASE=
c1b3d9d016d06c21c9ff7070c0043163739565ca

PRODUCTION_SUCCESSOR_SOURCE_TREE=
0c857fb0f830239717a2e937d176903a6acae8ac
```

The production N3-W fork `greenhouse_n3w_product_core` exists on the production-successor branch, not on current `main`.

### Frozen SOURCE_DESIGN

```text
DESIGN_BRANCH=
docs/n3w-production-multi-relay-gateway-selection-v1-source-design-20260922

DESIGN_HEAD=
1f628983820646ed53157cdd77d6ba39b9d5de86

DESIGN_DOC=
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260922.md

SOURCE_DESIGN_REVIEW=
PASS_AFTER_DOC_CORRECTION
```

### Prior physical role-symmetry authority

```text
ROLE_SWAP_PHYSICAL_AUTHORITY=
61fc6537fa5b856e8797d21af0c40b2159176981

ROLE_SWAP_CLOSURE_DOC=
docs/development/N3W_PR437_A_B_RELAY_ROLE_SWAP_PHYSICAL_ACCEPTANCE_CLOSURE_20260922.md
```

That closure proves the existing PR #437 artifact can operate with either Board A or Board B as Relay/Child in the tested two-board topology.

### Exact SOURCE_REPAIR under review

```text
SOURCE_REPAIR_BRANCH=
fix/n3w-production-multi-relay-gateway-selection-v1-source-repair-20260922

SOURCE_REPAIR_HEAD=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

SOURCE_REPAIR_TREE=
7dd99defcb27d2869e0fdaf2989afa4992480014

BASE=
c1b3d9d016d06c21c9ff7070c0043163739565ca

AHEAD_BY=
12 commits

BEHIND_BY=
0
```

Dedicated CI:

```text
CI_RUN_ID=
35699836611

CI_HEAD=
97e6d7892d0af8ec3bea28eb450433cfdbd13790

CI_RESULT=
PASS
```

---

## 3. Product background

N3-W is the production local fallback transport for the ESP32-C6 greenhouse node.

At a high level:

- Normal path: node uses Wi-Fi + MQTT directly.
- If Direct becomes unavailable, the node can enter Relay discovery.
- Another N3-W node that still has Direct + MQTT may act as a Relay.
- Child-to-Relay transport uses ESP-NOW.
- The ESP32-C6 has one 2.4 GHz radio, so Direct Wi-Fi recovery and Relay ESP-NOW must not simultaneously fight over radio/channel ownership.
- The current product reliability contract is Option B: ordinary telemetry is buffered until it gets a real transport opportunity, then receives one real transport attempt; application-level resend of every failed sample is not guaranteed.

The existing PR #437 recovery work already addressed major Direct/Relay single-radio problems. Gateway Selection V1 is intentionally a narrow feature on top of that work.

It must **not** become:
- proactive Relay roaming;
- dynamic load balancing;
- a rewrite of Direct recovery;
- an Option-C every-sample durable-delivery design;
- a refactor of the frozen lab implementation.

---

## 4. Why Gateway Selection V1 is needed

The future three-node scenario is:

```text
Board A = Direct + MQTT + Relay-capable
Board B = Direct + MQTT + Relay-capable
Board C = Direct unavailable, enters DISCOVERY
```

Before this work, C effectively chose whichever admissible Relay discovery was processed first.

Frozen source facts at `c1b3d9d...`:

1. `SimpleProductRuntime::handle_discovery_()` immediately starts Challenge for the first admissible Relay.
2. Once `pending_challenge_` exists, later Relay discoveries are rejected.
3. `EspNowDriver` already captures RSSI and channel in `EspNowReceiveMetadata`.
4. `SimpleProductComponent::RxSlot` previously dropped RSSI before passing the packet to runtime.

Therefore the old behavior could not make a deterministic multi-Relay choice based on signal quality.

---

## 5. Frozen product policy

The accepted V1 policy is intentionally simple and stable:

```text
PRIMARY_RANKING=RSSI
RSSI_EQUIVALENT_BAND_DB=3

EQUIVALENT_QUALITY_TIEBREAK=
stable child+relay SHA-256 hash

FINAL_EXACT_HASH_COLLISION_TIEBREAK=
relay_node_id lexical order

ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true

PROACTIVE_ROAMING=false
DYNAMIC_LOAD_BALANCING=false

RESELECTION=
only after the existing active-Relay failure path returns the child to DISCOVERY
```

This means a newly visible stronger Relay must **not** displace a healthy active Relay.

---

## 6. Frozen SOURCE_DESIGN requirements

### 6.1 Candidate collection

Entering `DISCOVERY` does not immediately start a selection timer.

The **first fully admissible Relay discovery** starts one selection epoch:

```text
CANDIDATE_WINDOW_MS=6500
```

During the 6500 ms window:

- keep scanning the existing allowed channels;
- collect/update candidates;
- do not send Challenge yet.

The design rationale is based on the existing:
- channels `{1,6,11}`;
- 250 ms dwell;
- 2000 ms Relay advertisement interval.

### 6.2 Candidate identity

```text
CANDIDATE_DEDUP_KEY=relay_node_id
```

Each candidate contains at least:

- Relay NODE_ID;
- source MAC;
- channel;
- RSSI sum;
- RSSI sample count;
- first-seen time;
- last-seen time;
- attempted flag.

Rules:

- same NODE_ID + same MAC + same channel: add another RSSI sample;
- same NODE_ID + same MAC + new valid channel: refresh channel and reset RSSI aggregate;
- same NODE_ID from a different MAC: identity conflict;
- same MAC claiming a different NODE_ID: identity conflict.

Candidate state is RAM-only and must be cleared at all selection-ending/reset boundaries defined by the design.

### 6.3 RSSI aggregation and comparison

Use arithmetic mean over all valid discovery RSSI samples in the current window.

Store sum + count; do not repeatedly round an average.

Compare means without division:

```text
A_mean > B_mean iff

A.rssi_sum * B.sample_count >
B.rssi_sum * A.sample_count
```

### 6.4 Strongest-anchored 3 dB band

Do not use pairwise “within 3 dB” as a sorting comparator.

For each selection attempt:

1. find strongest unattempted candidate S;
2. form a band containing each unattempted C where:

```text
S_mean - C_mean <= 3 dB
```

3. choose inside that band using the stable hash;
4. after candidate-specific timeout, repeat using remaining candidates.

Example:

```text
-60 / -62 / -64 dBm
```

Initial equivalent band is only `-60 / -62`, not all three.

### 6.5 Stable hash

Frozen primitive:

```text
SHA-256
```

Exact input bytes:

```text
ASCII "N3W-GWSEL-V1"
0x00
u16be(len(CHILD.NODE_ID UTF-8 bytes))
CHILD.NODE_ID UTF-8 bytes
u16be(len(RELAY.NODE_ID UTF-8 bytes))
RELAY.NODE_ID UTF-8 bytes
```

Winner:

- lexicographically smaller unsigned 32-byte digest wins;
- exact digest collision falls back to lexicographically smaller Relay NODE_ID.

The hash is used only inside the <=3 dB equivalent-quality band.

### 6.6 End-of-window behavior

At deadline:

- freeze candidate set;
- select candidate;
- set radio to selected channel;
- build/send existing Challenge;
- create `pending_challenge_` only after successful Challenge submit.

No parallel Relay handshakes and no second active Relay are introduced.

### 6.7 Direct-recovery guard

The existing recovery guard previously covered `challenge_pending()`.

V1 must cover the whole bounded selection transaction:

```text
gateway_selection_busy =
candidate window active
OR pending challenge
OR frozen candidate fallback in progress
```

While busy, Direct presence/full-verify recovery must not cut through the selection transaction.

The existing Direct-recovery backoff policy itself must remain unchanged.

### 6.8 Failure classification

Only a **candidate-specific Challenge timeout** may automatically fall through to the next collected candidate.

Local problems such as:

- nonce/build/encode failure;
- channel fixation failure;
- Challenge submit failure;
- authenticated Accept followed by local channel/peer/state failure;

must not be reinterpreted as “this Relay is bad”.

Invalid/unauthenticated Accept packets must not force an early candidate switch; current pending candidate remains pending until valid Accept or timeout.

### 6.9 No proactive roaming

These invariants must remain true:

- candidate collection only while `DISCOVERY`;
- discoveries rejected while `DIRECT` or `RELAY_ACTIVE`;
- active Relay is not compared with new candidates;
- healthy active Relay remains active;
- existing two-failure Relay path remains the authority that returns the child to `DISCOVERY`;
- only then may a new selection epoch start.

### 6.10 Option-B telemetry contract

Gateway Selection V1 must not change:

- FIFO ordering;
- one real transport attempt per ordinary sample;
- completion ownership;
- no application resend after a real failed transport attempt.

---

## 7. SOURCE_REPAIR changed-file boundary

Exact diff from `c1b3d9d...` to `97e6d789...` contains exactly seven files:

```text
.github/workflows/n3w-production-multi-relay-gateway-selection-v1-ci.yml

firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h

tests/n3w_production/n3w_multi_relay_gateway_selection_v1_host_test.cpp
tests/n3w_production/test_multi_relay_gateway_selection_v1_contract.py
```

No frozen `greenhouse_n3w_core`, `tests/n3w_phase4/**`, or `tests/n3w_kf089/**` file is in the source-repair diff.

---

## 8. What SOURCE_REPAIR actually implemented

### 8.1 Runtime header

`n3w_simple_product_runtime.h` adds:

- 6500 ms candidate-window policy value;
- RSSI-aware `on_radio_receive(..., channel, rssi_dbm)`;
- candidate record;
- selection epoch record;
- attempted flag;
- selection helper methods;
- `gateway_selection_busy()`;
- discovery rejection reasons for identity conflict / invalid RSSI / frozen selection.

### 8.2 Runtime implementation

`n3w_simple_product_runtime.cpp` adds:

- exact `N3W-GWSEL-V1` SHA-256 input encoding;
- first-candidate window creation;
- candidate dedup/update;
- same-node channel refresh with RSSI reset;
- strongest-mean comparison without division;
- strongest-anchored 3 dB band;
- stable hash tie-break;
- final Relay NODE_ID collision fallback;
- deadline freeze;
- Challenge start only after selection;
- candidate-specific Challenge-timeout fallback;
- selection clearing on success/reset/Direct restore/local failure paths;
- selected channel authority during pending Challenge;
- active-Relay stickiness through existing DISCOVERY-only admission.

A later SOURCE_REPAIR correction also enforces the 6500 ms deadline directly inside the discovery receive path, because the component drains queued radio frames before calling `runtime.tick()`.

### 8.3 Component header / implementation

`n3w_simple_product_component.h/.cpp` now:

- retains `rssi_dbm` in `RxSlot`;
- copies `EspNowReceiveMetadata.rssi_dbm` into the ring;
- forwards RSSI into runtime;
- changes Direct-recovery gating from only `challenge_pending()` to `gateway_selection_busy()`.

### 8.4 Tests

New host behavior test covers selection behavior, including:

- single Relay delayed Challenge;
- clear RSSI winner;
- <=3 dB stable hash;
- exact mean tie;
- forced hash-collision fallback;
- strongest-anchored band;
- advertisement order invariance;
- repeated RSSI aggregation;
- channel refresh;
- identity conflict;
- Challenge-timeout fallback;
- local Challenge submit failure;
- invalid Accept behavior;
- authenticated Accept + local channel failure;
- healthy active-Relay stickiness;
- existing two-failure return to Discovery;
- A/B role neutrality at runtime level;
- candidate arriving at 6499 ms;
- candidate first processed at exact 6500 ms rejection.

New Python source-contract tests check the frozen structural invariants.

### 8.5 Dedicated CI

Dedicated CI:

- runs source contract tests;
- compiles and runs the production host behavior test;
- validates the F1.0-RC2 production N3-W target;
- compiles the F1.0-RC2 production N3-W target.

Final exact-head CI `35699836611` passed.

---

## 9. Important implementation-history notes for review

These are not reasons to accept/reject the implementation; they are context for independent review.

### 9.1 Exact-deadline receive-path correction

During SOURCE_REPAIR review of the code flow, it was noticed that the component calls radio-drain processing before `runtime.tick()`.

Therefore a Relay discovery arriving/being processed at the candidate-window deadline could otherwise be admitted before `tick()` froze the epoch.

The implementation was changed so `handle_discovery_()` also rejects a new candidate when:

```text
now >= gateway_selection_epoch_->deadline_ms
```

A host test covers the exact-deadline case.

Astra should independently decide whether using runtime processing time rather than an RX-captured timestamp fully matches the intended timing contract.

### 9.2 Hash-collision test injection

A forced equal SHA-256 result is injected in the host test using the linker `--wrap=mbedtls_md` mechanism.

One intermediate commit had a failed CI because the new collision test was added before the dedicated CI link step had the matching wrapper option.

The final exact HEAD includes the wrapper option and the final CI passes.

Astra should review whether this test genuinely exercises the production fallback path and cannot accidentally mask unrelated SHA-256 behavior.

---

## 10. Prior physical evidence and reliability boundary

The role-swap physical closure predates Gateway Selection V1 and uses the existing PR #437 artifact.

Reversed-role evidence includes:

```text
B_AS_GATEWAY_A_AS_CHILD_DIRECT_TO_RELAY=PASS
B_AS_GATEWAY_A_AS_CHILD_RELAY_CONTINUITY_600S=PASS
B_AS_GATEWAY_A_AS_CHILD_RELAY_TO_DIRECT=PASS
B_AS_GATEWAY_A_AS_CHILD_SAME_BOOT_ROUND_TRIP=PASS

DIRECT_TO_RELAY_MOVE_START_TO_FIRST_RELAY_MS=47144
DIRECT_TO_RELAY_MANAGER_VISIBLE_GAP_MS=27652
DIRECT_TO_RELAY_MISSING_SEQUENCE_COUNT=2
DIRECT_TO_RELAY_MISSING_SEQUENCE_RANGE=179-180

RELAY_600S_EXPECTED_ROWS=121
RELAY_600S_ACCEPTED_ROWS=121
RELAY_600S_MISSING_SEQUENCE_COUNT=0
RELAY_600S_MAX_MANAGER_INTERARRIVAL_SECONDS=31.542

RELAY_TO_DIRECT_MOVE_START_TO_FIRST_DIRECT_MS=65835
RELAY_TO_DIRECT_MANAGER_VISIBLE_GAP_MS=17252
RELAY_TO_DIRECT_MISSING_SEQUENCE_COUNT=0
```

This remains inside the frozen Option-B contract:

```text
DIRECT_TO_RELAY_BOUNDARY_ZERO_LOSS=NOT_GUARANTEED
END_TO_END_EVERY_SAMPLE_DELIVERY=false
```

Do not reopen KF-096 merely because two sequence numbers were absent at the Direct->Relay boundary in that accepted Option-B test.

---

## 11. Critical boundary: current communication tests do not yet use real sensor data

The current physical communication tests and role-swap evidence did **not** include live greenhouse sensor measurements as the exercised application payload.

Freeze this distinction:

```text
REAL_SENSOR_DATA_USED_IN_CURRENT_COMMUNICATION_PHYSICAL_TEST=false

REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
```

The F1.0-RC2 production target includes the production telemetry bridge and compiles successfully, but compile success is **not** physical proof that live SCD30 / soil RS485 / illuminance / battery data has already traversed:

```text
sensor acquisition
-> N3-W telemetry bridge
-> Direct or Relay transport
-> gateway
-> Manager
-> final accepted telemetry
```

That must be a later physical acceptance item.

Do not reject Gateway Selection V1 merely because live-sensor physical acceptance is not part of this source-review gate, but do not claim that acceptance has already happened.

---

## 12. Review questions Astra should inspect carefully

The following are deliberate review targets, not pre-decided defects.

### A. Error propagation and safe recovery

Inspect whether local failures returned by runtime during:

- selected-channel fixation;
- Challenge submit;
- authenticated Accept channel fixation;
- encrypted-peer installation;
- state promotion;

actually reach an existing safe reset/recovery route in the component.

In particular, review all callers that intentionally discard runtime return values, including the normal loop/radio-drain paths.

Question:

> Could SOURCE_REPAIR correctly classify a local failure as `RADIO_FAILED` but then leave the runtime/radio/scan state partially inconsistent because the caller ignores that error?

This must be answered from exact call flow, not from comments.

### B. Candidate window timing semantics

Review:

- first-candidate start time;
- `6499 ms` vs `6500 ms`;
- radio-ring processing order;
- whether using packet-processing time rather than receive timestamp can materially violate the 6500 ms collection contract;
- what happens if the RX ring is delayed/backlogged.

### C. RSSI validity / missing metadata

The driver metadata structure defaults RSSI to `-127`.

The runtime validity range currently treats values in the `[-127, 0]` range as valid.

Review whether an unavailable/missing `rx_ctrl` case can therefore be indistinguishable from a legitimate `-127 dBm` sample, and whether that matters for production ESP-NOW receive behavior.

### D. Candidate-set resource bounds

The selection epoch stores candidates in a vector.

Review:

- practical maximum candidate count within 6500 ms;
- whether an untrusted or noisy environment can cause undesirable heap growth;
- whether identity validation and packet timing provide a sufficient bound for ESP32-C6 production use;
- whether a fixed small bound is required by the product design even though the SOURCE_DESIGN did not explicitly freeze one.

Do not invent a new requirement unless there is a concrete safety/reliability reason.

### E. RSSI arithmetic correctness

Check exact signed arithmetic for:

- negative RSSI sums;
- cross multiplication;
- 3 dB band formula;
- repeated sample counts;
- possible overflow under real bounds;
- total ordering of candidates after attempted candidates are removed.

### F. Hash encoding correctness

Verify byte-for-byte:

```text
"N3W-GWSEL-V1"
NUL
u16be(child length)
child UTF-8 bytes
u16be(relay length)
relay UTF-8 bytes
```

Check:

- byte lengths, not character counts;
- unsigned lexicographic digest comparison;
- exact-collision NODE_ID fallback;
- test injection only affects the intended selection hash scenario.

### G. Candidate identity and channel refresh

Check same-node/same-MAC/new-channel behavior and verify old-channel RSSI cannot remain mixed into the refreshed candidate.

Check both identity-conflict directions.

### H. Timeout fallback

Check:

- timeout only after a successfully submitted Challenge;
- selected candidate becomes attempted;
- next candidate is selected from the already frozen set;
- no new 6500 ms window opens while unattempted candidates remain;
- exhaustion clears epoch and returns to ordinary Discovery scanning;
- scan/channel state is coherent after fallback/exhaustion.

### I. Invalid Accept handling

Check that malformed, wrong-source, wrong-channel, wrong-node, wrong-generation, wrong-nonce, or unauthenticated Accept:

- cannot activate Relay;
- cannot prematurely mark the candidate failed;
- leaves the correct pending Challenge alive until valid Accept or timeout.

### J. Authenticated Accept + local failure

Check all partial-state cleanup when cryptographic verification succeeds but local channel/peer/path setup fails.

Particularly verify no stale encrypted peer, stale pending Challenge, stale selection epoch, or false `RELAY_ACTIVE`.

### K. Direct recovery vs selection ownership

Check `gateway_selection_busy()` across:

- collection window;
- pending Challenge;
- timeout fallback;
- candidate exhaustion;
- local error;
- success.

Check Direct recovery cannot cut through selection, but also cannot be suppressed indefinitely by a stale selection state.

### L. Active Relay stickiness

Verify new/stronger Relay advertisements while `RELAY_ACTIVE` cannot start ranking or Challenge.

Verify the existing two-failure path is still the only ordinary active-Relay reselection trigger.

### M. Selected-channel / rebind behavior

SOURCE_REPAIR changes `working_channel()` and `rebind_radio_state()` so a pending Challenge's selected channel is authoritative.

Check this is correct for:

- Direct recovery temporary ownership changes;
- Relay restore;
- scan state;
- pending Challenge;
- fallback to another candidate.

### N. Option-B telemetry regression

Although Gateway Selection V1 does not intentionally alter the telemetry queue, `n3w_simple_product_component.cpp` is modified.

Verify no change to:

- FIFO order;
- one real attempt;
- in-flight completion ownership;
- drop-after-real-failed-attempt rule;
- no application resend;
- Direct/no-MQTT accounting behavior.

### O. Test adequacy

Compare the exact tests against the full 23-case SOURCE_DESIGN regression matrix.

Identify any case that is:
- only asserted by source-text matching;
- simulated incompletely;
- not actually exercised;
- dependent on a mock that cannot reproduce the important failure;
- still requires later physical RF proof.

---

## 13. Frozen 23-case SOURCE_DESIGN regression matrix

Astra should map each item to exact source/test evidence:

1. Single Relay.
2. Two Relays, clear RSSI winner.
3. Two Relays within 3 dB.
4. Exact mean RSSI tie.
5. Hash collision fallback.
6. Strongest-anchored band.
7. Advertisement-order invariance.
8. Repeated same-channel RSSI update.
9. Channel refresh and RSSI reset.
10. Identity conflict.
11. Challenge local submit/radio failure.
12. Selected Relay Challenge timeout fallback.
13. Invalid/unauthenticated Accept.
14. Authenticated Accept + local peer/channel/state failure.
15. Selection-busy Direct-recovery guard.
16. Healthy active Relay + stronger new advertisement.
17. Existing active-Relay failure threshold -> Discovery -> new epoch.
18. Direct recovery preservation.
19. Option-B telemetry preservation.
20. A/B role symmetry.
21. Three-node A+B Direct, C selects by RSSI/hash rather than first advertisement.
22. RSSI plumbing from driver metadata through RX ring into runtime.
23. Worst-phase candidate timing within the frozen 6500 ms model.

For each, classify:

```text
SOURCE_PROVEN
HOST_TEST_PROVEN
CONTRACT_TEST_ONLY
COMPILE_ONLY
PHYSICAL_PROOF_REQUIRED
NOT_PROVEN
```

Multiple classifications may apply.

---

## 14. What this review must not do

Do not:

- merge the source-repair branch;
- build/bind a production exact artifact;
- flash Board A or Board B;
- access Board USB/serial/NVS;
- mutate T1, Manager, Broker, DynSec, TLS, or credentials;
- modify PR #469;
- change `greenhouse_n3w_core`;
- edit `tests/n3w_phase4/**` or `tests/n3w_kf089/**`;
- introduce proactive roaming;
- introduce dynamic load balancing;
- redesign Option B into durable every-sample delivery;
- treat missing live-sensor physical acceptance as if it were already proven.

This is a source review gate.

---

## 15. Exact files Astra should read

Read the design first:

```text
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260922.md
@ 1f628983820646ed53157cdd77d6ba39b9d5de86
```

Read prior role-symmetry evidence:

```text
docs/development/N3W_PR437_A_B_RELAY_ROLE_SWAP_PHYSICAL_ACCEPTANCE_CLOSURE_20260922.md
@ 61fc6537fa5b856e8797d21af0c40b2159176981
```

Then compare exact source:

```text
BASE=
c1b3d9d016d06c21c9ff7070c0043163739565ca

HEAD=
97e6d7892d0af8ec3bea28eb450433cfdbd13790
```

Review all seven changed files listed in section 7.

Also inspect unchanged supporting code when needed, especially:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_espnow_driver.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_espnow_driver.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_runtime.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_radio.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_radio.cpp
```

Inspect callers/callees beyond the diff whenever necessary to prove an error path or state transition.

---

## 16. Requested Astra output

Please return a source-review report in this structure:

```text
=== N3W GATEWAY SELECTION V1 ASTRA SOURCE REVIEW ===

REVIEW_BASE=
REVIEW_HEAD=
DESIGN_HEAD=
ROLE_SWAP_AUTHORITY=

AUTHORITY_BINDING=
CHANGED_FILE_SCOPE=

DESIGN_IMPLEMENTATION_MATCH=
RSSI_PLUMBING=
CANDIDATE_WINDOW=
CANDIDATE_IDENTITY=
RSSI_MATH=
HASH_TIEBREAK=
TIMEOUT_FALLBACK=
LOCAL_FAILURE_HANDLING=
INVALID_ACCEPT_HANDLING=
ACCEPT_LOCAL_FAILURE_CLEANUP=
DIRECT_RECOVERY_GUARD=
ACTIVE_RELAY_STICKINESS=
OPTION_B_PRESERVATION=
RADIO_CHANNEL_OWNERSHIP=
RESOURCE_BOUNDS=
TEST_ADEQUACY=

REAL_SENSOR_PHYSICAL_ACCEPTANCE=
NOT_PART_OF_THIS_SOURCE_REVIEW

BLOCKING_FINDINGS=
NON_BLOCKING_FINDINGS=
TEST_GAPS=

SOURCE_REVIEW=
PASS | REQUEST_CHANGES

READY_FOR_EXACT_ARTIFACT_GATE=
true | false

=== END ===
```

For every BLOCKING or NON_BLOCKING source finding, include:

- file;
- function/region;
- concrete failure scenario;
- why existing tests do or do not catch it;
- smallest safe correction.

Do not give a broad refactor proposal unless the current design genuinely cannot be made safe with a bounded fix.

---

## 17. Suggested Astra chat start prompt

```text
请对 N3-W Production Multi-Relay Gateway Selection V1 做一次独立源码复核。

先阅读：
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_ASTRA_SOURCE_REVIEW_BRIEF_20260922.md

该 review brief 位于：
branch =
docs/n3w-production-multi-relay-gateway-selection-v1-astra-source-review-20260922

注意：brief 分支只用于承载复核说明。真正需要复核的 SOURCE_REPAIR exact HEAD 是：
97e6d7892d0af8ec3bea28eb450433cfdbd13790

SOURCE_BASE：
c1b3d9d016d06c21c9ff7070c0043163739565ca

SOURCE_DESIGN：
1f628983820646ed53157cdd77d6ba39b9d5de86
docs/development/N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260922.md

ROLE_SWAP_PHYSICAL_AUTHORITY：
61fc6537fa5b856e8797d21af0c40b2159176981
docs/development/N3W_PR437_A_B_RELAY_ROLE_SWAP_PHYSICAL_ACCEPTANCE_CLOSURE_20260922.md

请不要直接相信 SOURCE_REPAIR=PASS 或 CI=PASS，要从 exact diff、调用关系、状态机和错误路径独立判断。

重点检查：
1. 6500 ms 候选窗口和截止边界；
2. RSSI 从 driver -> RX ring -> runtime 是否完整且缺失元数据是否安全；
3. 平均 RSSI 与 strongest-anchored 3 dB 数学是否正确；
4. SHA-256 输入编码、稳定裁决和碰撞 fallback；
5. Challenge timeout 和本地 radio/crypto/state failure 是否被严格区分；
6. runtime 返回 RADIO_FAILED 等错误后，component 是否真的进入安全恢复，而不是错误被忽略；
7. pending Challenge / fallback / rebind / scan channel 的单射频所有权是否一致；
8. gateway_selection_busy 是否既能阻止 Direct recovery 穿透，又不会造成永久阻塞；
9. active Relay 是否保持 sticky，没有引入主动漫游；
10. Option-B FIFO/one-attempt/no-resend 语义是否被完整保留；
11. candidate vector / heap / DoS 风险是否有实际工程问题；
12. 23 项 SOURCE_DESIGN regression matrix 中哪些是真正行为测试证明，哪些只是合同检查，哪些仍需实机 RF。

当前通信实机测试没有加入真实传感器数据。
因此：
REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
这不是本轮 SOURCE_REVIEW 的失败条件，但后续产品实机验收必须补上。

本轮只做 read-only SOURCE_REVIEW。
不要 merge，不要构建 production exact artifact，不要烧板，不要访问 T1。
最后给出 PASS 或 REQUEST_CHANGES，并列出所有 blocking finding 的最小修复建议。
```

---

## 18. Final review state

```text
SOURCE_DESIGN=FROZEN
SOURCE_REPAIR=IMPLEMENTED
SOURCE_REPAIR_CI=PASS
SOURCE_REVIEW=NOT_YET_COMPLETED

REAL_SENSOR_DATA_PHYSICAL_ACCEPTANCE=NOT_PROVEN

NEXT_ONE_GATE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_REVIEW_20260922_01

AUTO_MERGE=false
AUTO_ARTIFACT_BUILD=false
AUTO_BOARD_FLASH=false
AUTO_PHYSICAL_TEST=false
STOP_AFTER_REVIEW=true
```
