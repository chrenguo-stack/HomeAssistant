# Phase 1 Decision C: automatic NODE_ID allocation

- Status: **ACCEPTED / ARCHITECTURE CONTRACT FREEZE**
- Date: 2026-08-16
- Scope: first registration and node identity lifecycle
- Phase boundary: contract + host simulation only; existing registration code remains intact

## 1. Decision

`NODE_ID` is an internal stable system identity. A normal user SHALL NOT type or choose it during first registration.

The user-facing flow becomes:

```text
power on
-> configure Wi-Fi
-> scan/confirm the device
-> add device
-> complete
```

Friendly name and Home Assistant area remain user-editable metadata and are not part of `NODE_ID`.

## 2. Allocation contract

Manager SHALL generate `NODE_ID` automatically when an approved device first becomes a registered node.

Phase 1 deliberately does **not** freeze a textual encoding or bit-length that the source architecture plan does not specify. Phase 2 may choose an implementation representation only if it preserves these required properties:

- not derived from MAC;
- contains no customer-private meaning;
- absent from generic factory firmware;
- user does not enter it;
- stable once assigned;
- unique among allocated identities;
- allocation collision is resolved without reusing an already allocated identity;
- retirement permanently prevents the old `NODE_ID` from being issued again;
- the same physical hardware joining again after retirement receives a new `NODE_ID`.

## 3. HARDWARE_ID remains separate

```text
HARDWARE_ID = physical device identity
NODE_ID     = logical identity assigned by Manager
```

Hardware replacement is a new registration and a new `NODE_ID`. Historical curve stitching remains outside the system identity contract.

## 4. pairing_epoch after ADR-0007

`pairing_epoch` currently participates in the legacy registration replay/generation path. The ADR-0007 Setup Secret transcript does not depend on `pairing_epoch`.

Phase 1 freezes only the source-supported conclusion:

- re-audit whether `pairing_epoch` still participates in a real security decision after ADR-0007;
- if fresh `SETUP_SECRET`, `pairing_id`, `NODE_ID` and MQTT credentials make it redundant, it may become audit-only or be deleted later;
- while the legacy path still depends on it, it remains compatibility state and is not deleted in Phase 1.

## 5. Required host cases

- allocation does not derive the identity from MAC or user-friendly metadata;
- assigned identity remains stable for an active registration;
- a deliberate candidate collision retries rather than reusing an existing ID;
- retired identity is never issued again;
- re-registering retired hardware gets a new identity.

Phase 2 will implement the allocator in Manager storage; Phase 1 only freezes and simulates these rules.
