# N3-W T1 Broker LAN-IP-Independent Binding Repair — 2026-09-25

Status: `SOURCE_REPAIR_IN_PROGRESS`

## Scope

This repair is limited to T1 Broker/Manager deployment portability across customer LANs.

It does not reopen the closed PR #437 / KF-096 physical route, does not change the N3-W radio state machine, does not modify Board A/B/C firmware, and does not merge or alter PR #474.

## Fresh live failure

The current T1 changed from a predecessor customer-LAN address to a different customer-LAN address.

Fresh read-only Docker evidence proved:

- the authoritative Broker container is exited;
- Docker cannot recreate its TLS host publication because the configured concrete host IPv4 is no longer assigned to T1;
- Broker exit is not OOM-related;
- TCP 8883 is absent while the Broker is down;
- the Manager restart loop is downstream of Broker unreachability;
- Home Assistant remains running.

The exact private LAN addresses are intentionally not archived in this public document.

## Root cause

The deployment treated the current T1 LAN IPv4 as stable Broker binding authority.

That assumption is invalid for a production product because the T1 address is assigned by the customer's router and may change after:

- DHCP lease changes;
- router replacement;
- customer subnet changes;
- moving the product to another LAN.

A source fix must therefore remove all concrete customer-LAN IPv4 dependency from the Broker TLS publication contract.

This intentionally supersedes only the old KF-035 static publication requirement that tied TLS 8883 to one resolved loopback `host_ip`. KF-035's stronger runtime authority remains: Manager-to-Broker reachability must still be proven from the exact host-network Manager namespace with TCP+TLS server-name validation, and Broker network attachments/runtime mappings must still be checked after recreate/reboot.

## Frozen repair direction

The repaired deployment contract is:

```text
T1 LAN IPv4
  assigned by customer network
  not source authority

Broker external TLS
  port 8883
  IPv4 wildcard host publication
  no concrete LAN host_ip

Manager
  network_mode=host
  no Docker ports
  Manager -> Broker uses a loopback endpoint
  exact runtime TCP+TLS probe required after recreate/reboot

Nodes
  canonical broker host + port 8883
  no concrete T1 LAN IP stored as product authority
```

The current canonical node Broker host remains `mqtt.greenhouse.local` in source configuration. This repair does not claim that hostname resolution is already proven on the new LAN. Resolution of the canonical hostname to the current T1 LAN address remains a separate live gate before node acceptance resumes.

## Source changes

Branch:

```text
fix/n3w-t1-broker-lan-ip-independent-binding-20260925
```

Base:

```text
main
b32878682ab4981fd38b8982caefed95ba3e204d
```

Changed contract:

- `tools/n3w_pairing_deployment_gate.py`
  - schema advances to `gh.n3w-pairing-deployment-gate/2`;
  - Manager host-network / no-ports rule remains unchanged;
  - Manager Broker endpoint must remain IPv4 loopback;
  - Broker TLS 8883 must have exactly one publication;
  - the publication must use IPv4 wildcard semantics;
  - any concrete loopback or LAN `host_ip` for TLS 8883 is rejected;
  - static PASS explicitly requires a later runtime loopback TCP+TLS probe.

Regression coverage:

- accepts explicit `0.0.0.0` publication;
- accepts Compose implicit wildcard publication;
- rejects concrete loopback publication;
- rejects concrete LAN publication;
- rejects representative concrete non-loopback host bindings;
- rejects duplicate 8883 publications;
- preserves the host-network Manager UDP discovery guard;
- preserves secret-free structured CLI failure output.

Dedicated CI:

- `.github/workflows/n3w-t1-deployment-gate-ci.yml` runs the focused deployment-gate regression on every relevant pull request and main update.

## Live repair boundary

No T1 runtime mutation has been performed by this source repair.

Before any live Broker recreate:

1. source review and CI must pass;
2. current T1 Compose authority must be rebound read-only;
3. rollback material for Broker/Manager state must remain valid;
4. rendered Compose must pass deployment gate v2;
5. the live repair must replace the concrete TLS host binding with wildcard semantics only;
6. after recreate, verify actual Docker runtime mapping;
7. verify Manager loopback TCP+TLS connectivity from the exact Manager runtime namespace;
8. verify canonical node Broker hostname resolves to the current T1 LAN address;
9. only then resume Board B Direct telemetry and dual-Gateway physical acceptance.

## Current disposition

```text
KF097_STATUS=OPEN
SOURCE_REPAIR_BRANCH_CREATED=true
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
PR474_CHANGED=false
PHYSICAL_VALIDATION_RESUME=false
```
