# H3/N2 Stage 2D-2 Candidate MQTT Profile Validator

**Date:** 2026-07-21  
**Base main:** `2231ffbf27af4c359be18b5dc8fc415139918383`  
**Branch:** `feature/h3-n2-stage2d2-candidate-mqtt-profile-validator-20260721-v50`  
**Status:** non-production source and compile validation

## Goal

Validate a newly paired MQTT credential profile with an independent ESP-IDF
MQTT client while leaving the current active MQTT connection untouched.

The stage verifies:

- strict profile and credential generation validation;
- TLS/MQTT authentication observation;
- QoS 1 subscription readiness;
- a Manager-confirmed telemetry probe round trip;
- candidate destruction and secret wiping on every terminal path;
- success stopping at `VERIFIED`.

## Architecture

The shared `CandidateMqttProfileValidator` is transport-independent. It owns the
candidate profile, canonical probe exchange, timeout, failure classification,
and the existing Stage 2C-3 MQTT activation contract. It intentionally exposes
no activation method.

`CandidateMqttTransport` is the narrow boundary used by host fakes and the
ESP-IDF laboratory adapter.

The laboratory adapter owns a separate `esp_mqtt_client_handle_t`. It does not
reference the ESPHome production MQTT singleton and does not call production
username/password setters.

## State and invariants

Normal path:

```text
IDLE -> CANDIDATE_STAGED -> CONNECTING -> SUBSCRIBING
     -> ROUND_TRIP -> VERIFIED
```

Terminal failure and cancellation paths destroy the candidate client and wipe
profile material. The configured active generation is immutable throughout the
validator lifetime.

Success also destroys the temporary candidate client after the confirmation is
received. `VERIFIED` records that the credentials and ACL path worked; it does
not mean that the node switched its production connection.

## Probe protocol

Publish:

```text
gh/v1/<sid>/ingress/node/<node_id>/telemetry
```

Subscribe:

```text
gh/v1/<sid>/out/node/<node_id>/confirm
```

The request and confirmation bind:

- schema;
- node ID;
- credential generation;
- random lowercase-hex nonce;
- accepted status.

An exact Manager confirmation is required. A connect event or publish
acknowledgment alone is insufficient.

## Host fault matrix

The deterministic fake transport covers:

- invalid timeout;
- invalid profile and TLS host mismatch;
- stale generation;
- malformed nonce;
- client creation failure;
- client start failure;
- authentication failure;
- subscription failure;
- publish failure;
- confirmation mismatch;
- generic transport error;
- timeout;
- transport observation ordering violations;
- cancellation;
- successful authentication, subscription, round trip, secret wipe, and
  `VERIFIED` termination.

Every case asserts that active generation remains unchanged and that the
candidate client is not live at the terminal state.

## ESP32-C6 compile targets

Two non-production targets compile the real ESP-IDF MQTT adapter:

1. minimal ESP32-C6 target;
2. complete F1.0-RC2 product-board target.

Both targets contain no Broker host, CA, username, client ID, password, or
candidate generation. Wi-Fi is disabled at boot in the minimal target. Neither
YAML exposes a button or automation calling `begin_for_lab()`.

## Production boundary

This stage does not:

- modify `f1_0_rc2.yml`;
- read or write NVS;
- burn or read provisioning eFuse keys;
- replace the active ESPHome MQTT profile;
- restart the active connection;
- contact a real Broker in CI;
- modify Manager, Mosquitto, Home Assistant, M401A, or T1;
- operate a physical ESP32-C6 board;
- activate, commit, or retire credentials.

The boundary gate checks changed paths, startup behavior, forbidden mutation
APIs, absence of environment-looking Broker addresses, independent-client
lifecycle evidence, and the lack of an activation call.

## Remaining stages

Later work must separately design and authorize:

- Manager support for telemetry-probe confirmations;
- isolated real Broker and real-board validation;
- NVS `profile_verified` integration;
- atomic production profile switch;
- old-profile observation and retirement;
- reboot and rollback behavior;
- credential rotation and revocation.
