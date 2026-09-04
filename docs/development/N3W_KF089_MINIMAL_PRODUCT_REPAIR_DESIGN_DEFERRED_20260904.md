# N3-W KF-089 Minimal Product Repair Design — Deferred

Date: 2026-09-04  
Status: `DEFERRED_DESIGN`  
Implementation status: `NOT_STARTED`  
Implementation authority: `NOT_FINAL`  
Repository base at design time: `bff94bc4922d7a984eb1363cc24a163ad466a166`

## 1. Purpose

This document preserves the minimal product-repair design developed after the 2026-09-04 Board B real-world cold-boot Relay failure was traced to KF-089.

It is intentionally **not** an implementation authorization. The project subsequently chose to establish an Espressif official ESP-NOW reference baseline first, then use that physical reference to validate or revise this design before touching product source.

```text
KF089_SOURCE_DEFECT=PROVEN
MINIMAL_REPAIR_DESIGN=PRESERVED
MINIMAL_REPAIR_IMPLEMENTATION=DEFERRED
OFFICIAL_ESPNOW_REFERENCE_BASELINE_REQUIRED_FIRST=true
```

The exact public failure/evidence authority remains:

- `docs/development/N3W_BOARD_B_REAL_WORLD_FAILOVER_DEBUG_ARCHIVE_20260904.md`
- `docs/development/N3W_BOARD_B_REAL_WORLD_FAILOVER_KF087_KF089_DISPOSITION_20260904.md`

## 2. Proven blocker this design addresses

Current product startup blocks provisioned runtime initialization on current Direct Wi-Fi association:

```cpp
if (!runtime_state_loaded_ || !mqtt_configured_ || !wifi_connected()) {
  return false;
}
```

ESP-NOW initialization, broadcast-peer preparation and `SimpleProductRuntime::start(...)` are downstream of that guard.

Frozen classification:

```text
COLD_BOOT_RELAY_ACQUISITION_SOURCE_DEFECT=PROVEN
ROOT_CAUSE=PRODUCT_RUNTIME_STARTUP_REQUIRES_WIFI_CONNECTED
FAILURE_CLASS=RUNTIME_BOOTSTRAP_ARCHITECTURE
```

The defect is specifically about **provisioned cold boot with Direct Wi-Fi unavailable**. It does not prove that an already-running Direct node cannot perform live Direct→Relay failover.

## 3. Why deleting `!wifi_connected()` is insufficient

The existing `SimpleProductRuntime::start(...)` contract requires a valid `direct_channel`, immediately configures its scan plan from that channel, and calls the port channel setter. The `LocalPathController` also starts in `DIRECT`.

Therefore simply removing the Wi-Fi startup guard would create an invalid semantic state:

```text
Direct Wi-Fi unavailable
+ Direct channel unknown
+ runtime initial state forced to DIRECT
```

A correct repair needs an explicit no-Direct startup mode rather than synthesizing fake Direct failures.

## 4. Deferred minimal repair architecture

### 4.1 Explicit startup mode

Proposed concept:

```cpp
enum class SimpleProductStartMode : uint8_t {
  DIRECT,
  DISCOVERY,
};
```

Target semantics:

```text
DIRECT:
  direct_channel must be valid
  initial path = DIRECT

DISCOVERY:
  direct_channel may be 0 / absent
  initial path = DISCOVERY
  channel scan starts from allowed channels
```

The existing `ChannelScanPlan` already accepts `last_direct_channel=0` and can construct the allowed-channel scan list without inventing a previous Direct channel.

The design should add an explicit initial-state/reset surface to the path controller rather than entering Discovery by fabricating repeated Direct failures.

### 4.2 Explicit Wi-Fi / ESP-NOW radio ownership

The present adapter treats:

```text
wifi_connected()==false
```

as sufficient permission for N3-W to change the radio channel. This is too weak because the Wi-Fi component may still be scanning/connecting.

Proposed ownership model:

```text
WIFI_OWNS_RADIO
ESPNOW_OWNS_RADIO
```

Direct mode:

```text
Wi-Fi associated
→ WIFI_OWNS_RADIO
→ ESP-NOW shares the current STA channel
→ N3-W does not mutate the associated STA channel
```

Discovery mode:

```text
Direct unavailable after bounded preference window
→ explicitly stop/disable the ESPHome Wi-Fi state machine
→ keep/restart only the minimum ESP-IDF STA radio state required for ESP-NOW
→ ESPNOW_OWNS_RADIO
→ N3-W may scan allowed channels
```

Direct recovery reverses the ownership handoff before allowing the ESPHome Wi-Fi state machine to reconnect.

The exact implementation must be validated against the official ESP-NOW reference baseline before adoption.

### 4.3 Bounded Direct-first cold-boot window

A provisioned node should not enter Relay Discovery immediately on the first loop iteration because a normal Wi-Fi association needs time.

Provisional design value:

```text
INITIAL_DIRECT_GRACE_MS=15000
```

Conceptual flow:

```text
load durable provisioned state
→ configure MQTT
→ allow bounded Direct association window
→ if Wi-Fi becomes ready: start DIRECT
→ otherwise: explicit radio ownership handoff → start DISCOVERY
```

The exact duration is provisional and must not become final product policy until the official reference and real hardware results support it.

### 4.4 Future Direct recovery while in Discovery/Relay

Entering ESP-NOW Discovery must not permanently disable future Direct recovery.

Provisional design suggested periodic bounded Wi-Fi probes while no Relay is available, with ownership returned to ESP-NOW after an unsuccessful probe. Exact cadence/window values are intentionally not frozen as product authority in this document.

Existing Direct recovery semantics should be reused rather than building a second recovery state machine.

### 4.5 Broadcast peer channel semantics

The current broadcast control peer is prepared with a concrete channel. Discovery later scans multiple channels.

The deferred design proposes validating the official ESP-NOW current-channel peer pattern and, if confirmed in the exact target IDF revision, using current-channel semantics for the broadcast peer while retaining explicit authenticated channels for encrypted relay peers.

This must be verified against the official reference baseline before product implementation.

### 4.6 Failed channel-switch backoff

Current discovery scan code advances its next switch deadline only after a successful channel change. A channel-switch failure may therefore be retried at loop rate.

Deferred minimal repair:

```text
advance bounded retry deadline
→ attempt channel change
→ on failure retain bounded delay before next retry
```

This is directly coupled to safe Discovery operation and should be included when KF-089 product repair is eventually implemented.

## 5. Explicitly deferred issue: async ESP-NOW TX completion

The current ESP-NOW send callback result is not fed back into the product state machine.

```text
ASYNC_ESPNOW_TX_COMPLETION_GAP=CONFIRMED
ASYNC_ESPNOW_TX_COMPLETION_REPAIR=DEFERRED
KF089_REPAIR_DEPENDS_ON_ASYNC_TX_FIX=false
```

The issue is real but is not the proven KF-089 startup blocker. It should remain a separate repair unless the official reference or later physical evidence shows it is required for the same gate.

## 6. Intended source scope if this design survives reference validation

Provisional product-source scope:

```text
firmware/esphome_rc/components/greenhouse_n3w_core/
  n3w_radio.h
  n3w_radio.cpp
  n3w_simple_product_runtime.h
  n3w_simple_product_runtime.cpp
  n3w_simple_product_component.h
  n3w_simple_product_component.cpp
  n3w_espnow_driver.cpp

tests/n3w_phase4/
  n3w_phase4_runtime_host_test.cpp
  test_phase4_source_contract.py
```

Explicit non-scope:

```text
Manager
Broker
DynSec
pairing protocol
credential lifecycle
application-key lifecycle
SYSTEM_PEER_KEY lifecycle
NVS schema
factory peer binding
PR #361 diagnostic instrumentation
```

## 7. Provisional regression matrix

If the design remains valid after the official reference phase, the product repair should cover at least:

```text
R1  PROVISIONED_COLD_BOOT_DIRECT
R2  PROVISIONED_COLD_BOOT_NO_WIFI_DISCOVERY
R3  DISCOVERY_WITHOUT_DIRECT_CHANNEL
R4  WIFI_SCANNING_CHANNEL_MUTATION_FORBIDDEN
R5  ESPNOW_OWNERSHIP_CHANNEL_SCAN
R6  BROADCAST_PEER_CURRENT_CHANNEL
R7  FAILED_CHANNEL_SWITCH_BACKOFF
R8  COLD_BOOT_DISCOVERY_TO_RELAY
R9  DISCOVERY_OR_RELAY_TO_DIRECT_RECOVERY
R10 EXISTING_DIRECT_RELAY_DIRECT_REGRESSION
```

Physical acceptance must still use a fresh source→artifact→board binding per KF-087.

## 8. Superseding route

The active next route is now:

```text
N3W_OFFICIAL_ESPNOW_REFERENCE_BASELINE_R0
```

Sequence:

```text
R0 = unmodified official Espressif ESP-NOW baseline on ESP32-C6
R1 = official-reference Wi-Fi/ESP-NOW coexistence experiment
R2 = incrementally reintroduce N3-W semantics
then
re-evaluate this deferred minimal repair design
```

## 9. Frozen disposition

```text
DOCUMENT_CLASS=DEFERRED_PRODUCT_REPAIR_DESIGN
SOURCE_DEFECT_PROVEN=true
PRODUCT_SOURCE_MUTATION=false
IMPLEMENTATION_AUTHORIZED=false
DESIGN_MAY_BE_REVISED_BY_OFFICIAL_REFERENCE=true

NEXT_AUTHORITY=
OFFICIAL_ESPNOW_REFERENCE_PHYSICAL_EVIDENCE
```
