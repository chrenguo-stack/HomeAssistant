# FC4 R6D2 Manager Transport Rebind and Route Reconvergence — 2026-08-28

> Public-safe engineering archive. No raw hostnames, private addresses, credential bodies, CA paths, Setup Secret, pairing identifiers or private evidence paths are included.

## Scope

This note freezes the read-only R6D2-R1-S1A/S1B evidence gathered after the DynSec authority-repair executor stopped before authorization claim. No DynSec mutation, Broker stop/restart, Manager mutation/recreate, Home Assistant mutation, SQLite write, Board C access, flash or NVS operation occurred.

The product goal remains unchanged: restore the minimum FC4 runtime baseline, complete the already-planned four-SQLite directory-bind repair with the fewest Manager recreates, then resume Board C first registration and FC4 final physical acceptance.

## Evidence

The current Manager was uniquely rebound to the frozen FC4 Manager source authority and remains running, read-only-rootfs and unrestarted. Its current MQTT runtime settings are plaintext on port 1883 while preserving the expected Manager username/client-id identity.

The FC4 Broker remains the unique `n3wfc4` Broker runtime. Its production-equivalent TLS publication is on port 8883. A separate read-only runtime probe proved that the already-configured N3-W node-broker authority has:

- port 8883;
- configured and readable CA material;
- resolvable endpoint authority;
- a Broker publication binding matching that authority;
- a successful TLS handshake from the exact current Manager runtime without sending MQTT CONNECT or credentials.

Therefore the existing N3-W Broker TLS authority is reusable by the Manager. This closes the transport-target uncertainty needed for repair planning.

The observed host port 1883 listener was not used as a new authority. Its mere existence is insufficient to override the frozen FC4 final-product deployment contract, which requires the host-network Manager to reach the Broker through the production TLS publication. No additional listener-ownership investigation is required for the continuation decision.

## Classification

This is a recurrence of the existing host-network Manager/Broker TLS-continuity failure class (KF-035), not a new product architecture branch. The earlier R6D2 executor also reproduced the broader runtime-authority classifier class (KF-071) when it assumed global uniqueness for Home Assistant rather than selecting the FC4 `n3wfc4` Home Assistant authority.

At this boundary:

```text
MANAGER_TLS_TRANSPORT_REUSE_READY=true
CURRENT_MANAGER_TRANSPORT_MATCHES_FC4_TARGET=false
DYNSEC_REPAIR_PRECLAIM_COMPLETE=true
DYNSEC_REPAIR_AUTHORIZATION_CLAIMED=false
DYNSEC_REPAIR_AUTHORIZATION_CONSUMED=false
DYNSEC_MUTATION=false
BROKER_STOP=false
MANAGER_MUTATION=false
SQLITE_MUTATION=false
```

## Route reconvergence decision

Do not open a standalone chain of transport-only successors followed by a second Manager recreate for SQLite repair.

The next read-only successor materialization should combine the already-proven required Manager configuration changes into one future Manager recreate:

1. Manager MQTT transport rebind to the existing N3-W Broker TLS authority;
2. the original R6 four write-capable SQLite single-file binds converted to directory binds;
3. existing registration directory bind preserved unchanged;
4. existing relay-key directory preserved unchanged;
5. Manager identity/password authority preserved unchanged;
6. Broker and Home Assistant configuration unchanged.

This creates one consolidated Manager successor and avoids two sequential Manager recreates.

DynSec authority recovery remains a separate Broker mutation transaction because it changes the Broker's persisted authorization state and has its own rollback artifact. The already-granted DynSec authorization remains unclaimed/unconsumed and must not be reused until the consolidated Manager successor is ready and a fresh preclaim proves the intended ordering.

## Intended continuation

```text
READ_ONLY_CONSOLIDATED_MANAGER_SUCCESSOR_PRECLAIM
  -> explicit consolidated Manager mutation authorization
  -> one Manager recreate
  -> prove Manager TLS transport binding
  -> execute the already-preclaimed bounded DynSec authority repair
  -> prove Manager + Provisioning MQTT auth
  -> resume Board C first registration / original FC4 acceptance path
```

No S1C/S1D/R6D3-style diagnostic expansion is intended unless a new product-level blocker is actually observed.
