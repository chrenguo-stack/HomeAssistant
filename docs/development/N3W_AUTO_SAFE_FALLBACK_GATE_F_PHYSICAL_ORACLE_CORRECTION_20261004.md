# N3-W Auto Safe Fallback Gate F Physical Oracle Correction — 2026-10-04

Status: `GATE_F_BASELINE_FAILURE_CONFIRMED_DIAGNOSIS_OPEN`

## Correction notice

An earlier revision of this document incorrectly concluded that Manager canonical telemetry was not a valid liveness oracle for the exact F1.0-RC2 production target. That conclusion was based only on the comment in `n3w_product_transport.yml`, which says that the transport package itself does not build or submit telemetry.

The exact target also includes `packages/n3w_product_telemetry.yml`. At validated source head `b2419d17c198a85b7b50d9c1771544c2e3a0ab6b`, that package builds real-sensor `gh.telemetry/1` payloads and executes `publish_n3w_telemetry` every `${n3w_telemetry_interval}`. The exact target sets `n3w_telemetry_interval: 60s`.

Therefore the previous statement that this target does not publish telemetry is retracted.

## Exact target authority

```text
VALIDATED_SOURCE_HEAD=b2419d17c198a85b7b50d9c1771544c2e3a0ab6b
TARGET=firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
TELEMETRY_PACKAGE=firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml
TELEMETRY_INTERVAL_SECONDS=60
```

The telemetry bridge submits only when `id(n3w_product_core).runtime_ready()` is true. It obtains boot/sequence identity from the product core and calls `submit_telemetry_json()`.

## Physical evidence

After the exact artifact was written to Board B, a 90-second Manager canonical-cursor observation showed no advance:

```text
BOARD_B_BOOT_SESSION_BEFORE=dc40c82e1467cf88
BOARD_B_SEQ_BEFORE=112
BOARD_B_SOURCE_BEFORE=direct
BOARD_B_UPDATED_AT_BEFORE=2026-09-24T13:28:35.713Z
BOARD_B_BOOT_SESSION_AFTER=dc40c82e1467cf88
BOARD_B_SEQ_AFTER=112
BOARD_B_SOURCE_AFTER=direct
BOARD_B_UPDATED_AT_AFTER=2026-09-24T13:28:35.713Z
SEQ_ADVANCED=false
UPDATED_AT_ADVANCED=false
USB_DIRECT_BASELINE=FAIL
```

Additional T1-side evidence established:

```text
BOARD_B_LAN_REACHABLE=true
BOARD_B_BASE_MAC_MATCH=true
BROKER_8883_PUBLICATION=0.0.0.0:8883
BOARD_B_TO_BROKER_8883_CONNTRACK_PRESENT=false
```

A 30-second passive packet window also observed no Board B traffic on TCP/8883, TCP/47112, or UDP/47111. The short packet window by itself is not sufficient to exclude an idle long-lived connection, but the host connection/conntrack evidence did not establish a Board B 8883 session.

## Correct identity boundary

Two different public-safe hashes remain distinct:

```text
BOARD_B_ROM_IDENTITY_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
PAIRING_PROTOCOL_HARDWARE_ID_SHA256=cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0
```

The first is the esptool/write-time physical-board identity. The second is the application-layer pairing/registration hardware identity. Read-only registration lookup using the pairing-protocol identity matched exactly one active Board B registration and a canonical cursor.

## Gate F disposition

```text
BOARD_B_WRITE=PASS
BOARD_B_APPLICATION_POSTWRITE_READBACK=PASS
BOARD_B_RUNTIME_OTADATA_KNOWN_STATE_MATCH=PASS
BOARD_B_REGISTRATION_IDENTITY_BIND=PASS
BOARD_B_WIFI_LAN_REACHABILITY=PASS
USB_DIRECT_BASELINE=FAIL
BOARD_B_BROKER_8883_CONNECTIVITY=NOT_PROVEN
PRODUCTION_RUNTIME_FAILURE_DIAGNOSIS_OPEN=true
T1_ADDRESS_MUTATION_NOT_STARTED=true
GATE_F_PHYSICAL_ACCEPTANCE_COMPLETE=false
MERGE=false
```

## Next diagnostic boundary

Do not change the T1 address yet. The next read-only evidence must determine where Board B stops in the production startup path:

1. pairing client initialization / `ALREADY_PROVISIONED` recognition;
2. durable peer/broker state load and validation;
3. runtime MQTT reconfiguration and enable;
4. runtime readiness / telemetry submission.

Preferred next evidence is Board B boot/runtime serial logging while leaving Flash, NVS, T1, Broker, and Manager unchanged.
