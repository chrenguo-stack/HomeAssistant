# N3-W R2B KF-075 — Existing-Identity MQTT Credential Recovery Product Path

## Scope

This document records the source-only repair discovered during the separate N3-W three-board regression/retest route. FC4 final physical acceptance remains frozen PASS and is not reopened.

## KF-075

- **DOMAIN:** PRODUCT
- **Status:** OPEN pending final exact-head CI and review closure
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

## Transaction boundary and remaining live gate

The board persists the encrypted credential bundle before sending the final delivery receipt. Broker password replacement occurs only after that receipt. If an exceptional failure occurs after Broker password replacement but before the local secret-free lifecycle commit completes, the implementation fails closed and does not claim rollback; this partial-commit condition must be treated as a reconciliation state and must not be hidden as success.

No T1 deployment, live Manager/Broker/DynSec mutation, board access, Flash, NVS erase, reset, or serial action is authorized by this source repair. Board B live recovery remains a later independent mutation gate after source integration and deployment readiness are separately proven.
