# N3-W T1 Core Stack Clean Reference — R3 pairing-readiness authority gap design decision

Date: 2026-11-01

## 0. Status

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_PAIRING_READINESS_AUTHORITY_GAP_DESIGN_DECISION_20261101
STATUS=DECISION_PENDING

R2_COMMON_REFERENCE=CLOSED_PASS
R3=IN_PROGRESS
R3_WORKLOAD_EXECUTED=false
BOARD_ACCESS=false
PAIRING_EXECUTED=false

BLOCKER=FACTORY_ACCEPTED_AUTHORITY_GAP
```

## 1. Proven current state

The R2 common reference is frozen at:

```text
R2_REFERENCE_SHA256=89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747
R3_OBSERVER_CONTROL_HEAD=da9124fe18774cdb5822f9eb3afee40120cfb04f
HEALTH_OVERALL_PASS=true
FAILED_UNIT_COUNT=0
RUNTIME_SERVICES=broker,homeassistant,manager
```

The frozen product source contains the standard first-pairing onboarding tool:

`tools/n3w_t1_first_pairing_onboarding.py`

That tool requires:

`/var/lib/n3w-t1-provisioning/FACTORY_ACCEPTED.json`

The Clean Reference R1/R2 route did not create this marker.

## 2. Why old F4 must not be replayed

The old F4 factory marker is created only after `_factory_audit()`.

That audit requires a preactivation state:

- production activation units stopped;
- production activation units disabled;
- `production_service_start=false`.

The accepted Clean Reference R2 state is the opposite by design:

- production units enabled;
- production units active;
- three product services running;
- one real reboot already accepted.

Therefore:

```text
OLD_F4_REPLAY_SAFE=false
OLD_F4_REPLAY_WOULD_INVALIDATE_CURRENT_REFERENCE=true
```

Do not stop the healthy R2 reference and replay historical F4 merely to manufacture the
marker.

## 3. Option A — Clean Reference pairing-readiness bridge V1

Recommended.

Create a new bounded host-only one-shot tool whose only product-state mutation is an atomic
creation of the standard `FACTORY_ACCEPTED.json` marker after proving the Clean Reference
has already met equivalent or stronger acceptance conditions.

### Required preconditions

At minimum:

1. exact product source remains
   `24382caae4a1f5d459297f86e8d18f10a848ca64`;
2. R2A transaction remains `RUNTIME_STARTED`, consumed, non-replayable;
3. R2B transaction remains `REBOOT_ACCEPTED`, consumed, non-replayable;
4. R2 common-reference SHA remains bound to
   `89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747`;
5. current runtime health remains PASS;
6. current device-provisioning `verify` returns `DEVICE_READY`;
7. `release_id`, `host_instance_id`, `system_id` and `system_id_sha256` are obtained
   from existing provisioning authority, never invented;
8. Manager business tables are still at the pre-workload baseline;
9. no existing `FACTORY_ACCEPTED.json`;
10. no prior first-pairing transaction;
11. no pairing listeners are open;
12. no Board access.

### Marker compatibility

The standard onboarding tool currently validates these required fields:

```text
schema=gh.n3w.t1-factory-accepted/1
status=PASS
factory_accepted=true
release_id
host_instance_id
system_id
system_id_sha256
```

The bridge may add provenance fields because the standard reader does not require exact-key
equality, for example:

```text
acceptance_route=clean_reference_r2_bridge_v1
r2_reference_sha256=<frozen R2 reference>
r2b_transaction_sha256=<exact current R2B transaction>
```

Raw private host or Board identity must not be emitted publicly.

### Mutation boundary

```text
IMAGE_MUTATION=false
SERVICE_RESTART=false
CONTAINER_RECREATE=false
NETWORK_MUTATION=false
PAIRING_WINDOW_OPEN=false
BOARD_ACCESS=false

ONLY_PRODUCT_MUTATION=atomic FACTORY_ACCEPTED.json creation
```

The operation must be one-shot, durably claimed before marker creation, and non-replayable.

### Postconditions

After marker creation:

1. standard first-pairing `inspect` must PASS;
2. Broker / Manager / Home Assistant identities and start times remain unchanged;
3. boot ID remains unchanged;
4. no pairing listener is open yet;
5. R2 stable contracts remain unchanged;
6. marker provenance exactly binds the accepted Clean Reference authority.

Only then may the separate Board pairing sub-gate be proposed.

## 4. Option B — Non-pairing synthetic workload

Possible but not recommended.

A host-only synthetic workload could be created without the factory marker, but it would not
exercise the ordinary node lifecycle. It would provide weak evidence for the fields R3 is
intended to classify:

- registration tables;
- credential assignments;
- node leases;
- Dynamic Security node client state;
- replay/cursor state;
- Home Assistant node/entity/device state.

Therefore it would reduce the value of the R2-to-R3 comparison and leave A1 with major
classification gaps.

## 5. Option C — stop R2 and replay old F4

Rejected.

This would:

- destroy the accepted post-reboot R2 runtime reference;
- require service stop/disable and a historical transaction path;
- conflate the clean-reference architecture with the legacy F4 state machine;
- create avoidable operational risk.

```text
OPTION_C=REJECTED
```

## 6. Recommendation

```text
RECOMMENDED_OPTION=A
RECOMMENDATION=CLEAN_REFERENCE_PAIRING_READINESS_BRIDGE_V1
```

Rationale:

- preserves the current healthy R2 reference;
- reuses the standard first-pairing product path unchanged;
- does not modify images or service lifecycle;
- keeps the bridge narrowly scoped to missing acceptance authority;
- allows R3 to exercise a real ordinary node/pairing workload as requested by the frozen plan;
- gives A1 meaningful runtime drift evidence.

## 7. Decision boundary

No bridge source or live marker mutation is authorized by this document.

```text
BRIDGE_SOURCE_IMPLEMENTED=false
BRIDGE_LIVE_EXECUTED=false
BOARD_ACCESS=false
PAIRING_EXECUTED=false
DECISION_REQUIRED=true
```

If Option A is accepted, the next work is:

1. source design and exact one-shot bridge implementation;
2. unit/simulation tests and CI;
3. exact bridge artifact binding;
4. T1 read-only preflight;
5. separate host marker-creation authorization;
6. post-bridge standard onboarding inspect;
7. only after that, a separate Board qualification/pairing gate.
