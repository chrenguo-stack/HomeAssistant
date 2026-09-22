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
- set `candidate_window_deadline_ms = now + 4500`;
- continue normal scan rotation across all allowed channels;
- do **not** send Challenge yet.

This avoids expiring a candidate window before any Relay is actually observed.

### 3.2 Candidate window duration

Freeze:

```text
CANDIDATE_WINDOW_MS=4500
```

Rationale using the frozen source defaults:

- three channels × 250 ms dwell = 750 ms scan cycle;
- Relay advertisement period = 2000 ms;
- advertisement phase relative to a 750 ms scan cycle shifts by 500 ms on each advertisement;
- across three advertisement opportunities, the phase visits all three 250 ms dwell regions;
- therefore a healthy fixed-channel Relay has an opportunity to overlap its channel dwell within at most about 4 seconds in the ideal no-loss case;
- 4500 ms adds one extra 500 ms scheduling/processing margin without turning selection into a long recovery backoff.

This is a bounded collection policy, not a packet-delivery guarantee. RF loss can still prevent a Relay from entering the candidate set.

### 3.3 Candidate identity / dedup

Freeze the candidate key as:

```text
CANDIDATE_DEDUP_KEY=relay_node_id
```

Each candidate record contains at least:

- `relay_node_id`
- source MAC
- channel
- RSSI sum
- RSSI sample count
- first-seen timestamp
- last-seen timestamp
- attempted-in-current-epoch flag

For the same `relay_node_id` within one selection epoch:

- updates are accepted only when source MAC and channel match the first accepted binding;
- a conflicting MAC or channel does not overwrite the candidate and is rejected/diagnosed;
- this prevents one logical candidate from silently changing its transport binding during ranking.

Candidate state is RAM-only and is cleared whenever selection ends, Direct is restored, Relay becomes active, runtime stops, or a new discovery epoch begins.

## 4. RSSI update and comparison

### 4.1 Update rule

Freeze:

```text
CANDIDATE_RSSI_UPDATE_RULE=ARITHMETIC_MEAN_OF_ALL_VALID_DISCOVERY_RSSI_SAMPLES_IN_CURRENT_WINDOW
```

Implementation should store integer `rssi_sum` and `sample_count`; it should not repeatedly round an average.

### 4.2 Exact comparison

For candidates A and B, compare mean RSSI without division:

```text
delta_num =
  abs(A.rssi_sum * B.sample_count -
      B.rssi_sum * A.sample_count)

equivalent iff:
delta_num <= 3 * A.sample_count * B.sample_count
```

Use a sufficiently wide signed integer for the cross-products.

If the mean RSSI difference is greater than 3 dB, the less-negative / stronger mean RSSI wins.

If it is at most 3 dB, both are equal-quality and the stable hash rule decides.

This makes the decision independent of integer rounding and less sensitive to one instantaneous RSSI sample.

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

## 6. End-of-window selection

At `candidate_window_deadline_ms`:

- if no candidate remains, clear selection epoch state and continue ordinary Discovery scanning;
- otherwise rank candidates using the frozen RSSI/hash rules;
- select exactly one candidate;
- set radio to that candidate channel;
- build/send the existing Challenge;
- only then create `pending_challenge_`.

No second active Relay or parallel handshake is introduced.

## 7. Challenge / Accept failure behavior

### 7.1 Immediate Challenge build/send/channel failure

If the chosen candidate cannot be challenged because nonce generation, encoding, channel set, or Challenge submit fails:

- mark that candidate attempted/failed for the current selection epoch;
- do not promote it to active Relay;
- choose the next-best unattempted candidate from the already-collected candidate set immediately;
- if none remains, clear the candidate set/window and return to ordinary Discovery scanning, where the next valid discovery starts a fresh 4500 ms window.

A source-level radio failure that already requires existing fail-safe handling must retain that existing stronger error path; Gateway Selection V1 must not downgrade a radio fault into an ordinary candidate miss.

### 7.2 Challenge timeout

When `pending_challenge_->expires_at_ms` is reached:

- clear pending challenge;
- mark the selected candidate failed for this selection epoch;
- immediately attempt the next-best unattempted collected candidate;
- if none remains, clear the selection epoch and resume normal Discovery scanning until a new first candidate starts a new window.

Do not start another 4500 ms collection window merely because one already-ranked candidate timed out.

### 7.3 Invalid or failed Accept

If Accept is from the wrong source/channel/Relay identity, has wrong trust generation/nonce, fails authentication, or cannot complete peer install/path promotion:

- never activate that candidate;
- preserve existing packet/radio error classification;
- for an ordinary candidate-specific rejection, mark candidate failed and try the next ranked candidate;
- for a concrete radio-state failure, keep the existing radio-fault recovery/fail-safe route.

### 7.4 Success

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
4. `active_relay_` can be cleared by the existing Direct recovery path, runtime stop/reset, radio-fault reset, or active Relay failure path; a stronger advertisement is not a clearing condition.
5. Direct recovery scheduling remains owned by the existing recovery code and is not changed by Gateway Selection V1.
6. Ordinary Option-B telemetry queue and one-attempt delivery semantics are unchanged.

Therefore:

```text
ACTIVE_RELAY_HEALTHY => NO_GATEWAY_RESELECTION
STRONGER_RELAY_DISCOVERED_WHILE_ACTIVE => IGNORED/STATE_REJECTED
ACTIVE_RELAY_FAILED => EXISTING_RETURN_TO_DISCOVERY => NEW_SELECTION_EPOCH
```

## 9. Source changed-file allowlist for the later SOURCE_REPAIR gate

Product-source modifications must be limited to:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.cpp
```

Expected purpose:

- runtime h/cpp: candidate state, deterministic ranking, failure fallback, RSSI-aware receive signature;
- component h/cpp: retain RSSI in `RxSlot` and pass it from queued metadata into runtime.

The ESP-NOW driver already captures RSSI and therefore is **not** in the initial source allowlist.

Test-file allowlist:

```text
tests/n3w_phase4/n3w_phase4_runtime_host_test.cpp
tests/n3w_phase4/test_phase4_source_contract.py
tests/n3w_phase4/test_multi_relay_gateway_selection_v1_contract.py   # new
```

If implementation proves another product file is required, SOURCE_REPAIR must stop and expand the allowlist explicitly rather than editing opportunistically.

## 10. Regression matrix

The later SOURCE_REPAIR gate must prove at least:

1. **Single Relay**: one valid Relay is collected, waits only the bounded window, handshakes and becomes active.
2. **Two Relays, clear RSSI winner**: mean RSSI difference >3 dB; stronger candidate wins regardless of advertisement arrival order.
3. **Two Relays, within 3 dB**: stable hash decides.
4. **Exact mean RSSI tie**: stable hash decides.
5. **Hash collision fallback**: injected/mock equal digest uses Relay NODE_ID lexical order.
6. **Order invariance**: the same candidate samples in different advertisement order produce the same winner.
7. **Repeated advertisement update**: multiple RSSI samples update arithmetic mean correctly and conflicting MAC/channel for the same NODE_ID is rejected.
8. **Selected Relay Challenge submit failure**: next-ranked collected candidate is attempted without a new 4500 ms window.
9. **Selected Relay Challenge timeout**: next-ranked collected candidate is attempted; exhaustion returns to ordinary Discovery.
10. **Selected Relay invalid Accept/auth failure**: no activation; fallback/exhaustion behavior is correct.
11. **Healthy active Relay + stronger new advertisement**: active Relay remains unchanged; no new Challenge is sent.
12. **Active Relay delivery failure threshold reached**: existing path returns to Discovery; a new selection epoch can choose a different Relay.
13. **Direct recovery**: existing Direct probe/commit behavior is unchanged.
14. **Option-B telemetry**: queue ordering, single-attempt completion ownership, and no-resend policy are unchanged.
15. **A/B role symmetry**: the same runtime permits either node to be Relay when Direct+MQTT and the other to be Child after losing Direct.
16. **Three-node scenario**: A and B both Direct/relay-capable; C in Discovery chooses according to RSSI/hash rules, not first advertisement.
17. **RSSI plumbing**: driver metadata RSSI survives RX ring queueing and reaches runtime unchanged.

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

CANDIDATE_WINDOW_MS=4500
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
