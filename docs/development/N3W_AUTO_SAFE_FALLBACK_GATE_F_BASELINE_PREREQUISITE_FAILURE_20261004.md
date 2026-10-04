# N3-W Auto Safe Fallback Gate F Baseline Prerequisite Failure — 2026-10-04

Status: `GATE_F_BLOCKED_BY_PREEXISTING_PAIRING_REPAIR_WAIT`

## Scope

This record captures the physical Gate F baseline diagnosis after the exact production artifact was written to Board B. No T1 address mutation has started.

## Validated artifact and write boundary

```text
PRODUCT_SOURCE_HEAD=b2419d17c198a85b7b50d9c1771544c2e3a0ab6b
BOARD_B_WRITE=PASS
BOARD_B_APPLICATION_POSTWRITE_READBACK=PASS
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

The write preserved product NVS.

## Identity boundary

Two different identities remain distinct:

```text
BOARD_B_ROM_IDENTITY_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
PAIRING_PROTOCOL_HARDWARE_ID_SHA256=cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0
```

The Manager registration lookup by the pairing-protocol hardware identity matched exactly one active registration with a canonical cursor. Raw hardware ID, node ID, MAC address and LAN IPv4 are intentionally not archived here.

## Physical baseline evidence

Board B remained reachable on the LAN and the observed LAN identity matched the locally known board identity. The T1 Broker continued publishing TLS MQTT on TCP/8883. However no current Board-B-to-8883 connection was established, and the Manager canonical cursor did not advance during a 90-second observation.

The exact production target includes both `n3w_product_transport.yml` and `n3w_product_telemetry.yml`; the telemetry bridge submits at the configured 60-second interval when the N3-W runtime is ready. Therefore the lack of canonical advancement is a valid failure signal for this target.

A passive Board B USB serial capture then repeatedly showed:

```text
Simplified pairing waiting code=1
```

At the exact source head, `SimplePairingClientError` value 1 is `NOT_READY`. The repaired KF-099 client returns `NOT_READY` for the `rejected + transaction_disposition=continue -> WAIT` branch.

## Historical continuity

KF-099 physical closure on 2026-09-28 intentionally left Board B in the no-authorization repair-wait condition. The Manager returned `repair_intent_required`, the Board preserved its pairing transaction, and no repair authorization was granted. That gate explicitly proved WAIT behavior rather than restoring a normally provisioned runtime.

Current production and KF-099 runtime stores use the same Broker NVS namespace/key (`gh_n3w_v2` / `broker`), so the present WAIT state is not explained by a production-core namespace migration.

## Disposition

```text
BOARD_B_WIFI_BASELINE=PASS
BOARD_B_MQTT_8883_BASELINE=FAIL
BOARD_B_TELEMETRY_BASELINE=FAIL
BOARD_B_PAIRING_WAIT_OBSERVED=true
PAIRING_WAIT_ERROR_CODE=NOT_READY
PREEXISTING_KF099_REPAIR_WAIT_CONTINUITY=SUPPORTED
AUTO_SAFE_FALLBACK_DEFECT_PROVEN=false
GATE_F_PAIRED_BASELINE_PREREQUISITE=FAIL
T1_ADDRESS_MUTATION_NOT_STARTED=true
MERGE=false
```

Gate F must not proceed to T1 DHCP/address-change testing until Board B is restored to a normal, identity-preserving paired runtime with a current MQTT/TLS baseline.

The next gate is a read-only pairing/credential prerequisite audit. If the existing identity and credential lineage are intact, use the Manager's bounded ordinary-repair authorization path rather than deleting registration state or performing destructive re-pairing. After repair, freeze the new healthy baseline and restart Gate F from the paired-runtime prerequisite.
