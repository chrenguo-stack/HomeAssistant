# N3-W T1 Broker Network-Independence Architecture Decisions — 2026-09-26

Status: `DESIGN_DIRECTION_ARCHIVE`

This document preserves the architecture decisions and unresolved design routes already established during the 2026-09-25/26 T1 Broker network-independence work. It is not a live-deployment authorization and does not claim that the open routes below are implemented.

Private T1 locators, customer LAN addresses, credentials, and raw device identities are intentionally excluded.

## 1. Problem decomposition

The network-independence problem is split into three separate routes:

```text
B1=Broker Docker TLS publication must not depend on a concrete customer-LAN IPv4
B2=Nodes need a stable T1/Broker naming and TLS-identity lifecycle
B3=Already-provisioned nodes need a lossless migration path away from historical literal Broker addresses
```

These routes must not be collapsed into one change.

Current disposition:

```text
B1_SOURCE=PASS_IN_PR475
B1_LIVE_RECOVERY=BLOCKED_ON_8883_INGRESS_GUARD
B2=OPEN
B3=OPEN
```

## 2. B1 — Broker publication architecture

Frozen direction:

- customer LAN IPv4 is runtime state, not product source authority;
- Broker TLS 8883 uses one explicit IPv4 wildcard Docker host publication;
- Manager stays in host network;
- Manager does not use Docker `ports`;
- Manager-to-Broker access remains host-local/loopback and is proven from the exact Manager runtime namespace;
- Broker keeps the required two-network topology:
  - `n3wfc4-private`
  - `n3wfc4-services`;
- Mosquitto TLS identity remains independently verified by server name;
- wildcard publication does not itself prove safe ingress.

PR #475 is the source/deployment-contract implementation authority for this route.

## 3. B1 — 8883 ingress-guard direction

Fresh live evidence proved there is currently no project-specific 8883 ingress restriction. Therefore wildcard activation must be preceded by a durable ingress guard.

Current design direction, not yet source-closed:

```text
FILTER_HOOK=DOCKER-USER
CUSTOM_CHAIN=N3WFC4-BROKER-INGRESS
SERVICE_PORT=8883
WIRED_INTERFACE_AUTHORITY=eth0
NETWORK_AUTHORITY=NetworkManager
TRUSTED_SUBNET_AUTHORITY=current connected IPv4 subnet derived at runtime
STATIC_CUSTOMER_SUBNET=false
UNKNOWN_OR_AMBIGUOUS_SUBNET=FAIL_CLOSED
```

Required behavior:

- identify Docker-published TCP/8883 using semantics appropriate after Docker DNAT;
- allow the currently trusted wired-LAN source set;
- reject other ingress to the Broker publication;
- never flush or rewrite Docker-owned/global firewall chains;
- remain idempotent across repeated refresh;
- refresh on boot and NetworkManager DHCP/network changes;
- preserve a reversible rollback path;
- if trusted subnet derivation fails or is ambiguous, keep external Broker ingress closed rather than broadly open it.

The exact systemd/NetworkManager ownership, rule transaction model, conntrack/original-destination matching, test contract, and live acceptance oracle remain the subject of:

`N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01`

## 4. B2 — stable T1/Broker naming and TLS identity

PR #475 does not solve node-side stable addressing.

Established direction:

- use a stable T1 service name rather than a literal customer-LAN IPv4 as node product authority;
- prefer a per-T1 unique stable name when more than one T1 may exist on the same LAN;
- the stable-name publisher must be independent of Broker process health so discovery does not disappear merely because Broker is down;
- node resolution must be repeatable/re-resolvable after LAN changes rather than treated as a one-time boot assumption;
- if a trusted discovery fallback is added, it must be bounded and authenticated before replacing persisted connection state;
- mDNS/`.local` is link-local and therefore cannot be assumed to work across VLANs, multicast filtering, or routed customer-network boundaries;
- Broker connection location and TLS server identity are separate fields and may have separate migration timing;
- the current short-term TLS identity `armbian` can be retained during B1 recovery;
- long-term certificate migration should include the selected stable per-T1 name and should use an overlap period rather than a flag-day identity replacement.

Current source defaults such as `mqtt.greenhouse.local` are targets/configuration values only; the current simplified pairing runtime does not by itself prove that this name is being published or resolved on the customer LAN.

## 5. B2 — current discovery limitation

The current simplified pairing composition uses a null advertiser in the reviewed source path. Therefore:

```text
STABLE_NAME_PUBLISHER_PROVEN=false
MQTT_GREENHOUSE_LOCAL_LIVE_RESOLUTION_PROVEN=false
GREENHOUSE_MANAGER_LOCAL_LIVE_RESOLUTION_PROVEN=false
```

Do not switch production node configuration to a canonical hostname and call B2 complete until the actual T1-side publisher and ESP-side resolver behavior are implemented and physically verified.

## 6. B3 — already-provisioned node migration

Already-provisioned nodes are a separate migration problem.

Established facts/direction:

- a node that has already completed provisioning may retain historical Broker addressing state;
- the reviewed pairing client returns an already-provisioned disposition rather than automatically repeating first-time provisioning;
- changing Manager environment or source defaults does not prove that an already-provisioned node receives a new Broker address;
- DNS cannot repair a node that persisted a literal obsolete IPv4 value;
- do not erase NVS, delete registration state, or force destructive re-pairing merely to bypass this migration problem;
- preferred migration is an authenticated network-configuration update using the existing trust relationship;
- if the current firmware cannot perform that update safely, use a separately reviewed controlled maintenance/firmware-upgrade path;
- migration must preserve node identity, credentials/trust, and rollback/recovery semantics.

B3 remains open until the exact deployed firmware persistence/update capability is reviewed and a safe migration contract is implemented and verified.

## 7. TLS migration boundary

Short-term B1 recovery:

```text
BROKER_CONNECT_LOCATION=may change
TLS_SERVER_NAME=armbian
CERTIFICATE_CHANGE_REQUIRED=false
```

Long-term B2:

```text
TLS_STABLE_IDENTITY=per-T1 stable name preferred
CERTIFICATE_SAN_MIGRATION=required
MIGRATION_STYLE=overlap/controlled transition
```

No certificate rotation is authorized by this document.

## 8. Manager/Broker invariants

These remain preserved across B1/B2/B3:

- Manager remains `network_mode=host` for the limited-broadcast pairing path;
- Manager has no Docker `ports`;
- exact Manager runtime namespace resolution is authoritative for Manager-to-Broker access;
- TCP+TLS server-name validation must be performed after Broker recreate/reboot;
- Broker keeps both required Docker networks;
- TLS and Dynamic Security remain enabled;
- TLS/DynSec authentication must not be treated as a substitute for ingress-source restriction.

## 9. Relationship to PR #474

PR #474 full-channel Relay discovery fallback remains a separate radio/product-source route.

```text
PR474_SOURCE_REVIEW=PASS
PR474_PHYSICAL_VALIDATION=PENDING
PR474_REOPEN_SOURCE=false
```

Its physical validation is deferred until the T1 Broker/Manager route is safely operational again.

## 10. Completion boundaries

Do not claim complete customer-network independence until all applicable items are proven:

- no persisted concrete customer LAN IPv4 is required for Broker publication;
- wildcard publication has a durable ingress guard;
- Manager loopback TCP+TLS passes from the exact runtime namespace;
- Broker two-network runtime topology survives recreate/reboot;
- a stable node Broker name is actually published and resolvable from the product network;
- certificate validation succeeds for the intended TLS identity;
- pairing/advertised host uses a resolvable stable authority;
- already-provisioned nodes have a safe address-migration path;
- controlled reboot/rematerialization preserves the repaired behavior;
- node telemetry resumes only after the relevant B2/B3 conditions are actually satisfied.

## 11. Current next gate

```text
NEXT_ONE_GATE=N3W_T1_BROKER_8883_DYNAMIC_INGRESS_GUARD_SOURCE_DESIGN_20260926_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
PR474_MERGE=false
PR475_MERGE=false
```
