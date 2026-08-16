# Phase 1 Decision A: N3-W telemetry transport simplification

- Status: **ACCEPTED / ARCHITECTURE CONTRACT FREEZE**
- Date: 2026-08-16
- Scope: N3-W periodic environmental telemetry over ESP-NOW
- Phase boundary: contract + host simulation only; no firmware change in Phase 1

## 1. Code facts frozen by Phase 0

Current N3-W radio code uses a 240-byte application datagram cap and 180-byte fragment payloads. The current S5 telemetry host sample is 255 bytes. The existing DATA fragment wire header is 54 bytes. The current RelayFrame ciphertext ceiling is 1024 bytes.

For the simplified ESP-NOW v2 path:

```text
current host sample: 255 + 54 = 309 bytes
current maximum:     1024 + 54 = 1078 bytes
ESP-NOW v2 budget:                  1470 bytes
```

Therefore the current application envelope fits in one ESP-NOW v2 application frame without first inventing a new telemetry schema.

## 2. Decision

Periodic environmental telemetry SHALL use one authenticated application frame when the encoded frame is within the frozen ESP-NOW v2 payload budget.

The product reliability target is **latest state continues to advance**, not guaranteed delivery of every sample.

For ordinary periodic telemetry:

```text
sample N
  -> one authenticated frame
  -> one send attempt
  -> if lost, wait for sample N+1
```

No application-level receipt is required merely to prove that an ordinary sample was forwarded.

## 3. KEEP

- `NODE_ID`;
- `BOOT_ID` / monotonic boot session;
- `SEQ`;
- authenticated/encrypted telemetry payload;
- pair-specific ESP-NOW LMK;
- malformed/authentication rejection;
- transport send status as diagnostic information.

## 4. DELETE target after compatibility proof

For ordinary periodic telemetry only:

- `DATA_FRAGMENT` fragmentation;
- fragment index/count/offset state;
- Relay reassembly state;
- `RECEIPT_ACK`;
- `ChildRelayCache` periodic-telemetry retry ownership;
- periodic retry timers;
- RESEND behavior;
- REORDER/reassembly behavior;
- path-bound cached ciphertext.

This deletion does **not** apply to credential delivery, configuration commands, OTA, security rotation or other transactional operations.

## 5. Failure semantics

- one missing sample is acceptable;
- next valid higher `SEQ` sample recovers naturally;
- duplicate delivery is harmless at Manager ingress;
- a late lower `SEQ` sample must not roll canonical state backward;
- old `BOOT_ID` data must be rejected after a newer boot session is canonical.

## 6. Migration gates

Before firmware deletion work:

1. ESP-NOW v2 capability remains a product requirement for this path;
2. encoded frame size is asserted to be `<= 1470`;
3. Manager multi-ingress freshness rules pass host simulation;
4. transactional non-telemetry operations retain explicit success/failure semantics.

## 7. Phase 1 host proof

`test_system_simplification_phase1_contracts.py` proves the frozen maximum frame budget and the loss-then-next-sample recovery assumption at the contract level.
