# Phase 1 Decision B: multi-ingress latest-valid-wins

- Status: **ACCEPTED / ARCHITECTURE CONTRACT FREEZE**
- Date: 2026-08-16
- Scope: Manager canonical telemetry acceptance
- Phase boundary: contract + host simulation only; existing PATH implementation remains intact

## 1. Decision

Manager SHALL permit multiple authenticated ingress paths to present telemetry for the same registered node.

Examples:

```text
Direct MQTT
ESP-NOW Relay A -> MQTT
ESP-NOW Relay B -> MQTT
future LoRa gateway ingress
```

Transport path does not own node identity and does not own canonical freshness.

The canonical key is:

```text
authenticated NODE_ID
+ BOOT_ID / monotonic boot session
+ SEQ
```

## 2. Latest-valid-wins rule

For one `NODE_ID`, Manager maintains a durable canonical high-water cursor:

```text
highest_boot_session
highest_seq
```

Acceptance is frozen as:

```text
no cursor
  -> ACCEPT

boot_session > highest_boot_session
  -> ACCEPT and establish the new boot cursor

boot_session == highest_boot_session and seq > highest_seq
  -> ACCEPT

boot_session == highest_boot_session and seq == highest_seq
  -> DUPLICATE

boot_session == highest_boot_session and seq < highest_seq
  -> STALE_SEQUENCE

boot_session < highest_boot_session
  -> STALE_BOOT
```

Only authenticated data whose claimed `NODE_ID` matches the authenticated node identity can reach this decision.

## 3. Path metadata becomes diagnostic

The following may remain for diagnostics and product observability:

- last observed path;
- last direct timestamp;
- last relay timestamp;
- relay node ID;
- path switch count;
- RSSI/link quality.

They SHALL NOT be lease authority for canonical acceptance.

## 4. Migration guard

Current code stores the canonical boot/sequence high-water cursor inside PATH lease state. Therefore Phase 2 must first create an independent canonical freshness store and migrate/compare the cursor before removing PATH lease authority.

Deleting `n3w_path_lease.py` before that extraction is prohibited.

## 5. DELETE target after compatibility proof

- PATH DIRECT / PATH RELAY commands as canonical ownership operations;
- active path ownership;
- candidate path ownership;
- path lease TTL;
- stability-window ownership gate;
- previous-path/old-path grace authority;
- path-bound telemetry retry ownership.

## 6. Required host cases

- Direct seq100 ACCEPT;
- Relay seq100 DUPLICATE;
- Relay seq101 ACCEPT;
- late Direct seq100 STALE_SEQUENCE;
- Direct seq102 ACCEPT;
- newer boot with reset sequence ACCEPT;
- old boot after restart STALE_BOOT;
- Relay switching does not reset freshness;
- cross-node identity mismatch is rejected before cursor evaluation.

The Phase 1 host simulation freezes these semantics without changing Manager runtime code.
