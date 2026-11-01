# System Simplification Phase 4 — Source-only activation / physical-harness gate

Status: source/cloud-CI gate only; physical execution remains separately gated.

## Purpose

Phase 4 needs a clean isolated two-board E2E, but Phase 3 intentionally stopped at cross-language primitives and generic compile contexts. This gate closes the source-level activation gap without touching a board, USB, serial, Flash, Wi-Fi/ESP-NOW RF, Broker, Manager runtime, Home Assistant, production, N3-L, or retired R8 material.

## Source-only activation contract

The gate adds one role-neutral generic ESP32-C6 physical-harness compile target and one isolated Manager composition adapter.

Firmware source now binds, without executing during this gate:

- device-generated Setup Secret / simplified credential NVS stores;
- compact `N3W2` single-frame telemetry;
- the local `DIRECT -> DISCOVERY -> RELAY_ACTIVE -> DIRECT` path controller;
- simplified HMAC/LMK peer-control primitives;
- the concrete ESP-IDF ESP-NOW driver;
- explicit future physical methods for broadcast peer-control, authenticated pair-LMK installation, and compact unicast telemetry.

The generic public target contains no factory NODE_ID, SYSTEM_ID, Setup Secret, SYSTEM_PEER_KEY, peer MAC, LMK, gateway ID, customer Wi-Fi, MQTT credential, or customer binding. Source-only preparation performs no NVS access and does not initialize Wi-Fi or ESP-NOW.

## Concrete ESP-NOW frame-budget repair

The legacy `kEspNowDatagramLimit=240` remains unchanged for the old control/fragmentation regression implementation. The concrete ESP-NOW v2 driver now has a separate 1470-byte physical datagram ceiling so the new maximum 1072-byte `N3W2` frame can traverse the real driver in a future authorized test.

This is a migration repair, not an extension of legacy fragmentation, ACK, retry, RESEND, REORDER, finite grants, or PATH ownership.

## Isolated Manager harness

The Manager source-only adapter composes:

- `AutomaticNodeIdApprover`;
- `N3wCanonicalIngressCoordinator`;
- `CompactRelayIngressCore`;
- `N3wMultiIngressRouter`.

It has no network listener and performs no Broker/runtime mutation. Tests prove two first registrations receive different automatically allocated NODE_IDs and that Direct/Relay ingress share one canonical freshness cursor without path ownership.

## CI gate

Before this gate can be called closed, the exact PR head must pass:

1. the regular greenhouse-manager lint/test suite;
2. Phase 3 source and cross-language regression gates;
3. Phase 4 source-safety contracts;
4. the generic Phase 4 ESP32-C6 physical-harness cloud compile.

## Physical boundary

Passing this gate is not a physical claim or authorization. It does not authorize board/USB/serial access, Flash/erase/reset/power changes, Wi-Fi or ESP-NOW RF execution, isolated or production Broker/Manager/Home Assistant mutation, N3-L work, R8 replay, PR ready-for-review, or merge.

A later physical authorization must bind the then-current exact PR head, a frozen generic firmware artifact, two explicit board identities, an isolated network/runtime, and one private session evidence root.
