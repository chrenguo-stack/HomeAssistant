# N3-W T1 Explicit Device Provisioning P2A Boot / Activation Policy Independent Source Review（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2A_BOOT_ACTIVATION_POLICY_INDEPENDENT_SOURCE_REVIEW`

## 0. Exact authority

```text
REVIEW_HEAD=a971067d8b11677253c930d8975960de58473a58
PR=541
PR_STATE=OPEN_DRAFT
SOURCE_MUTATION_DURING_FINAL_REVIEW=false
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
SYSTEMD_LIVE_MUTATION=false
ACTIVATION_TOPOLOGY_LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

The immediately preceding repair commits were:

```text
61f6fc62aa89c5d00839e94404d0fb66275e9bfb
a971067d8b11677253c930d8975960de58473a58
```

They close the factory-acceptance path-validation / reopen TOCTOU window by opening the record with
`O_RDONLY | O_NOFOLLOW | O_CLOEXEC`, validating the opened descriptor with `fstat`, and parsing JSON
from that same descriptor. A regression test proves the validated pathname is not reopened.

## 1. CI closure

Exact-head CI for `a971067d8b11677253c930d8975960de58473a58`:

```text
TOTAL=25
COMPLETED=25
SUCCESS=25
FAILURE=0
CI=PASS
```

## 2. Independent review result

Final independent review against ADR-0009 and the frozen P2A source plan:

```text
P2A_INDEPENDENT_SOURCE_REVIEW=PASS
P2A_BLOCKER_COUNT=0
READY_FOR_P2B_SOURCE_MAPPING=true
```

Reviewed properties:

```text
UNPROVISIONED_BOOT_NOOP=true
INITIALIZING_RESUME_ONLY=true
DEVICE_READY_VERIFY_ONLY=true
BOOT_START_AUTHORITY_ABSENT=true
CONFLICT_FAIL_CLOSED=true
FACTORY_ACCEPTANCE_REQUIRED_FOR_ACTIVATION=true
FACTORY_MARKER_BINDING_FAIL_CLOSED=true
FACTORY_MARKER_SAME_FD_VALIDATE_AND_READ=true
PRODUCTION_SERVICE_START=false
LEGACY_ACTIVATION_TOPOLOGY_UNCHANGED=true
SOURCE_ONLY_RESUME_UNIT_NOT_DEPLOYED=true
```

## 3. Findings

### A1 — boot cannot start new provisioning: CLOSED

`device_provisioning_runtime.py` does not import or reference `start_device_provisioning`.
UNPROVISIONED returns NOOP. INITIALIZING only calls the already-closed P1 resume path.
DEVICE_READY only calls the already-closed P1 verify path.

### A2 — activation authority remains separate: CLOSED for P2A

`evaluate_product_activation()` only evaluates eligibility. Even with an exact
`FACTORY_ACCEPTED` record it returns `production_service_start=false` and does not start Broker,
Manager, Home Assistant, or systemd units.

### A3 — FACTORY_ACCEPTED record validation: CLOSED

Missing record is a normal DENY. Existing record must be a single-link regular file owned by the current
effective uid, mode 0600, and must exactly bind schema/status/factory flag/release/current verified host
instance/SYSTEM_ID/SYSTEM_ID hash.

The security-sensitive record is opened once with no-follow semantics; validation and JSON read are bound
to the same file descriptor.

### A4 — systemd source boundary: CLOSED for P2A

The new `n3wfc4-provision-resume.service` is a source-only oneshot helper. It invokes only
`n3w-t1-provision resume-if-needed`, orders before the legacy Broker/services activation units, and does
not itself start either unit.

The current legacy persistence installer remains unchanged and does not install/enable this new resume unit.

### A5 — legacy activation topology: NOT REDEFINED by P2A

The historical Broker/services activation units and NetworkManager dispatcher remain unchanged. They are
not suitable as the final golden-clone activation owner by themselves; P2B/later work must wire the new
provision/activation gate before any golden-master installation enables production activation.

This is not a P2A blocker because the P2A contract is intentionally source-only policy and explicitly does
not claim deployability.

## 4. Scope boundary after closure

P2A does **not** prove:

- deployable `/usr/local/sbin/n3w-t1-provision`;
- target-Armbian OS-host identity regeneration semantics;
- clone/release evidence acquisition;
- golden-master installation/enabling of the resume unit;
- FACTORY_ACCEPTED record creation;
- production activation ownership.

Those remain P2B/later gates.

## 5. Final decision

```text
P2A=CLOSED_PASS
P2B_SOURCE_MAPPING=AUTHORIZED_BY_EXISTING_CONTINUOUS_SOURCE_WORKFLOW
LIVE_APPLY_AUTHORIZATION=false
```
