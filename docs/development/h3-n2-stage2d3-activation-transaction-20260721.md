# H3/N2 Stage 2D-3 Profile Activation Transaction

## Status

Stage 2D-3 adds a transport- and storage-adapter-independent transaction
coordinator. The implementation is intentionally non-production and compile
only on ESP32-C6 targets.

Base main:

`54f4906e29db09c56df889e569c062efcad2b96e`

Development branch:

`feature/h3-n2-stage2d3-activation-transaction-20260721-v51`

## Goal

Stage 2D-2 proved that a candidate MQTT profile can be independently validated
without changing the active connection. Stage 2D-3 defines the next transaction:
make a verified candidate runtime-active, confirm it again, and only then commit
the persistent active marker.

## Coordinator sequence

```text
IDLE
→ ARMED
→ STOPPING_OLD
→ STARTING_CANDIDATE
→ CONFIRMING_CANDIDATE
→ COMMITTING_PERSISTENCE
→ ACTIVATED
```

Failure may end in `FAILED`, `ROLLED_BACK`, or `REBOOT_REQUIRED`.

## Safety properties

- Stage 2D-2 evidence must state that the candidate was verified, its temporary
  probe client was destroyed, and the active profile remained unchanged.
- Candidate and active generations must match the persistent PREPARED record.
- The old runtime is stopped before the candidate becomes the sole runtime.
- A fresh candidate round trip must complete before persistent commit.
- A known old-marker-preserved commit failure restores the old runtime.
- An indeterminate persistence result quiesces all runtime connections and
  requires reboot recovery instead of guessing.
- Candidate stop or old-runtime restoration failure also requires reboot.
- Transient candidate material is cleared on every terminal path.
- First enrollment is supported without pretending an old runtime exists.

## Fault matrix

The host matrix covers:

- invalid verification evidence and generation drift;
- PREPARED record mismatch;
- old runtime invariant mismatch;
- failure to stop the old runtime;
- candidate start failure;
- candidate round-trip failure;
- persistence rejection with old marker preserved;
- indeterminate persistence result;
- candidate stop failure;
- old runtime restoration failure;
- successful marker-last activation;
- first enrollment success and persistence rejection;
- call-order evidence proving persistence commit occurs after confirmation.

## ESP32-C6 compile targets

Two disabled laboratory assemblies are provided:

- minimal ESP32-C6 DevKitM target;
- full F1.0-RC2 product-board target.

The lab component constructs only the coordinator and calls `configure(0)`.
There is no runtime adapter, persistence adapter, action, button, startup
activation, MQTT setter, NVS mutation, or Broker address.

## CI and boundary enforcement

The dedicated workflow compiles and runs the host matrix, validates the exact
changed-path set, checks protected production files, rejects MQTT/NVS production
integration tokens, rejects YAML startup triggers, and compiles both ESP32-C6
targets with ephemeral disabled Wi-Fi values and secret-redaction checks.

## Exclusions

This stage does not perform or claim:

- production MQTT profile switching;
- physical NVS writes or marker changes;
- real Broker validation;
- eFuse provisioning;
- firmware flashing or physical-node testing;
- M401A, T1, Home Assistant, or Mosquitto operation;
- previous credential-slot retirement;
- recovery-factory-reset or revocation lifecycle completion.

The next decision after source and CI acceptance is whether to merge this
transaction contract before developing a production integration adapter and the
first isolated real-device acceptance package.
