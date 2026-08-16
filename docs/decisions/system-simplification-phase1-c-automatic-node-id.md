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

Manager SHALL allocate `NODE_ID` transactionally after the device has been approved for registration.

Frozen target format:

```text
node-<32 lowercase hexadecimal characters>
```

The suffix is generated from 128 bits of cryptographically secure random data.

Properties:

- not derived from MAC;
- not derived from location, customer or greenhouse name;
- absent from generic factory firmware;
- stable after assignment;
- database uniqueness enforced;
- collision causes generation of another candidate inside the same allocation transaction;
- retirement permanently reserves the old `NODE_ID`;
- the same physical hardware rejoining after retirement receives a new `NODE_ID`.

## 3. HARDWARE_ID remains separate

```text
HARDWARE_ID = physical device identity
NODE_ID     = logical identity assigned by Manager
```

Hardware replacement is a new registration and a new `NODE_ID`. Historical curve stitching remains outside the system identity contract.

## 4. pairing_epoch after ADR-0007

`pairing_epoch` currently participates in the legacy registration replay/generation path. The ADR-0007 Setup Secret transcript does not depend on `pairing_epoch`.

Phase 1 freezes the new rule:

- `pairing_epoch` is not a required input to new Setup Secret proof, bootstrap key derivation, SYSTEM_PEER_KEY trust or NODE_ID generation;
- it remains compatibility-only while the legacy pairing path exists;
- final deletion is a later migration decision after legacy replay tests are replaced.

## 5. Required host cases

- allocation does not use MAC or user metadata;
- generated ID matches the frozen opaque format;
- a deliberate candidate collision retries rather than reusing an existing ID;
- assigned ID remains stable for an active registration;
- retired ID is never issued again;
- re-registering retired hardware gets a new ID.

Phase 2 will implement the allocator in Manager storage; Phase 1 only freezes and simulates these rules.
