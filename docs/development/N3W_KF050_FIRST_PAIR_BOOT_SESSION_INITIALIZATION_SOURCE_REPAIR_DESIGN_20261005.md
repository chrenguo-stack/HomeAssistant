# N3-W KF-050 First-Pair Boot-Session Initialization — Source Repair Design — 2026-10-05

```text
TASK=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_SOURCE_REPAIR_DESIGN_20261005_01
STATUS=CLOSED_PASS
DESIGN_CLOSURE=COMPLETE
SOURCE_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
RECOVERY_FLOOR_EXECUTION=false
MERGE=false
```

## 1. Authority and scope

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_HEAD_AT_DESIGN_START=162683515bb7a72cc70020b4d5be96d563a5edce
R2_PRODUCT_SOURCE=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
R2_PRODUCT_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
```

A fresh compare from `67a0460...` to the current PR head shows documentation-only changes after the frozen R2 product source. Therefore the source defect and this repair design are still evaluated against the exact R2 product code.

This gate repairs only the inherited KF-050 first-pair boot-session initialization window. It does not redesign Broker relocation, B2 naming, Manager replay/high-water, recovery-floor migration, Relay behavior, or pairing cryptography.

## 2. Confirmed defect

Current product order is:

```text
startup
-> fresh_identity_candidate_ = !persisted_runtime_state_present_()
-> SimpleProductComponent::setup()
-> normal pairing
-> SimplePairingClient::persist_bundle_()
   -> peer_store_.save(peer)
   -> broker_store_.save(broker)
   -> ack_store_.save(pending)
-> pairing acknowledgement / provisioned
-> later first production telemetry
-> take_telemetry_identity()
-> begin_boot_session_if_needed_()
-> if boot_state missing and process was fresh, provision floor=0
-> begin session
```

The defect window is after durable product identity exists but before the first telemetry identity request creates `gh_n3w/boot_state`.

If power/reboot occurs there, the next process has a persisted identity, so `fresh_identity_candidate_` becomes false. A missing boot counter is then correctly treated as rollback/recovery state and fails closed. The security rule is correct; the initialization order is wrong.

Classification remains:

```text
CLASSIFICATION=INHERITED_PRODUCT_CORRECTNESS_GAP
R2_RELOCATION_REGRESSION=false
MANAGER_DEFECT=false
CLEAN_PRODUCT_RELEASE_BLOCKER=true
```

## 3. Design decision

### 3.1 Move initial floor preparation before pairing

Do not add a boot-session callback into `SimplePairingClient` and do not move Broker-relocation code.

The repaired startup order shall be:

```text
GreenhouseN3wCore::setup()
-> classify startup product identity state
-> if and only if PROVEN_FRESH:
     prepare durable initial boot floor=0
     readback verify
-> only after that succeeds:
     SimpleProductComponent::setup()
     -> pairing initialization / pairing persistence may proceed
```

The zero floor is not a boot session and does not allocate a `boot_id`. It is only the durable lower bound required before a formal product identity can be persisted. Session 1 is still allocated later by normal `BootSessionManager::begin()` when telemetry identity is first requested.

This preserves the existing rule that a `(boot_id, seq)` is not created until product runtime actually requests telemetry identity.

### 3.2 Exact fresh-state proof

The existing expression:

```text
fresh_identity_candidate_ = !persisted_runtime_state_present_()
```

is too weak for the new write authority because "not a complete valid identity" also includes partial/corrupt states.

The repaired code must classify the relevant durable identity stores explicitly.

`PROVEN_FRESH` requires all of:

```text
peer_store status == MISSING
broker_store status == MISSING
ack_store status == MISSING
```

Setup Secret and pairing-intent state are not product identity and may legitimately exist across an unfinished bootstrap attempt; they do not by themselves disqualify `PROVEN_FRESH`.

A complete valid matching peer+broker identity is `EXISTING_IDENTITY`, with pending-ack handled by the existing pairing client semantics.

Any mixed, corrupt, invalid or contradictory peer/broker/ack state is `INVALID_OR_PARTIAL`, not fresh.

For `INVALID_OR_PARTIAL`:

```text
INITIAL_BOOT_FLOOR_WRITE=false
AUTO_ERASE=false
FAIL_CLOSED=true
```

This gate must never turn a partial historical state into a fresh identity merely because the complete peer+broker pair is absent.

### 3.3 Initial boot-floor preparation

For `PROVEN_FRESH`, inspect `gh_n3w/boot_state` before entering `SimpleProductComponent::setup()`.

Required behavior:

```text
boot_state=MISSING
  -> BootSessionManager::provision_recovery_floor(store, 0)
  -> existing primitive performs save + readback verification
  -> PASS only on CoreError::NONE

boot_state=OK,value=0
  -> accept idempotently
  -> this represents an interrupted prior fresh-floor preparation
  -> do not rewrite

boot_state=OK,value>0
  -> conflict / fail closed
  -> do not lower or overwrite

boot_state=CORRUPT
  -> fail closed

boot_state=IO_ERROR
  -> fail closed
```

The existing `BootSessionManager::provision_recovery_floor()` already performs the required write and readback comparison. The repair must reuse it rather than introduce a second durability mechanism.

### 3.4 Delayed zero-floor creation is removed from telemetry path

After this repair, `begin_boot_session_if_needed_()` must no longer create floor=0 when telemetry is first requested.

Its responsibility becomes only:

```text
load existing durable boot_state
-> if MISSING/CORRUPT/IO_ERROR: fail closed
-> BootSessionManager::begin(...)
-> persist and readback next session
-> expose boot_id / sequence
```

This makes the invariant simple:

> Any product identity that reaches normal pairing persistence must already have a durable verified boot floor.

For a legacy or otherwise existing provisioned identity with missing counter, behavior remains fail closed. No implicit migration path is added.

## 4. Restart semantics frozen by this repair

### Case A — brand-new board, no interruption

```text
no peer/broker/ack
boot_state missing
-> prepare floor 0 and verify
-> pair normally
-> first telemetry begin() persists session 1
-> boot_id=boot_0000000000000001
```

### Case B — reboot after floor preparation but before identity persistence

```text
no peer/broker/ack
boot_state=0
-> still PROVEN_FRESH
-> accept existing exact zero floor without rewrite
-> pairing may proceed
```

This is the required idempotent restart boundary introduced by the repair.

### Case C — reboot after complete pairing persistence but before first telemetry

```text
valid product identity exists
boot_state=0
-> not fresh; no floor creation
-> first telemetry begin() increments 0 -> 1
-> telemetry identity succeeds
```

This directly closes the Astra-host-reproduced defect.

### Case D — normal reboot after telemetry already started

```text
valid product identity exists
boot_state=N, N>=1
-> begin() persists N+1
-> boot session monotonically advances
```

### Case E — existing provisioned identity, boot_state missing

```text
valid product identity exists
boot_state missing
-> no zero-floor creation
-> fail closed
```

This preserves the KF-050 security contract and ADR-0008 boundary.

### Case F — no identity but non-zero historical boot_state

```text
peer/broker/ack missing
boot_state=N, N>0
-> do not reset to zero
-> fail closed
```

This avoids silently laundering a historical/partially erased board into a clean product state.

## 5. Minimal source-change surface

Preferred repair surface:

```text
firmware/esphome_rc/components/greenhouse_n3w_product_core/greenhouse_n3w_product_core.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_core.h
firmware/esphome_rc/components/greenhouse_n3w_product_core/n3w_core.cpp
```

Tests may update/add under:

```text
tests/n3w_p4a/
tests/n3w_phase4/
```

No change is required by design to:

```text
n3w_simple_pairing_client.cpp
n3w_simple_pairing_client.h
n3w_simple_product_component_broker_relocation.cpp
n3w_broker_relocation_policy.*
Manager replay/high-water code
ADR-0008 legacy recovery helper
```

Implementation may keep the small initial-floor decision directly in `GreenhouseN3wCore`, but a tiny host-testable helper in `n3w_core.{h,cpp}` is preferred if that avoids duplicating StoreStatus mapping. Do not introduce a new state machine or a generic transaction framework for this repair.

## 6. Required regression coverage

### 6.1 Existing BootSessionManager behavior

Retain current host coverage for:

```text
missing store -> begin rejects
provision floor 0 -> verified
begin -> session 1
reboot -> session 2
rollback floor reject
corrupt store reject
store I/O failure reject
session exhaustion reject
```

### 6.2 New initial-floor policy tests

Add deterministic host coverage for:

```text
FRESH + boot missing -> floor 0 persisted and verified
FRESH + boot 0 -> idempotent PASS, no lowering/rewrite
FRESH + boot >0 -> FAIL
FRESH + corrupt -> FAIL
FRESH + I/O error -> FAIL
save/readback mismatch -> FAIL
```

### 6.3 Startup identity classification tests

Freeze:

```text
peer missing + broker missing + ack missing -> PROVEN_FRESH
valid matching peer+broker + ack missing -> EXISTING_IDENTITY
valid matching peer+broker + valid pending ack -> EXISTING_IDENTITY/PENDING_ACK
peer only -> INVALID_OR_PARTIAL
broker only -> INVALID_OR_PARTIAL
ack without complete identity -> INVALID_OR_PARTIAL
corrupt peer/broker/ack -> INVALID_OR_PARTIAL
mismatched peer/broker node/system identity -> INVALID_OR_PARTIAL
```

### 6.4 Ordering/source-contract regression

A source-contract test must prove that in `GreenhouseN3wCore::setup()`:

```text
startup identity classification
< fresh boot-floor preparation
< SimpleProductComponent::setup()
```

and that `begin_boot_session_if_needed_()` no longer provisions a missing zero floor.

### 6.5 Reboot behavior regression

Add a targeted behavior test for the exact defect:

```text
fresh startup
-> floor 0 prepared
-> simulate completed product identity persistence
-> reboot before first telemetry identity
-> begin boot session
-> accepted
-> session == 1
```

Also retain/prove:

```text
uninterrupted first telemetry -> session 1
next reboot -> session 2
existing provisioned identity + missing counter -> rejected/fail closed
```

A full ESPHome hardware-power-cut test is not required in this source-repair gate; it remains part of later clean-board physical acceptance.

## 7. Pairing multi-key persistence boundary observed during design review

`SimplePairingClient::persist_bundle_()` currently persists peer, broker and pending-ack as separate durable writes. This design gate does not claim atomic power-loss recovery inside those existing individual writes.

The present repair is specifically bounded to the confirmed sequence:

```text
complete local pairing persistence exists
+ boot_state still missing
+ reboot before first telemetry
```

The repair must not make the existing multi-key pairing persistence behavior worse. Partial/corrupt startup states must remain fail closed and must never be reclassified as fresh.

No generic pairing transaction framework is added in this gate. If later product acceptance requires arbitrary power removal between each peer/broker/ack NVS commit to be automatically recoverable, that is a separate bounded product-hardening question rather than a reason to expand this KF-050 repair into a new pairing architecture.

## 8. Non-regression contract

```text
R2_BROKER_RELOCATION_CHANGED=false
BROKER_CANDIDATE_RAM_ONLY=true
DURABLE_BROKER_REWRITE=false
MANAGER_REPLAY_RELAXATION=false
MANAGER_HIGH_WATER_CLEAR=false
LEGACY_RECOVERY_FLOOR_NORMAL_PRODUCT_PATH=false
PAIRING_CRYPTO_CHANGED=false
MQTT_CREDENTIAL_SEMANTICS_CHANGED=false
TELEMETRY_CADENCE_CHANGED=false
```

The existing legacy recovery-floor helper remains `LEGACY_MIGRATION_ONLY / ENGINEERING_MIGRATION_ONLY / BOARD_LAB_ONLY` and is not reused as a normal product pairing path.

## 9. Acceptance for the source-repair implementation gate

The next source repair may close only when all are true:

```text
EXACT_BASE_BOUND=true
SOURCE_CHANGE_MATCHES_THIS_DESIGN=true
PROVEN_FRESH_CLASSIFICATION_EXPLICIT=true
BOOT_FLOOR_ZERO_PREPARED_BEFORE_PAIRING=true
BOOT_FLOOR_READBACK_VERIFIED=true
ZERO_FLOOR_RESTART_IDEMPOTENT=true
NONZERO_OR_BAD_PREPAIR_BOOT_STATE_FAILS_CLOSED=true
EXISTING_IDENTITY_MISSING_COUNTER_FAILS_CLOSED=true
DELAYED_ZERO_FLOOR_CREATION_REMOVED=true
FIRST_PAIR_PRETELEMETRY_REBOOT_REGRESSION=PASS
BOOT_SESSION_MONOTONIC_REBOOT_REGRESSION=PASS
R2_RELOCATION_TESTS=PASS
REQUIRED_CI=PASS
BOARD_ACCESS=false
T1_MUTATION=false
MERGE=false
```

Any implementation that solves the defect by clearing Manager replay/high-water, lowering an existing boot counter, treating partial credentials as fresh, or invoking the legacy recovery helper is rejected.

## 10. Gate disposition

```text
DESIGN_CLOSURE=PASS
REPAIR_STRATEGY=PREPAIR_DURABLE_ZERO_FLOOR
PAIRING_CLIENT_PROTOCOL_REDESIGN=false
R2_RELOCATION_REDESIGN=false
PHYSICAL_EXECUTION_AUTHORIZED=false
PR_522_MERGE=false

NEXT_ONE_GATE=N3W_KF050_FIRST_PAIR_BOOT_SESSION_INITIALIZATION_SOURCE_REPAIR_20261005_01
```

The successor is a source-repair implementation and regression gate only. It does not authorize T1 mutation, board access, recovery-floor execution, Manager replay/high-water mutation, clean-board flashing, or PR merge.
