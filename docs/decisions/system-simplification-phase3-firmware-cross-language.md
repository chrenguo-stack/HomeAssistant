# System Simplification Phase 3 — N3-W firmware cross-language contract

Status: implemented in Draft PR #324; physical activation remains gated.

## Scope

Phase 3 implements the firmware side of the Phase 1/2 simplified N3-W contract without deleting the legacy S5 path. The implementation is additive so that the old finite-grant/PATH/reliable-fragmentation code can remain a regression reference until clean isolated E2E proves the replacement.

This phase is source/cloud-CI only. It does not authorize board access, USB/serial access, Flash/erase/reset/power operations, RF execution, Broker/Manager/Home Assistant production mutation, N3-L work, or reuse of retired R8 material.

## Bootstrap and persisted identity

- Factory firmware contains no NODE_ID, SYSTEM_ID, SYSTEM_PEER_KEY, peer MAC, LMK, MQTT credential, user Wi-Fi information, Manager identity, or peer relationship.
- A missing 32-byte Setup Secret is generated on-device from the ESP32 hardware RNG at first use and stored in NVS. It is not a compile-time firmware value.
- The one-time Setup Secret protocol exactly mirrors Manager `gh.pair.simple-bootstrap/1`:
  - node/Manager HMAC-SHA256 possession proofs;
  - transcript-bound HKDF-SHA256 bootstrap key;
  - AES-256-GCM credential-bundle decryption.
- After successful registration, the firmware can persist the N3-W subset of `gh.pair.credentials/2`: `SYSTEM_ID`, assigned `NODE_ID`, `PEER_TRUST_GENERATION`, `SYSTEM_PEER_KEY`, `n3w_key_epoch`, and the per-node N3-W application key.
- Setup Secret erasure is an explicit store operation after a successful credential commit. The Phase 3 code does not silently regenerate an existing corrupt record.

## Local peer trust

The firmware mirrors Manager ADR-0007 peer trust:

- HMAC-SHA256 proof binds SYSTEM_ID, trust generation, prover/verifier NODE_ID, both MAC addresses, prover boot nonce, and challenge nonce.
- Pair-specific ESP-NOW LMK is deterministically derived with HKDF-SHA256 from the long-lived SYSTEM_PEER_KEY and an order-independent pair binding.
- Discovery is not itself trusted. A discovered node becomes an encrypted peer only after the local HMAC challenge/accept exchange succeeds for the current trust generation.
- There is no Manager peer grant, authorization TTL, per-path lease, static peer MAC table, or factory peer binding in the new Phase 3 modules.

## Compact telemetry and Relay

Periodic Relay telemetry uses one `N3W2` ESP-NOW frame:

- magic: 4 bytes (`N3W2`)
- BOOT session: 8 bytes, big-endian
- SEQ: 4 bytes
- application-key epoch: 4 bytes
- AES-GCM nonce: 12 bytes
- AES-GCM tag: 16 bytes
- ciphertext: up to the existing 1024-byte telemetry payload ceiling

Header size is 48 bytes and the maximum current wire size is 1072 bytes, below the 1470-byte ESP-NOW v2 payload limit. The Phase 3 frame has no fragment index/count/offset, receipt ACK, telemetry retry cache, or resend state.

The AEAD AAD is canonical `gh.relay/2` JSON bound to SYSTEM_ID, NODE_ID, key epoch, BOOT_ID and SEQ. It intentionally contains no gateway/Relay identity. Therefore the same encrypted child frame may be forwarded by any authenticated same-system Relay without re-encryption. The Relay wrapper is `{"frame_b64":"...","schema":"gh.relay/2"}`.

## Automatic Direct/Relay fallback

Path choice remains local to the node. The replacement uses the existing bounded three-state local controller:

`DIRECT -> DISCOVERY -> RELAY_ACTIVE -> DIRECT`

Repeated Direct failures enter discovery; a successfully authenticated same-system peer enables Relay; repeated Relay failures return to discovery; repeated successful Direct recovery probes return to Direct. Manager is not a current-path owner and does not issue a PATH command for this flow.

## Cross-language gate

Phase 3 CI must prove all of the following before this phase is called closed:

1. C++ Setup Secret/HKDF/HMAC/AES-GCM vectors exactly match Phase 2 Manager vectors.
2. C++ peer HMAC and pair-LMK vectors exactly match Phase 2 Manager vectors.
3. C++ compact telemetry produces the exact Manager-compatible `N3W2` frame vector and gateway-independent AAD.
4. Mutual challenge/accept derives the same LMK on both endpoints and rejects trust-generation mismatch.
5. Direct failure -> authenticated Relay -> Direct recovery state transition passes host simulation.
6. The same generic ESP32-C6 component configures and links in both logical Child and Relay compile contexts.
7. Source safety checks find no factory secret, static peer binding, or private production marker.

Passing Phase 3 does not activate the new protocol on production systems and does not authorize Phase 4 physical E2E.
