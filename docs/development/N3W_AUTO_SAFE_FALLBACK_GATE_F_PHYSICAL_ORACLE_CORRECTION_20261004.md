# N3-W Auto Safe Fallback Gate F Physical Oracle Correction — 2026-10-04

Status: `GATE_F_ORACLE_CORRECTED_PHYSICAL_ACCEPTANCE_STILL_OPEN`

## Trigger

After the exact F1.0-RC2 production artifact was written to Board B, a 90-second Manager canonical-cursor observation showed no sequence advance:

```text
BOARD_B_BOOT_SESSION_BEFORE=dc40c82e1467cf88
BOARD_B_SEQ_BEFORE=112
BOARD_B_SOURCE_BEFORE=direct
BOARD_B_UPDATED_AT_BEFORE=2026-09-24T13:28:35.713Z
BOARD_B_SEQ_AFTER=112
BOARD_B_UPDATED_AT_AFTER=2026-09-24T13:28:35.713Z
USB_DIRECT_BASELINE=FAIL
```

That result must **not** be classified as a production runtime failure.

## Root cause: invalid observation oracle

The exact production target includes:

```text
firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml
```

At validated source head:

```text
b2419d17c198a85b7b50d9c1771544c2e3a0ab6b
```

that package explicitly states that it deliberately does **not** build or submit telemetry yet. Its current purpose is to attach the de-harnessed product runtime to the F1.0-RC2 whole-device baseline and provide the inert MQTT client that the runtime reconfigures after authenticated Manager pairing.

Therefore Manager canonical telemetry/cursor advance is not a valid liveness oracle for this exact production target.

## Correct identity boundary

Two different public-safe hashes must remain distinct:

```text
BOARD_B_ROM_IDENTITY_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
PAIRING_PROTOCOL_HARDWARE_ID_SHA256=cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0
```

The first is the esptool/write-time physical-board identity. The second is the application-layer pairing/registration hardware identity. Gate F must not use the ROM identity hash to query Manager registration state.

## Gate F disposition

```text
BOARD_B_WRITE=PASS
BOARD_B_APPLICATION_POSTWRITE_READBACK=PASS
BOARD_B_RUNTIME_OTADATA_KNOWN_STATE_MATCH=PASS
BOARD_B_REGISTRATION_IDENTITY_BIND=PASS
USB_DIRECT_BASELINE_CANONICAL_ORACLE=INVALID_FOR_CURRENT_PRODUCTION_TARGET
PRODUCTION_RUNTIME_FAILURE_PROVEN=false
GATE_F_PHYSICAL_ACCEPTANCE_COMPLETE=false
T1_ADDRESS_MUTATION_NOT_STARTED=true
MERGE=false
```

## Replacement physical oracle

Before any T1 address mutation, Gate F must establish current Board B runtime connectivity with non-telemetry evidence. Preferred evidence order:

1. Board B current LAN IPv4 resolved from the T1 LAN neighbor table using the locally known Board B base MAC; do not archive raw MAC/IP publicly.
2. Current established TLS/MQTT connection from that Board B IPv4 to T1 TCP/8883, observed from the T1 host/broker runtime.
3. Broker/Manager continuity and restart counters recorded before mutation.
4. For relocation execution, capture discovery traffic and prove that the Board reconnects to the new T1 IPv4 while preserving the same TLS server-name/CA/account contract.
5. Because this target does not publish telemetry yet, Manager canonical telemetry must not be used as the success criterion for this Gate F artifact.

No Board/T1 mutation is authorized by this document itself; the existing explicit Gate F authorization and per-step safety stops remain in force.
