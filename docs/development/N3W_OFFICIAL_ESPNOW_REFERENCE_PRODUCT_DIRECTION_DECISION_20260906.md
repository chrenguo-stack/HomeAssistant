# N3-W Official ESP-NOW Reference → Product Direction Decision

Date: 2026-09-06  
Status: `PARTIALLY_SUPERSEDED_PRODUCT_DIRECTION`  
Scope: N3-W ESP-NOW runtime / channel-management architecture  
Source authority at decision time: `127c3f1e89baaaba7b7fd60d6d263632d30b2461`

> **2026-09-06 路线更新：** 用户已确认 [R1R4 归档与产品路线调整](N3W_R1R4_ARCHIVE_AND_PRODUCT_ROUTE_RESET_20260906.md)。下文第 5、7、8 节中将保持关联的 controlled off-channel lifecycle 完整验证作为产品修复前置条件的要求已被替代。当前优先使用普通官方 ESP-NOW 能力，修复已配对节点无 Wi-Fi 冷启动与失联后的 bounded discovery；不再以 R1R4 完成事件诊断阻挡产品工作。其余身份、安全、单跳和简化原则继续有效。

## 1. Purpose

This document freezes the product-direction conclusions derived from the Espressif official ESP-NOW reference work and the subsequent N3-W design review.

It supersedes the assumption that N3-W should immediately implement a full custom Wi-Fi/ESP-NOW radio-ownership state machine. The deferred KF-089 design remains useful background, but any later implementation must follow this document unless new physical evidence proves that a more complex design is necessary.

No product source is modified by this decision record.

## 2. Current evidence summary

The official ESP-NOW reference has already established the following important facts on the ESP32-C6 target:

- Basic two-board ESP-NOW communication works.
- Home-channel ESP-NOW communication works.
- A Wi-Fi-connected DUT can perform an official controlled off-channel ESP-NOW transmit operation.
- A control node can remain on a target channel for a bounded interval.
- A frame can actually be delivered on the off-channel target.

The remaining incomplete evidence concerns the full lifecycle after the bounded off-channel operation, especially reverse reception and reliable return to the original home/Wi-Fi channel.

These incomplete items must not be treated as proof that the official ESP-NOW API is insufficient.

## 3. Gap 1 — startup architecture

### Conclusion

The current N3-W cold-boot Relay blocker is a product runtime/bootstrap defect, not a proven limitation of Espressif ESP-NOW.

Current product behavior requires live Wi-Fi connectivity before the Relay-capable N3-W runtime is allowed to start. Therefore a provisioned node that cold-boots outside usable Wi-Fi coverage cannot enter ESP-NOW discovery at all.

### Direction

This problem is considered deterministically solvable in product software.

The repair direction is:

1. Load durable provisioned state, identity, credentials and required runtime configuration.
2. Start the N3-W communication runtime without requiring an already-established Wi-Fi association.
3. Preserve Direct Wi-Fi as the preferred path.
4. Give Direct Wi-Fi a bounded connection/grace window.
5. If Direct becomes available, remain on Direct.
6. If Direct remains unavailable, enter ESP-NOW discovery/Relay acquisition.
7. Later allow bounded recovery back to Direct.

Important: the repair must not be implemented as merely deleting the existing `wifi_connected()` guard. The runtime start contract and initial-path semantics must also be corrected so that a node can start legitimately without a known Direct channel.

## 4. Gap 2 — channel-management architecture

### Conclusion

N3-W should not implement a full custom radio-ownership subsystem unless later evidence proves it necessary.

The preferred separation of responsibility is:

- N3-W decides **when** discovery is required, **which** channels should be tried, **how long** each attempt lasts, **which** peer is acceptable, and **when** to recover Direct.
- Espressif official ESP-NOW / Wi-Fi APIs perform the actual low-level channel operation whenever an official primitive exists.

### Product direction

The low-level channel-control layer should preferentially use Espressif-supported mechanisms, including bounded switch-channel transmit and bounded remain-on-channel behavior, rather than reproducing those operations through a custom low-level radio state machine.

N3-W retains only the simple product-level policy/state logic required for:

- Direct-first preference;
- bounded Relay discovery;
- single-hop Relay selection;
- bounded Direct recovery;
- peer trust/security decisions;
- retry/backoff policy.

A full `WIFI_OWNS_RADIO` / `ESPNOW_OWNS_RADIO` ownership state machine is therefore **deferred and not part of the default implementation direction**.

## 5. Gap 3 — peer channel semantics and controlled off-channel operation

### Officially supported facts

In the bound Espressif ESP-IDF API:

- an ESP-NOW peer with `channel = 0` uses the current channel of the associated station or SoftAP interface;
- Espressif provides a controlled API for switching to a specified channel for an ESP-NOW transmit operation;
- Espressif provides a controlled remain-on-channel API for staying on a target channel for a bounded duration.

### Important wording boundary

The combined architecture:

> current-channel peer + official controlled channel operation

is **not** frozen as an “Espressif officially recommended architecture”.

It is an N3-W candidate design constructed from official supported capabilities.

The stock Espressif ESP-NOW example at the bound revision still configures its broadcast peer with an explicit configured channel, so the project must not misrepresent the proposed combination as an official reference architecture.

### Product direction

Use “current-channel peer + official controlled channel operation” as the **preferred candidate for further validation**, because it may cleanly separate:

- peer semantics: communicate on the radio’s current working channel;
- discovery policy: N3-W chooses the target channel;
- low-level channel operation: official Espressif API performs the bounded transition.

Do not implement this combination in product source until the remaining lifecycle evidence is closed.

## 6. Why N3-W needs cross-channel capability

ESP-NOW peers must communicate on the same working Wi-Fi channel at the moment of exchange.

N3-W cannot assume that every nearby node will always be on the same channel because:

- devices are not factory-bound to specific peers;
- users may add nodes later;
- a node may lose Direct Wi-Fi while another nearby node remains associated to a router on a different channel;
- the searching node does not know in advance which nearby trusted Relay-capable node or channel will be available.

Therefore cross-channel operation is a **fallback discovery capability**, not the normal steady-state mode.

Preferred search order:

1. Try the current / last-known channel first.
2. If a trusted Relay is found, stay with that channel and avoid broader scanning.
3. Only if that fails, perform bounded scanning of the allowed channel set.
4. Stop scanning as soon as an acceptable Relay path is established.

This keeps the common case simple and limits radio disruption.

## 7. Frozen product-direction decision

The following direction is now authoritative for subsequent N3-W development:

### Startup architecture

**Modify.**

Provisioned runtime startup must no longer require live Wi-Fi association before ESP-NOW discovery/Relay can start.

### Low-level channel control

**Prefer Espressif official APIs.**

Do not reproduce low-level channel operations with custom radio-control machinery when the official API already provides the required primitive.

### Channel scanning and path selection

**Keep a small N3-W application-level policy layer.**

N3-W remains responsible for Direct-first preference, bounded discovery, peer/path choice, backoff and Direct recovery.

### Full radio-ownership state machine

**Do not implement for now.**

Only reconsider it if bounded official mechanisms are later proven insufficient on the exact ESP32-C6 / ESP-IDF authority.

### Current-channel peer + controlled off-channel operation

**Preferred candidate for continued validation.**

Treat it as an N3-W design candidate built from official capabilities, not as an Espressif-recommended architecture.

## 8. Immediate development sequence

The next development sequence is:

1. Complete the current R1R4 evidence-harness issue only to the point required to obtain reliable physical evidence; do not reopen historical CI root-cause archaeology.
2. Close the remaining official bounded off-channel lifecycle evidence:
   - receive while temporarily operating off the home channel;
   - cancel/end the bounded operation;
   - return to the original home channel;
   - recover Wi-Fi association as applicable;
   - resume normal home-channel ESP-NOW operation.
3. Re-evaluate the deferred KF-089 repair against those results.
4. Implement the smallest product repair consistent with this document.
5. Run host regression and then bounded physical validation.
6. Return to the N3-W three-board / T1 real-world Direct → Relay → Direct acceptance route.

## 9. Architecture guard

Future implementation proposals must start from the simplest model consistent with proven evidence.

Preferred order:

1. official native capability;
2. minimal N3-W application-layer policy;
3. only if proven necessary, custom low-level architecture.

No new full radio-ownership subsystem, parallel Wi-Fi state machine, or equivalent low-level abstraction may be introduced merely as a precautionary design.

## 10. Final disposition

This document is the active design authority for the next N3-W ESP-NOW development stage.

The deferred KF-089 design remains archived reference material, but any portions that assume a full radio-ownership state machine are subordinate to this decision and must be re-evaluated before implementation.
