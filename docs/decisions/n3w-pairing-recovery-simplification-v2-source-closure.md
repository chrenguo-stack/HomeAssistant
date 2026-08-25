# N3-W pairing/recovery simplification V2 — source closure

- Date: 2026-08-25
- Baseline: `40a21db73158ae65f789d246e076a6e3ae0324da`
- Baseline tree: `d8221762a34a62c718fdc68d995086d5ddb60d56`
- Scope: source, host tests, source contracts and source-only ESP32-C6 compile
- Physical execution: false
- Legacy epoch recovery executed: false

## Complexity Delta

| Authority / flow | Before | After |
|---|---:|---:|
| device product pairing correctness epochs | 1 | 0 |
| distributed monotonic pairing generations | 1 | 0 |
| pairing -> MQTT credential coupling | 1 | 0 |
| pairing -> N3-W application-key coupling | 1 | 0 |
| normal retry credential rotations | possible | 0 |
| normal retry N3-W key rotations | possible | 0 |
| normal retry SYSTEM_PEER_KEY rotations | 0 | 0 |
| formal product Setup Secret handoff mechanisms | filesystem inbox | Manager-owned UDS |
| product filesystem handoff states | create/write/chmod/rename/watch/consume/unlink | 0 |
| business timing authorities | registration TTL + handoff TTL/floors | one pairing transaction expiry |
| product helper/app swap recovery flows | 1 legacy path | 0 product path |
| physical preclaim/successor states caused by host failure | multiple legacy states | 0 product states |
| live product imports of pairing-epoch successor helper | 0 | 0 |

The retained `pairing_epoch` SQLite columns are backward-compatible audit
storage. New product hello messages do not send an epoch, and Manager assigns a
local attempt sequence without using it in security or lifecycle decisions.

## Source result

- the device persists a CSPRNG 128-bit UUID for the pending transaction and
  removes it only after the final delivery receipt commits;
- terminal Manager transaction IDs remain replay tombstones;
- first registration uses MQTT credential generation 1;
- application-key staging advances its own key store and need not equal the
  MQTT generation;
- ordinary product pairing never calls `SystemPeerTrustStore.rotate()`;
- product composition owns a bounded, permissioned, local Unix socket;
- the filesystem inbox remains a directly testable `LAB_ONLY` adapter but is
  not constructed or started by product composition;
- the pairing CLI calls the Manager socket and never writes SQLite;
- boot-session/sequence canonical replay guards and the final delivery digest
  receipt remain unchanged;
- pairing-epoch recovery helpers remain only under `board_lab` and are marked
  legacy/engineering/board-lab migration-only.

## Local validation

- Manager focused suites: `48 passed`;
- pairing simplification and UDS contracts: `9 passed`;
- Manager full pytest: `1171 passed, 1 skipped`;
- Phase3/Phase4/boot-recovery source contracts: `23 passed`;
- schema/public-safety pytest: `8 passed`;
- Ruff: passed;
- public repository safety scan: passed;
- ESPHome Phase4 generic configuration: passed;
- ESP32-C6 Phase4 generic compile: passed, image size `1108110` bytes.

The first local compile attempt stopped before compilation because the sandbox
could not write the existing PlatformIO cache lock. Re-running the same exact
source with permission to use that cache passed. This is an infrastructure
precheck result, not a product regression and not a protected claim.

## Safety boundary

No board, USB, serial, Flash, NVS, reset, RF, Spare T1, production T1, live
Manager, Broker, Home Assistant, DynSec, credential, or key mutation occurred.
No real Setup Secret or private credential was accessed. The generated build
tree is ignored reproducible cache material and is not public evidence.
