# N3-W T1 Broker 8883 Host-Local Ingress Coverage R5 Design

Status: `SOURCE_REPAIR_IMPLEMENTED_CI_PENDING`  
Date: 2026-09-27  
Gate: `N3W_T1_BROKER_8883_HOST_LOCAL_INGRESS_COVERAGE_R5_DESIGN_20260927_01`

## Scope

R5 only closes the ingress path that was not covered by the R4 `DOCKER-USER` guard.

The following R4 results remain valid and are not redesigned here:

- explicit Broker publication `0.0.0.0:8883 -> 8883/tcp`;
- fixed Compose project identity `n3wfc4`;
- Broker Docker restart policy `no`;
- Manager host-network loopback TLS path;
- NetworkManager current `eth0` unique IPv4 subnet as customer-LAN authority;
- `DOCKER-USER` original-destination TCP/8883 guard for forwarded/DNAT traffic;
- no global firewall flush and no mutation of foreign rules;
- dispatcher remains uninstalled until R5 source review and live validation pass.

B2 stable T1 hostname/TLS identity and B3 already-provisioned node hostname migration remain out of scope.

## Live evidence that opens R5

The R4 live route proved the trusted-LAN positive path, then exposed a second host-local packet path:

```text
TRUSTED_LAN_ETH0_TLS=PASS
TRUSTED_ALLOW_COUNTER_ADVANCED=true

NONTRUSTED_SOURCE_CLASS=DOCKER_BRIDGE_NAMESPACE
NONTRUSTED_SOURCE_IN_TRUSTED_SUBNET=false
NONTRUSTED_TCP_8883_CONNECT=SUCCESS

HOST_8883_LISTENER=docker-proxy
DOCKER_USER_ANCHOR_COUNTER_CHANGED=false
CUSTOM_CHAIN_DROP_COUNTER_CHANGED=false
DOCKER_NAT_8883_COUNTER_CHANGED=false

PACKET_PATH_CLASS=HOST_LOCAL_DOCKER_PROXY_INPUT_PATH
```

This evidence does not prove an external untrusted `eth0` source can evade the guard. It proves that a Docker bridge namespace can reach the host's wildcard listener through a local host path that does not traverse `DOCKER-USER`.

## R5 design decision

R5 keeps the existing `DOCKER-USER` guard and adds a second owned anchor in the filter `INPUT` chain.

Both anchors enter the same project-owned chain:

```text
DOCKER-USER original-destination TCP/8883
  -> N3WFC4-BROKER-INGRESS

INPUT TCP destination port 8883
  -> N3WFC4-BROKER-INGRESS
```

The shared chain is the single authorization policy for host TCP/8883.

When NetworkManager reports one valid current `eth0` IPv4 subnet:

```text
1. lo + source 127.0.0.0/8
   -> RETURN

2. eth0 + source current trusted subnet
   -> RETURN

3. everything else
   -> DROP
```

When NetworkManager reports zero, ambiguous, invalid, or unavailable customer-LAN IPv4 state:

```text
1. lo + source 127.0.0.0/8
   -> RETURN

2. everything else
   -> DROP
```

The loopback allowance is static and is not customer-network authority. It preserves the already-proven Manager endpoint `armbian -> IPv4 loopback -> TLS/8883` while the customer-LAN side remains fail-closed.

## Why INPUT is required

The observed host-local Docker source reached `docker-proxy` without changing the `DOCKER-USER`, custom DROP, or Docker NAT counters. Therefore extending only the existing `DOCKER-USER` rule cannot close the observed path.

The new INPUT anchor is limited to TCP destination port 8883. The rendered-Compose deployment gate already requires Broker to be the only host TCP/8883 publisher, so the new INPUT rule does not claim unrelated service ports.

R5 does not disable Docker userland proxy globally and does not change Docker daemon configuration.

## Firewall ownership contract

R5 owns only:

- one exact `DOCKER-USER` anchor for original-destination TCP/8883;
- one exact `INPUT` anchor for host TCP destination port 8883;
- one project chain `N3WFC4-BROKER-INGRESS`;
- the rules inside that project chain.

Required invariants:

```text
DOCKER_USER_ANCHOR_COUNT=1
DOCKER_USER_ANCHOR_POSITION=1

INPUT_ANCHOR_COUNT=1
INPUT_ANCHOR_POSITION=1

GLOBAL_FLUSH=false
INPUT_FLUSH=false
DOCKER_USER_FLUSH=false
FOREIGN_RULE_DELETE=false
FOREIGN_RULE_REWRITE=false
```

The R5 helper may insert its exact INPUT anchor at position 1, shifting existing INPUT rules down without deleting or rewriting them.

Any same-comment rule with different semantics, duplicate owned anchor, owned anchor at a non-first position, or foreign reference into the project chain remains fail-closed.

## R4 to R5 migration contract

R5 must recognize the exact R4-owned prestate so the live T1 can migrate without first deleting the working guard.

Accepted migration prestate:

- exact R4 `DOCKER-USER` anchor at position 1;
- no R5 INPUT anchor yet;
- exact R4 project chain:
  - trusted `eth0` RETURN + terminal DROP; or
  - terminal DROP in no-trusted-subnet state.

Migration order is frozen:

```text
1. verify R4/R5 owned prestate and foreign-rule preservation
2. atomically replace only the project chain with R5 rules
3. verify the R5 chain
4. insert the exact INPUT anchor at position 1 if missing
5. verify both anchors and final chain
```

This order prevents the new INPUT anchor from blocking the Manager loopback path before the loopback RETURN rule exists.

After the first successful R5 apply, final validation accepts only the R5 chain form.

## Parser and semantic matching changes

The firewall parser must treat option/value pairs as authority.

R5 adds exact semantic support for the INPUT anchor's TCP destination-port match. It must not use substring/comment-only matching.

The source must independently classify:

- `DOCKER-USER` exact anchor;
- `INPUT` exact anchor;
- project-chain rules;
- ambiguous same-comment rules;
- foreign references to the project chain.

## Refresh behavior

NetworkManager dispatcher behavior does not change.

On each relevant `eth0` event, guard reload recalculates the current trusted subnet and atomically rewrites only the project chain. The static loopback RETURN and both exact anchors remain owned state.

If the network state becomes unavailable or ambiguous:

- loopback Manager access remains allowed;
- customer-LAN access becomes DROP;
- Docker bridge / other host-local non-loopback sources remain DROP.

## Broker and Manager lifecycle

R5 does not change the R4 activation contract:

```text
Docker
  -> ingress guard
  -> Broker activation
```

Broker stays `restart: no` under Docker and is supervised by the systemd activation owner.

Manager continues to use host network and the existing loopback TLS endpoint.

## Source regression requirements

R5 source repair is not complete until regression coverage proves all of the following:

- trusted chain order is loopback RETURN -> trusted `eth0` RETURN -> DROP;
- fail-closed chain order is loopback RETURN -> DROP;
- INPUT anchor exact TCP/8883 semantics;
- DOCKER-USER anchor exact original-destination TCP/8883 semantics;
- both anchors are unique and first;
- duplicate/wrong-position/ambiguous owned anchors fail closed;
- foreign INPUT and DOCKER-USER rules are preserved;
- foreign references to the project chain are rejected;
- R4 exact prestate is accepted only as migration input;
- R5 final state is required after apply;
- first install creates the owned chain before either anchor can reference it;
- R5 migration installs loopback allowance before the INPUT anchor;
- idempotent reload preserves normalized foreign firewall state;
- zero/ambiguous subnet preserves loopback but allows no customer-LAN or Docker-bridge source;
- deployment gate remains unchanged for Compose project/network/8883 ownership;
- existing lifecycle tests remain green.

## Live acceptance required after source review

Static source/CI cannot close R5.

The later T1 live gate must prove, in separate bounded phases:

1. exact R5 source staging and readback;
2. R4 -> R5 migration with foreign firewall state preserved;
3. Manager loopback TLS remains PASS with no restart-count increase;
4. trusted Mac -> T1 LAN TCP/TLS 8883 remains PASS;
5. trusted `eth0` allow counter advances;
6. Docker-bridge namespace -> T1 LAN 8883 connection fails;
7. INPUT anchor and terminal DROP counter advance for that negative probe;
8. Broker identity/project/restart policy remain unchanged;
9. `recipes-broker-1` remains non-running;
10. guard reload idempotence after R5;
11. only after all above PASS may dispatcher installation resume.

A second physical external subnet/VLAN is not currently available. Therefore R5 live acceptance must not claim a physically observed external-untrusted-`eth0` negative test unless such a source is actually provided.

## Rollback safety

While wildcard Broker publication is live, R5 protection must not be removed first.

If R5 live migration or validation fails:

```text
1. stop Broker activation owner
2. prove host TCP/8883 wildcard listener is closed
3. restore prior guard source/unit if required
4. only then remove the R5 INPUT anchor or restore R4 firewall form
```

A failed R5 validation must never roll back by deleting the INPUT anchor while wildcard Broker remains listening.

## Frozen design result

```text
R5_DESIGN=COMPLETE
R5_SOURCE_REPAIR_HEAD=6b48104d13f77e4866f02b0825515472b8853cb4
R5_SOURCE_REPAIR_TREE=ffc32e1b97e522670dccb4a97336eaefd2d87d25
R5_GUARD_BLOB=795903b06c7ee93a0602649e478bc070723ab8c0
R5_TEST_BLOB=6f9509463225f15c0e6697327d9183206be8f2ba
R5_SOURCE_MUTATION=true
R5_CI=PENDING
R5_T1_MUTATION=false
R5_INPUT_HOOK=INPUT
R5_FORWARD_HOOK=DOCKER-USER
R5_POLICY_CHAIN=N3WFC4-BROKER-INGRESS
R5_LOOPBACK_ALLOW=lo+127.0.0.0/8
R5_TRUSTED_LAN_ALLOW=eth0+current_unique_subnet
R5_TERMINAL_ACTION=DROP
R5_ZERO_OR_AMBIGUOUS_SUBNET=LOOPBACK_ONLY_THEN_DROP
R5_DOCKER_DAEMON_MUTATION=false
R5_DISPATCHER_INSTALL=false
NEXT_REQUIRED_STAGE=R5_CI_AND_SOURCE_REVIEW
```
