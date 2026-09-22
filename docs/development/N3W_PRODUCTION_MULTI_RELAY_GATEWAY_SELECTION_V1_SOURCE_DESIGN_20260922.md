# N3-W Production Multi-Relay Gateway Selection V1
## Implementation-ready source design

- Date: 2026-09-22
- Gate: `N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01`
- Repository: `chrenguo-stack/HomeAssistant`
- Fresh main at design time: `3b4a75b039a8d5d9572b4a8f7cfb1e580e7f3476`
- Frozen production successor source: `c1b3d9d016d06c21c9ff7070c0043163739565ca`
- Frozen source tree: `0c857fb0f830239717a2e937d176903a6acae8ac`
- Product source mutation in this gate: **none**
- Board / T1 access in this gate: **none**

## 1. Frozen product policy

Gateway Selection V1 replaces the current first-valid-discovery / first-successful-handshake behavior only while the child is in `DISCOVERY`.

The approved policy is:

- primary ranking: received RSSI;
- candidates whose mean RSSI differs by at most 3 dB are treated as equivalent quality;
- equivalent-quality candidates use a stable child+relay hash tie-break;
- an exact hash collision uses Relay NODE_ID lexical order;
- no dynamic load balancing;
- no proactive roaming;
- once a Relay is active and healthy, it remains active;
- reselection occurs only after the existing active-Relay failure path returns the child to `DISCOVERY`.

## 2. Current-source facts

At frozen source `c1b3d9d...`:

1. `SimpleProductRuntime::handle_discovery_()` only accepts discovery while `path == DISCOVERY` and no `pending_challenge_` exists. The first accepted discovery immediately starts Challenge, so later candidates are blocked by the pending challenge.
2. `EspNowDriver` already captures `rx_ctrl->rssi` and `rx_ctrl->channel` in `EspNowReceiveMetadata`.
3. `SimpleProductComponent::on_espnow_receive_with_metadata()` currently stores only source, size and channel in its RX ring. RSSI is therefore dropped before `SimpleProductRuntime::on_radio_receive()`.
4. `SimpleProductPolicy` currently uses `scan_dwell_ms=250`, `challenge_timeout_ms=1500`, `relay_advertisement_interval_ms=2000`, and allowed channels `{1,6,11}`.
5. Active Relay failure already exits through `note_relay_delivery_result(..., false)` -> path controller -> `leave_relay_for_discovery_()`.
6. Discovery packets are already rejected outside `DISCOVERY`, so the current state machine has a natural no-proactive-roaming boundary.

## 3. Candidate lifecycle

### 3.1 Candidate collection starts

Entering `DISCOVERY` does **not** immediately start a fixed selection deadline.

The child keeps the existing channel scan behavior until the first fully admissible Relay discovery is received.

On the first admissible Relay discovery:

- create selection epoch state;
- insert/update that Relay candidate;
- set `candidate_window_deadline_ms = now + 6500`;
- continue normal scan rotation across all allowed channels;
- do **not** send Challenge yet.

This avoids expiring a candidate window before any Relay is actually observed.

### 3.2 Candidate window duration

Freeze:

```text
CANDIDATE_WINDOW_MS=6500
```

Rationale using the frozen source defaults:

- three channels × 250 ms dwell = 750 ms scan cycle;
- Relay advertisement period = 2000 ms;
- advertisement phase relative to a 750 ms scan cycle shifts by 500 ms on each advertisement;
- after the first candidate starts the window, a different Relay may have its next advertisement almost 2000 ms later;
- in the worst phase alignment, up to three advertisement opportunities are needed to cover all three 250 ms channel dwell regions;
- the third opportunity can therefore arrive just under 6000 ms after the window starts;
- 6500 ms adds 500 ms scheduling/loop margin without turning selection into a long recovery backoff.

The earlier 6500 ms draft was insufficient for the worst-case phase offset of a second Relay and is superseded by this 6500 ms value.

This is a bounded collection policy, not a packet-delivery guarantee. RF loss can still prevent a Relay from entering the candidate set.

### 3.3 Candidate identity / dedup

Freeze the logical candidate key as:

```text
CANDIDATE_DEDUP_KEY=relay_node_id
```

Each candidate record contains at least:

- `relay_node_id`
- source MAC
- current channel
- RSSI sum
- RSSI sample count
- first-seen timestamp
- last-seen timestamp
- attempted-in-current-epoch flag

Within one selection epoch:

- a new `relay_node_id` creates one candidate binding;
- the same `relay_node_id` from the same MAC and same channel updates the RSSI aggregate;
- the same `relay_node_id` from the same MAC on a different valid channel is treated as a channel refresh: update to the latest channel and reset the RSSI aggregate to the new-channel sample, so stale RSSI from the old channel is not mixed with the new channel;
- the same `relay_node_id` from a different MAC is an identity conflict and must not overwrite the existing candidate;
- the same MAC claiming a different `relay_node_id` in the same epoch is also an identity conflict and must not create a second logical candidate.

Candidate state is RAM-only and is cleared whenever selection ends, Direct is restored, Relay becomes active, runtime stops, a radio-fault reset occurs, or a fresh Discovery epoch begins.

## 4. RSSI update and comparison

### 4.1 Update rule

Freeze:

```text
CANDIDATE_RSSI_UPDATE_RULE=ARITHMETIC_MEAN_OF_ALL_VALID_DISCOVERY_RSSI_SAMPLES_IN_CURRENT_WINDOW
```

Implementation should store integer `rssi_sum` and `sample_count`; it should not repeatedly round an average.

### 4.2 Exact mean comparison

For candidates A and B, compare mean RSSI without division:

```text
A_mean > B_mean iff:
A.rssi_sum * B.sample_count >
B.rssi_sum * A.sample_count
```

Use a sufficiently wide signed integer for the cross-products.

### 4.3 The <=3 dB band is anchored to the strongest candidate

Do **not** use a pairwise “within 3 dB” comparator as a sort comparator, because that relation is not transitive.

For every pick from the unattempted candidate set:

1. find the strongest mean RSSI candidate `S`;
2. form the equivalent-quality band containing every unattempted candidate `C` satisfying:

```text
S_mean - C_mean <= 3 dB
```

without division:

```text
S.rssi_sum * C.sample_count -
C.rssi_sum * S.sample_count
<=
3 * S.sample_count * C.sample_count
```

3. if the band has one candidate, select it;
4. if the band has multiple candidates, select among that band using the stable hash rule in section 5;
5. after a candidate-specific timeout failure, mark that candidate attempted and repeat the same procedure over the remaining candidates.

Example: means `-60 / -62 / -64 dBm` produce an initial equivalent band of `-60 / -62`; `-64` is not pulled into the first band merely because it is within 3 dB of `-62`.

This gives a deterministic total fallback sequence without using a non-transitive comparator.

## 5. Stable hash tie-break

Freeze:

```text
STABLE_HASH_PRIMITIVE=SHA-256
```

No new cryptographic dependency is required; SHA-256 is already available in the firmware toolchain.

### 5.1 Exact input encoding

For each candidate Relay R and child C, hash the following byte sequence:

```text
ASCII "N3W-GWSEL-V1"
0x00
u16be(len(C.NODE_ID UTF-8 bytes))
C.NODE_ID UTF-8 bytes
u16be(len(R.NODE_ID UTF-8 bytes))
R.NODE_ID UTF-8 bytes
```

NODE_ID lengths are byte lengths, not character counts.

This length-prefixed encoding preserves the approved semantic `HASH(C.NODE_ID || RELAY.NODE_ID)` while eliminating concatenation ambiguity.

### 5.2 Winner

- Compare the 32 SHA-256 digest bytes lexicographically as unsigned bytes.
- The numerically/lexicographically smaller digest wins.
- If the digest bytes are exactly equal, compare `relay_node_id` bytewise lexicographically; the smaller Relay NODE_ID wins.

The hash is used only inside the <=3 dB equivalent-quality band. It is not a load metric and does not cause roaming.

## 6. End-of-window selection and radio-ownership guard

At `candidate_window_deadline_ms`:

- freeze the collected candidate set for the current epoch;
- if the set is empty, clear selection state and continue ordinary Discovery scanning;
- otherwise choose one candidate using the strongest-anchored RSSI band plus stable hash rule;
- set radio to that candidate channel;
- build/send the existing Challenge;
- only after a successful Challenge submit create `pending_challenge_`.

No second active Relay or parallel handshake is introduced.

### 6.1 Do not let Direct recovery cut through an active selection epoch

The component currently suppresses Direct recovery while `runtime_.challenge_pending()` is true. Gateway Selection V1 must extend that guard to the whole bounded selection transaction.

Freeze a runtime query equivalent to:

```text
gateway_selection_busy =
    candidate_window_active
    OR pending_challenge
    OR frozen_candidate_fallback_in_progress
```

While this is true, `SimpleProductComponent::advance_recovery_()` must not start a Direct presence/full-verify probe. This defers an already-scheduled Direct recovery probe only for the bounded candidate/handshake transaction; it does not change the existing Direct-recovery backoff policy.

Any explicit runtime reset/radio-fault reset clears selection state before a fresh Discovery epoch.

## 7. Challenge / Accept failure behavior

The design distinguishes **candidate-specific non-response** from **local radio/crypto/state failure**. Only the former falls through to the next ranked candidate.

### 7.1 Challenge preparation or local submit failure

If nonce generation, packet construction, encoding, channel fixation, or Challenge submit fails:

- do not activate the candidate;
- do not reinterpret the failure as “that Relay is bad”;
- preserve the existing `CRYPTO_FAILED` / `RADIO_FAILED` / state-fault classification;
- clear/fail the current selection transaction through the existing safe Discovery/radio-fault route;
- do **not** immediately try another candidate on a local radio/crypto path that is already known to be unhealthy.

### 7.2 Challenge timeout — candidate-specific failure

A Challenge that was successfully submitted retains the existing bounded pending timeout:

```text
PENDING_CHALLENGE_TIMEOUT_MS = 2 * challenge_timeout_ms = 3000 ms
```

If no valid authenticated Accept is received by that deadline:

- clear `pending_challenge_`;
- mark the selected candidate attempted/failed for the frozen epoch;
- choose the next candidate by repeating the section 4.3 selection procedure over the remaining unattempted candidates;
- do not open a new 6500 ms collection window while already-collected candidates remain;
- if all collected candidates are exhausted, clear the epoch and return to ordinary Discovery scanning; the next admissible discovery starts a fresh 6500 ms window.

### 7.3 Invalid or unauthenticated Accept does not force an early switch

If an Accept has the wrong source/channel/Relay identity, wrong trust generation/nonce, or fails authentication:

- reject that packet exactly as today;
- keep the current candidate pending until a valid Accept arrives or the 3000 ms deadline expires;
- do not mark the candidate failed immediately merely because one invalid packet was received.

This prevents an unrelated or spoofed invalid Accept from forcing deterministic fallback.

### 7.4 Authenticated Accept followed by local radio/state failure

If Accept authentication succeeds but concrete channel fixation, encrypted-peer installation, or path promotion fails:

- never activate the candidate;
- preserve the existing local radio/state failure classification;
- remove any partially installed peer when required by the existing path;
- abandon the current selection epoch and use the existing safe radio-fault/fresh-Discovery route;
- do not immediately try the next candidate on a possibly inconsistent local radio state.

### 7.5 Success

Only the existing fully verified Accept path may set:

```text
active_relay_ = selected_relay
path = RELAY_ACTIVE
```

On success, clear all candidate-selection state.

## 8. No-proactive-roaming proof

The implementation must keep these invariants:

1. Candidate collection and ranking code is reachable only when `path_.state() == DISCOVERY`.
2. `handle_discovery_` continues to reject discovery while `DIRECT` or `RELAY_ACTIVE`.
3. No RSSI comparison is executed against `active_relay_`.
4. A stronger/new Relay advertisement while `RELAY_ACTIVE` is ignored/rejected by state and cannot start a candidate window.
5. The existing active-Relay health rule remains authoritative: `relay_failures_to_discovery=2`. Two qualifying failed delivery results drive the existing `RELAY_ACTIVE -> DISCOVERY` transition.
6. Only after that transition (or an existing reset/radio-fault route) may a fresh candidate-selection epoch start.
7. Direct recovery scheduling remains owned by the existing recovery code. Gateway Selection V1 adds only the bounded “selection busy” deferral so a probe cannot cut through candidate collection/handshake.
8. Ordinary Option-B telemetry queue and one-attempt delivery semantics are unchanged.

Therefore:

```text
ACTIVE_RELAY_HEALTHY => NO_GATEWAY_RESELECTION
STRONGER_RELAY_DISCOVERED_WHILE_ACTIVE => IGNORED/STATE_REJECTED
ACTIVE_RELAY_FAILED_BY_EXISTING_THRESHOLD
  => EXISTING_RETURN_TO_DISCOVERY
  => NEW_SELECTION_EPOCH
```

Direct failback to Wi-Fi remains an existing independent product behavior; it is not Relay-to-Relay proactive roaming.

## 9. Source changed-file allowlist for the later SOURCE_REPAIR gate

Product-source modifications must be limited to:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.cpp
```

Expected purpose:

- runtime h/cpp: candidate epoch/state, RSSI aggregate, deterministic strongest-band/hash selection, timeout fallback, RSSI-aware receive signature, selection-busy query;
- component h/cpp: retain RSSI in `RxSlot`, pass it into runtime, and extend the existing Direct-recovery guard across the bounded selection transaction.

The ESP-NOW driver already captures RSSI and therefore is **not** in the initial source allowlist. The frozen PR #437 lab component is not in the allowlist and must remain unchanged.

Test-file allowlist:

```text
tests/n3w_phase4/n3w_phase4_runtime_host_test.cpp
tests/n3w_phase4/test_phase4_source_contract.py
tests/n3w_kf089/test_relay_discovery_observability_contract.py
tests/n3w_phase4/test_multi_relay_gateway_selection_v1_contract.py   # new
```

The KF-089 observability test is explicitly included because its current host helper assumes the first discovery immediately creates `pending_challenge_`; that assertion becomes stale once the candidate window is introduced.

If implementation proves another product or test file is required, SOURCE_REPAIR must stop and expand the allowlist explicitly rather than editing opportunistically.

## 10. Regression matrix

The later SOURCE_REPAIR gate must prove at least:

1. **Single Relay**: one valid Relay starts a 6500 ms collection window, then handshakes and becomes active.
2. **Two Relays, clear RSSI winner**: strongest mean is >3 dB above the other; stronger candidate wins regardless of advertisement arrival order.
3. **Two Relays, within 3 dB**: stable hash decides.
4. **Exact mean RSSI tie**: stable hash decides.
5. **Hash collision fallback**: injected/mock equal digest uses Relay NODE_ID lexical order.
6. **Strongest-anchored band**: e.g. `-60/-62/-64 dBm` does not create a transitive three-candidate tie.
7. **Order invariance**: the same candidate samples in different advertisement order produce the same winner.
8. **Repeated advertisement update**: multiple same-channel RSSI samples update the arithmetic mean correctly.
9. **Channel refresh**: same NODE_ID+MAC on a new valid channel replaces channel and resets that candidate's RSSI aggregate to the new-channel sample.
10. **Identity conflict**: same NODE_ID with a different MAC, or same MAC with a different NODE_ID, cannot overwrite/create an ambiguous candidate.
11. **Challenge local submit/radio failure**: does not get misclassified as a candidate miss and does not blindly try the next Relay.
12. **Selected Relay Challenge timeout**: next-ranked collected candidate is attempted without a new 6500 ms window; exhaustion returns to ordinary Discovery.
13. **Invalid/unauthenticated Accept**: no activation and no early candidate switch; pending remains until valid Accept or timeout.
14. **Authenticated Accept + peer/channel/state failure**: no activation; local fault route is preserved; no immediate next-candidate attempt.
15. **Selection busy guard**: scheduled Direct recovery does not cut through candidate collection or pending Challenge.
16. **Healthy active Relay + stronger new advertisement**: active Relay remains unchanged; no candidate window/Challenge starts.
17. **Active Relay delivery failure threshold reached**: existing two-failure path returns to Discovery; a new selection epoch can choose a different Relay.
18. **Direct recovery**: existing Direct probe/commit behavior is unchanged apart from bounded deferral during selection.
19. **Option-B telemetry**: queue ordering, single-attempt completion ownership, and no-resend policy are unchanged.
20. **A/B role symmetry**: the same runtime permits either node to be Relay when Direct+MQTT and the other to be Child after losing Direct.
21. **Three-node scenario**: A and B both Direct/relay-capable; C in Discovery chooses according to RSSI/hash rules, not first advertisement.
22. **RSSI plumbing**: driver metadata RSSI survives RX ring queueing and reaches runtime unchanged.
23. **Candidate-window timing**: second Relay with worst-case advertisement phase is still collectible inside 6500 ms under the frozen 250/2000 ms timing model.

## 11. Later physical acceptance outline

Source/host CI cannot close the physical role/reselection gap. A later explicitly authorized physical gate should separately test:

- A as Gateway / B as Child;
- B as Gateway / A as Child;
- A and B both Direct while C loses Direct;
- clear RSSI winner;
- <=3 dB deterministic tie case where practical or with controlled attenuation;
- active Gateway remains sticky while the other Gateway becomes stronger;
- active Gateway disappears, then C re-enters Discovery and selects a surviving Gateway;
- no regression to Direct -> Relay -> Direct continuity and single-radio channel ownership.

## 12. PR #469 separation

PR #469 remains a separate Board-B readonly-preflight route.

At design time:

```text
PR469_STATE=OPEN
PR469_HEAD=d9f6a4d33b8354053e736c71e887b176236a79d9
PR469_DEDICATED_PREFLIGHT_CI=PASS
PR469_PUBLIC_REPOSITORY_SAFETY=FAIL
PR469_MUTATION_IN_THIS_GATE=false
```

Gateway Selection V1 does not repair, merge, or otherwise mutate PR #469.

## 13. Gate closure

```text
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN=PASS

CANDIDATE_WINDOW_MS=6500
CANDIDATE_DEDUP_KEY=relay_node_id
CANDIDATE_RSSI_UPDATE_RULE=ARITHMETIC_MEAN
RSSI_EQUIVALENT_BAND_DB=3

STABLE_HASH_PRIMITIVE=SHA-256
STABLE_HASH_INPUT_ENCODING=DOMAIN_TAG_NUL+U16BE_LEN+CHILD_UTF8+U16BE_LEN+RELAY_UTF8
FINAL_COLLISION_RULE=RELAY_NODE_ID_LEXICOGRAPHIC

ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true
PROACTIVE_ROAMING=false
DYNAMIC_LOAD_BALANCING=false
ACTIVE_RELAY_FAILURE_RESELECTION=true

PRODUCT_SOURCE_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false

READY_FOR_GATEWAY_SELECTION_V1_SOURCE_REPAIR=true
AUTO_EXECUTE_SOURCE_REPAIR=false
STOP=true
```
