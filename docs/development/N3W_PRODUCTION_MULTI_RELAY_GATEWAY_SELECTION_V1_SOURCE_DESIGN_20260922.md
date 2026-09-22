# N3-W Production Multi-Relay Gateway Selection V1 — Source Design

- Date: 2026-09-22
- Gate: `N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01`
- Document status: implementation-ready source design
- Repository: `chrenguo-stack/HomeAssistant`
- Fresh main at design freeze: `3b4a75b039a8d5d9572b4a8f7cfb1e580e7f3476`
- Fresh main tree: `f19701fb432f76d6913fed38891b8cbeedeb124f`
- Frozen production successor branch: `feature/n3w-production-telemetry-bridge-20260921`
- Frozen production successor source: `c1b3d9d016d06c21c9ff7070c0043163739565ca`
- Frozen production successor tree: `0c857fb0f830239717a2e937d176903a6acae8ac`
- Product-source mutation in this gate: **none**
- Board access / live runtime mutation in this gate: **none**

This document freezes only the source design. It does not repair PR #469, does not modify production firmware, and does not authorize a board write or physical RF test.

## 1. Fresh rebind closure

Fresh repository evidence overrides the older handoff main pointer where they differ.

```text
MAIN=3b4a75b039a8d5d9572b4a8f7cfb1e580e7f3476
MAIN_TREE=f19701fb432f76d6913fed38891b8cbeedeb124f

PRODUCTION_SUCCESSOR_SOURCE_HEAD=c1b3d9d016d06c21c9ff7070c0043163739565ca
PRODUCTION_SUCCESSOR_SOURCE_TREE=0c857fb0f830239717a2e937d176903a6acae8ac
PRODUCTION_SUCCESSOR_SOURCE_CHANGED=false

EXACT_PRODUCTION_ARTIFACT_ID=10644667734
EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS
PRODUCTION_SUCCESSOR_BOARD_A_DEPLOYMENT=NOT_EXECUTED
PRODUCTION_SUCCESSOR_BOARD_B_DEPLOYMENT=NOT_EXECUTED

PR469_STATE=OPEN
PR469_HEAD=d9f6a4d33b8354053e736c71e887b176236a79d9
PR469_DEDICATED_PREFLIGHT_CI_RUN=35616545967
PR469_DEDICATED_PREFLIGHT_CI=PASS
PR469_PUBLIC_REPOSITORY_SAFETY_RUN=35616545975
PR469_PUBLIC_REPOSITORY_SAFETY=FAIL
PR469_PUBLIC_SAFETY_FAILURE_CLASS=CI_CONTENT_SAFETY
PR469_PUBLIC_SAFETY_FAILURE_REASON=synthetic MAC-looking test fixtures at test_executor.py lines 124 and 194
PR469_REPAIR_IN_THIS_GATE=false
```

The production successor is still the frozen source above even though main has advanced by documentation/process work.

## 2. Exact current source behavior

The current runtime is role-symmetric. A node in Direct with MQTT is relay-capable through `runtime_.set_relay_capable(mqtt_connected())`; there is no Board-A-only or Board-B-only relay branch. Reverse physical acceptance (B as Gateway / A as Child) remains unproven.

Current multi-Gateway behavior is first-arrival driven:

1. only `DISCOVERY` accepts relay advertisements;
2. the first valid discovery immediately triggers Challenge;
3. `pending_challenge_` rejects later discoveries;
4. a valid Accept binds `active_relay_` and moves the path to `RELAY_ACTIVE`.

ESP-NOW RX metadata already captures RSSI in `EspNowReceiveMetadata.rssi_dbm`, but the component RX ring currently stores only source, size, channel, and payload. The RSSI sample is therefore dropped before `SimpleProductRuntime::on_radio_receive(...)`.

The existing relay-health rule is unchanged: two Relay delivery failures move `RELAY_ACTIVE -> DISCOVERY`; only after that transition is Gateway reselection allowed.

## 3. Frozen V1 product policy

```text
PRIMARY_SELECTION=RSSI
RSSI_EQUIVALENT_BAND_DB=3

EQUAL_QUALITY_TIE_BREAK=STABLE_HASH(CHILD_NODE_ID, RELAY_NODE_ID)
FINAL_HASH_COLLISION_TIE_BREAK=RELAY_NODE_ID_LEXICOGRAPHIC_ASCENDING

DYNAMIC_LOAD_BALANCING=false
PROACTIVE_RSSI_ROAMING=false
ACTIVE_RELAY_STICKY_WHILE_HEALTHY=true
ACTIVE_RELAY_FAILURE_REQUIRED_FOR_RESELECTION=true
```

V1 is a disconnected-selection policy, not a roaming policy.

## 4. Candidate window

### 4.1 Frozen duration

```text
CANDIDATE_WINDOW_MS=6750
```

Rationale from the current source defaults:

```text
ALLOWED_CHANNELS={1,6,11}
SCAN_DWELL_MS=250
FULL_SCAN_CYCLE_MS=3*250=750
RELAY_ADVERTISEMENT_INTERVAL_MS=2000
CANDIDATE_WINDOW_MS=3*2000+750=6750
```

A Relay can advertise at any phase relative to the Child's 750 ms three-channel scan. Because 2000 ms mod 750 ms is 500 ms, three advertisement opportunities move through the three scan phases. Six seconds covers those opportunities; one additional full 750 ms scan cycle provides a bounded scheduling margin.

The window starts on the first **eligible** Relay discovery. It is not started by malformed, wrong-generation, self, channel-mismatched, or RSSI-unknown discovery traffic.

### 4.2 Lifecycle

While `path == DISCOVERY`:

1. first eligible discovery starts the 6750 ms window;
2. no Challenge is sent during collection;
3. scanning continues on the existing channel plan;
4. eligible discoveries update the candidate set;
5. at the deadline, collection is frozen and deterministic selection begins.

Candidate state is cleared on:

- successful transition to `RELAY_ACTIVE`;
- Direct restoration;
- `begin_discovery_()` starting a genuinely new discovery epoch;
- stop/reset/radio-fault reset.

Candidate collection never runs in `DIRECT` or `RELAY_ACTIVE`.

### 4.3 Candidate identity and dedup

The stable candidate identity key is `RELAY_NODE_ID`.

A candidate record binds:

```text
RELAY_NODE_ID
source MAC
channel
best_rssi_dbm
```

Repeated advertisements for the same NODE_ID are treated as the same candidate only when source MAC and channel are unchanged.

If one NODE_ID appears with a different MAC or different channel during the same collection window, that NODE_ID is marked endpoint-conflicted and excluded for that window. V1 does not pick one conflicting endpoint by arrival order.

For bounded embedded memory:

```text
MAX_RELAY_CANDIDATES=8
```

This matches the existing `max_relay_children=8` product scale. A ninth distinct legal Relay is outside the V1 supported selection set; it is rejected with a bounded diagnostic rather than growing memory without limit. Regression acceptance is defined for up to eight legal simultaneous candidates.

## 5. RSSI update rule

Only a discovery that passes the existing packet/trust/self/channel checks and carries a usable RSSI sample may update a candidate.

Frozen update rule:

```text
candidate.best_rssi_dbm =
    max(candidate.best_rssi_dbm, new_rssi_dbm)
```

In other words, V1 keeps the strongest observed RSSI for that Relay during the current window.

Reasons:

- commutative and independent of advertisement arrival order;
- constant memory;
- a later weaker packet cannot erase a previously observed good link;
- no sample-count advantage for a Relay that happens to advertise more often;
- the 3 dB equivalence band already prevents tiny RSSI differences from forcing the result.

V1 does not use moving averages, load, child count, latency, or historical success score.

## 6. Deterministic selection algorithm

For each selection attempt over the remaining frozen candidates:

1. find `RMAX`, the strongest `best_rssi_dbm`;
2. form the equal-quality set:
   `RMAX - candidate.best_rssi_dbm <= 3 dB`;
3. within that set choose the candidate with the smallest stable 64-bit hash score;
4. if two hash scores are identical, choose lexicographically smaller `RELAY_NODE_ID`;
5. if that candidate later times out at the authenticated handshake stage, remove it from the remaining snapshot and repeat the same algorithm.

This avoids a non-transitive pairwise “within 3 dB” comparator when more than two Relays are present.

## 7. Stable hash primitive and input encoding

V1 uses **FNV-1a 64-bit** only as a deterministic tie-breaker. It is not a security primitive.

Exact arithmetic:

```text
offset_basis = 14695981039346656037
prime        = 1099511628211
for every input byte:
    hash = hash XOR byte
    hash = (hash * prime) mod 2^64
lower unsigned 64-bit hash wins
```

Exact input bytes:

```text
ASCII("gh.n3w.gateway-select/1")
0x00
uint8(len(CHILD_NODE_ID))
raw ASCII bytes of CHILD_NODE_ID
uint8(len(RELAY_NODE_ID))
raw ASCII bytes of RELAY_NODE_ID
```

NODE_ID is already restricted by the current product identity validator to 3..64 ASCII characters, so the one-byte lengths are unambiguous.

This is the versioned, length-delimited encoding of the approved semantic input `HASH(C.NODE_ID || RELAY.NODE_ID)`. No `std::hash`, pointer value, MAC address, boot nonce, clock, random value, or advertisement order may participate.

Hash collision fallback is exact bytewise/ASCII lexicographic ascending Relay NODE_ID.

## 8. Challenge / Accept failure behavior

Selection produces a frozen remaining-candidate snapshot. The Child challenges one selected Relay at a time.

### 8.1 Challenge submission

A selected candidate is tuned to its recorded channel and challenged using the existing authenticated handshake.

Local failures before a Challenge is successfully submitted — nonce/encode failure, channel-set failure, or ESP-NOW submit failure — are classified as local crypto/radio failures. They are **not** evidence that another Relay is better, and V1 must not silently hop to the next candidate to mask such a local fault. The existing RADIO_FAILED/fault-recovery semantics remain authoritative.

### 8.2 Accept wait

After Challenge submit succeeds, the existing timeout remains:

```text
ACCEPT_WAIT_MS=2*challenge_timeout_ms=3000
```

A received Accept with wrong source, channel, NODE_ID, generation, nonce, or invalid proof is rejected but does not evict the selected candidate immediately. The Child continues waiting for a valid Accept from the selected Relay until the deadline. This prevents unrelated or malformed traffic from forcing candidate fallback.

### 8.3 Selected Relay timeout

If no valid Accept arrives by the 3000 ms deadline:

1. mark that selected candidate exhausted for this frozen snapshot;
2. clear the pending Challenge;
3. select the next candidate using the same deterministic V1 algorithm;
4. challenge each candidate at most once per frozen snapshot.

If the snapshot is exhausted, clear it and resume ordinary Discovery scanning. The next eligible advertisement starts a new 6750 ms candidate window.

### 8.4 Valid Accept

A valid Accept keeps the current source contract:

1. fix/read back the selected channel;
2. install the encrypted peer;
3. commit `RELAY_ACTIVE`;
4. assign `active_relay_`;
5. clear all collection/ranking state.

Peer-install/channel failures after a cryptographically valid Accept remain local radio failures and do not trigger within-snapshot candidate roulette.

## 9. No-proactive-roaming proof obligation

The later implementation must make these invariants mechanically testable:

```text
CANDIDATE_MUTATION_ALLOWED_ONLY_WHEN path == DISCOVERY
CANDIDATE_SELECTION_ALLOWED_ONLY_WHEN path == DISCOVERY
DISCOVERY_RX_WHILE_RELAY_ACTIVE_CANNOT_REPLACE_ACTIVE_RELAY=true
ACTIVE_RELAY_RSSI_NOT_CONTINUOUSLY_RANKED=true
```

The current path controller already provides the required gate:

```text
RELAY_ACTIVE
  -- two existing relay delivery failures -->
DISCOVERY
  -- new 6750 ms collection + authenticated handshake -->
RELAY_ACTIVE(new relay)
```

Therefore a stronger Relay advertisement while the active Relay remains healthy cannot cause a switch. Direct-recovery behavior is unchanged.

## 10. Later SOURCE_REPAIR changed-file allowlist

Only a later separately authorized source-repair gate may modify product source.

Exact production-source allowlist:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_runtime.cpp
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_simple_product_component.cpp
```

Exact new-test allowlist:

```text
tests/n3w_production/n3w_gateway_selection_v1_host_test.cpp
tests/n3w_production/test_gateway_selection_v1_behavior.py
```

The ESP-NOW driver is intentionally not on the allowlist: it already captures RSSI and channel metadata. The later repair should carry RSSI through the existing component RX ring to the runtime instead of rewriting the driver.

Forbidden in the later repair unless a new high-level design gate explicitly proves necessity:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/**
firmware/esphome_rc/board_lab/n3w_phase4_physical/**
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_espnow_driver.*
firmware/esphome_rc/f1_0_rc2/**
tests/execution_packages/n3w/production/board_b_preflight/**
.github/workflows/**
PR #469 content
```

No Manager/Broker/HA change is required for Gateway Selection V1.

## 11. Regression matrix for the later repair

| ID | Scenario | Required result |
|---|---|---|
| GS-01 | one legal Relay | collected, selected after bounded window, authenticated, RelayActive |
| GS-02 | two Relays, RSSI difference >3 dB | stronger Relay wins regardless of advertisement order |
| GS-03 | two Relays, RSSI difference <=3 dB | stable hash decides, not arrival order |
| GS-04 | exact RSSI tie | stable hash decides |
| GS-05 | injected equal hash scores | lexicographically smaller Relay NODE_ID wins |
| GS-06 | three-to-eight candidates / advertisement permutations | same candidate result for the same final candidate snapshot |
| GS-07 | repeated weaker RSSI sample | stored best RSSI does not decrease |
| GS-08 | repeated stronger RSSI sample | stored best RSSI increases |
| GS-09 | same NODE_ID with changed MAC/channel in one window | candidate excluded as endpoint conflict |
| GS-10 | selected Relay sends no valid Accept | after 3000 ms, next frozen candidate is attempted |
| GS-11 | stray/wrong/invalid Accept | rejected; selected candidate remains pending until valid Accept or timeout |
| GS-12 | all frozen candidates timeout | fresh Discovery/window begins; no permanent lock |
| GS-13 | local Challenge submit/channel failure | RADIO_FAILED path; no silent next-candidate masking |
| GS-14 | valid Accept then local peer/channel install failure | local radio failure; no candidate roulette |
| GS-15 | active Relay healthy, stronger Relay advertisement appears | no switch, no candidate collection |
| GS-16 | active Relay reaches existing two-failure threshold | active binding cleared, enters Discovery, fresh V1 selection allowed |
| GS-17 | B Direct+MQTT as Gateway, A as Child in host/source model | same runtime code path works; no board-specific role branch |
| GS-18 | metadata RSSI enters component RX ring/runtime | exact RSSI sample reaches candidate update path |
| GS-19 | existing Direct->Discovery->Relay and Relay->Direct recovery regression | unchanged existing tests remain PASS |
| GS-20 | MAX_RELAY_CANDIDATES boundary | 8 accepted; ninth does not create unbounded state |

Hash collision testing must use an injected/helper hash seam; tests must not search for a real FNV collision.

## 12. Source-design closure

```text
=== N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN CLOSURE ===

EXECUTION_ID=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01
AUTHORIZATION=N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN_20260921_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

FRESH_MAIN=3b4a75b039a8d5d9572b4a8f7cfb1e580e7f3476
FROZEN_PRODUCTION_SOURCE=c1b3d9d016d06c21c9ff7070c0043163739565ca

CANDIDATE_WINDOW_FROZEN=true
CANDIDATE_WINDOW_MS=6750
RSSI_UPDATE_RULE=MAX_OBSERVED_WITHIN_WINDOW
RSSI_EQUIVALENT_BAND_DB=3

STABLE_HASH_PRIMITIVE=FNV1A64
STABLE_HASH_INPUT=VERSIONED_LENGTH_DELIMITED_CHILD_NODE_ID_AND_RELAY_NODE_ID
HASH_WINNER=LOWEST_UNSIGNED_64
HASH_COLLISION_TIE_BREAK=RELAY_NODE_ID_LEXICOGRAPHIC_ASCENDING

CHALLENGE_ACCEPT_FAILURE_BEHAVIOR_FROZEN=true
NO_PROACTIVE_ROAMING_PROOF_FROZEN=true
SOURCE_CHANGED_FILE_ALLOWLIST_FROZEN=true
REGRESSION_MATRIX_FROZEN=true

PRODUCT_SOURCE_MUTATION=false
PR469_MUTATION=false
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_MUTATION=false
RF_EXECUTION=false
LIVE_RUNTIME_MUTATION=false

N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_SOURCE_DESIGN=PASS
READY_FOR_SOURCE_REPAIR_DESIGN_REVIEW=true
AUTO_EXECUTE_SOURCE_REPAIR=false
STOP=true

=== END ===
```
