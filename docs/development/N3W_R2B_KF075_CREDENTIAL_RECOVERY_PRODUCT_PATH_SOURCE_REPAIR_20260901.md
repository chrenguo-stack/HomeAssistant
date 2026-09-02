# N3-W R2B KF-075 — Existing-Identity MQTT Credential Recovery Product Path

## Scope

This document records the source repair and its later live Board B closure discovered during the separate N3-W three-board regression/retest route. FC4 final physical acceptance remains frozen PASS and is not reopened.

## KF-075

- **DOMAIN:** PRODUCT
- **Status:** GUARDED
- **Phenomenon:** a previously registered node may lose its board-side durable runtime credential state while Manager still retains its stable NODE_ID and active MQTT credential lifecycle; ordinary pairing correctly stops at `credential_recovery_required`, but the product had no explicit path to recover that credential onto the existing identity.
- **Root cause:** the MQTT credential recovery lifecycle existed below the pairing layer, but it was not wired into the Manager-owned pairing authorization / provisioning product path.
- **Required guard:** existing-identity recovery must be separately and explicitly authorized for the exact fresh hardware/pairing transaction; stable NODE_ID is preserved; ordinary repair must remain non-rotating; MQTT recovery stages `active_generation + 1`; the active N3-W application key and existing SYSTEM_PEER_KEY are re-delivered without rotation; recovery must not initialize missing peer trust; Broker identity/ACL are preserved and only the existing client password may change after the board has durably persisted the encrypted recovery bundle.

## Source repair

PR #350 adds:

1. an ephemeral, exact-pairing credential-recovery authorization separate from ordinary repair;
2. a Manager-owned local UDS and CLI operation for that authorization;
3. a recovery staging path that preserves the stable NODE_ID and stages only the MQTT credential generation;
4. existing-identity Broker password replacement without client/role/ACL recreation;
5. explicit reuse of the active N3-W application key;
6. explicit existing-only SYSTEM_PEER_KEY lookup during recovery;
7. focused regression tests for authorization, identity preservation, pre-receipt rollback, peer-trust no-create/no-rotate behavior, and post-Broker-mutation fail-closed behavior.

PR #350 merged as product-source revision `8fbedc7e0778ce91d146cd5f0772bebdd20ad13a`. The deployed/frozen Manager runtime used for R2B was bound to that revision; later documentation-only repository `main` movement does not redefine the deployed product-source authority.

## Transaction boundary

The board persists the encrypted credential bundle before sending the final delivery receipt. Broker password replacement occurs only after that receipt. If an exceptional failure occurs after Broker password replacement but before the local secret-free lifecycle commit completes, the implementation fails closed and does not claim rollback; this partial-commit condition must be treated as a reconciliation state and must not be hidden as success.

## Board B live recovery closure — 2026-09-02

The separately authorized Board B recovery completed successfully and the authorization was consumed exactly once with replay forbidden. Public-safe closure facts:

- stable NODE_ID remained bound; no NODE_ID replacement occurred;
- pairing reached `approved` and the exact fresh pairing transaction became the Manager current pairing;
- MQTT credential lifecycle advanced from active generation 1 to active generation 2, with no pending generation left after commit;
- the active N3-W application key remained epoch 1 and its material was preserved;
- SYSTEM_PEER_KEY remained generation 1 and its material was preserved;
- Broker `changeIndex` advanced exactly from 30 to 31;
- the existing Broker client/role/ACL binding remained exact and only the encoded password material changed;
- non-target Broker semantic state was preserved;
- Board A and Board C were not mutated;
- no Flash, NVS erase, or manual reset occurred during credential recovery.

The live recovery executor reported `VALID_RECEIPT_COMMIT_CHAIN_WITH_GENERATION2_ACTIVE`, establishing the required Board durable-persist → final receipt → Broker password replacement → local lifecycle commit ordering.

## Post-closure read-only verification

A subsequent read-only Manager/Broker audit confirmed generation 2 active, pending generation absent, pairing approved, application-key epoch 1 preserved, peer-trust generation 1 preserved, Broker `changeIndex=31`, the rotated encoded password still present, and non-target Broker state unchanged.

The first 40-second serial verifier saw three pairing-payload log lines while simultaneously observing 8/8 strictly increasing Direct telemetry records accepted successfully. Because this single whole-window absence oracle could not distinguish a current live pairing output from stale/transient serial-buffer material, it was not treated as a product failure.

A separate read-only serial-quiescence adjudication then used a 20-second stabilization window followed by an authoritative 50-second verification window. It observed zero pairing payloads in both windows and 10/10 strictly increasing Direct telemetry records with zero rejections over a 45.004-second span. Therefore post-closure pairing quiescence and generation-2 Direct runtime use are proven.

## Closure boundary

`REBOOT_PERSISTENCE_TESTED=false` remains explicit. The R2B closeout proves durable credential persistence and active generation-2 runtime use in the current boot; it does not claim that an operator-induced reboot/power-cycle persistence test occurred. That untested boundary does not block KF-075 closure because no reboot was authorized in the read-only post-closure stage.

KF-075 is therefore **GUARDED**: the product path is merged, deployed, source/runtime regression-protected, exercised by the exact Board B existing-identity recovery, and closed by post-recovery runtime/quiescence evidence.

## Route return

After this closeout, R2B leaves the Board B recovery detour and returns to the N3-W three-board regression/retest mainline for fresh A→B→C R2 runtime liveness. FC4 remains frozen PASS and is not reopened.
