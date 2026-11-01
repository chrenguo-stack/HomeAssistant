# GH H3 Node Production Profile Adapters v1

## 1. Scope

This contract defines the Stage 2D-5 source adapters that connect the previously
verified profile lifecycle to ESP-IDF MQTT and authenticated NVS persistence.
The contract does not authorize a physical node, Broker, eFuse, or NVS operation.

## 2. Adapter roles

Three MQTT session roles are isolated:

1. **candidate probe session** — validates a PREPARED candidate independently;
2. **active session** — carries the currently authoritative profile;
3. **activation candidate session** — becomes the sole runtime during marker-last
   activation and performs a fresh confirmation round trip.

The candidate probe session must never reuse or mutate the active session.

## 3. MQTT transport requirements

The ESP-IDF session adapter shall:

- use a dedicated `esp_mqtt_client_handle_t` per session;
- require TLS and a supplied CA certificate;
- bind Broker hostname, TLS verification name, username, password, client ID,
  and credential generation to one immutable configured session;
- use QoS 1 for the confirmation subscription and telemetry probe publication;
- compare the full confirmation topic and payload, including fragmented MQTT
  data events;
- destroy a failed or completed probe client and clear its credential material;
- classify connection refusal separately from general transport failure;
- expose bounded connection and round-trip waits only to a caller-controlled
  worker context, never from the ESP-IDF MQTT event callback.

## 4. Runtime activation requirements

Before rotation, the active session must already be bound to the same recovered
active credential bundle. A lifecycle runtime must reject:

- an absent or non-live active session when an active generation exists;
- any active credential mismatch;
- a candidate generation not strictly greater than active;
- a live candidate session before activation;
- any generation drift between recovery, validation, runtime staging, and
  persistence preflight.

Activation order remains:

```text
stop old active
→ start candidate as sole runtime
→ confirm fresh QoS 1 round trip
→ commit persistent active marker last
```

After a successful marker commit, candidate credential material becomes active
material. The caller must invoke `finalize_activation_promotion()` after the
lifecycle integration reports `ACTIVATED`; this swaps session roles for the next
rotation without changing the coordinator's final candidate-live observation.

## 5. Persistence composition

`ProductionPersistenceAdapter` composes an injected backend, key provider,
crypto envelope, and `PairingPersistentStore` for deterministic host testing.

`EspIdfProductionPersistenceAdapter` composes:

- `EspIdfNvsPersistenceBackend`;
- `EfuseHmacPersistenceKeyProvider`;
- `PairingPersistenceCrypto`;
- `PairingPersistentStore`.

Read-only open is permitted by default. Read-write open must be enabled by an
explicit `allow_read_write` policy at configuration time. Opening a namespace is
not itself evidence that a lifecycle write is authorized.

## 6. Failure closure

- Candidate authentication, subscribe, publish, timeout, or payload mismatch
  leaves the persistent active marker unchanged.
- Candidate runtime confirmation failure stops the candidate and restores the
  old active session when old authority is provable.
- Ambiguous persistent authority requires quiescing all MQTT sessions and reboot
  recovery.
- A session-role promotion failure is a post-commit integration fault and must
  block the next lifecycle until resolved.

## 7. Stage 2D-5 execution boundary

This stage is source, host-test, and ESP32-C6 compile-only. It does not:

- connect to a real Broker;
- open or write physical NVS during validation;
- read, provision, or burn eFuse on a device;
- flash or operate an ESP32-C6 board;
- modify M401A, T1, Home Assistant, or Mosquitto;
- add startup automation, buttons, switches, or production YAML activation.
