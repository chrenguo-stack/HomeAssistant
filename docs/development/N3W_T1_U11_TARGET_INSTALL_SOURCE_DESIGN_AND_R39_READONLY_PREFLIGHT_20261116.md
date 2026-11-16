# N3-W T1 U11 target install source design and R39 read-only preflight — 2026-11-16

## Context

R38 real-T1 execution is CLOSED_PASS.

```text
LIVE_TRANSACTION_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
LIVE_TRANSACTION_SHA256=c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3
R38_AUTHORIZATION_CLAIMED=true
R38_AUTHORIZATION_CONSUMED=true
R38_REPLAY_PERMITTED=false
PREDECESSOR_RUNTIME_RELEASED=true
PREDECESSOR_IMAGE_RELEASED=true
TARGET_INTERNAL_IMAGE_ABSENT=true
BROKER_RUNNING=true
MANAGER_QUIESCED=true
U11_AUTHORIZED=false
```

R39 is the next bounded read-only gate. It must prove that the durable U10 state is a valid starting point for a future U11 implementation without loading the target image, changing Compose binding, starting services, or advancing the transaction.

## Frozen U11 semantics

The mandatory-USB OTA architecture V1.1 defines U11 as:

1. load the exact target archive from the bound USB into the internal image store;
2. verify the loaded runtime image identity;
3. publish the Home Assistant target binding;
4. recreate Home Assistant using the preserved production `/config`.

U12 is the later target-health acceptance phase. It owns the full health checks such as expected runtime/binding/network contract, listeners, Home Assistant HTTP/MQTT readiness, Manager/Broker continuity, restart-loop checks, and migrated production configuration usability.

A post-U9 target failure must remain recoverable from the bound USB by restoring the predecessor image and the protected pre-upgrade Home Assistant data backup. R39 does not perform that rollback; it only revalidates the recovery assets required for it.

## Existing-source reuse review

### Reusable

The current source already provides useful bounded primitives:

- `SubprocessPrepareBackend.resolve_transaction_media()` for exact bound USB resolution;
- `SubprocessPrepareBackend.verify_prepared_target()` for target archive identity;
- protected Home Assistant backup verification;
- transaction validation and USB transaction metadata formats;
- `LocalHost.image_id()`, `load_image()`, `verify_image_archive()`, `component_binding_v2()` and component activation primitives;
- `record_target_started()` for the U10 -> U11 state transition after real target activation evidence exists.

### Not directly reusable as the U11 orchestrator

The legacy generic `CoreUpdaterV2.apply()` assumes the predecessor container/image still exists as current binding authority while the target is applied. R38 intentionally released both predecessor runtime and predecessor internal image in U10.

Therefore the old P5 apply path must not be invoked directly from the real U10 state. Its predecessor-authority assumptions would conflict with the mandatory-USB low-storage transaction.

The synthetic R2 test sequence demonstrates the intended logical order:

```text
U10
-> load exact target
-> start target
-> record_target_started()
-> U11
```

but the repository does not yet contain a dedicated production U10->U11 USB-OTA controller that binds those operations to the durable U10 transaction and recovery contract.

## R39 read-only preflight contract

R39 is intentionally command-minimal and read-only.

It requires:

```text
EXACT_U10_TRANSACTION=true
R38_CLAIMED_CONSUMED_NO_REPLAY=true
SAME_BOUND_USB=true
EXACT_U10_USB_MIRROR=true
TARGET_ARCHIVE_CONTINUITY=true
PREDECESSOR_RECOVERY_ARCHIVE_CONTINUITY=true
PROTECTED_HA_BACKUP_REVERIFIED=true
RECOVERY_CAPACITY_PASS=true

PREDECESSOR_CONTAINER_ABSENT=true
PREDECESSOR_IMAGE_ABSENT=true
TARGET_INTERNAL_IMAGE_ABSENT=true
NO_HOMEASSISTANT_CONTAINER_RESIDUE=true

BROKER_RUNNING=true
MANAGER_QUIESCED=true
MANAGER_BROKER_PRESERVED=true

HOMEASSISTANT_COMPOSE_BINDING_STILL_PREDECESSOR=true
INTERNAL_TARGET_IMPORT_CAPACITY_PASS=true
```

The frozen storage-policy values used for the internal U11 import headroom check are:

```text
TARGET_IMPORT_WORST_CASE_ALLOWANCE_BYTES=3339788321
DERIVED_POST_PEAK_RESERVE_BYTES=1610612736
REQUIRED_INTERNAL_FREE_BYTES=4950401057
```

The exact target archive is already on the bound USB, so R39 does not count the old internal archive-staging term again. This is a conservative U11 admission check derived from the existing storage policy; it does not freeze a new long-term product runtime free-space minimum.

## R39 forbidden actions

```text
TRANSACTION_MUTATION=false
USB_MUTATION=false
TARGET_IMAGE_LOAD=false
COMPOSE_BINDING_MUTATION=false
SERVICE_MUTATION=false
U11_TRANSITION=false
U12_PLUS=false
BOARD_ACCESS=false
MERGE=false
LIVE_EXECUTION_AUTHORIZED=false
```

R39 has no execute switch and does not carry a U11 live authorization.

## Expected result

```text
STATUS=U11_R39_READONLY_PREFLIGHT_PASS
U11_READONLY_ELIGIBLE=true
U11_LIVE_EXECUTION_AUTHORIZED=false
```

A PASS means only that the real T1 remains a valid U11 starting point. It does not authorize target image load, binding mutation, Home Assistant recreation/start, U10->U11 advancement, or U12 acceptance.

## Next design boundary after R39

If R39 physically passes, the next repository-only task is to build a dedicated U10->U11 production controller/execution package with:

- exact target archive load from the already-bound USB;
- post-load portable/runtime identity verification;
- explicit Home Assistant binding update;
- controlled Home Assistant recreation using preserved `/config`;
- durable USB metadata before host U11 transaction persistence;
- transport-ambiguity reconciliation;
- fail-closed handling after any partially completed U11 action;
- explicit recovery/rollback handoff rather than blind replay;
- no U12 success claim until target health acceptance is independently proven.

Any real T1 U11 mutation still requires a fresh explicit user authorization after focused source review and exact-head CI.
