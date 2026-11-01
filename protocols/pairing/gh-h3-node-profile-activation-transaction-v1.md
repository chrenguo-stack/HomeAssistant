# GH H3 Node Profile Activation Transaction V1

## 1. Purpose

This contract defines the transaction boundary between a previously verified
candidate MQTT profile, the current active MQTT runtime, and the dual-slot
credential store. It is a source-level contract only. Stage 2D-3 does not wire
this transaction into production startup, a physical node, or a real Broker.

## 2. Entry evidence

Activation may be armed only when all of the following are true:

- the candidate credential generation is non-zero and greater than the active generation;
- the Stage 2D-2 authentication, subscription, and controlled telemetry round trip succeeded;
- the temporary candidate probe client was destroyed;
- the active MQTT profile remained unchanged during candidate verification;
- persistent recovery reports a matching PREPARED candidate generation.

Evidence mismatch fails closed before any runtime connection is changed.

## 3. Transaction order

```text
verify PREPARED generation
→ stop old active runtime, when one exists
→ start candidate as the sole runtime connection
→ confirm a fresh controlled round trip
→ commit candidate record and active marker
→ clear transient candidate material
```

Persistence commit is deliberately last. A candidate is never made the
persistent active profile before the runtime has completed its own fresh
round-trip confirmation.

## 4. Commit outcomes

The persistence adapter exposes three outcomes:

- `COMMITTED`: candidate record and authenticated active marker are committed;
- `OLD_ACTIVE_PRESERVED`: the old marker is known to remain authoritative;
- `INDETERMINATE_REBOOT_REQUIRED`: the write boundary cannot prove which marker
  is authoritative and the runtime must quiesce pending read-only recovery after
  reboot.

A boolean result is insufficient because a failed marker write and an unknown
post-write verification state require different recovery behavior.

## 5. Rollback

Before persistence commit, or after `OLD_ACTIVE_PRESERVED`, rollback is:

```text
stop candidate runtime
→ restore previous active runtime, when one existed
→ clear transient candidate material
```

If candidate stop or old-runtime restoration cannot be proven, all runtime
connections are quiesced and the state becomes `REBOOT_REQUIRED`.

For first enrollment, there is no previous active runtime. A rejected commit
stops the candidate and leaves the node without a committed MQTT profile.

## 6. Power-loss interpretation

- Loss before persistence commit: reboot recovery selects the previous marker.
- Candidate record committed but marker unchanged: recovery exposes a committed
  orphan and retains the previous active profile.
- Marker committed: reboot recovery selects the new generation.
- Marker authority unknown: no in-memory guess is allowed; reboot and read-only
  recovery are mandatory.

## 7. Terminal states

- `ACTIVATED`: new generation is runtime-active and persistence-committed;
- `ROLLED_BACK`: previous active runtime is restored and remains authoritative;
- `FAILED`: no runtime ambiguity exists, but activation did not complete;
- `REBOOT_REQUIRED`: runtime is quiesced because persistent or runtime authority
  cannot be proven.

All terminal paths clear transient candidate material. Old credential-slot
retirement is outside this contract and remains a later explicit lifecycle
operation.

## 8. Explicit exclusions

Stage 2D-3 does not:

- call ESPHome production MQTT username or password setters;
- restart the production MQTT component;
- invoke `PairingPersistentStore` from the compile-only lab;
- connect to a real Broker;
- write physical NVS or provision eFuse keys;
- modify production RC2 YAML;
- operate M401A, T1, Home Assistant, Mosquitto, or a physical ESP32-C6;
- revoke or erase the previous credential slot.
