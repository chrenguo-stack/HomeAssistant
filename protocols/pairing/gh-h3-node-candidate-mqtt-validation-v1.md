# GH H3/N2 Candidate MQTT Profile Validation V1

## 1. Scope

This contract validates a newly delivered node MQTT profile without replacing or
stopping the currently active MQTT connection.

Stage 2D-2 ends at `VERIFIED`. It does not activate the candidate, update the
production ESPHome MQTT component, commit an NVS marker, or revoke the old
profile.

## 2. Isolation rule

The validator creates a dedicated `esp_mqtt_client_handle_t` for the candidate.
The candidate handle has its own Broker address, CA, username, client ID,
password, subscriptions, event handler, timeout, and lifecycle.

The active MQTT connection is outside the validator API. No active-client
pointer, username/password setter, global MQTT singleton, reconnect request, or
profile-switch method is accepted by this contract.

All terminal paths destroy the candidate handle and wipe candidate credential
material. The recorded active generation must remain unchanged.

## 3. Required candidate fields

- `system_id`
- `node_id`
- canonical DNS `broker_host`
- TLS port
- `broker_tls_server_name`, exactly equal to `broker_host` in V1
- system CA PEM
- per-node MQTT username
- per-node MQTT client ID
- per-node MQTT password
- monotonically newer credential generation

IP literals are rejected as the TLS server identity. Candidate generation must
be non-zero and greater than the configured active generation.

## 4. Probe states

```text
IDLE
  -> CANDIDATE_STAGED
  -> CONNECTING
  -> SUBSCRIBING
  -> ROUND_TRIP
  -> VERIFIED
```

Any invalid input, transport error, timeout, authentication rejection,
subscription failure, publish failure, confirm mismatch, or observation
invariant violation enters `FAILED`.

An explicit cancellation enters `CANCELLED`.

Neither `VERIFIED`, `FAILED`, nor `CANCELLED` changes the active generation.

## 5. Controlled telemetry round trip

The candidate subscribes with QoS 1 to:

```text
gh/v1/<system_id>/out/node/<node_id>/confirm
```

It then publishes with QoS 1 to:

```text
gh/v1/<system_id>/ingress/node/<node_id>/telemetry
```

Canonical request payload:

```json
{"credential_generation":7,"node_id":"n_01JABCDEF","nonce":"0123456789abcdef","schema":"gh.telemetry-probe/1"}
```

Canonical accepted confirmation:

```json
{"credential_generation":7,"node_id":"n_01JABCDEF","nonce":"0123456789abcdef","schema":"gh.telemetry-probe-confirm/1","status":"accepted"}
```

The confirmation must match the expected topic and exact canonical payload. The
nonce is lowercase hexadecimal, 8 to 32 bytes, generated outside this contract.

The round trip proves the following candidate properties together:

1. TLS server authentication succeeded;
2. MQTT username/password authentication succeeded;
3. the candidate can subscribe to its permitted node output namespace;
4. the candidate can publish to its permitted node ingress namespace;
5. the Manager accepted the controlled probe and returned the bound generation
   and nonce.

A publish acknowledgment alone is not a telemetry round trip.

## 6. Completion semantics

Success records:

- `authenticated=true`;
- `subscribe_ready=true`;
- `telemetry_round_trip=true`;
- phase `VERIFIED`;
- candidate client destroyed;
- candidate secrets wiped;
- active generation unchanged.

Stage 2D-2 deliberately provides no `activate()` operation. Candidate
activation, persistent marker switch, old-profile retirement, reboot recovery,
and real Broker/board acceptance are separate later stages requiring explicit
operator authorization.

## 7. Current test boundary

The repository includes a deterministic host transport fault matrix and two
ESP32-C6 compile-only targets. Their Wi-Fi is disabled at boot and no candidate
credentials or Broker address are supplied. They must not be interpreted as
real Broker, real node, NVS, eFuse, or production acceptance evidence.
