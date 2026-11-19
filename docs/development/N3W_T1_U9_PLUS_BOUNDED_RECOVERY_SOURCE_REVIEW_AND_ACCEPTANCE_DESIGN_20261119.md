# N3-W T1 U9+ bounded recovery source review and acceptance design

DATE=2026-11-19
GATE=N3W_T1_U9_PLUS_BOUNDED_RECOVERY_SOURCE_REVIEW_AND_ACCEPTANCE_DESIGN
PR=807
BASE_HEAD=32204b7632c4e6159e21d502d048eb2c90e390d5

## 1. Scope

This gate closes the source-design gap identified as KF-168 without authorizing
any real-T1 destructive action.

Allowed in this gate:

- source review;
- source design and implementation;
- deterministic unit/simulation tests;
- GitHub CI;
- documentation and evidence archive.

Not authorized:

- real T1 destructive U10;
- service stop/start/write on the live T1;
- target image load or U11+;
- merge of PR #807.

The live transaction remains U9 with its one-shot authorization already
consumed. Replay is forbidden.

## 2. Fresh source review

The repository already contains the required low-level rollback mechanisms:

- `n3w_t1_core_updater_ha_usb.py` owns U9-U13 state transitions;
- `n3w_t1_core_updater_ha_u13b.py` restores target cleanup, predecessor
  image, pre-upgrade HA data, predecessor runtime and health;
- `n3w_t1_core_updater_ha_u13b_reconcile.py` repairs only the bounded
  one-phase Host/USB durable split after power loss;
- `n3w_t1_core_updater_ha_u13b_auto.py` already sequences reconciliation
  before normal U13B rollback;
- `n3w_t1_core_updater_ha_u13b_host.py` contains the production host
  adapters.

The missing product behavior is orchestration, not another recovery stack.
Before this repair, `HaUsbIpcExecutor.start_background_recovery()` handled
only U1/U2/U3. A daemon restart in U9-U12 therefore had no product-owned
coordinator to classify and recover the consumed transaction.

## 3. Frozen recovery policy

For a daemon/host re-entry with a durable phase in U9-U12:

1. never call `claim_live_authorization()`;
2. require `authorization_claimed=true` and
   `authorization_consumed=true`;
3. reconcile only the already-supported one-phase USB-ahead durable split;
4. require the same bound filesystem UUID;
5. if the bound media is absent or the wrong device is present, expose
   `RECOVERY_MEDIA_REQUIRED`; never auto-format or substitute another USB;
6. choose the legal rollback edge rather than guessing that interrupted
   forward mutation completed;
7. resume any existing U13B0-U13B4 rollback through the same controller.

This is deliberately conservative. Normal same-process forward U10/U11 is a
separate destructive execution path and remains outside this gate.

## 4. Customer-visible recovery oracle

`ROLLED_BACK` is not allowed merely because the old container starts.
Completion requires all eight facts:

1. exact predecessor runtime is healthy;
2. Home Assistant HTTP is ready;
3. Manager is ready;
4. Broker continuity is healthy;
5. fresh greenhouse telemetry is visible again;
6. expected pre-upgrade history is readable;
7. Host and bound-USB terminal transaction authorities are exact;
8. the consumed U9 authorization was not replayed.

The generic source contract is implemented in
`U9PlusRecoveryCompletionEvidence`. A production adapter must prove every
field; missing evidence fails closed.

## 5. Source slice 1

This commit implements:

- `U9PlusBoundedRecoveryCoordinator` in the existing automatic rollback
  module;
- consumed-authorization/no-replay guard;
- conservative U9-U12 -> U13B recovery;
- same-media wait projection for recoverable USB absence/mismatch;
- terminal eight-fact completion oracle contract;
- IPC background worker ownership and public recovery phase projection;
- deterministic tests for U9 restart rollback, missing media, incomplete
  customer oracle, unconsumed authorization, and IPC lifecycle wiring.

It intentionally does not construct the production host adapter yet. That is
source slice 2, after slice 1 CI proves the state-machine/IPC contract.

## 6. Acceptance before real destructive U10

Source closure requires:

- focused tests PASS;
- HA target-binding CI PASS;
- no existing U0-U8 regression;
- production daemon actually constructs the U9+ coordinator;
- production completion oracle has concrete telemetry/history proofs;
- no false PASS path from container-only health.

Only after those source/CI conditions are archived may a separately authorized
real-T1 destructive U10 acceptance be considered.
