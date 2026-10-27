# N3W scan-triggered first pairing R1 closure repair

Date: 2026-10-26

Authority scope:

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_IMPLEMENTATION_R1_CLOSURE_REPAIR_20261026_01
BASE_R1_HEAD=ced0d1a161109e4414eb022884e129bfdd2f67f5
R2_IMPLEMENTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
MERGE=false
```

This repair closes the four blockers found by the independent R1 exact-head review.

## B1 production staging registration evidence

Production-stopped staging must include:

```text
TCP_LISTENER_ABSENT=47110,47112
UDP_LISTENER_ABSENT=47111

REGISTRATION_GUARD_UNIT_ACTIVE=true
REGISTRATION_GUARD_UNIT_ENABLED=true
BROKER_INPUT_ANCHOR_POSITION=1
REGISTRATION_INPUT_ANCHOR_POSITIONS=2,3,4
REGISTRATION_INPUT_ANCHOR_ORDER=47110/tcp,47111/udp,47112/tcp
REGISTRATION_CHAIN_TERMINAL_DROP=true
RAW_CUSTOMER_SUBNET_IN_PUBLIC_EVIDENCE=false
```

The registration firewall proof is required in addition to the existing Broker ingress guard proof.

## B2 mDNS authority lifecycle

Registration mDNS is not a startup-only advertisement.

It is controlled by the current trusted-product-LAN authority:

```text
authority valid + current eth0 IPv4 authorized
  -> registration mDNS may be advertised

authority unavailable / malformed / ambiguous
  -> registration mDNS must be withdrawn

authority generation changes or current eth0 IPv4 changes
  -> withdraw predecessor advertisement first
  -> rebuild from the newly proven current authority
```

UDP 47111 and TLS 47110 continue to re-read authority on each request.

A predecessor mDNS address must never remain advertised after the authority that justified it is lost.

## B3 production Manager mDNS dependency

`zeroconf` is a production runtime dependency, not only a development/pairing test extra.

Exact ARM64 Manager-image CI must prove the real production image can import both:

```text
zeroconf
greenhouse_manager.runtime.n3w_registration_discovery.RegistrationMdnsAdvertiser
```

A dev-environment-only import is not sufficient evidence.

## B4 UDP no-amplification contract

The phrase `no amplification-sized response` is frozen to the following exact byte rule:

```text
REGISTRATION_UDP_MAX_DATAGRAM_BYTES=1400
REGISTRATION_UDP_RESPONSE_BYTES <= REGISTRATION_UDP_REQUEST_BYTES
```

The registration discovery JSON schema is unchanged.

A node may append JSON-insignificant ASCII space bytes after the JSON document so that the request datagram is large enough to carry the candidate response without amplification.

The product node implementation target is:

```text
REGISTRATION_UDP_QUERY_DATAGRAM_BYTES=1400
PADDING_BYTE=0x20
```

Server behavior:

```text
decode request under the existing 1400-byte maximum
validate exact query schema
build the candidate response
if response_bytes > request_bytes:
    emit no UDP response
else:
    send response
```

There is no `4x`, `1024-byte floor`, or other amplification allowance.

This anti-amplification rule is independent of trusted-LAN admission and rate limiting; all three protections remain required.

Required tests:

```text
padded valid query -> response accepted and response_bytes <= request_bytes
un-padded valid query whose response would be larger -> no response / rejected
request > 1400 bytes -> rejected by existing datagram bound
rate limiting remains active
```

## Closure boundary

This repair does not activate first registration.

```text
R1_RUNTIME_WIRED_TO_MANAGER_STARTUP=false
FIRST_REGISTRATION_LEDGER=false
IDENTITY_BOUND_47112_TRANSACTION=false
FIRST_REGISTRATION_TTL_1800_IMPLEMENTED=false
PENDING_ACK_STATUS=false
```

After B1-B4 source repair and exact-head CI, perform a narrow focused closure review before entering R2.
