# N3W T1 E03 Fresh Replacement Reconciled-Ledger Preauthorization Source Repair

Date: 2026-10-30

## Problem

Fresh E03 replacement preauthorization still required the historical E03 fixture ledger:

- one first-registration attempt,
- one registration,
- one unresolved cleanup,
- ACTIVE / BOOTSTRAP_ACCEPTED.

The current T1 readonly forensic instead proves the same pairing/hardware attempt has naturally reached the already-supported safe terminal state:

- EXPIRED / TERMINAL / COMPLETE,
- zero registrations,
- zero unresolved cleanup,
- zero pairing credentials,
- zero hardware credential history.

That exact state is already the required validate_post_ledger() acceptance state.

## Safety rule

Preauthorization may accept only two explicit, exact ledger states:

1. LEGACY_ACTIVE: the existing historical E03 prestate validated by validate_pre_ledger().
2. RECONCILED_TERMINAL: the existing exact terminal state validated by validate_post_ledger().

No generic empty/clean shortcut is introduced. Unknown terminal states, unresolved cleanup, registration drift, credential residue, pairing/hardware drift, or malformed evidence remain fail-closed.

## Transaction binding

Fresh preauthorization stores:

- ledger mode,
- canonical ledger SHA-256,
- attempt count,
- registration count,
- registration inventory SHA-256,
- unresolved count.

Claim already reruns preauthorization inside the global maintenance lock, so it rebinds the ledger before transaction creation.

Before the first product mutation (activation_gate_install) and again before service_stop, runtime rebind rereads the Manager ledger and requires the exact same preauthorization binding.

## Non-goals

This repair does not:

- delete historical first-registration attempts,
- change release IDs,
- change target artifacts,
- change Broker continuity rules,
- change rollback logic,
- change strict post-upgrade acceptance,
- mutate T1 during source repair.
