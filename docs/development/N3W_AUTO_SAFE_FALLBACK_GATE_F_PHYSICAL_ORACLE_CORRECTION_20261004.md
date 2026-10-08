# N3-W Auto Safe Fallback Gate F Physical Oracle Correction — 2026-10-04

Status: `GATE_F_BASELINE_PREREQUISITE_REPAIR_PREPARED_EXECUTION_NOT_STARTED`

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

## Initial physical evidence

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

## Direct serial diagnosis

A 30-second passive USB-CDC capture on Board B produced repeated:

```text
Simplified pairing waiting code=1
```

At the validated production source, `SimplePairingClientError::NOT_READY == 1`. The repaired KF-099 client maps Manager `status=rejected + transaction_disposition=continue` to WAIT/NOT_READY and preserves the current pairing transaction without calling `/begin`.

This is consistent with the prior KF-099 physical validation where Board B was intentionally left waiting on `repair_intent_required` and no repair authorization was granted.

Therefore the Gate F baseline failure is not evidence that auto-safe-fallback broke a healthy paired node. The stronger classification is:

```text
GATE_F_PREREQUISITE_HEALTHY_PAIRED_BASELINE=false
BOARD_B_ENTERED_GATE_F_WITH_KF099_REPAIR_WAIT_STATE=true
AUTO_SAFE_FALLBACK_REGRESSION_PROVEN=false
```

## Registration and credential prerequisite audit

A read-only Manager audit matched exactly one active Board B registration and one current credential assignment:

```text
REGISTRATION_MATCH_COUNT=1
REGISTRATION_ACTIVE=true
PAIRING_EPOCH=7
NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
PAIRING_SESSION_FOUND=true
PAIRING_SESSION_STATE=approved
CREDENTIAL_HISTORY_COUNT=1
CURRENT_CREDENTIAL_COUNT=1
CREDENTIAL_STATE=active
ACTIVE_GENERATION=2
PENDING_GENERATION=None
CREDENTIAL_NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
REGISTRATION_CREDENTIAL_NODE_MATCH=true
PAIRING_PREREQUISITE_AUDIT=PASS
```

The Manager-side durable identity and credential lineage are therefore healthy. No database reset or registration deletion is required.

## Live repair transaction binding

A passive T1 raw-socket capture of Board B TCP/47112 traffic established one exact current pairing transaction:

```text
TCP47112_PAYLOAD_PACKET_COUNT=24
TCP47112_PAYLOAD_BYTES=2028
LIVE_HARDWARE_ID_COUNT=1
LIVE_PAIRING_ID_COUNT=1
LIVE_HARDWARE_ID_SHA256=cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0
LIVE_HARDWARE_ID_MATCH=true
LIVE_PAIRING_ID_SHA256=142d1e0c9fc035645ce38e4681add39ba3ed5b3b0d60e14a4a1dfa398ab2472e
PAIRING_EQUALS_OLD_REGISTRATION=false
PAIRING_EQUALS_OLD_CREDENTIAL=false
LIVE_REPAIR_TRANSACTION_BIND=PASS
```

No raw hardware ID or pairing ID is recorded in this document.

## Setup Secret read-only recovery

The production source stores the Setup Secret as a 72-byte `PersistedSetupSecret` record in NVS namespace/key:

```text
namespace=gh_n3w_v2
key=setup
```

Record layout:

```text
uint32 magic
uint16 version
uint16 reserved
uint8 secret[32]
uint8 check[32]
```

The check is SHA-256 over the bytes preceding `check`.

Board B NVS was read using esptool in read-only mode from the discovered NVS partition:

```text
NVS_OFFSET=0x790000
NVS_SIZE=0x70000
BOARD_FLASH_WRITE=false
```

The existing record decoded and validated successfully:

```text
SETUP_RECORD_COUNT=1
SETUP_RECORD_BYTES=72
SETUP_MAGIC_VALID=true
SETUP_VERSION=1
SETUP_RESERVED=0
SETUP_RECORD_CHECK_VALID=true
SETUP_SECRET_BYTES=32
SETUP_SECRET_NONZERO=true
SETUP_SECRET_SHA256=9f82618077f22f64d467fe8080457b9c16cf2e9647cae6299218dba19f1f366d
SETUP_SECRET_LOCAL_FILE_PRESENT=true
SETUP_SECRET_FILE_MODE=600
SETUP_RECORD_DECODE=PASS
RAW_NVS_ARTIFACTS_REMOVED=true
```

The raw Setup Secret is intentionally not archived in GitHub or chat. Only its SHA-256 is recorded. The secret remains only in a local mode-0600 temporary file on the Mac for the controlled recovery transaction.

## Correct recovery path

Source review confirms that ordinary `authorize-repair` is insufficient for this exact existing-identity recovery. Product recovery requires the explicit existing-identity credential-recovery path:

```text
authorize-credential-recovery
+ matching live hardware_id/pairing_id
+ matching Setup Secret import
```

The Manager then preserves the stable node identity and uses credential lifecycle staging. Broker credential mutation is deferred until the Board receipt/ACK commits the staged recovery. An aborted recovery before receipt preserves the previous active generation.

## Correct identity boundary

Two different public-safe hashes remain distinct:

```text
BOARD_B_ROM_IDENTITY_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
PAIRING_PROTOCOL_HARDWARE_ID_SHA256=cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0
```

## Gate F disposition

```text
BOARD_B_WRITE=PASS
BOARD_B_APPLICATION_POSTWRITE_READBACK=PASS
BOARD_B_RUNTIME_OTADATA_KNOWN_STATE_MATCH=PASS
BOARD_B_REGISTRATION_IDENTITY_BIND=PASS
BOARD_B_WIFI_LAN_REACHABILITY=PASS
USB_DIRECT_BASELINE=FAIL
GATE_F_PREREQUISITE_HEALTHY_PAIRED_BASELINE=false
KF099_REPAIR_WAIT_STATE_CONFIRMED=true
MANAGER_IDENTITY_AND_CREDENTIAL_LINEAGE=PASS
LIVE_REPAIR_TRANSACTION_BIND=PASS
SETUP_SECRET_RECORD_DECODE=PASS
CREDENTIAL_RECOVERY_EXECUTION_NOT_STARTED=true
T1_ADDRESS_MUTATION_NOT_STARTED=true
GATE_F_PHYSICAL_ACCEPTANCE_COMPLETE=false
MERGE=false
```

## Next boundary

Do not change the T1 address yet. First restore Board B to a healthy paired baseline through the exact live existing-identity credential-recovery transaction, then re-establish MQTT/TLS and canonical telemetry. Only after that baseline passes may the formal Gate F T1-address-change test begin.
