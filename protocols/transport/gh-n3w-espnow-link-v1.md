# GH N3-W ESP-NOW single-hop link v1

Status: Draft / P4b host-only + compile-only contract gate.

This document freezes the Child↔Relay **local radio link** used by N3-W. It does not authorize board execution, production key provisioning, production MQTT forwarding, or Manager production activation. The Manager-facing application contract remains `gh-n3w-single-hop-v1.md`.

## 1. Topology and identity

- Exactly one hop is permitted: **Child → Wi-Fi Relay**.
- ESP-NOW Mesh, multi-hop forwarding, Child-as-Relay behavior, and Relay-to-Relay forwarding are forbidden.
- A Child transmits only its own `NODE_ID` telemetry.
- Switching between Wi-Fi Direct and Relay must not create a second `NODE_ID` or a second Home Assistant device.
- The Relay never owns the Child↔Manager application key and never decrypts the application ciphertext.
- Manager remains the only canonical publisher. The Relay only transports an opaque N3-W application frame to the Manager ingress boundary.

## 2. Two independent cryptographic layers

### 2.1 Child↔Manager application AEAD

The P4a contract remains unchanged:

- AES-256-GCM;
- per-node/per-epoch 32-byte application key;
- nonce = `uint64_be(boot_session) || uint32_be(seq)`;
- AAD binds `schema`, `transport`, `gateway_id`, `node_id`, `hop_count`, `key_epoch`, `boot_id`, and `seq`.

The Relay does not possess this key.

### 2.2 Child↔Relay local link protection

A provisioned peer binding contains:

- exact `gateway_id`;
- exact Relay STA MAC address;
- exact 16-byte ESP-NOW LMK;
- optional preferred Wi-Fi channel.

A Relay-side Child binding contains exact `node_id`, exact Child STA MAC, and the same 16-byte peer LMK.

ESP-NOW unicast peers must be configured with `encrypt=true`. A nonzero 16-byte PMK is injected into the driver before peer configuration. Production PMK/LMK provisioning is outside P4b.

Authenticated control packets additionally use HMAC-SHA-256 truncated to 16 bytes. The HMAC key is domain-separated from the ESP-NOW LMK:

`control_key = HMAC-SHA256(LMK, "gh.n3w-control-v1")`

`auth16 = first_16_bytes(HMAC-SHA256(control_key, packet_without_auth16))`

This control authentication never uses the Child↔Manager application key.

## 3. Discovery is an untrusted hint

Relay discovery advertisements are broadcast and unauthenticated. They may only provide a hint containing `gateway_id` and current Wi-Fi channel.

A Child MUST reject an advertisement unless:

1. the advertised `gateway_id` exactly matches its persisted Relay binding;
2. the ESP-NOW source MAC exactly matches the persisted Relay MAC;
3. the advertised channel is valid and, when a preferred channel is frozen, equals that channel.

An advertisement MUST NOT create, replace, or mutate a peer binding.

After a matching hint, the Child configures the pre-provisioned encrypted peer and performs the authenticated Probe/ProbeAck exchange before Relay mode is considered usable.

## 4. Channel policy

The Relay operates ESP-NOW on its current Wi-Fi channel. The Child discovery scan plan:

1. tries the last known Direct Wi-Fi channel first when available;
2. then visits a configured, de-duplicated allow-list of valid channels;
3. never accepts a channel outside that allow-list/preferred binding policy;
4. returns channel ownership to normal Wi-Fi behavior when Direct mode is restored.

P4b freezes the policy machinery only. It does not freeze a production channel list.

## 5. Binary link packet envelope

All packets start with four bytes:

| Offset | Field | Value |
|---:|---|---|
| 0 | magic[0] | ASCII `G` |
| 1 | magic[1] | ASCII `H` |
| 2 | link_version | `1` |
| 3 | packet_type | see below |

Packet types:

- `1` DiscoveryAdvertisement
- `2` Probe
- `3` ProbeAck
- `4` DataFragment
- `5` ReceiptAck

All integers are unsigned big-endian. Every encoded datagram MUST be `<= 240` bytes so the implementation remains within the conservative ESP-NOW v1 payload boundary even though the current ESP32-C6 stack can support newer ESP-NOW versions.

## 6. Control packets

### 6.1 DiscoveryAdvertisement (`type=1`)

`prefix || channel:u8 || gateway_id_len:u8 || gateway_id:utf8`

No `auth16`. It is an untrusted hint and is accepted only through the exact persisted MAC+gateway binding check above.

### 6.2 Probe (`type=2`)

`prefix || challenge:u64 || gateway_id_len:u8 || gateway_id || node_id_len:u8 || node_id || auth16`

- `challenge` MUST be nonzero and fresh for the attempt.
- The Relay verifies HMAC, expected local `gateway_id`, and source-MAC-bound `node_id`.

### 6.3 ProbeAck (`type=3`)

`prefix || challenge:u64 || accepted:u8 || auth16`

The Child accepts it only from its exact bound Relay MAC, with valid HMAC and the exact outstanding challenge.

### 6.4 ReceiptAck (`type=5`)

`prefix || boot_session:u64 || seq:u32 || status:u8 || auth16`

`status=0` means `ACCEPTED_FOR_FORWARDING`. `status=1` is reserved as an internal negative result; P4b does not require a negative receipt to be transmitted.

A Child may delete a cached Relay frame only after an authenticated `status=0` receipt matching the exact `(boot_session, seq)`.

## 7. Data fragmentation (`type=4`)

The Manager-facing `gh.relay/1` JSON/base64 envelope is **not** transmitted directly over ESP-NOW. The Child transmits the already encrypted P4a `RelayFrame` through compact binary fragments.

Each fragment is:

`prefix`
`|| boot_session:u64`
`|| seq:u32`
`|| key_epoch:u32`
`|| total_ciphertext:u16`
`|| fragment_index:u8`
`|| fragment_count:u8`
`|| offset:u16`
`|| nonce:12 bytes`
`|| tag:16 bytes`
`|| ciphertext_fragment:1..180 bytes`

Rules:

- `total_ciphertext` is `1..1024` bytes.
- fragment payload is at most `180` bytes.
- at most `6` fragments are required for a 1024-byte ciphertext.
- canonical `offset = fragment_index * 180`.
- `fragment_count = ceil(total_ciphertext / 180)`.
- nonce, tag, boot session, seq, key epoch, total length, and fragment count MUST be identical across all fragments of one frame.
- every datagram is at most `234` bytes under this format.
- retries resend the exact same already-encrypted fragments. They MUST NOT re-encrypt modified plaintext under the same `(key_epoch, boot_session, seq)`.

`gateway_id` and `node_id` are intentionally absent from DataFragment. The Relay reconstructs them from its local gateway identity and the exact source-MAC Child binding. If the Child encrypted with different identity values in application AAD, the Manager's application AEAD validation fails closed.

## 8. Relay reassembly and forwarding receipt

For each bound Child peer, Relay reassembly is bounded to one in-flight `(boot_session, seq)` frame.

- exact duplicate fragments are idempotent;
- a duplicate index with different bytes is rejected as conflict;
- a different tuple while one frame is incomplete is rejected as busy;
- inconsistent metadata/nonce/tag is rejected;
- the Relay does not decrypt or validate application plaintext.

After complete reassembly, the Relay passes the reconstructed `RelayFrame` to an abstract `RelayForwardSink`.

A positive ReceiptAck is eligible only **after** that sink has accepted the frame for forwarding. It is not a Manager canonical-acceptance acknowledgment. Manager persistent replay/high-water logic remains the final duplicate and canonical-ingress authority.

If the local receipt is lost, the Child may retransmit the identical frame. The Relay may forward the duplicate again; Manager replay protection must reject duplicate canonical consumption.

## 9. Child bounded cache and retry

The Child maintains a bounded Relay cache of already-encrypted frames. Capacity and retry policy are configuration inputs rather than production constants.

The reference policy implementation provides:

- configurable initial retry delay;
- exponential backoff capped by configurable maximum delay;
- configurable maximum attempts;
- exact immutable datagram reuse across retries;
- deletion only after authenticated positive ReceiptAck for the exact tuple;
- retry exhaustion surfaced as Relay degradation rather than silently dropping identity/replay rules.

## 10. Local Direct↔Relay path controller

The node-side radio controller is distinct from Manager path lease arbitration.

Reference states:

- `DIRECT`
- `DISCOVERY`
- `RELAY_ACTIVE`

Reference transition policy is configurable:

- consecutive Direct failures: `DIRECT → DISCOVERY`;
- matching advertisement + encrypted peer + authenticated ProbeAck: `DISCOVERY → RELAY_ACTIVE`;
- while Relay is active, bounded Direct recovery probes continue;
- consecutive Direct recovery successes: `RELAY_ACTIVE/DISCOVERY → DIRECT`;
- consecutive Relay failures: `RELAY_ACTIVE → DISCOVERY`.

This controller only chooses the node's transmission path. Manager remains authoritative for which fully validated ingress may become canonical.

## 11. ESP-IDF adapter contract

The P4b ESP-IDF adapter compiles against the frozen ESPHome 2026.4.3 / ESP-IDF 5.5.x toolchain and provides methods for:

- `esp_now_init` / deinit;
- PMK injection;
- receive/send callback registration;
- encrypted peer add/modify/remove;
- `esp_wifi_set_channel`;
- bounded `esp_now_send`.

ESP-IDF 5.5's `esp_now_send_info_t` callback signature is used when building on 5.5 or newer.

Driver callbacks run on the high-priority Wi-Fi task. A consumer MUST only copy/queue minimal metadata in those callbacks and perform parsing/reassembly/forwarding in a lower-priority context.

## 12. P4b boundaries

P4b authorizes source implementation, host/native tests, and ESP32-C6 compile/link validation only.

It does **not** authorize:

- board connection, serial access, Flash, erase, OTA, or over-air execution;
- production PMK/LMK/application-key provisioning;
- production Relay advertisement or packet transmission;
- product firmware path activation;
- production MQTT forwarding or subscription changes;
- T1, Broker, Home Assistant, or production Manager DB access;
- `GH_N3W_RUNTIME_ENABLED=true`;
- production replay/path baseline migration;
- deployment, release, tag, or N3-L work.
