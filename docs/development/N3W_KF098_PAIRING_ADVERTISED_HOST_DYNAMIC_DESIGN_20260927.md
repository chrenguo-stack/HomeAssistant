# N3-W KF-098 Pairing Advertised Host Dynamic Repair Design

Updated: 2026-09-27  
Status: `DESIGN_FROZEN_SOURCE_REPAIR_PENDING`

## Scope

KF-098 covers the N3-W simplified pairing discovery path on T1.

Observed failure:

- an unprovisioned Board B sends UDP pairing discovery to T1 every 5 seconds;
- T1 receives the discovery requests and the Manager responds;
- the Manager response advertises the value from `GH_N3W_PAIRING_ADVERTISED_HOST`;
- that value is a stale IPv4 literal from a predecessor customer-LAN assignment;
- Board B therefore does not open HTTP pairing TCP/47112 to the current T1 address.

This is not:

- a reopening of B1 Broker publication closure;
- B2 stable hostname / TLS identity;
- B3 already-provisioned node Broker-address migration;
- a PR #474 Relay RF failure;
- a Board B flash-write failure.

## Live evidence

Public-safe evidence:

```text
PAIRING_DISCOVERY_UDP_PATH=PASS
MANAGER_UDP_47111_BOUND=true
MANAGER_TCP_47112_BOUND=true

DISCOVERY_QUERY_COUNT=4
DISCOVERY_RESPONSE_COUNT=4
DISCOVERY_RESPONSE_HOST_MATCHES_CONFIG=true

PAIRING_ADVERTISED_HOST_MATCHES_CURRENT_T1=false
BOARD_HTTP_47112_SYN_TO_CURRENT_T1_COUNT=0

MANAGER_CONTAINER_CREATED=2026-09-09
MANAGER_CONTAINER_STARTED=2026-09-27
MANAGER_RESTART_POLICY=unless-stopped
MANAGER_COMPOSE_LABEL_COUNT=0
STALE_ADVERTISED_HOST_IN_CONTAINER_CONFIG_ENV=true
```

The persistent T1 runtime authority was then bound:

```text
LIVE_COMPOSE=/opt/greenhouse-fc4-95c42fa5/runtime/docker-compose.yml
LIVE_MANAGER_ENV=/opt/greenhouse-fc4-95c42fa5/runtime/manager/manager.env

COMPOSE_HAS_ENV_FILE_DIRECTIVE=true
COMPOSE_REFERENCES_MANAGER_ENV=true
COMPOSE_REFERENCES_SERVICE_IDENTITIES_ENV=false
COMPOSE_HAS_PAIRING_ADVERTISED_ENV_NAME=false

MANAGER_ENV_HAS_PAIRING_ADVERTISED_HOST=true
```

Therefore both the running container environment and the durable Manager environment preserve the stale value. Recreating the Manager from the current live runtime authority without changing the contract would reproduce the defect.

## Current source behavior

Current Manager source loads:

```text
GH_N3W_PAIRING_ADVERTISED_HOST
```

once through `Settings.from_env()`.

The value is copied through:

```text
Settings
-> SimplifiedProductCompositionConfig.advertised_host
-> SimplifiedPairingNetworkSettings.advertised_host
-> SimplifiedManagerCandidate.host
```

The UDP discovery handler returns the same frozen candidate for every request.

Current validation only requires the configured advertised host to be non-empty and contain no whitespace. It does not reject a concrete stale LAN IPv4 and does not bind that value to the current route/interface state.

## Design decision

Do not repair KF-098 by replacing the predecessor IPv4 with the current DHCP IPv4.

That would restore service only until the next LAN address change.

Freeze an explicit automatic discovery-address mode:

```text
GH_N3W_PAIRING_ADVERTISED_HOST=auto
```

In `auto` mode, the Manager must derive the IPv4 address advertised in each UDP discovery response from the current route to the requesting client.

The derived address must be evaluated per request, not once at Manager startup.

This makes DHCP/customer-LAN changes visible to pairing discovery without rewriting `manager.env` and without recreating the Manager solely because its LAN IPv4 changed.

## Runtime contract

For each accepted simplified pairing discovery query:

1. preserve the existing local-source and rate-limit checks;
2. if configured advertised host is not `auto`, preserve the explicit-host path;
3. if configured advertised host is `auto`:
   - derive the current route-selected local IPv4 for the request source;
   - require one valid non-unspecified IPv4 result;
   - construct a request-local candidate using that address;
   - return that candidate in the discovery response;
4. if dynamic address derivation fails, emit no candidate response for that request;
5. never fall back to a previously derived IPv4.

The automatic path must not cache the address across requests.

## Address derivation

The implementation should use the kernel routing decision for the requesting IPv4 peer rather than parsing a fixed interface name or persisting a NetworkManager address.

A bounded IPv4 UDP route probe may connect a temporary datagram socket to the request source and inspect the selected local address. No application payload is sent by UDP `connect()`.

The helper must reject:

- unspecified address;
- multicast address;
- invalid/non-IPv4 result;
- route/socket failure.

Loopback behavior may remain available for loopback-only test/runtime configurations, but production wildcard pairing discovery must not silently advertise loopback to LAN clients.

## Configuration contract

`GH_N3W_PAIRING_ADVERTISED_HOST` supports:

- `auto` for route-selected dynamic IPv4;
- an explicit hostname for future stable-name deployments.

Production product-pairing configuration must reject concrete IPv4 literals as the durable advertised-host configuration.

This prevents the exact KF-098 failure from being reintroduced through deployment configuration.

The existing hostname path remains separate from B2. This design does not claim hostname resolution, hostname lifecycle, or TLS identity closure.

## Regression requirements

Source repair must include focused tests proving:

- `auto` is accepted;
- concrete IPv4 literals are rejected in product configuration;
- explicit hostname remains accepted;
- auto mode derives a request-local IPv4;
- two sequential discovery requests can advertise two different route-selected addresses without restarting the runtime;
- auto-mode derivation failure returns no discovery response;
- no stale-address fallback exists;
- local-source rejection and rate limiting remain unchanged;
- explicit-host mode behavior remains unchanged;
- response request-id and nonce binding remain unchanged.

A regression must specifically model:

```text
request A -> address A
network/route state changes
request B -> address B
same Manager runtime
```

and prove response B does not contain address A.

## Deployment guard requirements

The production deployment gate must reject a concrete IPv4 literal for the product pairing advertised-host authority.

The live Manager environment must be migrated from the predecessor literal to:

```text
GH_N3W_PAIRING_ADVERTISED_HOST=auto
```

The live cutover must bind the exact reviewed Manager source/image and preserve:

- registration database;
- credential lifecycle state;
- relay/application-key state;
- Manager identity;
- Broker state;
- B1 R5 ingress guard;
- PR #474 firmware on Board B.

## Live acceptance

After reviewed source deployment:

1. Manager UDP/47111 and TCP/47112 are bound;
2. Board B discovery request reaches T1;
3. Manager discovery response host equals the current T1 route-selected LAN IPv4;
4. the response host no longer equals the predecessor stale hash;
5. Board B initiates TCP/47112 to current T1;
6. expected next pairing disposition is observed.

If the existing registration requires an explicit repair intent, that is a later identity-recovery gate. KF-098 closes when the discovery/HTTP target path is correct; it does not require bypassing the repair authorization contract.

## Boundaries

```text
B1_REOPEN=false
B2=OPEN_OUT_OF_SCOPE
B3=OPEN_OUT_OF_SCOPE
PR474_SOURCE_CHANGE=false
BOARD_REFLASH_REQUIRED=false

T1_LIVE_MUTATION=false
MANAGER_RECREATE=false
PAIRING_REPAIR_AUTHORIZATION=false
```

This design authorizes no live mutation. The next stage is exact-base Manager source repair plus regression coverage.
