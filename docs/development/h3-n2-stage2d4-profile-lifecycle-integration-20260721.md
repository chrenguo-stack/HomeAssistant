# H3/N2 Stage 2D-4 Profile Lifecycle Integration

## Status

Stage 2D-4 integrates the authenticated persistent store, independent candidate
MQTT validator, and marker-last activation transaction behind injected runtime
and transport adapters.

Base main:

`6ee5aacb1ebc5845bebacbb98cdb2c622ae4be1c`

Development branch:

`feature/h3-n2-stage2d4-profile-lifecycle-integration-20260721-v52`

## Goal

Previous stages established three isolated guarantees:

- Stage 2D-1: authenticated dual-slot persistence with marker-last commit;
- Stage 2D-2: candidate MQTT validation without changing the active profile;
- Stage 2D-3: runtime activation, rollback, and reboot-required semantics.

Stage 2D-4 proves that these contracts can be joined without weakening their
ordering, generation binding, or failure boundaries.

## Integrated sequence

```text
recover PREPARED generation pair
→ stage recovered profiles in an injected runtime
→ validate candidate through an independent client
→ re-read PREPARED persistence state
→ activate candidate runtime
→ confirm a fresh round trip
→ commit persistent active marker last
```

The admitted persistent states are limited to `NO_ACTIVE_PREPARED` and
`ACTIVE_WITH_PREPARED`.

## Persistence adapter

`PairingPersistentStoreActivationAdapter` converts concrete store outcomes into
the Stage 2D-3 three-state commit result:

- `COMMITTED` only when post-commit recovery proves the candidate generation is
  active;
- `OLD_ACTIVE_PRESERVED` only when post-failure recovery proves the old marker,
  or the absence of a marker during first enrollment, remains authoritative;
- `INDETERMINATE_REBOOT_REQUIRED` for recovery failure or ambiguous authority.

The adapter caches a generation-bound preflight and rejects drift before any
runtime change.

## Runtime boundary

`ProfileLifecycleRuntime` remains an injected interface. It must stage the
recovered active/candidate generation pair and implement the Stage 2D-3 runtime
operations, but this stage provides no ESPHome MQTT setter and no active
connection restart implementation.

The compile-only laboratory component does not construct a persistence backend,
candidate MQTT transport, or runtime adapter. It never calls `configure`,
`recover_prepared`, `begin_validation`, or `activate`.

## Host fault matrix

The deterministic matrix covers:

- normal rotation from generation 1 to generation 2;
- first enrollment;
- independent candidate authentication failure;
- persistent marker-write rejection with known old authority and runtime
  rollback;
- indeterminate persistent authority and runtime quiescence;
- candidate runtime confirmation failure before persistent commit;
- runtime staging failure;
- persistence generation drift;
- invalid configuration and terminal reset policy;
- call-order evidence proving active-marker write does not precede candidate
  confirmation.

## ESP32-C6 compile targets

Two disabled targets compile the complete source set:

- minimal ESP32-C6 DevKitM laboratory target;
- full F1.0-RC2 product-board target.

Both targets contain no Broker address, CA, MQTT username, client ID, password,
eFuse key identifier, NVS namespace, partition name, or candidate generation.
Wi-Fi remains disabled at boot in the minimal target.

## Exclusions

Stage 2D-4 does not perform or claim:

- production MQTT profile switching;
- automatic startup recovery;
- physical NVS writes or active-marker mutation;
- real Broker validation;
- eFuse provisioning;
- firmware flashing or real-device testing;
- M401A, T1, Home Assistant, or Mosquitto operation;
- previous-slot retirement or credential revocation.

The next acceptance gate is source review and CI. A later isolated real-device
package requires separate explicit authorization before any hardware, eFuse,
physical NVS, or real Broker operation.
