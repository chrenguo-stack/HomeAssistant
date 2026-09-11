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

### 3.1 Route clarification — disconnected Relay discovery is the required failover path

The product must distinguish two different cross-channel scenarios:

1. **Wi-Fi-disconnected Relay discovery — required product behavior.** A provisioned node has no usable Direct Wi-Fi association. In this state N3-W must still be able to start and autonomously search for a trusted Relay-capable peer.
2. **Associated off-channel operation — optional capability / separate validation subject.** A node remains logically associated to an AP while temporarily operating away from the AP home channel.

The first case is the required failover path. The second case must not be a prerequisite for the first.

A cached Relay or cached Relay channel is only a search optimization. It is not authoritative because the previous Relay may have moved, lost power, lost Wi-Fi, changed channel, or otherwise become unavailable.

Therefore, after Direct Wi-Fi is unavailable, the node-local discovery policy must be able to:

1. try the current / last-known useful channel first when available;
2. try a cached trusted Relay channel as a hint when available;
3. if no acceptable Relay is found, perform a bounded sweep of the allowed channel set;
4. on each candidate channel, perform the required ESP-NOW discovery exchange;
5. stop scanning as soon as an acceptable trusted Relay path is established.

This scan is an N3-W application-level discovery loop constructed from Espressif-supported Wi-Fi / ESP-NOW primitives. The project does not require Espressif to provide a single high-level "automatic Relay scan" API.

Because a Wi-Fi-disconnected node cannot communicate with Home Assistant / Manager through its lost Direct path, this discovery process must be node-local and autonomous. Home Assistant / Manager may retain last-known channel information for diagnostics or as a future hint, but they are not a real-time authority for offline channel selection.

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
- Wi-Fi-disconnected autonomous bounded Relay discovery;
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

Use “current-channel peer + official controlled channel operation” as a candidate for further validation where associated off-channel behavior is useful.

However, **closing the full associated off-channel lifecycle is no longer a prerequisite for implementing or validating Wi-Fi-disconnected autonomous Relay discovery**.

For the required disconnected failover path, use the simplest Espressif-supported channel-control + ESP-NOW discovery mechanism that can perform the bounded channel sweep safely on the exact ESP32-C6 / ESP-IDF authority.

Do not implement a complex product radio-ownership layer merely to preserve an existing Wi-Fi association across temporary off-channel operation unless later product evidence proves that capability is actually required.

## 6. Why N3-W needs cross-channel capability

ESP-NOW peers must communicate on the same working Wi-Fi channel at the moment of exchange.

N3-W cannot assume that every nearby node will always be on the same channel because:

- devices are not factory-bound to specific peers;
- users may add nodes later;
- a node may lose Direct Wi-Fi while another nearby node remains associated to a router on a different channel;
- a cached Relay/channel may become stale;
- the searching node does not know in advance which nearby trusted Relay-capable node or channel will be available.

Therefore cross-channel operation is a **fallback discovery capability**, not the normal steady-state mode.

The primary required case is a node with no usable Direct Wi-Fi path. It must be able to discover a Relay without depending on Home Assistant or Manager for real-time channel guidance.

Preferred search order:

1. Try the current / last-known useful channel first.
2. Try a cached trusted Relay channel as a hint if available.
3. If a trusted Relay is found, stay with that channel and avoid broader scanning.
4. Only if that fails, perform bounded scanning of the allowed channel set.
5. Stop scanning as soon as an acceptable Relay path is established.

This keeps the common case simple and makes failover self-contained on the node.

## 7. Frozen product-direction decision

The following direction is now authoritative for subsequent N3-W development:

### Startup architecture

**Modify.**

Provisioned runtime startup must no longer require live Wi-Fi association before ESP-NOW discovery/Relay can start.

### Wi-Fi-disconnected Relay discovery

**Required product behavior.**

A provisioned node with no usable Direct Wi-Fi association must be able to start N3-W and autonomously perform bounded channel-by-channel Relay discovery. Cached Relay/channel information is an optimization hint only, never a prerequisite or authority.

### Associated off-channel operation

**Not a prerequisite for failover.**

Keeping a live AP association while temporarily leaving the AP home channel may continue to be studied, but it is not the primary Relay acquisition path and must not block implementation of disconnected Relay discovery.

### Low-level channel control

**Prefer Espressif official APIs.**

Do not reproduce low-level channel operations with custom radio-control machinery when the official API already provides the required primitive.

### Channel scanning and path selection

**Keep a small N3-W application-level policy layer.**

N3-W remains responsible for Direct-first preference, bounded discovery, peer/path choice, backoff and Direct recovery.

### Full radio-ownership state machine

**Do not implement for now.**

Only reconsider it if official mechanisms are later proven insufficient for a required product behavior on the exact ESP32-C6 / ESP-IDF authority.

### Current-channel peer + controlled associated off-channel operation

**Optional candidate for continued validation.**

Treat it as an N3-W design candidate built from official capabilities, not as an Espressif-recommended architecture, and not as a gate for disconnected Relay discovery.

## 8. Immediate development sequence

The next development sequence is:

1. Rebind current product source and identify the complete startup contract surrounding `start_runtime_if_ready_()`; do not reduce the repair to deletion of the `wifi_connected()` guard.
2. Define the minimum legitimate no-association startup state and initial-path semantics.
3. Implement Wi-Fi-disconnected autonomous bounded Relay discovery using the smallest Espressif-supported channel-control + ESP-NOW discovery mechanism.
4. Run host regression and bounded physical validation of cold boot / Wi-Fi loss → channel sweep → trusted Relay acquisition → Relay telemetry.
5. Validate bounded Direct recovery from Relay back to Wi-Fi.
6. Continue associated off-channel lifecycle work only if it remains useful as a separate capability; do not let it block the required disconnected failover route.
7. Return to the N3-W three-board / T1 real-world Direct → Relay → Direct acceptance route.

## 9. Architecture guard

Future implementation proposals must start from the simplest model consistent with proven evidence.

Preferred order:

1. official native capability;
2. minimal N3-W application-layer policy;
3. only if proven necessary, custom low-level architecture.

No new full radio-ownership subsystem, parallel Wi-Fi state machine, or equivalent low-level abstraction may be introduced merely as a precautionary design.

The following additional guard is frozen:

> A node that has lost Wi-Fi must not depend on Home Assistant, Manager, or a previously cached Relay remaining valid in order to discover a new Relay. Relay discovery after Direct loss is a node-local autonomous operation.

## 10. Final disposition

This document is the active design authority for the next N3-W ESP-NOW development stage.

The deferred KF-089 design remains archived reference material, but any portions that assume a full radio-ownership state machine or that make associated off-channel lifecycle closure a prerequisite for disconnected Relay acquisition are subordinate to this decision and must be re-evaluated before implementation.
