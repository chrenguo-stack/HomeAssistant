# H3/N2 Stage 2D-8 G1 Test-Board Selection Record

## Operator decision

The operator selected **Scheme 1: a dedicated spare ESP32-C6 board** for the later isolated-device acceptance run.

The selected board may be fully erased and may use a test-only partition layout. No preservation of pre-existing Flash or NVS content is required. The board must not be a production node and must not contain production credentials, Home Assistant state, M401A/T1 state, or production Broker data.

## Initial serial inventory

The initial macOS serial-port inventory returned no matching ESP32 serial device:

```text
=== ESP32 SERIAL PORT INVENTORY ===
=== END ===
```

Therefore the physical serial path is unresolved and the execution gate remains locked.

## Current authorization boundary

This record authorizes only selection of the dedicated-board route and further read-only USB/serial enumeration.

It does not authorize:

- Flash read or write;
- chip erase;
- partition-table changes;
- physical NVS open;
- temporary Broker start;
- Wi-Fi or MQTT connection;
- loading a test key;
- `PREPARE_CANDIDATE`;
- `ACTIVATE_PROFILE`;
- `CLEANUP_TEST_STATE`.

## Next gate

Connect the dedicated board with a known data-capable USB cable and identify the exact USB device and `/dev/cu.*` path. Only after the path and board identity are recorded may a read-only chip-identification command be prepared.
